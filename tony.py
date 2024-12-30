#!python3


import asyncio

from typing import Annotated
from langchain_core import messages
from pydantic import BaseModel

import typer
from langchain.prompts import ChatPromptTemplate

from loguru import logger
from rich.console import Console
import langchain_helper
import httpx
from icecream import ic
from datetime import datetime, timedelta
import os
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
    Notes: str
    Reminders: list[str]
    JournalEntry: list[str]
    CompletedHabits: list[str]
    CallSummary: list[str]


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
        CostBreakdown=cost_breakdown
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
    costs: Annotated[bool, typer.Option(help="Show detailed cost breakdown")] = False
):
    """List all recent VAPI calls with their details."""
    calls = vapi_calls()
    print(f"Found {len(calls)} calls")
    total_cost = 0.0
    for call in calls:
        start = call.Start.strftime("%Y-%m-%d %H:%M")
        print(f"Call: {call.Caller} at {start} ({call.length_in_seconds():.0f}s, {len(call.Transcript)} chars) ${call.Cost:.3f}")
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
                if 'analysisCostBreakdown' in breakdown:
                    analysis = breakdown['analysisCostBreakdown']
                    print("    Analysis Costs:")
                    print(f"      Summary: ${analysis.get('summary', 0):.3f}")
                    print(f"      Structured Data: ${analysis.get('structuredData', 0):.3f}")
                    print(f"      Success Evaluation: ${analysis.get('successEvaluation', 0):.3f}")
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
    langchain_helper.langsmith_trace_if_requested(
        trace, lambda: asyncio.run(a_parse_calls())
    )


from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static, Footer, Label
from textual.containers import Horizontal, Center
from textual.binding import Binding
from textual.screen import ModalScreen

class HelpScreen(ModalScreen):
    """Help screen showing available commands."""
    
    def compose(self) -> ComposeResult:
        with Center():
            yield Static(
                """╔════════════════════════════╗
║      Available Commands     ║
║                            ║
║  ? - Show this help        ║
║  j - Move down             ║
║  k - Move up              ║
║  q - Quit application     ║
║                            ║
║  Press any key to close    ║
╚════════════════════════════╝""",
                id="help-text"
            )

    def on_key(self):
        self.app.pop_screen()

class CallBrowserApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "move_down", "Down"),
        Binding("k", "move_up", "Up"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.calls = vapi_calls()
        logger.info(f"Loaded {len(self.calls)} calls")

    def compose(self):
        # Create three columns using Horizontal layout
        with Horizontal():
            # Left column: Call list with explicit sizing
            self.call_table = DataTable(id="calls")
            self.call_table.add_columns("Time", "Length", "Cost", "Summary")
            self.call_table.styles.width = "30%"
            
            # Add calls to table with error handling
            try:
                for call in self.calls:
                    start = call.Start.strftime("%Y-%m-%d %H:%M")
                    length = f"{call.length_in_seconds():.0f}s"
                    self.call_table.add_row(
                        start,
                        length,
                        f"${call.Cost:.2f}",
                        call.Summary[:50] + "..." if call.Summary else "No summary",
                        key=call.id
                    )
                logger.info(f"Added {self.call_table.row_count} rows to table")
            except Exception as e:
                logger.error(f"Error adding calls to table: {e}")
            yield self.call_table

            # Middle column: Call details with explicit sizing
            self.details = Static("Select a call to view details", id="details")
            self.details.styles.width = "35%"
            yield self.details

            # Right column: JSON view with explicit sizing
            self.json_view = Static("Select a call to view JSON", id="json")
            self.json_view.styles.width = "35%"
            yield self.json_view

    def on_data_table_row_selected(self, event):
        try:
            # Get selected call
            call = next(c for c in self.calls if c.id == event.row_key.value)
            
            # Update details view
            details_text = f"""
Start: {call.Start}
End: {call.End}
Length: {call.length_in_seconds():.0f}s
Cost: ${call.Cost:.2f}
Caller: {call.Caller}

Summary:
{call.Summary}

Transcript:
{call.Transcript[:500]}...
"""
            self.details.update(details_text)

            # Get the raw API response for this call
            headers = {
                "authorization": f"{os.environ['VAPI_API_KEY']}",
            }
            response = httpx.get(f"https://api.vapi.ai/call/{call.id}", headers=headers)
            raw_call = response.json()
            
            # Format and update JSON view
            json_text = json.dumps(raw_call, indent=2, default=str)
            self.json_view.update(json_text)
            logger.info(f"Updated JSON view for call {call.id}")
        except Exception as e:
            logger.error(f"Error updating views: {e}")
            self.json_view.update("Error loading call details")

    def action_move_down(self):
        self.call_table.action_cursor_down()

    def action_move_up(self):
        self.call_table.action_cursor_up()
        
    def action_help(self):
        """Show help screen when ? is pressed."""
        self.push_screen(HelpScreen())

@app.command()
def browse():
    """Browse calls in an interactive TUI"""
    app = CallBrowserApp()
    app.run()

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
        llm = langchain_helper.get_model(openai=True)
        callSummary: CallSummary = await (
            prompt_transcribe_call(user_text) | llm.with_structured_output(CallSummary)
        ).ainvoke({})  # type:ignore
        return callSummary

    calls = vapi_calls()

    def interesting_call(call: Call):
        return call.length_in_seconds() > 90 and "4339" in call.Caller

    interesting_calls = [call for call in calls if interesting_call(call)]
    for call in interesting_calls:
        start = call.Start.strftime("%Y-%m-%d %H:%M")
        ic(call.length_in_seconds(), call.Caller, start)
        call_summary = await transcribe_call(call.Transcript)
        print(call_summary)


if __name__ == "__main__":
    app_wrap_loguru()
