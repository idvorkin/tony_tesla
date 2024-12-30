import pytest
from datetime import datetime
from dateutil import tz
from calls import parse_call, format_phone_number, Call, CallBrowserApp, HelpScreen
from textual.pilot import Pilot

@pytest.fixture
def sample_call():
    """Create a sample call for testing"""
    return Call(
        id="test-id",
        Caller="1234567890",
        Transcript="Tony: Hello\nIgor: Hi",
        Summary="Test summary",
        Start=datetime(2024, 1, 15, 14, 30, tzinfo=tz.tzutc()),
        End=datetime(2024, 1, 15, 14, 35, tzinfo=tz.tzutc()),
        Cost=1.23,
        CostBreakdown={"transcription": 0.5, "analysis": 0.73}
    )

@pytest.fixture
def long_transcript_call():
    """Create a sample call with a long transcript for testing scrolling"""
    # Create a transcript that's definitely longer than the viewport
    lines = []
    for i in range(100):
        if i % 2 == 0:
            lines.append(f"Tony: Line {i}")
        else:
            lines.append(f"Igor: Line {i}")
    
    return Call(
        id="test-id",
        Caller="1234567890",
        Transcript="\n".join(lines),
        Summary="Test summary",
        Start=datetime(2024, 1, 15, 14, 30, tzinfo=tz.tzutc()),
        End=datetime(2024, 1, 15, 14, 35, tzinfo=tz.tzutc()),
        Cost=1.23,
        CostBreakdown={"transcription": 0.5, "analysis": 0.73}
    )

def test_format_phone_number():
    """Test phone number formatting"""
    assert format_phone_number("1234567890") == "(123)456-7890"
    assert format_phone_number("+11234567890") == "(123)456-7890"
    assert format_phone_number("123-456-7890") == "(123)456-7890"
    assert format_phone_number("invalid") == "invalid"  # Returns original if can't format
    assert format_phone_number("12345") == "12345"  # Returns original if too short

def test_parse_call():
    """Test parsing a call from API response"""
    sample_call = {
        "id": "test-id",
        "customer": {"number": "1234567890"},
        "createdAt": "2024-01-15T14:30:00.000Z",
        "endedAt": "2024-01-15T14:35:00.000Z",
        "artifact": {"transcript": "Sample transcript"},
        "analysis": {"summary": "Sample summary"},
        "cost": 1.23,
        "costBreakdown": {"transcription": 0.5, "analysis": 0.73}
    }

    call = parse_call(sample_call)
    
    assert isinstance(call, Call)
    assert call.id == "test-id"
    assert call.Caller == "1234567890"
    assert call.Transcript == "Sample transcript"
    assert call.Summary == "Sample summary"
    assert call.Cost == 1.23
    assert isinstance(call.Start, datetime)
    assert isinstance(call.End, datetime)
    assert call.Start.tzinfo is not None  # Should be timezone-aware
    assert call.End.tzinfo is not None
    
    # Test length calculation
    length = call.length_in_seconds()
    assert length == 300.0  # 5 minutes = 300 seconds

@pytest.mark.asyncio
async def test_pane_navigation(sample_call):
    """Test navigation between widgets"""
    app = CallBrowserApp()
    app.calls = [sample_call]  # Use sample call for testing
    
    async with app.run_test() as pilot:
        # Test initial focus
        assert app.focused == app.call_table
        
        # Test tab navigation
        await pilot.press("tab")
        await pilot.pause()
        transcript_container = app.query_one("#transcript-container")
        assert app.focused == transcript_container
        
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused == app.call_table
        
        # Test reverse tab navigation
        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.focused == transcript_container
        
        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.focused == app.call_table

@pytest.mark.asyncio
async def test_pane_scrolling(sample_call):
    """Test scrolling behavior in different widgets"""
    app = CallBrowserApp()
    app.calls = [sample_call]
    
    async with app.run_test() as pilot:
        # Test call table navigation
        await pilot.press("j")  # Move down
        assert app.call_table.cursor_row == 0  # Only one row
        await pilot.press("k")  # Move up
        assert app.call_table.cursor_row == 0
        
        # Test transcript scrolling
        await pilot.press("tab")  # Focus transcript container
        await pilot.pause()
        transcript_container = app.query_one("#transcript-container")
        assert app.focused == transcript_container
        
        # Test scroll commands
        await pilot.press("g")  # Top
        await pilot.press("g")
        await pilot.press("G")  # Bottom
        await pilot.press("j")  # Down
        await pilot.press("k")  # Up

@pytest.mark.asyncio
async def test_focus_indicators(sample_call):
    """Test that focus is visually indicated"""
    app = CallBrowserApp()
    app.calls = [sample_call]
    
    async with app.run_test() as pilot:
        # Check initial focus border
        call_table = app.query_one("#calls")
        assert call_table.styles.border_top[0] == "double"
        
        # Check focus change updates borders
        await pilot.press("tab")
        transcript_container = app.query_one("#transcript-container")
        assert transcript_container.styles.border_top[0] == "double"
        assert call_table.styles.border_top[0] == "solid"
        
        # Verify details pane never gets focus border
        details = app.query_one("#details")
        assert not details.can_focus

