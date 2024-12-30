#!python3

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


class SortScreen(ModalScreen):
    """Sort selection screen"""

    def __init__(self, columns):
        super().__init__()
        self.columns = columns

    def compose(self) -> ComposeResult:
        with Container(classes="sort-overlay"):
            yield Static("Select column to sort by:")
            for i, col in enumerate(self.columns, 1):
                yield Static(f"{i}. {col}")
            yield Static("\nPress 1-{} to sort, or ESC to cancel".format(len(self.columns)))

    def on_mount(self) -> None:
        container = self.query_one(Container)
        container.styles.align = ("center", "middle")
        container.styles.height = "auto"
        container.styles.width = "auto"
        container.styles.background = "rgba(0,0,0,0.8)"
        container.styles.padding = (2, 4)
        container.styles.border = ("solid", "white")

    def on_key(self, event):
        if event.key == "escape":
            self.dismiss(None)
        elif event.key in [str(i) for i in range(1, len(self.columns) + 1)]:
            self.dismiss(int(event.key) - 1)

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
║  s - Sort by column       ║
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
        Binding("s", "sort", "Sort"),
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
            self.transcript = Static("Select a call to view transcript", id="transcript")
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
"""
            self.details.update(details_text)

            # Update transcript pane
            transcript_text = f"""Full Transcript for call {call.id}
Time: {call.Start.strftime('%Y-%m-%d %H:%M')}
Length: {call.length_in_seconds():.0f}s
Cost: ${call.Cost:.2f}

{call.Transcript}
"""
            self.transcript.update(transcript_text)

        except Exception as e:
            logger.error(f"Error updating views: {e}")
            self.details.update(f"Error loading call details: {str(e)}")
            self.transcript.update(f"Error loading transcript: {str(e)}")

    def _update_views_for_current_row(self):
        """Update both details and transcript for current row"""
        selected_row = self.call_table.cursor_row
        if selected_row is None:
            return
            
        try:
            call = self.calls[selected_row]
            
            details_text = f"""
Start: {call.Start}
End: {call.End}
Length: {call.length_in_seconds():.0f}s
Cost: ${call.Cost:.2f}
Caller: {call.Caller}

Summary:
{call.Summary}
"""
            self.details.update(details_text)
            
            transcript_text = f"""Full Transcript for call {call.id}
Time: {call.Start.strftime('%Y-%m-%d %H:%M')}
Length: {call.length_in_seconds():.0f}s
Cost: ${call.Cost:.2f}

{call.Transcript}
"""
            self.transcript.update(transcript_text)
            
        except Exception as e:
            logger.error(f"Error updating views: {e}")
            self.details.update(f"Error loading call details: {str(e)}")
            self.transcript.update(f"Error loading transcript: {str(e)}")

    def action_move_down(self):
        """Move cursor down and update transcript"""
        self.call_table.action_cursor_down()
        self._update_views_for_current_row()

    def action_move_up(self):
        """Move cursor up and update transcript"""
        self.call_table.action_cursor_up()
        self._update_views_for_current_row()

    def action_help(self):
        """Show help screen when ? is pressed."""
        self.push_screen(HelpScreen())

    def action_sort(self):
        """Show sort column selection screen"""
        async def show_sort_screen() -> None:
            print("\nDEBUG: Starting sort screen")
            print("Column keys:", self.call_table.columns.keys())
            
            try:
                # Extract column names with debug info
                columns = [str(col).replace("ColumnKey('", "").replace("')", "") 
                          for col in self.call_table.columns.keys()]
                print("DEBUG: Extracted columns:", columns)
            except Exception as e:
                print(f"Error extracting columns: {e}")
                raise
                
            screen = SortScreen(columns)
            print("DEBUG: Created sort screen")
            
            column_index = await self.push_screen_wait(screen)
            print(f"DEBUG: Selected column index: {column_index}")
            
            if column_index is not None:  # None means user cancelled
                # Sort the calls based on the selected column
                column_name = columns[column_index]
                
                # Define sort key based on column
                if column_name == "Time":
                    self.calls.sort(key=lambda x: x.Start)
                elif column_name == "Length":
                    self.calls.sort(key=lambda x: x.length_in_seconds())
                elif column_name == "Cost":
                    self.calls.sort(key=lambda x: x.Cost)
                elif column_name == "Summary":
                    self.calls.sort(key=lambda x: x.Summary)
                
                # Refresh the table
                self.call_table.clear()
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

        self.run_worker(show_sort_screen())


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
