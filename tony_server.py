#!python3


import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Dict
from zoneinfo import ZoneInfo
import httpx
import asyncio

import azure.cosmos.cosmos_client as cosmos_client
import pydantic
import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from icecream import ic

# import asyncio
from modal import App, Image, Mount, Secret, asgi_app
from pydantic import BaseModel


# Configure icecream to truncate long output
def truncate_value(obj):
    str_val = str(obj)
    if len(str_val) > 2000:
        return str_val[:2000] + "..."
    return str_val


ic.configureOutput(prefix="", outputFunction=print)
ic.configureOutput(argToStringFunction=truncate_value)

PPLX_API_KEY_NAME = "PPLX_API_KEY"
TONY_API_KEY_NAME = "TONY_API_KEY"
ONEBUSAWAY_API_KEY = "ONEBUSAWAY_API_KEY"
TONY_STORAGE_SERVER_API_KEY = "TONY_STORAGE_SERVER_API_KEY"
TWILIO_ACCOUNT_SID = "TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN = "TWILIO_AUTH_TOKEN"
TWILIO_FROM_NUMBER = "TWILIO_FROM_NUMBER"
IFTTT_WEBHOOK_KEY = "IFTTT_WEBHOOK_KEY"
IFTTT_WEBHOOK_SMS_EVENT = "IFTTT_WEBHOOK_SMS_EVENT"
X_VAPI_SECRET = "x-vapi-secret"
TONY_ASSISTANT_ID = "f5fe3b31-0ff6-4395-bc08-bc8ebbbf48a6"

modal_storage = "modal_readonly"

default_image = Image.debian_slim(python_version="3.12").pip_install(
    [
        "icecream",
        "requests",
        "pydantic",
        "azure-cosmos",
        "onebusaway",
        "fastapi[standard]",
        "twilio",
        "httpx",
    ]
).add_local_dir(modal_storage, remote_path="/" + modal_storage)

app = FastAPI()
modal_app = App("modal-tony-server")


class FunctionCall(pydantic.BaseModel):
    id: str
    name: str
    args: Dict


def make_vapi_response(call: FunctionCall, result: str):
    return {"results": [{"toolCallId": call.id, "result": result}]}


def make_call(name, input: Dict):
    id = input.get("id", str(uuid.uuid4()))
    return FunctionCall(id=id, name=name, args=input)


def parse_tool_call(function_name, params: Dict) -> FunctionCall:
    """Parse the call from VAPI or from the test tool."""
    # Handle simple format (used in tests and justfile commands)
    if not params.get("message"):
        args = {k: v for k, v in params.items() if v is not None}
        return FunctionCall(id=str(uuid.uuid4()), name=function_name, args=args)

    # Handle VAPI format
    message = params["message"]
    toolCalls = message.get("toolCalls", [])
    if not toolCalls:
        # If no toolCalls in message, treat the entire params as args
        return FunctionCall(id=str(uuid.uuid4()), name=function_name, args=params)

    tool = toolCalls[-1]
    return FunctionCall(
        id=tool["id"],
        name=tool["function"]["name"],
        args=tool["function"]["arguments"],
    )


def raise_if_not_authorized(headers: Dict):
    token = headers.get(X_VAPI_SECRET, "")
    if not token:
        ic(headers)
    if token != os.environ[TONY_API_KEY_NAME]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def search_logic(params: Dict, headers: Dict):
    """Core search logic used by both Modal and FastAPI endpoints"""
    # Perplexity AI configuration
    # See model details at https://docs.perplexity.ai/guides/model-cards
    PPLX_MODEL = "sonar-pro"  # 200k context, 8k output limit

    raise_if_not_authorized(headers)
    call = parse_tool_call("search", params)
    url = "https://api.perplexity.ai/chat/completions"
    pplx_token = os.getenv(PPLX_API_KEY_NAME)
    auth_line = f"Bearer {pplx_token}"
    ic(auth_line)

    payload = {
        "model": PPLX_MODEL,
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {"role": "user", "content": call.args["question"]},
        ],
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": auth_line,
    }
    ic(payload)
    ic(headers)

    search_response = requests.post(url, json=payload, headers=headers)
    ic(search_response.json())
    search_answer = search_response.json()["choices"][0]["message"]["content"]
    vapi_response = make_vapi_response(call, search_answer)
    ic(vapi_response)
    return vapi_response


DB_HOST = "https://tonyserver.documents.azure.com:443/"
DATABASE_ID = "grateful"
CONTAINER_ID = "main"
JOURNAL_DATABASE_ID = "journal"
JOURNAL_ID_CONTAINER = "journal_container"


