#!python3


# import asyncio
from modal import App, web_endpoint
from typing import Dict
import os
from icecream import ic
from pathlib import Path
import json
import datetime
import pydantic
from zoneinfo import ZoneInfo

from modal import Image, Mount, Secret
import requests
import uuid

from fastapi import Depends, HTTPException, Request, status


default_image = Image.debian_slim(python_version="3.12").pip_install(
    ["icecream", "requests", "pydantic"]
)

X_VAPI_SECRET = "x-vapi-secret"
TONY_ASSISTANT_ID = "f5fe3b31-0ff6-4395-bc08-bc8ebbbf48a6"

app = App("modal-tony-server")

modal_storage = "modal_readonly"


def get_headers(request: Request):
    ic(request.headers)
    return request.headers


@app.function(
    image=default_image,
    mounts=[Mount.from_local_dir(modal_storage, remote_path="/" + modal_storage)],
)
@web_endpoint(method="POST")
def assistant(input: Dict, headers=Depends(get_headers)):
    ic(input)
    base = Path(f"/{modal_storage}")
    assistant_txt = (base / "tony_assistant_spec.json").read_text()
    tony = json.loads(assistant_txt)
    tony_prompt = (base / "tony_system_prompt.md").read_text()
    # Add context to system prompt
    time_in_pst = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    extra_state = f"""
<CurrentState>
    Date and Time: {time_in_pst}
    Igor's Location: Seattle
</CurrentState>
    """
    tony_prompt += extra_state
    ic(extra_state)
    # update system prompt
    tony["assistant"]["model"]["messages"][0]["content"] = tony_prompt

    secret = headers.get(X_VAPI_SECRET, "no secret passed to search")
    # for each tool set the secret
    for tool in tony["assistant"]["model"]["tools"]:
        tool["server"]["secret"] = secret

    ic(len(tony))

    return tony


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
    """Parse the call from VAPI or from the test tool. When from VAPI has the following shape

    'toolCalls': [{'function': {'arguments': {'question': 'What is the rain in '
                                                        'Spain?'},
                              'name': 'search'},
                 'id': 'toolu_01FDyjjUG1ig7hP9YQ6MQXhX',
                 'type': 'function'}],
    """
    message = params.get("message", "")
    if not message:
        ic(params)
        return make_call(function_name, params)

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


PPLX_API_KEY_NAME = "PPLX_API_KEY"
TONY_API_KEY_NAME = "TONY_API_KEY"


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


# x-vapi-secret header -


@app.function(
    image=default_image,
    secrets=[Secret.from_name(PPLX_API_KEY_NAME), Secret.from_name(TONY_API_KEY_NAME)],
)
@web_endpoint(method="POST")
def search(params: Dict, headers=Depends(get_headers)):
    """question: the question"""

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


@app.function(
    image=default_image,
    secrets=[Secret.from_name(PPLX_API_KEY_NAME), Secret.from_name(TONY_API_KEY_NAME)],
)
@web_endpoint(method="POST")
def journal_append(params: Dict, headers=Depends(get_headers)):
    raise_if_not_authorized(headers)
    call = parse_tool_call("journal_append", params)
    return make_vapi_response(
        call, f"journal append not implemented yet content:{call.args["content"]}"
    )


@app.function(
    image=default_image,
    secrets=[Secret.from_name(PPLX_API_KEY_NAME), Secret.from_name(TONY_API_KEY_NAME)],
)
@web_endpoint(method="POST")
def journal_read(params: Dict, headers=Depends(get_headers)):
    raise_if_not_authorized(headers)
    call = parse_tool_call("journal_read", params)
    return make_vapi_response(
        call, f"journal append not implemented yet date: {call.args["date"]}"
    )
