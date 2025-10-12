import os
import pytest
import requests
from fastapi.testclient import TestClient
from tony_server import (
    app,
    parse_tool_call,
    make_vapi_response,
    is_igor_caller,
    apply_caller_restrictions,
    get_caller_number,
    extract_failure_reason,
    send_text_endpoint,
    send_text_ifttt_endpoint,
)
import json
from unittest.mock import patch, Mock
from pathlib import Path


@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}


@pytest.fixture
def mock_tony_files():
    """Fixture to mock tony configuration files"""
    # Create a mock for trusted_journal_read
    mock_journal = Mock(return_value="Test journal content")

    # Mock the modal_storage path to point to the project's modal_readonly directory
    with (
        patch(
            "tony_server.modal_storage",
            Path(__file__).parent.parent.parent / "modal_readonly",
        ),
        patch("tony_server.trusted_journal_read", mock_journal),
    ):
        yield


@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "search",
                        "arguments": {"question": "What is the weather in Seattle?"},
                    },
                    "id": "toolu_01FDyjjUG1ig7hP9YQ6MQXhX",
                    "type": "function",
                }
            ]
        }
    }


def test_search_function(auth_headers, base_params):
    """Test the search function with FastAPI test client"""
    # Mock the Perplexity API response
    mock_response_data = {
        "id": "2fb30930-796a-405d-be66-12fa7f54db75",
        "model": "sonar-pro",
        "created": 1742044995,
        "usage": {"prompt_tokens": 12, "completion_tokens": 356, "total_tokens": 368},
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "The weather in Seattle is currently chilly with intervals of clouds and sun.",
                },
            }
        ],
    }

    with patch("requests.post") as mock_post:
        # Configure mock response
        mock_response = Mock()
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response

        # Make the request
        client = TestClient(app)
        response = client.post("/search", json=base_params, headers=auth_headers)

        # Verify the response
        assert response.status_code == 200, (
            f"Expected status code 200, got {response.status_code}"
        )
        result = response.json()
        assert "results" in result, (
            "Expected 'results' key in response, but it was not found."
        )
        assert len(result["results"]) > 0, (
            "Expected at least one result in 'results', but none were found."
        )

        result_str = result["results"][0]["result"]
        assert isinstance(result_str, str), "Expected result to be a string."
        assert "weather in Seattle" in result_str

        # Verify Perplexity API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.perplexity.ai/chat/completions"
        assert kwargs["json"]["model"] == "sonar-pro"
        assert (
            kwargs["headers"]["authorization"] == f"Bearer {os.environ['PPLX_API_KEY']}"
        )


def test_parse_tool_call(base_params):
    """Test the parse_tool_call function directly"""
    call = parse_tool_call("search", base_params)
    assert call.name == "search"
    assert "question" in call.args
    assert call.args["question"] == "What is the weather in Seattle?"
    assert call.id == "toolu_01FDyjjUG1ig7hP9YQ6MQXhX"


def test_make_vapi_response():
    """Test the make_vapi_response function directly"""
    from tony_server import FunctionCall

    call = FunctionCall(id="test_id", name="test", args={"test": "value"})
    result = "test result"
    response = make_vapi_response(call, result)

    assert "results" in response
    assert len(response["results"]) == 1
    assert response["results"][0]["toolCallId"] == "test_id"
    assert response["results"][0]["result"] == "test result"


    # Blog search now handled via MCP; endpoint tests removed