def trusted_journal_read():
    client = cosmos_client.CosmosClient(
        DB_HOST,
        {"masterKey": os.environ[TONY_STORAGE_SERVER_API_KEY]},
        user_agent="tony_server.py",
        user_agent_overwrite=True,
    )
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    first = None
    for i in items:
        first = i
        break
    if first is None:
        return "No journal entries found"
    return first["content"]


def get_headers(request: Request):
    ic(dict(request.headers))
    return request.headers


async def warm_up_endpoints(secret: str):
    """Fire and forget calls to warm up the endpoints."""
    async with httpx.AsyncClient() as client:
        base_url = "https://idvorkin--modal-tony-server"
        headers = {"x-vapi-secret": secret}

        # Prepare warm-up calls
        tasks = [
            client.post(
                f"{base_url}-search.modal.run",
                json={"question": "warm up"},
                headers=headers,
            ),
            client.post(
                f"{base_url}-library-arrivals.modal.run", json={}, headers=headers
            ),
            client.post(
                "https://idvorkin--modal-blog-server-blog-handler.modal.run",
                json={
                    "message": {
                        "toolCalls": [
                            {
                                "function": {"name": "blog_info", "arguments": {}},
                                "id": "warm-up",
                                "type": "function",
                            }
                        ]
                    }
                },
                headers=headers,
            ),
        ]

        # Execute calls without waiting for response
        await asyncio.gather(*tasks, return_exceptions=True)


def get_caller_number(input: Dict) -> str | None:
    """Extract caller's phone number from input"""
    if input is None:
        ic("Input is None")
        return None

    try:
        # Check each level of nesting and log if missing
        if "message" not in input:
            ic("Missing 'message' key")
            return None

        if "call" not in input["message"]:
            ic("Missing 'call' key")
            return None

        if "customer" not in input["message"]["call"]:
            ic("Missing 'customer' key")
            return None

        if "number" not in input["message"]["call"]["customer"]:
            ic("Missing 'number' key")
            return None

        return input["message"]["call"]["customer"]["number"]
    except TypeError as e:
        ic(f"TypeError accessing nested dict: {e}")
        return None


def is_igor_caller(input: Dict) -> bool:
    """Check if the caller is Igor based on the phone number"""
    caller_number = get_caller_number(input)
    return caller_number == "+12068904339"


def apply_caller_restrictions(tony: Dict, is_igor: bool) -> Dict:
    """Apply restrictions to Tony's capabilities based on caller"""
    if not is_igor:
        # Remove sensitive tools for non-Igor callers
        restricted_tools = ["journal_read", "journal_append"]
        tony["assistant"]["model"]["tools"] = [
            tool
            for tool in tony["assistant"]["model"]["tools"]
            if tool["function"]["name"] not in restricted_tools
        ]

        # Add restriction notice to the system prompt
        current_prompt = tony["assistant"]["model"]["messages"][0]["content"]
        restriction_notice = """
<Restrictions>
You are talking to someone other than Igor. You must:
- Before your second message say "Hello "user's phone number", I know you're not igor so there are some restrictions"
- Do not offer or provide access to Igor's journal
- You can still search and share Igor's public blog posts
</Restrictions>
"""
        tony["assistant"]["model"]["messages"][0]["content"] = (
            restriction_notice + current_prompt
        )

    return tony


def extract_failure_reason(input: Dict) -> str | None:
    """Extract failure reason from a status-update message"""
    if not input.get("message"):
        return None

    message = input["message"]
    if message.get("type") != "status-update":
        return None

    if message.get("status") != "ended":
        return None

    # Get the debugging artifacts if they exist
    debugging = message.get("inboundPhoneCallDebuggingArtifacts", {})

    # First try to get the assistant request error
    if debugging.get("assistantRequestError"):
        return debugging["assistantRequestError"]

    # Fallback to the general error
    if debugging.get("error"):
        return debugging["error"]

    # Finally fallback to the ended reason
    return message.get("endedReason")


