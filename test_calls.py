import pytest
from datetime import datetime, timedelta
from calls import CallBrowserApp, Call, HelpScreen, SortScreen
from textual.widgets import DataTable, Static
from textual.pilot import Pilot

# Mark all tests as async
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

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
        # Check table exists and has correct columns
        table = app.query_one(DataTable)
        assert [str(col).strip("ColumnKey('')") for col in table.columns.keys()] == [
            "Time", "Length", "Cost", "Summary"
        ]
        
        # Check initial details and transcript
        details = app.query_one("#details", Static)
        assert "Select a call to view details" in details.render()
        
        transcript = app.query_one("#transcript", Static)
        assert "Select a call to view transcript" in transcript.render()

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
        # Open sort screen
        await pilot.press("s")
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
        
        # Select first row
        await pilot.click(f"DataTable @ 0,0")
        
        # Verify details and transcript updated
        details_text = details.render()
        transcript_text = transcript.render()
        
        assert "Test summary 1" in details_text
        assert "Test transcript 1" in transcript_text
        assert "$1.50" in details_text

async def test_quit(app):
    """Test quit command works."""
    async with app.run_test() as pilot:
        # Send quit command
        await pilot.press("q")
        assert not app.is_running