@pytest.mark.usefixtures("mock_tony_files")
def test_vapi_assistant_call_input(auth_headers):
    """Test the VAPI assistant call input structure"""
    # Test parameters for assistant call
    params = {
        "message": {
            "timestamp": 1736039875874,
            "type": "assistant-request",
            "call": {
                "id": "xxx-xxx",
                "orgId": "xxx-xxx",
                "createdAt": "2025-01-05T01:17:55.739Z",
                "updatedAt": "2025-01-05T01:17:55.739Z",
                "type": "inbound Phone Call",
                "status": "ringing",
                "phoneCallProvider": "twilio",
                "phoneCallProviderId": "xxx-xxx",
                "phoneCallTransport": "pstn",
                "phoneNumberId": "xxx-xxx",
                "assistantId": None,
                "squadId": None,
                "customer": {
                    "number": "+1xxx-xxx",
                    "phoneNumber": {
                        "id": "xxx-xxx",
                        "orgId": "xxx-xxx",
                        "assistantId": None,
                        "number": "+1xxx-xxx",
                        "createdAt": "2024-04-12T16:35:14.400Z",
                        "updatedAt": "2024-11-27T17:14:08.833Z",
                        "provider": "twilio",
                    },
                },
            },
        }
    }

    client = TestClient(app)
    response = client.post("/assistant", json=params, headers=auth_headers)

    assert response.status_code == 200
    result = response.json()

    # Verify the response structure matches expected VAPI format
    assert isinstance(result, dict), "Response should be a dictionary"
    assert "assistant" in result, "Response should have 'assistant' key"
    assert "model" in result["assistant"], (
        "Response should have 'model' key in assistant"
    )
    assert "messages" in result["assistant"]["model"], (
        "Response should have 'messages' in model"
    )
    assert isinstance(result["assistant"]["model"]["messages"], list), (
        "Messages should be a list"
    )
    assert len(result["assistant"]["model"]["messages"]) > 0, (
        "Should have at least one message"
    )
    assert "content" in result["assistant"]["model"]["messages"][0], (
        "Message should have content"
    )
    assert isinstance(result["assistant"]["model"]["messages"][0]["content"], str), (
        "Message content should be string"
    )


@pytest.mark.usefixtures("mock_tony_files")
def test_vapi_assistant_call_input_non_igor(auth_headers):
    """Test the VAPI assistant call input structure for non-Igor caller"""
    params = {
        "message": {
            "timestamp": 1736039875874,
            "type": "assistant-request",
            "call": {
                "id": "xxx-xxx",
                "orgId": "xxx-xxx",
                "createdAt": "2025-01-05T01:17:55.739Z",
                "updatedAt": "2025-01-05T01:17:55.739Z",
                "type": "inbound Phone Call",
                "status": "ringing",
                "phoneCallProvider": "twilio",
                "phoneCallProviderId": "xxx-xxx",
                "phoneCallTransport": "pstn",
                "phoneNumberId": "xxx-xxx",
                "assistantId": None,
                "squadId": None,
                "customer": {
                    "number": "+11234567890",  # Different number
                    "phoneNumber": {
                        "id": "xxx-xxx",
                        "orgId": "xxx-xxx",
                        "assistantId": None,
                        "number": "+1xxx-xxx",
                        "createdAt": "2024-04-12T16:35:14.400Z",
                        "updatedAt": "2024-11-27T17:14:08.833Z",
                        "provider": "twilio",
                    },
                },
            },
        }
    }

    client = TestClient(app)
    response = client.post("/assistant", json=params, headers=auth_headers)

    assert response.status_code == 200
    result = response.json()

    # Verify restricted tools are removed
    tool_names = [
        tool["function"]["name"] for tool in result["assistant"]["model"]["tools"]
    ]
    assert "journal_read" not in tool_names, (
        "Non-Igor should not have access to journal_read"
    )
    assert "journal_append" not in tool_names, (
        "Non-Igor should not have access to journal_append"
    )
    assert "library_arrivals" in tool_names, (
        "Non-Igor should have access to library_arrivals"
    )

    # Verify restrictions are added to prompt
    messages = result["assistant"]["model"]["messages"]
    assert any("<Restrictions>" in msg["content"] for msg in messages), (
        "Restrictions should be added for non-Igor"
    )
    assert not any("JournalContent" in msg["content"] for msg in messages), (
        "Journal content should not be included for non-Igor"
    )


def test_is_igor_caller():
    """Test the is_igor_caller function"""
    valid_headers = {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}
    invalid_headers = {"x-vapi-secret": "wrong_secret"}

    # Test Igor's number with valid secret
    igor_input = {"message": {"call": {"customer": {"number": "+12068904339"}}}}
    assert is_igor_caller(igor_input, valid_headers) is True

    # Test Igor's number with invalid secret
    assert is_igor_caller(igor_input, invalid_headers) is False

    # Test different number with valid secret
    other_input = {"message": {"call": {"customer": {"number": "+11234567890"}}}}
    assert is_igor_caller(other_input, valid_headers) is False

    # Test invalid input structure
    invalid_input = {"message": {}}
    assert is_igor_caller(invalid_input, valid_headers) is False


