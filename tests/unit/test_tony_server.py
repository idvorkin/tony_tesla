import os
import requests
from unittest.mock import patch, Mock
from tony_server import extract_failure_reason, send_text_ifttt_endpoint, parse_tool_call, raise_if_not_authorized


def test_extract_failure_reason_assistant_request_error():
    input_msg = {
        "message": {
            "timestamp": 1737157773126,
            "type": "status-update",
            "status": "ended",
            "endedReason": "assistant-request-returned-invalid-assistant",
            "inboundPhoneCallDebuggingArtifacts": {
                "error": "Couldn't Get Assistant...",
                "assistantRequestError": 'Invalid Assistant. Errors: [\n  "assistant.model.All fallbackModels\'s elements must be unique"\n]',
                "assistantRequestResponse": {"assistant": {"name": "Tony"}},
            },
        }
    }

    result = extract_failure_reason(input_msg)
    assert (
        result
        == 'Invalid Assistant. Errors: [\n  "assistant.model.All fallbackModels\'s elements must be unique"\n]'
    )


def test_extract_failure_reason_general_error():
    input_msg = {
        "message": {
            "type": "status-update",
            "status": "ended",
            "endedReason": "some-reason",
            "inboundPhoneCallDebuggingArtifacts": {"error": "General error occurred"},
        }
    }

    result = extract_failure_reason(input_msg)
    assert result == "General error occurred"


def test_extract_failure_reason_ended_reason():
    input_msg = {
        "message": {
            "type": "status-update",
            "status": "ended",
            "endedReason": "some-specific-reason",
        }
    }

    result = extract_failure_reason(input_msg)
    assert result == "some-specific-reason"


def test_extract_failure_reason_not_status_update():
    input_msg = {"message": {"type": "something-else", "status": "ended"}}

    result = extract_failure_reason(input_msg)
    assert result is None


def test_extract_failure_reason_not_ended():
    input_msg = {"message": {"type": "status-update", "status": "in-progress"}}

    result = extract_failure_reason(input_msg)
    assert result is None


def test_extract_failure_reason_empty_input():
    input_msg = {}
    result = extract_failure_reason(input_msg)
    assert result is None


import pytest


@pytest.mark.asyncio
async def test_send_text_ifttt_unit():
    """Unit test for the IFTTT SMS webhook function"""
    # Test data
    text_message = "Hello, this is a test message"
    phone_number = "+12068904339"
    
    # Test parameters
    headers = {"x-vapi-secret": "test_secret"}
    params = {
        "message": {
            "toolCalls": [{
                "function": {
                    "name": "send_text_ifttt",
                    "arguments": {
                        "text": text_message,
                        "to_number": phone_number
                    }
                },
                "id": "test_id",
                "type": "function"
            }]
        }
    }
    
    # Create test environment variables
    test_env = {
        "IFTTT_WEBHOOK_KEY": "test_key",
        "IFTTT_WEBHOOK_SMS_EVENT": "test_event",
        "TONY_API_KEY": "test_secret"  # Match x-vapi-secret for authorization
    }
    
    # Mock the authorization function and requests.post
    with patch.dict(os.environ, test_env), patch("requests.post") as mock_post:
        # Configure mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Webhook successful"
        mock_post.return_value = mock_response
        
        # Call the function
        response = await send_text_ifttt_endpoint(params, headers)
        
        # Verify that the function returns the expected response
        assert "results" in response
        assert len(response["results"]) > 0
        assert "text message sent via ifttt" in response["results"][0]["result"].lower()
        
        # Verify that requests.post was called with the expected arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        # Verify URL
        assert args[0] == f"https://maker.ifttt.com/trigger/test_event/with/key/test_key"
        
        # Verify payload
        assert kwargs["json"]["value1"] == text_message
        assert kwargs["json"]["value2"] == phone_number
        assert "From Tony Tesla at " in kwargs["json"]["value3"]
    
    # Test with missing environment variables
    with patch.dict(os.environ, {"IFTTT_WEBHOOK_KEY": "", "TONY_API_KEY": "test_secret"}):
        response = await send_text_ifttt_endpoint(params, headers)
        assert "error" in response["results"][0]["result"].lower()
        assert "missing ifttt configuration" in response["results"][0]["result"].lower() or "failed to send webhook request" in response["results"][0]["result"].lower()
    
    # Test with request exception
    with patch.dict(os.environ, test_env), patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        response = await send_text_ifttt_endpoint(params, headers)
        assert "error" in response["results"][0]["result"].lower()
        assert "failed to send webhook request" in response["results"][0]["result"].lower()
    
    # Test with HTTP error
    with patch.dict(os.environ, test_env), patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_post.return_value = mock_response
        response = await send_text_ifttt_endpoint(params, headers)
        assert "error" in response["results"][0]["result"].lower()
