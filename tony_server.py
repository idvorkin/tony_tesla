#!python3


# import asyncio
from modal import App, web_endpoint
import modal
from typing import Dict
from icecream import ic
from pathlib import Path
import json
import httpx
import datetime

from modal import Image, Mount

default_image = Image.debian_slim(python_version="3.10").pip_install(
    ["icecream", "httpx", "requests"]
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
    extra_state = f"""
# Current state
date in UTC (but convert to PST as that's where Igor is, though don't mention it) :{datetime.datetime.now()} -
weather:
{parse_weather(weather_from_server())}
    """
    tony_prompt += extra_state
    ic(extra_state)
    # update system prompt
    tony["assistant"]["model"]["messages"][0]["content"] = tony_prompt
    ic(len(tony))
    return tony


@app.function(image=default_image, secrets=[modal.Secret.from_name("PPLX_API_KEY")])
@web_endpoint(method="POST")
def search(input:Dict):
    import requests
    import os
    tool_call_id = "tool_call_id"
    question = "Who is Dr Seuss"
    ic(input.keys())
    if message := input.get("message"):
        ic(message.keys())


    if _question := input.get("question"):
        question = _question

    ic(tool_call_id, question)

    url = "https://api.perplexity.ai/chat/completions"
    token = os.getenv("PPLX_API_KEY")
    auth_line = f"Bearer {token}"
    ic(auth_line)

    payload = {
        "model": "llama-3-sonar-large-32k-online",
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {
                "role": "user",
                "content": question
            },
        ],
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": auth_line,
    }

    search_response = requests.post(url, json=payload, headers=headers)
    ic(search_response)
    response = {"tool_call_id": tool_call_id, "toolCallId": tool_call_id, "result": search_response.text}
    return response


def parse_weather(weather):
    current = weather["current_condition"][0]
    degree, desc = get_weather(current)
    output = f"""Current Weather: {desc}: degrees {degree}
Weather Throught the Day hour, condition, temperature"""

    hourly = weather["weather"][0]["hourly"]
    for hour in hourly:
        time = hour["time"]
        degree, desc = get_weather(hour)
        output += f" {time}: {desc}: degrees {degree} \n"

    return output


def get_weather(line):
    desc = line["weatherDesc"][0]["value"]
    degree = line["FeelsLikeF"]
    return degree, desc


def weather_from_server():
    params = {"format": "j1"}
    response = httpx.get("https://wttr.in/seattle?format=json", params=params)
    return response.json()
