#!python3

import asyncio
import os

from typing import Annotated
from langchain_core import messages
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import httpx

import typer
from langchain.prompts import ChatPromptTemplate

from loguru import logger
from rich.console import Console
from icecream import ic
from datetime import datetime, timedelta
import json
from pathlib import Path
from dateutil import tz

console = Console()
app = typer.Typer(no_args_is_help=True)

TONY_ASSISTANT_ID = "f5fe3b31-0ff6-4395-bc08-bc8ebbbf48a6"


@logger.catch()
def app_wrap_loguru():
    app()


def prompt_transcribe_call(transcript):
    instructions = """
You are an AI assistant transcriber. Below is a  conversation with the assisatant (Tony) and a user (Igor)  that may capture todos and reminders
Parse them with a function call

"""
    return ChatPromptTemplate.from_messages(
        [
            messages.SystemMessage(content=instructions),
            messages.HumanMessage(content=transcript),
        ]
    )


class CallSummary(BaseModel):
    Notes: str = ""
    Reminders: list[str] = []
    JournalEntry: list[str] = []
    CompletedHabits: list[str] = []
    CallSummary: list[str] = []


class Call(BaseModel):
    id: str
    Caller: str
    Transcript: str
    Summary: str
    Start: datetime
    End: datetime
    Cost: float = 0.0
    CostBreakdown: dict = {}  # Add costBreakdown field

    def length_in_seconds(self):
        return (self.End - self.Start).total_seconds()


def parse_call(call) -> Call:
    """Parse a VAPI call response into a Call model.

    Args:
        call: Raw call data from VAPI API

    Returns:
        Call: Parsed call data with standardized fields
    """
    # Get customer number, defaulting to empty string if not present
    customer = ""
    if "customer" in call and "number" in call["customer"]:
        customer = call["customer"]["number"]

    # Get timestamps, using created time as fallback for end time
    created_at = call.get("createdAt")
    ended_at = call.get("endedAt", created_at)

    # Parse timestamps and convert to local timezone
    start_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
    end_dt = datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%S.%fZ")

    # Convert UTC to local timezone
    start_dt = start_dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())
    end_dt = end_dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())

    # Get transcript and summary, defaulting to empty strings
    transcript = call.get("artifact", {}).get("transcript", "")
    summary = call.get("analysis", {}).get("summary", "")

    # Get cost, handling both direct float and nested dict cases
    cost = call.get("cost", 0.0)
    if isinstance(cost, dict):
        cost = cost.get("total", 0.0)

    cost_breakdown = call.get("costBreakdown", {})

    return Call(
        id=call["id"],
        Caller=customer,
        Transcript=transcript,
        Start=start_dt,
        End=end_dt,
        Summary=summary,
        Cost=cost,
        CostBreakdown=cost_breakdown,
    )


def vapi_calls() -> list[Call]:
    # list all calls from VAPI
    # help:  https://api.vapi.ai/api#/Calls/CallController_findAll

    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
        "createdAtGE": (datetime.now() - timedelta(days=1)).isoformat(),
    }
    # future add createdAtGe
    return [
        parse_call(c)
        for c in httpx.get("https://api.vapi.ai/call", headers=headers).json()
    ]


@app.command()
def debug_loader():
    """Load and debug the Tony assistant configuration."""
    base = Path("modal_readonly")
    assistant_txt = (base / "tony_assistant_spec.json").read_text()
    tony = json.loads(assistant_txt)
    tony_prompt = (base / "tony_system_prompt.md").read_text()
    # Add context to system prompt
    extra_state = f"""
# Current state
date in UTC (but convert to PST as that's where Igor is, though don't mention it) :{datetime.now()} -
weather:
    """
    tony_prompt += extra_state
    ic(extra_state)
    # update system prompt
    tony["assistant"]["model"]["messages"][0]["content"] = tony_prompt
    ic(len(tony))
    return tony


@app.command()
def calls(
    costs: Annotated[bool, typer.Option(help="Show detailed cost breakdown")] = False,
):
    """List all recent VAPI calls with their details."""
    calls = vapi_calls()
    print(f"Found {len(calls)} calls")
    total_cost = 0.0
    for call in calls:
        start = call.Start.strftime("%Y-%m-%d %H:%M")
        print(
            f"Call: {call.Caller} at {start} ({call.length_in_seconds():.0f}s, {len(call.Transcript)} chars) ${call.Cost:.3f}"
        )
        total_cost += call.Cost
        if costs:
            # Display cost breakdown components
            breakdown = call.CostBreakdown
            if breakdown:
                print("  Cost Breakdown:")
                print(f"    Transport: ${breakdown.get('transport', 0):.3f}")
                print(f"    Speech-to-Text: ${breakdown.get('stt', 0):.3f}")
                print(f"    LLM: ${breakdown.get('llm', 0):.3f}")
                print(f"    Text-to-Speech: ${breakdown.get('tts', 0):.3f}")
                print(f"    VAPI: ${breakdown.get('vapi', 0):.3f}")
                if "analysisCostBreakdown" in breakdown:
                    analysis = breakdown["analysisCostBreakdown"]
                    print("    Analysis Costs:")
                    print(f"      Summary: ${analysis.get('summary', 0):.3f}")
                    print(
                        f"      Structured Data: ${analysis.get('structuredData', 0):.3f}"
                    )
                    print(
                        f"      Success Evaluation: ${analysis.get('successEvaluation', 0):.3f}"
                    )
        print(f"  Summary: {call.Summary}")
        print()

    if costs:
        print(f"\nTotal cost: ${total_cost:.3f}")