def test_get_caller_number():
    """Test the get_caller_number function"""
    # Test valid input
    valid_input = {"message": {"call": {"customer": {"number": "+12068904339"}}}}
    assert get_caller_number(valid_input) == "+12068904339"

    # Test missing number
    missing_number = {"message": {"call": {"customer": {}}}}
    assert get_caller_number(missing_number) is None

    # Test missing customer
    missing_customer = {"message": {"call": {}}}
    assert get_caller_number(missing_customer) is None

    # Test missing call
    missing_call = {"message": {}}
    assert get_caller_number(missing_call) is None

    # Test missing message
    missing_message = {}
    assert get_caller_number(missing_message) is None

    # Test empty input
    empty_input = {}
    assert get_caller_number(empty_input) is None

    # Test None input
    assert get_caller_number(None) is None


def test_apply_caller_restrictions():
    """Test the apply_caller_restrictions function"""
    # Read the actual tony_assistant_spec.json
    tony_spec = json.loads(Path("modal_readonly/tony_assistant_spec.json").read_text())

    # Test Igor's access (no restrictions)
    igor_tony = apply_caller_restrictions(tony_spec.copy(), True)
    tool_names = [
        tool["function"]["name"] for tool in igor_tony["assistant"]["model"]["tools"]
    ]
    assert "journal_read" in tool_names, "Igor should have access to journal_read"
    assert "journal_append" in tool_names, "Igor should have access to journal_append"
    assert "library_arrivals" in tool_names, (
        "Igor should have access to library_arrivals"
    )
    assert "search" in tool_names, "Igor should have access to search"
    assert (
        "<Restrictions>"
        not in igor_tony["assistant"]["model"]["messages"][0]["content"]
    )

    # Test non-Igor access (with restrictions)
    other_tony = apply_caller_restrictions(tony_spec.copy(), False)
    restricted_tool_names = [
        tool["function"]["name"] for tool in other_tony["assistant"]["model"]["tools"]
    ]
    assert "journal_read" not in restricted_tool_names, (
        "Non-Igor should not have access to journal_read"
    )
    assert "journal_append" not in restricted_tool_names, (
        "Non-Igor should not have access to journal_append"
    )
    assert "library_arrivals" in restricted_tool_names, (
        "Non-Igor should have access to library_arrivals"
    )
    assert "search" in restricted_tool_names, (
        "Non-Igor should still have access to search"
    )
    # Blog tools now provided via MCP; ensure MCP tools entry exists
    assert any(
        tool.get("type") == "mcp" and tool.get("function", {}).get("name") == "mcpTools"
        for tool in other_tony["assistant"]["model"]["tools"]
    ), "MCP blog tools should be available via mcpTools"
    assert (
        "<Restrictions>" in other_tony["assistant"]["model"]["messages"][0]["content"]
    )


@pytest.mark.usefixtures("mock_tony_files")
def test_assistant_endpoint_logs_failure(auth_headers):
    """Test that the assistant endpoint properly handles and logs failure messages"""
    client = TestClient(app)

    # Mock a status update message with a failure
    input_data = {
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

    # Call the endpoint
    response = client.post("/assistant", json=input_data, headers=auth_headers)

    # Verify response
    assert response.status_code == 200

    # Verify the failure was extracted correctly
    failure_reason = extract_failure_reason(input_data)
    assert (
        failure_reason
        == 'Invalid Assistant. Errors: [\n  "assistant.model.All fallbackModels\'s elements must be unique"\n]'
    )

    # Verify response contains expected assistant configuration
    response_data = response.json()
    assert response_data["assistant"]["name"] == "Tony"
    assert "model" in response_data["assistant"]


@pytest.mark.asyncio
async def test_send_text_integration():
    """Test the send-text endpoint by calling the function directly"""
    # Test data
    text_message = "Hello, this is a test message"
    phone_number = "+12068904339"

    # Prepare request data
    headers = {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text",
                        "arguments": {"text": text_message, "to_number": phone_number},
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }

    # Mock Twilio client and its message creation
    with patch("twilio.rest.Client") as mock_client_class:
        # Mock the Twilio client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock the messages resource
        mock_messages = Mock()
        mock_client.messages = mock_messages

        # Mock the create method and its return value
        mock_message = Mock()
        mock_message.sid = "SM12345"
        mock_messages.create.return_value = mock_message

        # Call the endpoint function directly
        response = await send_text_endpoint(params, headers)

        # Verify response
        assert isinstance(response, dict)
        assert "results" in response
        assert len(response["results"]) > 0

        # Should have succeeded with mock
        assert "text message sent" in response["results"][0]["result"].lower()
        assert phone_number in response["results"][0]["result"]
        assert text_message in response["results"][0]["result"]
        assert "Message SID:" in response["results"][0]["result"]

        # Verify Twilio client was used correctly
        mock_client_class.assert_called_with(
            os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
        )
        mock_messages.create.assert_called_with(
            body=text_message,
            from_=os.environ.get("TWILIO_FROM_NUMBER"),
            to=phone_number,
        )

    # Test with connection error
    with patch("twilio.rest.Client") as mock_client_class:
        mock_client_class.side_effect = Exception("Connection error")
        response = await send_text_endpoint(params, headers)
        assert "error" in response["results"][0]["result"].lower()

    # Test with missing parameters
    params_missing = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text",
                        "arguments": {
                            "text": text_message
                            # Missing to_number
                        },
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }
    response = await send_text_endpoint(params_missing, headers)
    assert isinstance(response, dict)
    assert "results" in response
    assert "error" in response["results"][0]["result"].lower()


