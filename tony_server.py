#!python3


import datetime
import json
import os
import random
import uuid
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
import httpx
import asyncio

import azure.cosmos.cosmos_client as cosmos_client
import pydantic
import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from icecream import ic

# import asyncio
from modal import App, Image, Mount, Secret, web_endpoint, asgi_app

# Configure icecream to truncate long output
def truncate_value(obj):
    str_val = str(obj)
    if len(str_val) > 2000:
        return str_val[:2000] + "..."
    return str_val

ic.configureOutput(prefix='', outputFunction=print)
ic.configureOutput(argToStringFunction=truncate_value)

PPLX_API_KEY_NAME = "PPLX_API_KEY"
TONY_API_KEY_NAME = "TONY_API_KEY"
ONEBUSAWAY_API_KEY = "ONEBUSAWAY_API_KEY"
TONY_STORAGE_SERVER_API_KEY = "TONY_STORAGE_SERVER_API_KEY"
X_VAPI_SECRET = "x-vapi-secret"
TONY_ASSISTANT_ID = "f5fe3b31-0ff6-4395-bc08-bc8ebbbf48a6"

default_image = Image.debian_slim(python_version="3.12").pip_install(
    ["icecream", "requests", "pydantic", "azure-cosmos", "onebusaway", "fastapi[standard]"]
)


app = FastAPI()
modal_app = App("modal-tony-server")

modal_storage = "modal_readonly"

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
        return FunctionCall(
            id=str(uuid.uuid4()),
            name=function_name,
            args=args
        )
    
    # Handle complex format (used by VAPI)
    message = params["message"]
    ic(message.keys())
    toolCalls = message["toolCalls"]
    ic(toolCalls)
    tool = toolCalls[-1]
    ic(tool)
    # todo validate the function names match.
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
    raise_if_not_authorized(headers)
    call = parse_tool_call("search", params)
    url = "https://api.perplexity.ai/chat/completions"
    pplx_token = os.getenv(PPLX_API_KEY_NAME)
    auth_line = f"Bearer {pplx_token}"
    ic(auth_line)

    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
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
    content = first["content"]
    return content

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
            client.post(f"{base_url}-search.modal.run",
                       json={"question": "warm up"},
                       headers=headers),
            client.post(f"{base_url}-library-arrivals.modal.run",
                       json={},
                       headers=headers),
            client.post("https://idvorkin--modal-blog-server-blog-handler.modal.run",
                       json={
                           "message": {
                               "toolCalls": [{
                                   "function": {
                                       "name": "blog_info",
                                       "arguments": {}
                                   },
                                   "id": "warm-up",
                                   "type": "function"
                               }]
                           }
                       },
                       headers=headers)
        ]

        # Execute calls without waiting for response
        await asyncio.gather(*tasks, return_exceptions=True)

def is_igor_caller(input: Dict) -> bool:
    """Check if the caller is Igor based on the phone number"""
    try:
        caller_number = input["input"]["message"]["call"]["customer"]["number"]
        return caller_number == "+12068904339"
    except (KeyError, TypeError):
        return False

def apply_caller_restrictions(tony: Dict, is_igor: bool) -> Dict:
    """Apply restrictions to Tony's capabilities based on caller"""
    if not is_igor:
        # Remove sensitive tools for non-Igor callers
        restricted_tools = ["journal_read", "journal_append", "library_arrivals"]
        tony["assistant"]["model"]["tools"] = [
            tool for tool in tony["assistant"]["model"]["tools"]
            if tool["function"]["name"] not in restricted_tools
        ]
        
        # Add restriction notice to the system prompt
        current_prompt = tony["assistant"]["model"]["messages"][0]["content"]
        restriction_notice = """
<Restrictions>
You are talking to someone other than Igor. You must:
- Do not mention or acknowledge Igor's personal information
- Do not offer or provide access to Igor's journal
- Do not provide bus arrival information
- Keep responses general and avoid mentioning specific details about Igor's life
- You can still search and share Igor's public blog posts
</Restrictions>
"""
        tony["assistant"]["model"]["messages"][0]["content"] = restriction_notice + current_prompt
    
    return tony

@app.post("/assistant")
async def assistant_endpoint(input: Dict, headers=Depends(get_headers)):
    ic(input)
    base = Path(f"/{modal_storage}")
    assistant_txt = (base / "tony_assistant_spec.json").read_text()
    tony = json.loads(assistant_txt)
    tony_prompt = (base / "tony_system_prompt.md").read_text()
    
    # Check if caller is Igor
    is_igor = is_igor_caller(input)
    
    # Add context to system prompt
    time_in_pst = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    journal_content = trusted_journal_read() if is_igor else "Journal access restricted"
    extra_state = f"""
<CurrentState>
    Date and Time: {time_in_pst}
    Location: Seattle
    {f'<JournalContent>{journal_content}</JournalContent>' if is_igor else ''}
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
    ic(first)
    journal_item = first
    journal_item["content"] += f"{datetime.datetime.now()}: {call.args["content"]}\n"
    ret = container.upsert_item(journal_item)
    ic(ret)
    return make_vapi_response(call, "success")

@app.post("/journal-read")
async def journal_read_endpoint(params: Dict, headers=Depends(get_headers)):
    raise_if_not_authorized(headers)
    call = parse_tool_call("journal_read", params)
    content = trusted_journal_read()
    return make_vapi_response(call, f"{content}")

@modal_app.function(
    image=default_image.pip_install(["httpx"]),
    mounts=[Mount.from_local_dir(modal_storage, remote_path="/" + modal_storage)],
    secrets=[
        Secret.from_name(TONY_API_KEY_NAME),
        Secret.from_name(TONY_STORAGE_SERVER_API_KEY),
        Secret.from_name(PPLX_API_KEY_NAME),
        Secret.from_name(ONEBUSAWAY_API_KEY),
    ],
)
@asgi_app()
def fastapi_app():
    return app