@app.command()
def last_transcript():
    """Show the transcript of the most recent call."""
    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
        "createdAtGE": (datetime.now() - timedelta(days=1)).isoformat(),
    }
    # future add createdAtGe
    calls = [c for c in httpx.get("https://api.vapi.ai/call", headers=headers).json()]
    ic(len(calls))
    ic(calls[0])


@app.command()
def dump_last_call():
    """Dump the complete raw JSON of the most recent call"""
    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
        "createdAtGE": (datetime.now() - timedelta(days=1)).isoformat(),
    }
    calls = httpx.get("https://api.vapi.ai/call", headers=headers).json()
    if not calls:
        print("No calls found")
        return

    # Get most recent call's complete data and print it
    print(json.dumps(calls[0], indent=2))


@app.command()
def export_vapi_tony_config(assistant_id=TONY_ASSISTANT_ID):
    """Export the current VAPI Tony assistant configuration."""
    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
    }
    tony = httpx.get(
        f"https://api.vapi.ai/assistant/{assistant_id}", headers=headers
    ).json()
    print(json.dumps(tony, indent=4))


@app.command()
def update_tony():
    """Update the Tony assistant configuration in VAPI."""
    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
    }
    tony = httpx.get(
        f"https://api.vapi.ai/assistant/{TONY_ASSISTANT_ID}", headers=headers
    ).json()
    # ic (tony)
    # original = tony["model"]["messages"][0]
    # print(original)
    # Run a diff to make sure happy with the path
    Path("tony.json").write_text(json.dumps(tony, indent=4))

    patch_document = [
        {"op": "replace", "path": "/model/messages", "value": tony["model"]["messages"]}
    ]

    ic(patch_document)

    patched = httpx.patch(
        f"https://api.vapi.ai/assistant/{TONY_ASSISTANT_ID}",
        headers=headers,
        json=patch_document,
    )
    ic(patched)
    ic(patched.text)
    # Ha, for now just copy the life convo to the clipboard, and paste it into the uX:
    # https://dashboard.vapi.ai/assistants


@app.command()
def parse_calls(
    trace: bool = False,
):
    """Parse and analyze recent calls for todos and reminders."""
    asyncio.run(a_parse_calls())


@app.command()
def local_parse_config():
    """Parse the local Tony assistant configuration files."""
    modal_storage = "modal_readonly"
    base = Path(f"{modal_storage}")
    assistant_txt = (base / "tony_assistant_spec.json").read_text(
        encoding="utf-8", errors="ignore"
    )
    ic(assistant_txt)
    tony = json.loads(assistant_txt)
    tony_prompt = (base / "tony_system_prompt.md").read_text()
    # update system prompt
    tony["assistant"]["model"]["messages"][0]["content"] = tony_prompt
    ic(len(tony))


async def a_parse_calls():
    async def transcribe_call(user_text):
        llm = ChatOpenAI(model="gpt-4.1", temperature=0)
        result = await (
            prompt_transcribe_call(user_text) | llm.with_structured_output(CallSummary)
        ).ainvoke({})
        return CallSummary(**result) if isinstance(result, dict) else result

    calls = vapi_calls()

    def interesting_call(call: Call):
        return call.length_in_seconds() > 90 and "4339" in call.Caller

    interesting_calls = [call for call in calls if interesting_call(call)]
    for call in interesting_calls:
        start = call.Start.strftime("%Y-%m-%d %H:%M")
        ic(call.length_in_seconds(), call.Caller, start)
        call_summary = await transcribe_call(call.Transcript)
        print(call_summary)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="The search query to send")],
    url: Annotated[
        str, typer.Option(help="The search endpoint URL")
    ] = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/search",
):
    """Search using Tony's search endpoint."""
    headers = {"x-vapi-secret": os.environ["TONY_API_KEY"]}

    data = {"question": query}

    # Increase timeout to 30 seconds
    response = httpx.post(url, headers=headers, json=data, timeout=30.0)

    if response.status_code == 200:
        results = response.json()
        if results and "results" in results and results["results"]:
            print(results["results"][0]["result"])
        else:
            print("No results found")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


@app.command()
def send_text(
    text: Annotated[str, typer.Argument(help="The text message to send")],
    to_number: Annotated[
        str, typer.Argument(help="The phone number to send the text to")
    ],
    url: Annotated[
        str, typer.Option(help="The send-text endpoint URL")
    ] = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/send-text",
):
    """Send a text message using Tony's send-text endpoint."""
    headers = {"x-vapi-secret": os.environ["TONY_API_KEY"]}

    data = {"text": text, "to_number": to_number}

    # Increase timeout to 30 seconds
    response = httpx.post(url, headers=headers, json=data, timeout=30.0)

    if response.status_code == 200:
        results = response.json()
        if results and "results" in results and results["results"]:
            print(results["results"][0]["result"])
        else:
            print("No results found")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    app_wrap_loguru()
