import pytest
from datetime import datetime, timedelta
from calls import CallBrowserApp, Call, HelpScreen, SortScreen
from textual.widgets import DataTable, Static
from textual.pilot import Pilot

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
        
        # Add extensive debugging
        print("\nDEBUG: Column keys type:", type(table.columns.keys()))
        print("DEBUG: All column keys:", list(table.columns.keys()))
        print("DEBUG: First column key:", next(iter(table.columns.keys())))
        print("DEBUG: Dir of column key:", dir(next(iter(table.columns.keys()))))
        
        # Try different ways to get column names
        print("\nDEBUG: Attempting different column name extraction methods:")
        try:
            print("1. Using str():", [str(col) for col in table.columns.keys()])
        except Exception as e:
            print(f"Error with str(): {e}")
            
        try:
            print("2. Using value:", [col.value for col in table.columns.keys()])
        except Exception as e:
            print(f"Error with value: {e}")
            
        try:
            print("3. Using _value:", [getattr(col, '_value', None) for col in table.columns.keys()])
        except Exception as e:
            print(f"Error with _value: {e}")

        # Extract column names with debug info
        columns = [str(col).replace("ColumnKey('", "").replace("')", "") 
                  for col in table.columns.keys()]
        print("\nDEBUG: Final extracted columns:", columns)
        
        assert columns == ["Time", "Length", "Cost", "Summary"]
        
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
        # Add debugging
        print("\nDEBUG: Before pressing s")
        await pilot.press("s")
        print("DEBUG: After pressing s")
        print("DEBUG: Current screen:", app.screen)
        print("DEBUG: Screen type:", type(app.screen))
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
        
        await pilot.click("DataTable")
        table.move_cursor(row=0)
        table.action_select_cursor()
        
        # Add extensive debugging for rendered content
        print("\nDEBUG: Details widget info:")
        print("Type of details:", type(details))
        print("Dir of details:", dir(details))
        
        print("\nDEBUG: Render info:")
        rendered = details.render()
        print("Type of render result:", type(rendered))
        print("Dir of render result:", dir(rendered))
        print("Rendered content:", rendered)
        
        try:
            print("\nDEBUG: Attempting different ways to get text:")
            print("1. _renderable:", getattr(rendered, '_renderable', None))
            print("2. plain:", getattr(rendered, 'plain', None))
            print("3. text:", getattr(rendered, 'text', None))
            print("4. str(render):", str(rendered))
        except Exception as e:
            print(f"Error getting text attributes: {e}")
        
        # Try to get text content with debug info
        try:
            details_text = str(details.render()._renderable)
            print("\nDEBUG: Successfully got details_text:", details_text)
        except Exception as e:
            print(f"Error getting details text: {e}")
            raise
            
        transcript_text = str(transcript.render()._renderable)
        
        assert "Test summary 1" in details_text
        assert "Test transcript 1" in transcript_text
        assert "$1.50" in details_text

async def test_quit(app):
    """Test quit command works."""
    async with app.run_test() as pilot:
        # Send quit command
        await pilot.press("q")
        assert not app.is_running
