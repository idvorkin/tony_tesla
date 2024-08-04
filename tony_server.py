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

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

auth_scheme = HTTPBearer()


default_image = Image.debian_slim(python_version="3.12").pip_install(
    ["icecream", "requests", "pydantic"]
)

TONY_ASSISTANT_ID = "f5fe3b31-0ff6-4395-bc08-bc8ebbbf48a6"

app = App("modal-tony-server")

modal_storage = "modal_readonly"


@app.function(
    image=default_image,
    mounts=[Mount.from_local_dir(modal_storage, remote_path="/" + modal_storage)],
)
@web_endpoint(method="POST")
def assistant(input: Dict):
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
    ic(len(tony))
    return tony


class FunctionCall(pydantic.BaseModel):
    id: str
    name: str
    arguments: Dict


def parse_vapi_call(input) -> FunctionCall | None:
    """Parse the call from VAPI which has the following shape

    'toolCalls': [{'function': {'arguments': {'question': 'What is the rain in '
                                                        'Spain?'},
                              'name': 'search'},
                 'id': 'toolu_01FDyjjUG1ig7hP9YQ6MQXhX',
                 'type': 'function'}],
    """
    message = input.get("message", "")
    if not message:
        return None

    ic(message.keys())
    toolCalls = message["toolCalls"]
    ic(toolCalls)
    tool = toolCalls[-1]
    ic(tool)
    return FunctionCall(
        id=tool["id"],
        name=tool["function"]["name"],
        arguments=tool["function"]["arguments"],
    )


PPLX_API_KEY_NAME = "PPLX_API_KEY"
TONY_API_KEY_NAME = "TONY_API_KEY"


def raise_if_not_authorized(token):
    ic(token)
    if token.credentials != os.environ[TONY_API_KEY_NAME]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.function(
    image=default_image,
    secrets=[Secret.from_name(PPLX_API_KEY_NAME), Secret.from_name(TONY_API_KEY_NAME)],
)
@web_endpoint(method="POST")
def search(input: Dict, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    import requests

    raise_if_not_authorized(token)

    tool_call_id = ""
    question = ""

    ic(input.keys())
    if call := parse_vapi_call(input):
        ic(call)
        question, tool_call_id = call.arguments["question"], call.id

    if not question:
        question = input.get("question")

    if not tool_call_id:
        tool_call_id = input.get("id", "no_id_passed_in")

    ic(tool_call_id, question)

    url = "https://api.perplexity.ai/chat/completions"
    pplx_token = os.getenv(PPLX_API_KEY_NAME)
    auth_line = f"Bearer {pplx_token}"
    ic(auth_line)

    payload = {
        "model": "llama-3.1-sonar-large-128k-online",
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {"role": "user", "content": question},
        ],
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": auth_line,
    }

    search_response = requests.post(url, json=payload, headers=headers)
    ic(search_response)
    ic(search_response.json())
    search_answer = search_response.json()["choices"][0]["message"]["content"]
    response = {"results": [{"toolCallId": tool_call_id, "result": search_answer}]}
    ic(response)
    return response
