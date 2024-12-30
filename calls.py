#!/usr/bin/python3

import os
import json
import tempfile
import httpx
from datetime import datetime, timedelta
from dateutil import tz
from typing import List
import typer
from loguru import logger
from pydantic import BaseModel
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static, Footer, Label
from textual.containers import Horizontal, Center, Container
from textual.binding import Binding
from textual.screen import ModalScreen
from icecream import ic

app = typer.Typer(no_args_is_help=True)

class Call(BaseModel):
    id: str
    Caller: str 
    Transcript: str
    Summary: str
    Start: datetime
    End: datetime
    Cost: float = 0.0
    CostBreakdown: dict = {}

    def length_in_seconds(self):
        return (self.End - self.Start).total_seconds()

def parse_call(call) -> Call:
    """Parse a VAPI call response into a Call model."""
    customer = ""
    if "customer" in call and "number" in call["customer"]:
        customer = call["customer"]["number"]

    created_at = call.get("createdAt")
    ended_at = call.get("endedAt", created_at)

    start_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
    end_dt = datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%S.%fZ") 
    
    start_dt = start_dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())
    end_dt = end_dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())

    transcript = call.get("artifact", {}).get("transcript", "")
    summary = call.get("analysis", {}).get("summary", "")

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

def vapi_calls() -> List[Call]:
    headers = {
        "authorization": f"{os.environ['VAPI_API_KEY']}",
        "createdAtGE": (datetime.now() - timedelta(days=1)).isoformat(),
    }
    return [
        parse_call(c)
        for c in httpx.get("https://api.vapi.ai/call", headers=headers).json()
    ]

class TranscriptScreen(ModalScreen):
    """Modal screen showing the full transcript."""
    
    BINDINGS = [("escape,space,enter", "dismiss", "Close")]

    def __init__(self, transcript_text: str):
        super().__init__()
        self.transcript_text = transcript_text

    def compose(self) -> ComposeResult:
        with Container(classes="transcript-overlay"):
            yield Static(self.transcript_text, id="transcript-text")

    def on_mount(self) -> None:
        container = self.query_one(Container)
        container.styles.align = ("center", "middle")
        container.styles.height = "90%"
        container.styles.width = "90%"
        
        self.styles.background = "rgba(0,0,0,0.5)"
        container.styles.background = "rgba(0,0,0,0.8)"
        container.styles.padding = (2, 4)
        container.styles.border = ("solid", "white")
        container.styles.overflow_y = "scroll"

    def on_key(self, event):
        self.dismiss()

class HelpScreen(ModalScreen):
    """Help screen showing available commands."""
    
    BINDINGS = [("escape,space,question_mark", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Container(classes="help-overlay"):
            yield Static(
                """╔════════════════════════════╗
║      Available Commands     ║
║                            ║
║  ? - Show this help        ║
║  j - Move down             ║
║  k - Move up              ║
║  e - Edit JSON details    ║
║  d - Show transcript      ║
║  q - Quit application     ║
║                            ║
║  Press any key to close    ║
╚════════════════════════════╝""",
                id="help-text"
            )

    def on_mount(self) -> None:
        container = self.query_one(Container)
        container.styles.align = ("center", "middle")
        container.styles.height = "100%"
        container.styles.width = "100%"
        
        self.styles.background = "rgba(0,0,0,0.5)"
        container.styles.background = "rgba(0,0,0,0.8)"
        container.styles.padding = (2, 4)
        container.styles.border = ("solid", "white")

    def on_key(self, event):
        self.dismiss()

class CallBrowserApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "move_down", "Down"),
        Binding("k", "move_up", "Up"),
        Binding("?", "help", "Help"),
        Binding("e", "edit_json", "Edit JSON"),
        Binding("d", "show_transcript", "Show Details"),
    ]

    def on_mount(self) -> None:
        """Called when app is mounted"""
        logger.info(f"App mounted, bindings: {self.BINDINGS}")

    def __init__(self):
        super().__init__()
        self.calls = vapi_calls()
        logger.info(f"Loaded {len(self.calls)} calls")

    def compose(self):
        """Change layout to horizontal split with transcript below"""
        with Container():
            with Horizontal(classes="top-container"):
                self.call_table = DataTable(id="calls")
                self.call_table.add_columns("Time", "Length", "Cost", "Summary")
                self.call_table.styles.width = "50%"
                
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

                self.details = Static("Select a call to view details", id="details")
                self.details.styles.width = "50%"
                self.details.styles.border = ("solid", "white")
                yield self.details

            # Bottom transcript pane
            self.transcript = Static("Press 'd' to view transcript", id="transcript")
            self.transcript.styles.height = "50vh"  # Take up half vertical height
            self.transcript.styles.border = ("solid", "white")
            self.transcript.styles.overflow_y = "scroll"
            yield self.transcript

    def on_data_table_row_selected(self, event):
        try:
            call = next(c for c in self.calls if c.id == event.row_key.value)
            
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
            
        except Exception as e:
            logger.error(f"Error updating views: {e}")
            self.details.update(f"Error loading call details: {str(e)}")

    def action_move_down(self):
        self.call_table.action_cursor_down()

    def action_move_up(self):
        self.call_table.action_cursor_up()
        
    def action_help(self):
        """Show help screen when ? is pressed."""
        self.push_screen(HelpScreen())

    def action_show_transcript(self):
        """Show full transcript in a modal when 'd' is pressed"""
        logger.info("Show transcript action triggered")
        selected_row = self.call_table.cursor_row
        if selected_row is None:
            return
            
        try:
            # Get the call directly from self.calls using the selected row index
            call = self.calls[selected_row]
            
            transcript_text = f"""Full Transcript for call {call.id}
Time: {call.Start.strftime('%Y-%m-%d %H:%M')}
Length: {call.length_in_seconds():.0f}s
Cost: ${call.Cost:.2f}

{call.Transcript}
"""
            # Update the bottom transcript pane
            self.transcript.update(transcript_text)
            
            # Show the modal popup
            self.push_screen(TranscriptScreen(transcript_text))
        except Exception as e:
            logger.error(f"Error showing transcript: {e}")
            error_message = f"Error loading transcript: {str(e)}"
            self.transcript.update(error_message)
            self.push_screen(TranscriptScreen(error_message))

    def action_edit_json(self):
        """Open the current call's JSON in external editor"""
        selected_row = self.call_table.cursor_row
        if selected_row is None:
            logger.warning("No row selected")
            return
            
        try:
            call = self.calls[selected_row]
            call_id = call.id
            
            headers = {
                "authorization": f"{os.environ['VAPI_API_KEY']}",
            }
            response = httpx.get(f"https://api.vapi.ai/call/{call_id}", headers=headers)
            raw_call = response.json()
            
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            with temp_file as f:
                json.dump(raw_call, f, indent=2, default=str)
                temp_path = f.name
                
            if os.name == 'nt':  # Windows
                os.system(f'notepad {temp_path}')
            else:  # Unix
                os.system(f'fx {temp_path}')
            
            # Refresh all panes by re-selecting the current row
            self.refresh()
            if selected_row is not None:
                self.call_table.select_row(selected_row)
            
        except Exception as e:
            logger.error(f"Error opening JSON: {e}")

@app.command()
def browse():
    """Browse calls in an interactive TUI"""
    app = CallBrowserApp()
    app.run()

@logger.catch()
def app_wrap_loguru():
    app()

if __name__ == "__main__":
    app_wrap_loguru()
