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
from cache import get_cached_calls, cache_calls, get_latest_cached_call, get_cache_stats
from models import Call

app = typer.Typer(no_args_is_help=True)

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

def format_phone_number(phone: str) -> str:
    """Format a phone number into a nice display format."""
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Handle different length phone numbers
    if len(digits) >= 10:  # Take last 10 digits if longer
        last_ten = digits[-10:]  # Get last 10 digits
        return f"({last_ten[:3]}){last_ten[3:6]}-{last_ten[6:]}"
    else:
        return phone  # Return original if we can't format it

def vapi_calls() -> List[Call]:
    """Get all calls from the last 24 hours, using cache when possible."""
    from cache import get_cached_calls, cache_calls, get_latest_cached_call, get_cache_stats
    
    logger.debug("Fetching calls...")
    stats = get_cache_stats()
    logger.debug(f"Current cache stats: {stats}")
    
    try:
        # Try to get cached calls first
        cached_calls = get_cached_calls(max_age_minutes=1440)  # 24 hours
        if cached_calls is not None:
            logger.info(f"Found {len(cached_calls)} calls in cache")
            
            try:
                # Get the latest call from API to check if we need to update cache
                headers = {
                    "authorization": f"{os.environ['VAPI_API_KEY']}",
                    "createdAtGE": (datetime.now() - timedelta(minutes=10)).isoformat(),  # Look back 10 minutes
                    "limit": "1"  # Only get the latest call
                }
                latest_api_call = httpx.get("https://api.vapi.ai/call", headers=headers).json()
                
                if latest_api_call:
                    latest_api_call = parse_call(latest_api_call[0])
                    latest_cached_call = get_latest_cached_call()
                    
                    # If the latest API call is already in our cache, return cached calls
                    if latest_cached_call and latest_api_call.id == latest_cached_call.id:
                        logger.info("Cache is up to date, using cached calls")
                        return cached_calls
                    else:
                        logger.info("Found new calls, refreshing cache")
            except Exception as e:
                logger.warning(f"Error checking for new calls: {e}. Using cached calls as fallback.")
                return cached_calls

        logger.info("Cache miss or new calls available, fetching from API")
        # If no valid cache or new calls exist, fetch all calls from API
        headers = {
            "authorization": f"{os.environ['VAPI_API_KEY']}",
            "createdAtGE": (datetime.now() - timedelta(days=1)).isoformat(),
        }
        response = httpx.get("https://api.vapi.ai/call", headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        calls_data = response.json()
        
        calls = [parse_call(c) for c in calls_data]
        logger.info(f"Fetched {len(calls)} calls from API")
        
        # Cache the results
        cache_calls(calls)
        logger.info("Calls cached successfully")
        
        return calls
        
    except Exception as e:
        logger.error(f"Error fetching calls: {e}")
        # If we have cached calls and hit an error, use them as fallback
        if cached_calls is not None:
            logger.warning("Using cached calls as fallback due to error")
            return cached_calls
        raise  # Re-raise the exception if we have no fallback


class SortScreen(ModalScreen):
    """Screen for sorting options."""
    
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("t", "sort('time')", "Sort by Time"),
        ("l", "sort('length')", "Sort by Length"),
        ("c", "sort('cost')", "Sort by Cost"),
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
            yield Label("Press 'R' to toggle sort direction", id="reverse-label")
            yield Label("Sort: Descending", id="reverse-status")

    def action_toggle_reverse(self):
        """Toggle reverse sort order."""
        self.reverse_sort = not self.reverse_sort
        status_label = self.query_one("#reverse-status", Label)
        status_label.update(f"Sort: {'Ascending' if self.reverse_sort else 'Descending'}")

    def action_sort(self, column: str):
        """Handle sort action for a column."""
        # Get the parent app
        app = self.app
        if isinstance(app, CallBrowserApp):
            # Sort the calls
            reverse = not self.reverse_sort
            if column == "time":
                app.calls.sort(key=lambda x: x.Start, reverse=reverse)
            elif column == "length":
                app.calls.sort(key=lambda x: x.length_in_seconds(), reverse=reverse)
            elif column == "cost":
                app.calls.sort(key=lambda x: x.Cost, reverse=reverse)
            
            # Refresh the table
            app.call_table.clear()
            for call in app.calls:
                start = call.Start.strftime("%Y-%m-%d %H:%M")
                length = f"{call.length_in_seconds():.0f}s"
                app.call_table.add_row(
                    start,
                    length,
                    f"${call.Cost:.2f}",
                    key=call.id
                )
        
        # Reset reverse sort status
        self.reverse_sort = False
        status_label = self.query_one("#reverse-status", Label)
        status_label.update("Sort: Descending")
        
        # Dismiss the modal
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id
        if button_id in ["time", "length", "cost"]:
            self.action_sort(button_id)

    def on_mount(self) -> None:
        """Reset state when screen is mounted."""
        self.reverse_sort = False
        status_label = self.query_one("#reverse-status", Label)
        status_label.update("Sort: Descending")

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

class EditScreen(ModalScreen):
    """Screen for editing options."""
    
    BINDINGS = [
        ("escape,q", "dismiss", "Close"),
        ("f", "edit_fx", "View in fx"),
        ("s", "view_summary", "View Summary"),
        ("c", "view_conversation", "View Conversation"),
        ("v", "view_json", "View JSON in VI"),
    ]

    CSS = """
    Screen {
        align: center middle;
        background: $primary 30%;
    }

    #edit-container {
        width: 40;
        height: auto;
        background: $boost;
        border: tall $background;
        padding: 1;
    }

    #edit-grid {
        layout: grid;
        grid-size: 1;
        padding: 1;
        content-align: center middle;
    }
    
    Button {
        width: 100%;
        margin-bottom: 1;
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
            yield Label("View Options (press q to close):", id="edit-label")
            with Grid(id="edit-grid"):
                yield Button("[F]x View", id="fx", variant="primary")
                yield Button("[S]ummary", id="summary")
                yield Button("[C]onversation", id="conversation")
                yield Button("[V]iew JSON", id="view_json")

    def _run_external_command(self, command: str):
        """Run an external command with proper terminal handling."""
        try:
            # Remove focus to restore terminal to cooked mode
            self.app.set_focus(None)
            # Run in new tmux window with 'q to close' in title
            os.system(f'tmux new-window -n "q to close" "{command}"')
        except Exception as e:
            logger.error(f"Error running command: {e}")
        finally:
            # Restore focus to put terminal back in raw mode
            self.app.set_focus(self)

    def _get_editor(self):
        """Get the editor command from $EDITOR environment variable or fallback to vi."""
        return os.environ.get('EDITOR', 'vi')

    def action_edit_fx(self):
        """Open the raw JSON in fx"""
        temp_path = self._write_temp_file(json.dumps(self.call_data, indent=2, default=str))
        self._run_external_command(f'fx {temp_path}')

    def action_view_summary(self):
        """Edit the summary in vi"""
        summary = self.call_data.get("analysis", {}).get("summary", "No summary available")
        temp_path = self._write_temp_file(summary, '.txt')
        editor = self._get_editor()
        self._run_external_command(f'{editor} {temp_path}')

    def action_view_conversation(self):
        """Edit the full conversation in vi"""
        transcript = self.call_data.get("artifact", {}).get("transcript", "No transcript available")
        temp_path = self._write_temp_file(transcript, '.vapi_transcript.txt')
        editor = self._get_editor()
        self._run_external_command(f'{editor} {temp_path}')

    def action_view_json(self):
        """View the entire call JSON in VI"""
        temp_path = self._write_temp_file(json.dumps(self.call_data, indent=2, default=str))
        editor = self._get_editor()
        self._run_external_command(f'{editor} {temp_path}')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        button_id = event.button.id
        if button_id == "fx":
            self.action_edit_fx()
        elif button_id == "summary":
            self.action_view_summary()
        elif button_id == "conversation":
            self.action_view_conversation()
        elif button_id == "view_json":
            self.action_view_json()

class CallBrowserApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j,down", "move_down", "Down"),
        Binding("k,up", "move_up", "Up"),
        Binding("g,g", "move_top", "Top"),
        Binding("G", "move_bottom", "Bottom"),
        Binding("?", "help", "Help"),
        Binding("e", "edit_json", "Edit JSON"),
        Binding("s", "sort", "Sort"),
        Binding("enter", "select_row", "Select"),
    ]

    def on_mount(self) -> None:
        """Called when app is mounted"""
        logger.info(f"App mounted, bindings: {self.BINDINGS}")
        # Select first row on load if there are any calls
        if self.calls and len(self.calls) > 0:
            self.call_table.move_cursor(row=0)
            self.call_table.action_select_cursor()
            self._update_views_for_current_row()

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
                self.call_table.styles.width = "50%"
                self.call_table.cursor_type = "row"

                try:
                    for call in self.calls:
                        start = call.Start.strftime("%Y-%m-%d %H:%M")
                        # Format length in MM:SS
                        length_seconds = call.length_in_seconds()
                        minutes = int(length_seconds // 60)
                        seconds = int(length_seconds % 60)
                        length = f"{minutes}:{seconds:02d}"
                        self.call_table.add_row(
                            start,
                            length,
                            f"${call.Cost:.2f}",
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        ic("Row selected event:", event)
        ic("Current cursor row:", self.call_table.cursor_row)
        if self.call_table.cursor_row is not None:
            self.current_call = self.calls[self.call_table.cursor_row]
            self._update_views_for_current_row()

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
                
                # Refresh the table
                self.call_table.clear()
                for call in self.calls:
                    start = call.Start.strftime("%Y-%m-%d %H:%M")
                    length = f"{call.length_in_seconds():.0f}s"
                    self.call_table.add_row(
                        start,
                        length,
                        f"${call.Cost:.2f}",
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
            
            # Format length in MM:SS
            length_seconds = call.length_in_seconds()
            minutes = int(length_seconds // 60)
            seconds = int(length_seconds % 60)
            length_str = f"{minutes}:{seconds:02d}"
            
            details_text = f"""[bold cyan]Start:[/] {call.Start.strftime("%Y-%m-%d %H:%M")}
[bold yellow]Length:[/] {length_str}
[bold green]Cost:[/] ${call.Cost:.2f}
[bold magenta]Caller:[/] {format_phone_number(call.Caller)}

{call.Summary}"""
            self.details.markup = True  # Enable markup parsing
            self.details.update(details_text)
            
            # Colorize the transcript
            transcript_lines = call.Transcript.split('\n')
            colored_lines = []
            for line in transcript_lines:
                if line.strip().startswith('AI:') or line.strip().startswith('Tony:'):
                    prefix, rest = line.split(':', 1)
                    colored_lines.append(f"[bright_cyan]{prefix}:[/][green]{rest}[/]")
                elif line.strip().startswith('User:') or line.strip().startswith('Igor:'):
                    prefix, rest = line.split(':', 1)
                    colored_lines.append(f"[bright_yellow]{prefix}:[/][yellow]{rest}[/]")
                else:
                    colored_lines.append(line)
            
            colored_transcript = '\n'.join(colored_lines)
            self.transcript.markup = True  # Enable markup parsing
            self.transcript.update(colored_transcript)
            
        except Exception as e:
            logger.error(f"Error updating views: {e}")
            ic("Error updating views:", str(e))
            self.details.update(f"Error loading call details: {str(e)}")
            self.transcript.update(f"Error loading transcript: {str(e)}")

    def action_move_top(self):
        """Move cursor to top of list"""
        self.call_table.move_cursor(row=0)
        self.call_table.action_select_cursor()
        self._update_views_for_current_row()

    def action_move_bottom(self):
        """Move cursor to bottom of list"""
        last_row = len(self.calls) - 1
        self.call_table.move_cursor(row=last_row)
        self.call_table.action_select_cursor()
        self._update_views_for_current_row()

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
