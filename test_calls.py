import pytest
from datetime import datetime, timedelta
from calls import CallBrowserApp, Call, HelpScreen, SortScreen
from textual.widgets import DataTable, Static, Button, Label
from textual.pilot import Pilot
from icecream import ic

# Mark all tests as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_calls():
    """Create sample calls for testing."""
    now = datetime.now()
    return [
        Call(
            id="1",
            Caller="+1234567890",
            Transcript="Test transcript 1",
            Summary="Test summary 1",
            Start=now,
            End=now + timedelta(minutes=1),
            Cost=1.50,
            CostBreakdown={}
        ),
        Call(
            id="2",
            Caller="+0987654321",
            Transcript="Test transcript 2",
            Summary="Test summary 2",
            Start=now + timedelta(hours=1),
            End=now + timedelta(hours=1, minutes=2),
            Cost=2.50,
            CostBreakdown={}
        ),
        Call(
            id="3",
            Caller="+1111111111",
            Transcript="Test transcript 3",
            Summary="A test summary 3",  # Note the 'A' prefix for testing summary sort
            Start=now + timedelta(hours=2),
            End=now + timedelta(hours=2, minutes=3),
            Cost=3.50,
            CostBreakdown={}
        )
    ]

@pytest.fixture
def app(monkeypatch, sample_calls):
    """Create app instance with mocked calls."""
    monkeypatch.setattr('calls.vapi_calls', lambda: sample_calls)
    return CallBrowserApp()

async def test_app_initial_state(app):
    """Test initial app state."""
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        
        # Debug column information
        ic("Column objects:", table.columns)
        # Get column labels from the Column objects in the dictionary values
        columns = [str(col.label) for col in table.columns.values()]
        assert columns == ["Time", "Length", "Cost", "Summary"]

        # Check initial details and transcript
        details = app.query_one("#details", Static)
        assert "Select a call to view details" in str(details.render())

        transcript = app.query_one("#transcript", Static)
        assert "Select a call to view transcript" in str(transcript.render())

async def test_navigation(app):
    """Test basic navigation works."""
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)

        # Test moving down
        await pilot.press("j")
        assert table.cursor_row == 1

        # Test moving up
        await pilot.press("k")
        assert table.cursor_row == 0

async def test_help_screen(app):
    """Test help screen shows and hides."""
    async with app.run_test() as pilot:
        # Open help screen
        await pilot.press("?")
        assert isinstance(app.screen, HelpScreen)

        # Close help screen
        await pilot.press("escape")
        assert not isinstance(app.screen, HelpScreen)

async def test_sort_screen(app):
    """Test sort screen shows and allows selection."""
    async with app.run_test() as pilot:
        # Debug sort screen navigation
        ic("Before pressing s")
        await pilot.press("s")
        ic("After pressing s",
           "Current screen", app.screen,
           "Screen type", type(app.screen))
        assert isinstance(app.screen, SortScreen)

        # Press escape to cancel
        await pilot.press("escape")
        assert not isinstance(app.screen, SortScreen)

async def test_call_selection(app):
    """Test selecting a call updates details and transcript."""
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        details = app.query_one("#details", Static)
        transcript = app.query_one("#transcript", Static)

        # Debug initial state
        ic("Initial cursor row:", table.cursor_row)
        ic("Initial details:", details.render())

        # Select first row using enter key
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause()

        # Get the rendered text
        details_text = str(details.render())
        transcript_text = str(transcript.render())

        # Debug final state
        ic("Final details:", details_text)
        ic("Final transcript:", transcript_text)

        # Check content
        assert "Test summary 1" in details_text
        assert "Test transcript 1" in transcript_text
        assert "$1.50" in details_text

async def test_quit(app):
    """Test quit command works."""
    async with app.run_test() as pilot:
        # Send quit command
        await pilot.press("q")
        assert not app.is_running

async def test_sort_functionality(app):
    """Test that sorting actually changes the table order."""
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        
        # Get initial order
        ic("Initial rows:", [table.get_row_at(i) for i in range(table.row_count)])
        
        # Open sort screen
        await pilot.press("s")
        assert isinstance(app.screen, SortScreen)
        
        # Sort by cost using keyboard shortcut
        await pilot.press("c")
        await pilot.pause()
        
        # Verify sort happened
        sorted_rows = [table.get_row_at(i) for i in range(table.row_count)]
        ic("Sorted rows:", sorted_rows)
        
        # Verify ascending order
        costs = [float(row[2].replace('$', '')) for row in sorted_rows]
        assert costs == [1.50, 2.50, 3.50]
        
        # Try reverse sort
        await pilot.press("s")  # Open sort screen again
        await pilot.press("r")  # Toggle reverse sort
        await pilot.press("c")  # Sort by cost
        await pilot.pause()
        
        # Verify reverse sort
        reverse_sorted_rows = [table.get_row_at(i) for i in range(table.row_count)]
        ic("Reverse sorted rows:", reverse_sorted_rows)
        
        # Verify descending order
        costs = [float(row[2].replace('$', '')) for row in reverse_sorted_rows]
        assert costs == [3.50, 2.50, 1.50]

