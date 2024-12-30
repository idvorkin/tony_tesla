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
from textual.widgets import DataTable, Static, Footer, Label, Button
from textual.containers import Horizontal, Center, Container, Grid
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
    """Screen for sorting options."""
    
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("t", "sort('time')", "Sort by Time"),
        ("l", "sort('length')", "Sort by Length"),
        ("c", "sort('cost')", "Sort by Cost"),
        ("s", "sort('summary')", "Sort by Summary"),
        ("r", "toggle_reverse", "Toggle Reverse Sort"),
    ]

    CSS = """
    Screen {
        align: center middle;
    }

    #sort-container {
        width: 60;
        height: auto;
        background: $boost;
        border: tall $background;
        padding: 1;
    }

    #sort-grid {
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1 2;
        padding: 1;
        content-align: center middle;
    }
    
    Button {
        width: 100%;
    }

    Label {
        content-align: center middle;
        width: 100%;
        padding: 1;
    }

    #sort-label {
        color: $secondary;
        text-style: bold;
    }

    #reverse-label {
        color: $text;
    }

    #reverse-status {
        color: $warning;
        text-style: bold;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.reverse_sort = False

    def compose(self) -> ComposeResult:
        with Container(id="sort-container"):
            yield Label("Sort by:", id="sort-label")
            with Grid(id="sort-grid"):
                yield Button("[T]ime", id="time", variant="primary")
                yield Button("[L]ength", id="length")
                yield Button("[C]ost", id="cost")
                yield Button("[S]ummary", id="summary")
            yield Label("Press 'R' to toggle reverse sort", id="reverse-label")
            yield Label("Reverse sort: OFF", id="reverse-status")

    def action_toggle_reverse(self):
        """Toggle reverse sort order."""
        self.reverse_sort = not self.reverse_sort
        status_label = self.query_one("#reverse-status", Label)
        status_label.update(f"Reverse sort: {'ON' if self.reverse_sort else 'OFF'}")

    def action_sort(self, column: str):
        """Handle sort action for a column."""
        # Get the parent app
        app = self.app
        if isinstance(app, CallBrowserApp):
            # Sort the calls
            reverse = self.reverse_sort
            if column == "time":
                app.calls.sort(key=lambda x: x.Start, reverse=reverse)
            elif column == "length":
                app.calls.sort(key=lambda x: x.length_in_seconds(), reverse=reverse)
            elif column == "cost":
                app.calls.sort(key=lambda x: x.Cost, reverse=reverse)
            else:  # summary
                app.calls.sort(key=lambda x: x.Summary or "", reverse=reverse)
            
            # Refresh the table
            app.call_table.clear()
            for call in app.calls:
                start = call.Start.strftime("%Y-%m-%d %H:%M")
                length = f"{call.length_in_seconds():.0f}s"
                app.call_table.add_row(
                    start,
                    length,
                    f"${call.Cost:.2f}",
                    call.Summary[:50] + "..." if call.Summary else "No summary",
                    key=call.id
                )
        
        # Reset reverse sort status
        self.reverse_sort = False
        status_label = self.query_one("#reverse-status", Label)
        status_label.update("Reverse sort: OFF")
        
        # Dismiss the modal
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id
        if button_id in ["time", "length", "cost", "summary"]:
            self.action_sort(button_id)

    def on_mount(self) -> None:
        """Reset state when screen is mounted."""
        self.reverse_sort = False
        status_label = self.query_one("#reverse-status", Label)
        status_label.update("Reverse sort: OFF")

class HelpScreen(ModalScreen):
    """Help screen showing available commands."""

    BINDINGS = [("escape,q", "dismiss", "Close")]

    CSS = """
    Screen {
        align: center middle;
    }

    #help-container {
        width: 35;
        background: $boost;
        border: tall $background;
        padding: 1;
    }

    #help-title {
        text-align: center;
        padding-bottom: 1;
        color: $text;
    }

    #help-content {
        padding: 1;
    }

    .command {
        text-align: left;
        padding-left: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="help-container"):
            yield Label("Available Commands", id="help-title")
            with Container(id="help-content"):
                yield Label("? - Show help", classes="command")
                yield Label("j - Move down", classes="command")
                yield Label("k - Move up", classes="command")
                yield Label("e - Edit JSON", classes="command")
                yield Label("s - Sort", classes="command")
                yield Label("q - Quit", classes="command")

    def on_key(self, event):
        self.dismiss()

class TranscriptScreen(ModalScreen):
    """Modal screen for displaying call transcript."""
    
    BINDINGS = [("escape,q", "dismiss", "Close")]

    CSS = """
    Screen {
        align: center middle;
    }

    #transcript-container {
        width: 80%;
        height: 80%;
        background: $boost;
        border: tall $background;
        padding: 1;
    }

    #transcript-content {
        height: 100%;
        overflow-y: scroll;
        padding: 1;
    }
    """

    def __init__(self, transcript: str):
        super().__init__()
        self.transcript = transcript

    def compose(self) -> ComposeResult:
        with Container(id="transcript-container"):
            yield Static(f"Full Transcript:\n{self.transcript}", id="transcript-content")