@app.post("/assistant")
async def assistant_endpoint(input: Dict, headers=Depends(get_headers)):
    ic(input)
    base = Path(f"/{modal_storage}")
    assistant_txt = (base / "tony_assistant_spec.json").read_text()
    tony = json.loads(assistant_txt)
    tony_prompt = (base / "tony_system_prompt.md").read_text()

    if failure_reason := extract_failure_reason(input):
        ic(failure_reason)

    # Check if caller is Igor
    is_igor = is_igor_caller(input)

    # Add context to system prompt
    time_in_pst = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    journal_content = trusted_journal_read() if is_igor else "Journal access restricted"
    caller_number = get_caller_number(input) or "Unknown"
    extra_state = f"""
<CurrentState>
    Date and Time: {time_in_pst}
    Location: Seattle
    Phone Number if Asked: {caller_number}
    {f"<JournalContent>{journal_content}</JournalContent>" if is_igor else ""}
</CurrentState>
    """
    tony_prompt += extra_state
    # update system prompt
    tony["assistant"]["model"]["messages"][0]["content"] = tony_prompt

    # Apply caller-based restrictions
    tony = apply_caller_restrictions(tony, is_igor)

    secret = headers.get(X_VAPI_SECRET, "no secret passed to search")
    # Fire off warm-up calls without waiting
    asyncio.create_task(warm_up_endpoints(secret))
    # for each tool set the secret
    for tool in tony["assistant"]["model"]["tools"]:
        tool["server"]["secret"] = secret

    ic(len(tony))
    return tony


@app.post("/search")
async def search_endpoint(params: Dict, headers=Depends(get_headers)):
    """Modal endpoint for search"""
    return search_logic(params, headers)


@app.post("/library-arrivals")
async def library_arrivals_endpoint(params: Dict, headers=Depends(get_headers)):
    import onebusaway

    raise_if_not_authorized(headers)
    call = parse_tool_call("library_arrivals", params)
    client = onebusaway.OnebusawaySDK(
        api_key=os.environ.get(ONEBUSAWAY_API_KEY),
    )
    response = client.arrival_and_departure.list("1_29249")
    trips = response.data.entry.arrivals_and_departures
    arrivals: list[str] = []
    for trip in trips:
        at_time = trip.predicted_arrival_time / 1000
        at_time_pst = datetime.datetime.fromtimestamp(
            at_time, tz=ZoneInfo("America/Los_Angeles")
        )
        at_time_pst_str = at_time_pst.strftime("%I:%M %p")
        arrivals.append(f"{trip.trip_headsign} arriving at {at_time_pst_str}")
        ic(trip)
    vapi_response = make_vapi_response(call, str(arrivals))
    ic(vapi_response)
    return vapi_response


@app.post("/journal-append")
async def journal_append_endpoint(params: Dict, headers=Depends(get_headers)):
    raise_if_not_authorized(headers)
    call = parse_tool_call("journal_append", params)
    client = cosmos_client.CosmosClient(
        DB_HOST,
        {"masterKey": os.environ[TONY_STORAGE_SERVER_API_KEY]},
        user_agent="storage.py",
        user_agent_overwrite=True,
    )
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    first = None
    for i in items:
        first = i
        break

    if first is None:
        # Create new journal if none exists
        journal_item = {
            "id": str(uuid.uuid4()),
            "content": "",
            "type": "journal",  # partition key
            "created_at": datetime.datetime.now(
                ZoneInfo("America/Los_Angeles")
            ).isoformat(),
            "updated_at": datetime.datetime.now(
                ZoneInfo("America/Los_Angeles")
            ).isoformat(),
        }
    else:
        journal_item = first
        journal_item["updated_at"] = datetime.datetime.now(
            ZoneInfo("America/Los_Angeles")
        ).isoformat()

    current_time = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M")
    journal_item["content"] += f"{formatted_time}: {call.args['content']}\n"
    ret = container.upsert_item(journal_item)
    ic(ret)
    return make_vapi_response(call, "success")


@app.post("/journal-read")
async def journal_read_endpoint(params: Dict, headers=Depends(get_headers)):
    raise_if_not_authorized(headers)
    call = parse_tool_call("journal_read", params)
    content = trusted_journal_read()
    return make_vapi_response(call, f"{content}")


class TextMessageRequest(BaseModel):
    text: str
    to_number: str


