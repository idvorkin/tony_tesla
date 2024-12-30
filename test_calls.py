import pytest
from datetime import datetime
from dateutil import tz
from calls import parse_call, format_phone_number, Call

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
