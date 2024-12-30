import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from calls import Call, CallBrowserApp, EditScreen, TranscriptScreen, HelpScreen
from textual.pilot import Pilot

@pytest.fixture
def sample_call():
    now = datetime.now()
    return Call(
        id="test123",
        Caller="+1234567890",
        Transcript="Hello, this is a test call",
        Summary="Test call summary",
        Start=now,
        End=now + timedelta(minutes=5),
        Cost=1.23,
        CostBreakdown={"transcription": 0.5, "analysis": 0.73}
    )

@pytest.fixture
def sample_raw_call():
    now = datetime.now()
    return {
        "id": "test123",
        "customer": {"number": "+1234567890"},
        "artifact": {"transcript": "Hello, this is a test call"},
        "analysis": {"summary": "Test call summary"},
        "createdAt": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "endedAt": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "cost": 1.23,
        "costBreakdown": {"transcription": 0.5, "analysis": 0.73}
    }

def test_call_model(sample_call):
    """Test Call model basic functionality"""
    assert sample_call.id == "test123"
    assert sample_call.Caller == "+1234567890"
    assert sample_call.Cost == 1.23
    assert isinstance(sample_call.length_in_seconds(), float)
    # Use pytest.approx for float comparison
    assert sample_call.length_in_seconds() == pytest.approx(300, rel=1e-6)  # 5 minutes = 300 seconds

@pytest.mark.asyncio
async def test_edit_screen():
    """Test EditScreen functionality"""
    raw_call = {
        "id": "test123",
        "analysis": {"summary": "Test summary"},
        "artifact": {"transcript": "Test transcript"}
    }
    
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            with patch('os.system') as mock_system:
                # Test fx view
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.press("f")
                mock_system.assert_called_once()
                assert ".json" in mock_system.call_args[0][0]
                
                # Test summary view
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.press("s")
                assert mock_system.call_count == 2
                assert ".txt" in mock_system.call_args[0][0]
                
                # Test conversation view
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.press("c")
                assert mock_system.call_count == 3
                assert ".txt" in mock_system.call_args[0][0]

@pytest.mark.asyncio
async def test_edit_screen_buttons():
    """Test EditScreen button interactions"""
    raw_call = {
        "id": "test123",
        "analysis": {"summary": "Test summary"},
        "artifact": {"transcript": "Test transcript"}
    }
    
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            with patch('os.system') as mock_system:
                # Test fx button
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.click("#fx")
                mock_system.assert_called_once()
                assert ".json" in mock_system.call_args[0][0]
                
                # Test summary button
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.click("#summary")
                assert mock_system.call_count == 2
                assert ".txt" in mock_system.call_args[0][0]
                
                # Test conversation button
                screen = EditScreen(raw_call)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.click("#conversation")
                assert mock_system.call_count == 3
                assert ".txt" in mock_system.call_args[0][0]

@pytest.mark.asyncio
async def test_edit_screen_file_content():
    """Test EditScreen creates correct file content"""
    raw_call = {
        "id": "test123",
        "analysis": {"summary": "Test summary content"},
        "artifact": {"transcript": "Test transcript content"},
        "cost": 1.23
    }
    
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                # Setup mock file
                mock_file = Mock()
                mock_file.__enter__ = Mock(return_value=mock_file)
                mock_file.__exit__ = Mock(return_value=None)
                mock_file.name = '/tmp/test.json'
                mock_temp.return_value = mock_file
                
                with patch('os.system'):
                    # Test fx view file content
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("f")
                    write_calls = mock_file.write.call_args_list
                    written_content = write_calls[0][0][0]
                    assert '"id": "test123"' in written_content
                    assert '"cost": 1.23' in written_content
                    
                    # Test summary file content
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("s")
                    write_calls = mock_file.write.call_args_list
                    written_content = write_calls[1][0][0]
                    assert "Test summary content" in written_content
                    
                    # Test transcript file content
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("c")
                    write_calls = mock_file.write.call_args_list
                    written_content = write_calls[2][0][0]
                    assert "Test transcript content" in written_content