class EditScreen(ModalScreen):
    """Screen for editing options."""
    
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("f", "edit_fx", "Edit in fx"),
        ("s", "edit_summary", "Edit Summary"),
        ("c", "edit_conversation", "Edit Conversation"),
    ]

    CSS = """
    Screen {
        align: center middle;
        background: $primary 30%;
    }

    #edit-container {
        width: 60;
        height: auto;
        background: $boost;
        border: tall $background;
        padding: 1;
    }

    #edit-grid {
        layout: grid;
        grid-size: 1 3;
        grid-gutter: 1 2;
        padding: 1;
        content-align: center middle;
    }
    
    Button {
        width: 100%;
    }

    Label {
        content-align: center middle;
        width: 100%;
        padding: 1;
    }

    #edit-label {
        color: $secondary;
        text-style: bold;
    }
    """
    
    def __init__(self, call_data: dict):
        super().__init__()
        self.call_data = call_data

    def compose(self) -> ComposeResult:
        with Container(id="edit-container"):
            yield Label("Edit Options:", id="edit-label")
            with Grid(id="edit-grid"):
                yield Button("[F]x View", id="fx", variant="primary")
                yield Button("[S]ummary in vi", id="summary")
                yield Button("[C]onversation in vi", id="conversation")

    def _write_temp_file(self, content: str, suffix: str = '.json') -> str:
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
        with temp_file as f:
            f.write(content)
            return f.name

    def _get_editor(self):
        """Get the editor command from $EDITOR environment variable or fallback to bat."""
        return os.environ.get('EDITOR', 'bat')

    def _run_external_command(self, command: str):
        """Run an external command with proper terminal handling."""
        try:
            # Remove focus to restore terminal to cooked mode
            self.app.set_focus(None)
            # Run the command
            if 'bat' in command:
                command += ' | less'  # Ensure bat output is paginated
            os.system(command)
        finally:
            # Restore focus to put terminal back in raw mode
            self.app.set_focus(self)
            # Dismiss the screen
            self.dismiss()

    def action_edit_fx(self):
        """Open the raw JSON in fx"""
        temp_path = self._write_temp_file(json.dumps(self.call_data, indent=2, default=str))
        self._run_external_command(f'fx {temp_path}')

    def action_edit_summary(self):
        """Open the summary in editor"""
        summary = self.call_data.get("analysis", {}).get("summary", "No summary available")
        temp_path = self._write_temp_file(summary, '.txt')
        editor = self._get_editor()
        self._run_external_command(f'{editor} {temp_path}')

    def action_edit_conversation(self):
        """Open the full conversation in editor"""
        transcript = self.call_data.get("artifact", {}).get("transcript", "No transcript available")
        temp_path = self._write_temp_file(transcript, '.txt')
        editor = self._get_editor()
        self._run_external_command(f'{editor} {temp_path}')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id
        if button_id == "fx":
            self.action_edit_fx()
        elif button_id == "summary":
            self.action_edit_summary()
        elif button_id == "conversation":
            self.action_edit_conversation()

class CallBrowserApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j,down", "move_down", "Down"),
        Binding("k,up", "move_up", "Up"),
        Binding("?", "help", "Help"),
        Binding("e", "edit_json", "Edit JSON"),
        Binding("s", "sort", "Sort"),
        Binding("enter", "select_row", "Select"),
        Binding("t", "show_transcript", "Transcript"),
    ]

    def on_mount(self) -> None:
        """Called when app is mounted"""
        logger.info(f"App mounted, bindings: {self.BINDINGS}")

    def __init__(self):
        super().__init__()
        self.calls = vapi_calls()
        logger.info(f"Loaded {len(self.calls)} calls")
        self.current_call = None

    def compose(self):
        """Change layout to horizontal split with transcript below"""
        with Container():
            with Horizontal(classes="top-container"):
                self.call_table = DataTable(id="calls")
                # Add columns with proper string labels
                self.call_table.add_column("Time")
                self.call_table.add_column("Length")
                self.call_table.add_column("Cost")
                self.call_table.add_column("Summary")
                self.call_table.styles.width = "50%"
                self.call_table.cursor_type = "row"

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

    def action_show_transcript(self) -> None:
        """Show the transcript modal for the current call"""
        if self.current_call:
            self.push_screen(TranscriptScreen(self.current_call.Transcript))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        ic("Row selected event:", event)
        ic("Current cursor row:", self.call_table.cursor_row)
        if self.call_table.cursor_row is not None:
            self.current_call = self.calls[self.call_table.cursor_row]
            details_text = f"""
Start: {self.current_call.Start}
End: {self.current_call.End}
Length: {self.current_call.length_in_seconds():.0f}s
Cost: ${self.current_call.Cost:.2f}
Caller: {self.current_call.Caller}

Summary:
{self.current_call.Summary}

Press 't' to view full transcript
"""
            self.details.update(details_text)

    def action_select_row(self):
        """Handle enter key press to select row"""
        ic("Select row action triggered")
        ic("Current cursor row:", self.call_table.cursor_row)
        if self.call_table.cursor_row is not None:
            self.call_table.action_select_cursor()

    def action_move_down(self):
        """Move cursor down and update transcript"""
        self.call_table.action_cursor_down()
        if self.call_table.cursor_row is not None:
            self.call_table.action_select_cursor()
        self._update_views_for_current_row()

    def action_move_up(self):
        """Move cursor up and update transcript"""
        self.call_table.action_cursor_up()
        if self.call_table.cursor_row is not None:
            self.call_table.action_select_cursor()
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
                
            screen = SortScreen()
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
        """Show edit options modal"""
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

            self.push_screen(EditScreen(raw_call))

        except Exception as e:
            logger.error(f"Error opening edit options: {e}")

    def _update_views_for_current_row(self):
        """Update both details and transcript for current row"""
        selected_row = self.call_table.cursor_row
        ic("Updating views for row:", selected_row)
        
        if selected_row is None:
            ic("No row selected")
            return
            
        try:
            call = self.calls[selected_row]
            ic("Found call:", call.id)
            
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
            
            # Update transcript without the "Full Transcript:" header
            self.transcript.update(call.Transcript)
            
        except Exception as e:
            logger.error(f"Error updating views: {e}")
            ic("Error updating views:", str(e))
            self.details.update(f"Error loading call details: {str(e)}")
            self.transcript.update(f"Error loading transcript: {str(e)}")

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