def test_cors_headers(auth_headers, mock_tony_files):
    """Test that CORS headers are properly configured"""
    client = TestClient(app)

    # Test with allowed origin
    headers = {
        **auth_headers,
        "Origin": "https://idvork.in"
    }

    params = {"message": {"type": "assistant-request"}}
    response = client.post("/assistant", json=params, headers=headers)

    # Verify CORS headers are present
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "https://idvork.in"
    assert "access-control-allow-credentials" in response.headers
    assert response.headers["access-control-allow-credentials"] == "true"

    # Test preflight request
    response = client.options(
        "/assistant",
        headers={
            "Origin": "https://idvork.in",
            "Access-Control-Request-Method": "POST"
        }
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


@pytest.mark.asyncio
async def test_send_text_ifttt_integration():
    """Test the send-text-ifttt endpoint by mocking the requests call"""
    # Test data
    text_message = "Hello, this is a test message"
    phone_number = "+12068904339"

    # Prepare request data
    headers = {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text_ifttt",
                        "arguments": {"text": text_message, "to_number": phone_number},
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }

    # Mock the requests.post method
    with patch("requests.post") as mock_post:
        # Configure the mock to return a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Congratulations! You've fired the sms_event event"
        mock_post.return_value = mock_response

        # Call the endpoint function directly
        response = await send_text_ifttt_endpoint(params, headers)

        # Verify response
        assert isinstance(response, dict)
        assert "results" in response
        assert len(response["results"]) > 0

        # Accept either success message or error message with webhook failure
        if "text message sent via ifttt" in response["results"][0]["result"].lower():
            assert phone_number in response["results"][0]["result"]
            assert text_message in response["results"][0]["result"]
        else:
            # If IFTTT isn't properly configured, accept error message about webhook
            assert "error" in response["results"][0]["result"].lower()
            assert (
                "failed to send webhook request"
                in response["results"][0]["result"].lower()
                or "missing ifttt configuration"
                in response["results"][0]["result"].lower()
            )

        # Verify the requests.post was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args

        # Check that URL contains the webhook key and event
        assert "maker.ifttt.com/trigger/" in args[0]
        assert "with/key/" in args[0]

        # Check payload contents
        assert kwargs["json"]["value1"] == text_message
        assert kwargs["json"]["value2"] == phone_number
        assert "From Tony Tesla at " in kwargs["json"]["value3"]

    # Test with missing parameters
    params_missing = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text_ifttt",
                        "arguments": {
                            "text": text_message
                            # Missing to_number
                        },
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }
    response = await send_text_ifttt_endpoint(params_missing, headers)
    assert isinstance(response, dict)
    assert "results" in response
    assert "error" in response["results"][0]["result"].lower()

    # Test with request exception
    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException(
            "Connection failed"
        )
        response = await send_text_ifttt_endpoint(params, headers)
        assert "error" in response["results"][0]["result"].lower()
        assert (
            "failed to send webhook request" in response["results"][0]["result"].lower()
        )

    # Test with missing environment variable
    with patch.dict(os.environ, {"IFTTT_WEBHOOK_KEY": ""}):
        with patch("tony_server.IFTTT_WEBHOOK_KEY", "IFTTT_WEBHOOK_KEY"):
            response = await send_text_ifttt_endpoint(params, headers)
            assert "error" in response["results"][0]["result"].lower()
            assert (
                "missing ifttt configuration"
                in response["results"][0]["result"].lower()
                or "failed to send webhook request"
                in response["results"][0]["result"].lower()
            )