@app.post("/send-text")
async def send_text_endpoint(params: Dict, headers=Depends(get_headers)):
    """Modal endpoint for sending text messages using Twilio"""
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    raise_if_not_authorized(headers)
    call = parse_tool_call("send_text", params)

    # Extract text and to_number from the call arguments
    text = call.args.get("text")
    to_number = call.args.get("to_number")

    if not text or not to_number:
        error_msg = "Both text and to_number are required"
        return make_vapi_response(call, f"Error: {error_msg}")

    try:
        # Log Twilio environment variables (without sensitive data)
        ic("Twilio environment check:")
        ic("TWILIO_ACCOUNT_SID exists:", TWILIO_ACCOUNT_SID in os.environ)
        ic("TWILIO_AUTH_TOKEN exists:", TWILIO_AUTH_TOKEN in os.environ)
        ic("TWILIO_FROM_NUMBER exists:", TWILIO_FROM_NUMBER in os.environ)
        ic("TWILIO_FROM_NUMBER value:", os.environ.get(TWILIO_FROM_NUMBER))

        # Initialize Twilio client
        client = Client(os.environ[TWILIO_ACCOUNT_SID], os.environ[TWILIO_AUTH_TOKEN])

        # Log the message parameters
        ic("Sending message with params:")
        ic("To:", to_number)
        ic("From:", os.environ[TWILIO_FROM_NUMBER])
        ic("Text:", text)

        # Send message
        message = client.messages.create(
            body=text, from_=os.environ[TWILIO_FROM_NUMBER], to=to_number
        )

        # Log the Twilio response
        ic("Twilio response:", message.__dict__)

        # Return success response with message SID
        return make_vapi_response(
            call,
            f"Text message sent to {to_number}: {text} (Message SID: {message.sid})",
        )

    except TwilioRestException as e:
        error_msg = f"Failed to send message: {str(e)}"
        ic(error_msg)  # Log the error
        return make_vapi_response(call, f"Error: {error_msg}")
    except KeyError as e:
        error_msg = f"Missing Twilio configuration: {str(e)}"
        ic(error_msg)  # Log the error
        return make_vapi_response(call, f"Error: {error_msg}")
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ic(error_msg)  # Log the error
        return make_vapi_response(call, f"Error: {error_msg}")


@app.post("/send-text-ifttt")
async def send_text_ifttt_endpoint(params: Dict, headers=Depends(get_headers)):
    """Modal endpoint for sending text messages using IFTTT webhook"""
    raise_if_not_authorized(headers)
    call = parse_tool_call("send_text_ifttt", params)

    # Extract text and to_number from the call arguments
    text = call.args.get("text")
    to_number = call.args.get("to_number")

    if not text or not to_number:
        error_msg = "Both text and to_number are required"
        return make_vapi_response(call, f"Error: {error_msg}")

    try:
        # Check if IFTTT environment variables exist
        ic("IFTTT environment check:")
        ic("IFTTT_WEBHOOK_KEY exists:", IFTTT_WEBHOOK_KEY in os.environ)
        ic("IFTTT_WEBHOOK_SMS_EVENT exists:", IFTTT_WEBHOOK_SMS_EVENT in os.environ)
        
        webhook_key = os.environ[IFTTT_WEBHOOK_KEY]
        webhook_event = os.environ[IFTTT_WEBHOOK_SMS_EVENT]
        
        # Construct IFTTT webhook URL
        ifttt_url = f"https://maker.ifttt.com/trigger/{webhook_event}/with/key/{webhook_key}"
        
        # Prepare the payload for IFTTT
        payload = {
            "value1": text,
            "value2": to_number,
            "value3": f"From Tony Tesla at {datetime.datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        # Log the webhook request
        ic("Sending IFTTT webhook request:")
        ic("URL:", ifttt_url)
        ic("Payload:", payload)
        
        # Send the webhook request
        response = requests.post(ifttt_url, json=payload)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        # Log the IFTTT response
        ic("IFTTT response status:", response.status_code)
        ic("IFTTT response text:", response.text)
        
        # Return success response
        return make_vapi_response(
            call,
            f"Text message sent via IFTTT to {to_number}: {text}"
        )
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to send webhook request: {str(e)}"
        ic(error_msg)
        return make_vapi_response(call, f"Error: {error_msg}")
    except KeyError as e:
        error_msg = f"Missing IFTTT configuration: {str(e)}"
        ic(error_msg)
        return make_vapi_response(call, f"Error: {error_msg}")
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ic(error_msg)
        return make_vapi_response(call, f"Error: {error_msg}")


@modal_app.function(
    image=default_image,
    secrets=[
        Secret.from_name(TONY_API_KEY_NAME),
        Secret.from_name(TONY_STORAGE_SERVER_API_KEY),
        Secret.from_name(PPLX_API_KEY_NAME),
        Secret.from_name(ONEBUSAWAY_API_KEY),
        Secret.from_name(TWILIO_ACCOUNT_SID),
        Secret.from_name(TWILIO_AUTH_TOKEN),
        Secret.from_name(TWILIO_FROM_NUMBER),
        Secret.from_name(IFTTT_WEBHOOK_KEY),
        Secret.from_name(IFTTT_WEBHOOK_SMS_EVENT),
    ],
)
@asgi_app()
def fastapi_app():
    return app