def test_parse_call_missing_fields():
    """Test parsing a call with missing optional fields"""
    minimal_call = {
        "id": "test-id",
        "createdAt": "2024-01-15T14:30:00.000Z",
    }

    call = parse_call(minimal_call)
    
    assert call.id == "test-id"
    assert call.Caller == ""  # Empty string for missing customer
    assert call.Transcript == ""  # Empty string for missing transcript
    assert call.Summary == ""  # Empty string for missing summary
    assert call.Cost == 0.0  # Zero for missing cost
    assert isinstance(call.Start, datetime)
    assert isinstance(call.End, datetime)
    assert call.Start == call.End  # End time defaults to start time

def test_parse_call_cost_formats():
    """Test parsing different cost formats"""
    # Test numeric cost
    call_numeric = parse_call({"id": "test", "createdAt": "2024-01-15T14:30:00.000Z", "cost": 1.23})
    assert call_numeric.Cost == 1.23

    # Test dictionary cost
    call_dict = parse_call({"id": "test", "createdAt": "2024-01-15T14:30:00.000Z", "cost": {"total": 2.34}})
    assert call_dict.Cost == 2.34

    # Test missing cost
    call_no_cost = parse_call({"id": "test", "createdAt": "2024-01-15T14:30:00.000Z"})
    assert call_no_cost.Cost == 0.0

@pytest.mark.asyncio
async def test_transcript_scrolling(long_transcript_call):
    """Test scrolling behavior in transcript widget"""
    app = CallBrowserApp()
    app.calls = [long_transcript_call]
    
    async with app.run_test() as pilot:
        # Focus the transcript container directly
        await pilot.press("tab")
        await pilot.pause()
        container = app.query_one("#transcript-container")
        assert app.focused == container
        
        # Get initial scroll position
        initial_scroll_y = container.scroll_y
        
        # Scroll down multiple times
        for _ in range(5):
            await pilot.press("j")
        assert container.scroll_y > initial_scroll_y
        
        # Scroll up
        current_scroll_y = container.scroll_y
        for _ in range(3):
            await pilot.press("k")
        assert container.scroll_y < current_scroll_y
        
        # Test gg (top)
        await pilot.press("g")
        await pilot.press("g")
        assert container.scroll_y == 0
        
        # Test G (bottom)
        await pilot.press("G")
        assert container.scroll_y > 0  # Should be scrolled down
        
        # Verify we can scroll up from bottom
        current_scroll_y = container.scroll_y
        await pilot.press("k")
        assert container.scroll_y < current_scroll_y

@pytest.mark.asyncio
async def test_help_screen_dismiss():
    """Test that help screen dismisses on both escape and q, but q doesn't quit the app"""
    app = CallBrowserApp()
    
    async with app.run_test() as pilot:
        # Open help screen
        await pilot.press("?")
        await pilot.pause()
        
        # Verify help screen is shown
        help_screen = app.query_one(HelpScreen)
        assert help_screen is not None
        
        # Press 'q' - should dismiss help screen but not quit app
        await pilot.press("q")
        await pilot.pause()
        
        # Verify help screen is dismissed
        help_screen = app.query(HelpScreen)
        assert len(help_screen) == 0
        
        # Verify app is still running (can open help screen again)
        await pilot.press("?")
        await pilot.pause()
        help_screen = app.query_one(HelpScreen)
        assert help_screen is not None
        
        # Press escape - should also dismiss
        await pilot.press("escape")
        await pilot.pause()
        help_screen = app.query(HelpScreen)
        assert len(help_screen) == 0

@pytest.mark.asyncio
async def test_enter_key_navigation(sample_call):
    """Test that Enter key behaves like Tab for widget focus navigation."""
    app = CallBrowserApp()
    app.calls = [sample_call]  # Use sample call for testing
    
    async with app.run_test() as pilot:
        # Test initial focus
        assert app.focused == app.call_table
        
        # Test enter navigation
        await pilot.press("enter")
        await pilot.pause()  # Add pause to allow focus change to complete
        transcript_container = app.query_one("#transcript-container")
        assert app.focused == transcript_container
        
        await pilot.press("enter")
        await pilot.pause()  # Add pause to allow focus change to complete
        assert app.focused == app.call_table
        
        # Verify it behaves the same as tab
        await pilot.press("tab")
        await pilot.pause()  # Add pause to allow focus change to complete
        assert app.focused == transcript_container
        
        await pilot.press("tab")
        await pilot.pause()  # Add pause to allow focus change to complete
        assert app.focused == app.call_table