@pytest.mark.asyncio
async def test_edit_screen_error_handling():
    """Test EditScreen handles errors gracefully"""
    raw_call = {
        "id": "test123",
        # Missing analysis and artifact to test error cases
    }
    
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                # Setup mock file
                mock_file = Mock()
                mock_file.__enter__ = Mock(return_value=mock_file)
                mock_file.__exit__ = Mock(return_value=None)
                mock_temp.return_value = mock_file
                
                with patch('os.system'):
                    # Test summary with missing data
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("s")
                    write_calls = mock_file.write.call_args_list
                    written_content = write_calls[0][0][0]
                    assert "No summary available" in written_content
                    
                    # Test transcript with missing data
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("c")
                    write_calls = mock_file.write.call_args_list
                    written_content = write_calls[1][0][0]
                    assert "No transcript available" in written_content

@pytest.mark.asyncio
async def test_help_screen():
    """Test HelpScreen functionality"""
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            # Create and mount HelpScreen
            screen = HelpScreen()
            app.push_screen(screen)
            await pilot.pause()
            
            # Test screen content
            assert screen.query_one("#help-title")
            help_content = screen.query_one("#help-content")
            assert help_content
            
            # Verify all commands are listed
            commands = screen.query(".command")
            assert len(commands) > 0
            
            # Test escape dismisses screen
            await pilot.press("escape")
            with pytest.raises(Exception):
                screen.query_one("#help-title")

@pytest.mark.asyncio
async def test_transcript_screen():
    """Test TranscriptScreen functionality"""
    test_transcript = "This is a test transcript"
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            # Create and mount TranscriptScreen
            screen = TranscriptScreen(test_transcript)
            app.push_screen(screen)
            await pilot.pause()
            
            # Test screen content
            content = screen.query_one("#transcript-content")
            assert content
            assert test_transcript in content.renderable
            
            # Test escape dismisses screen
            await pilot.press("escape")
            with pytest.raises(Exception):
                screen.query_one("#transcript-content")

@pytest.mark.asyncio
async def test_call_browser_app(sample_call):
    """Test main app functionality"""
    with patch('calls.vapi_calls', return_value=[sample_call]):
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Test initial state
            table = app.query_one("#calls")
            assert table
            assert table.row_count == 1

            details = app.query_one("#details")
            assert details
            transcript = app.query_one("#transcript")
            assert transcript

            # Test row selection
            await pilot.press("enter")
            app._update_views_for_current_row()  # Explicitly update views
            assert sample_call.Summary in details.renderable
            assert sample_call.Transcript in transcript.renderable
            
            # Test help screen
            await pilot.press("?")
            help_screen = app.screen
            assert isinstance(help_screen, HelpScreen)
            await pilot.press("escape")
            
            # Test edit screen
            with patch('httpx.get') as mock_get:
                mock_get.return_value.json.return_value = sample_raw_call
                await pilot.press("e")
                edit_screen = app.screen
                assert isinstance(edit_screen, EditScreen)
                await pilot.press("escape")

def test_parse_call(sample_raw_call):
    """Test call parsing from API response"""
    from calls import parse_call
    
    call = parse_call(sample_raw_call)
    assert isinstance(call, Call)
    assert call.id == "test123"
    assert call.Caller == "+1234567890"
    assert call.Transcript == "Hello, this is a test call"
    assert call.Summary == "Test call summary"
    assert call.Cost == 1.23
    assert call.CostBreakdown == {"transcription": 0.5, "analysis": 0.73}

@pytest.mark.asyncio
async def test_edit_screen_editor_selection():
    """Test EditScreen uses correct editor"""
    raw_call = {
        "id": "test123",
        "analysis": {"summary": "Test summary"},
        "artifact": {"transcript": "Test transcript"}
    }
    
    with patch('httpx.get') as mock_get:
        mock_get.return_value.json.return_value = []
        app = CallBrowserApp()
        async with app.run_test() as pilot:
            with patch('os.system') as mock_system:
                # Test with EDITOR environment variable set
                with patch.dict('os.environ', {'EDITOR': 'code'}):
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("s")
                    assert 'code' in mock_system.call_args[0][0]
                
                # Test with no EDITOR set (should use bat)
                with patch.dict('os.environ', clear=True):
                    screen = EditScreen(raw_call)
                    app.push_screen(screen)
                    await pilot.pause()
                    await pilot.press("s")
                    assert 'bat' in mock_system.call_args[0][0]