async def test_sort_screen_layout(app):
    """Test sort screen layout and components."""
    async with app.run_test() as pilot:
        await pilot.press("s")

        # Check that all components are present
        sort_label = app.screen.query_one("#sort-label", Label)
        assert "Sort by:" in str(sort_label.render())

        buttons = app.screen.query(Button)
        button_texts = [str(b.get_content()) for b in buttons]
        assert any("[T]ime" in text for text in button_texts)
        assert any("[L]ength" in text for text in button_texts)
        assert any("[C]ost" in text for text in button_texts)
        assert any("[S]ummary" in text for text in button_texts)

        reverse_label = app.screen.query_one("#reverse-label", Label)
        assert "Press 'R' to toggle reverse sort" in str(reverse_label.render())

        reverse_status = app.screen.query_one("#reverse-status", Label)
        assert "Reverse sort: OFF" in str(reverse_status.render())

async def test_sort_screen_keyboard_shortcuts(app):
    """Test sort screen keyboard shortcuts."""
    async with app.run_test() as pilot:
        await pilot.press("s")
        
        # Test reverse sort toggle
        reverse_status = app.screen.query_one("#reverse-status", Label)
        assert "OFF" in str(reverse_status.render())
        await pilot.press("r")
        assert "ON" in str(reverse_status.render())
        
        # Test sorting by time (should dismiss screen)
        await pilot.press("t")
        assert not isinstance(app.screen, SortScreen)
        # First row should be earliest time
        assert "2024" in app.call_table.get_row_at(0)[0]  # Time column
        
        # Test sorting by length
        await pilot.press("s")  # Reopen sort screen
        await pilot.press("l")
        # First row should be shortest call (60s)
        assert "60s" in app.call_table.get_row_at(0)[1]  # Length column
        
        # Test sorting by cost
        await pilot.press("s")
        await pilot.press("c")
        # First row should be lowest cost ($1.50)
        assert "$1.50" in app.call_table.get_row_at(0)[2]  # Cost column
        
        # Test sorting by summary
        await pilot.press("s")
        await pilot.press("s")
        # First row should start with 'A' due to our test data
        first_row = app.call_table.get_row_at(0)
        assert "A test summary" in first_row[3]  # Summary column

async def test_sort_screen_reverse_sort(app):
    """Test reverse sort functionality."""
    async with app.run_test() as pilot:
        # Sort by cost in reverse order
        await pilot.press("s")
        await pilot.press("r")  # Enable reverse sort
        await pilot.press("c")  # Sort by cost
        
        # Check rows are in reverse order (highest cost first)
        rows = [app.call_table.get_row_at(i) for i in range(app.call_table.row_count)]
        costs = [float(row[2].replace('$', '')) for row in rows]
        assert costs == [3.50, 2.50, 1.50]
        
        # Test toggling reverse sort multiple times
        await pilot.press("s")
        await pilot.press("r")  # Disable reverse sort
        assert "OFF" in str(app.screen.query_one("#reverse-status").render())
        await pilot.press("r")  # Enable reverse sort
        assert "ON" in str(app.screen.query_one("#reverse-status").render())

async def test_sort_screen_button_clicks(app):
    """Test sort screen button interactions."""
    async with app.run_test() as pilot:
        await pilot.press("s")
        
        # Click the cost button
        cost_button = app.screen.query_one("#cost", Button)
        await pilot.click(cost_button)
        
        # Verify sort happened and screen dismissed
        assert not isinstance(app.screen, SortScreen)
        assert "$1.50" in app.call_table.get_row_at(0)[2]  # Cost column
        
        # Test clicking with reverse sort
        await pilot.press("s")
        await pilot.press("r")  # Enable reverse sort
        length_button = app.screen.query_one("#length", Button)
        await pilot.click(length_button)
        
        # Verify reverse sort worked
        rows = [app.call_table.get_row_at(i) for i in range(app.call_table.row_count)]
        lengths = [int(row[1].replace('s', '')) for row in rows]
        assert lengths == [180, 120, 60]  # Longest to shortest

async def test_arrow_key_navigation(app):
    """Test that both arrow keys and j/k work for navigation and update transcripts."""
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        details = app.query_one("#details", Static)
        transcript = app.query_one("#transcript", Static)
        
        # Select initial row
        await pilot.press("enter")
        await pilot.pause()
        assert "Test summary 1" in str(details.render())
        assert "Test transcript 1" in str(transcript.render())
        
        # Test arrow keys
        assert table.cursor_row == 0
        await pilot.press("down")
        await pilot.pause()  # Wait for cursor move
        await pilot.press("enter")  # Select the row
        await pilot.pause()  # Wait for selection to process
        assert table.cursor_row == 1
        assert "Test summary 2" in str(details.render())
        assert "Test transcript 2" in str(transcript.render())
        
        await pilot.press("up")
        await pilot.pause()  # Wait for cursor move
        await pilot.press("enter")  # Select the row
        await pilot.pause()  # Wait for selection to process
        assert table.cursor_row == 0
        assert "Test summary 1" in str(details.render())
        assert "Test transcript 1" in str(transcript.render())
        
        # Test j/k keys
        await pilot.press("j")
        await pilot.pause()  # Wait for cursor move
        await pilot.press("enter")  # Select the row
        await pilot.pause()  # Wait for selection to process
        assert table.cursor_row == 1
        assert "Test summary 2" in str(details.render())
        assert "Test transcript 2" in str(transcript.render())
        
        await pilot.press("k")
        await pilot.pause()  # Wait for cursor move
        await pilot.press("enter")  # Select the row
        await pilot.pause()  # Wait for selection to process
        assert table.cursor_row == 0
        assert "Test summary 1" in str(details.render())
        assert "Test transcript 1" in str(transcript.render())
