import os
import pytest
from fastapi.testclient import TestClient
from tony_server import app, parse_tool_call, make_vapi_response, trusted_journal_read, is_igor_caller, apply_caller_restrictions
from blog_server import app as blog_app
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
    mock_system_prompt = "Test system prompt"

    # Create a mock for trusted_journal_read
    mock_journal = Mock(return_value="Test journal content")

    # Only mock the system prompt and journal read, and adjust the modal_storage path
    with patch('tony_server.modal_storage', 'modal_readonly'), \
         patch('tony_server.trusted_journal_read', mock_journal):
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
                        "arguments": {"question": "What is the weather in Seattle?"}
                    },
                    "id": "toolu_01FDyjjUG1ig7hP9YQ6MQXhX",
                    "type": "function"
                }
            ]
        }
    }

def test_search_function(auth_headers, base_params):
    """Test the search function with FastAPI test client"""
    client = TestClient(app)
    response = client.post("/search", json=base_params, headers=auth_headers)
    
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    result = response.json()
    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    
    result_str = result["results"][0]["result"]
    assert isinstance(result_str, str), "Expected result to be a string."

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

def test_blog_search(auth_headers):
    """Test the blog search endpoint"""
    client = TestClient(blog_app)
    
    # Test parameters for blog search
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "blog_search",
                        "arguments": {"query": "meditation"}
                    },
                    "id": "test_id",
                    "type": "function"
                }
            ]
        }
    }
    
    response = client.post("/blog_search", json=params, headers=auth_headers)
    
    # Check response status and structure
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    result = response.json()
    assert "results" in result, "Expected 'results' key in response"
    assert len(result["results"]) > 0, "Expected at least one result"
    
    # Parse the results JSON string
    search_results = json.loads(result["results"][0]["result"])
    assert isinstance(search_results, list), "Expected results to be a list"
    
    # Check the structure of each search result
    if len(search_results) > 0:
        first_result = search_results[0]
        assert "title" in first_result, "Expected 'title' in search result"
        assert "url" in first_result, "Expected 'url' in search result"
        assert "content" in first_result, "Expected 'content' in search result"
        assert first_result["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"

@pytest.mark.usefixtures("mock_tony_files")
def test_vapi_assistant_call_input(auth_headers):
    """Test the VAPI assistant call input structure"""
    # Test parameters for assistant call
    params = {
        "input": {
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
                            "provider": "twilio"
                        }
                    }
                }
            }
        }
    }
    
    client = TestClient(app)
    response = client.post("/assistant", json=params, headers=auth_headers)
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify the response structure matches expected VAPI format
    assert isinstance(result, dict), "Response should be a dictionary"
    assert "assistant" in result, "Response should have 'assistant' key"
    assert "model" in result["assistant"], "Response should have 'model' key in assistant"
    assert "messages" in result["assistant"]["model"], "Response should have 'messages' in model"
    assert isinstance(result["assistant"]["model"]["messages"], list), "Messages should be a list"
    assert len(result["assistant"]["model"]["messages"]) > 0, "Should have at least one message"
    assert "content" in result["assistant"]["model"]["messages"][0], "Message should have content"
    assert isinstance(result["assistant"]["model"]["messages"][0]["content"], str), "Message content should be string"

@pytest.mark.usefixtures("mock_tony_files")
def test_vapi_assistant_call_input_non_igor(auth_headers):
    """Test the VAPI assistant call input structure for non-Igor caller"""
    params = {
        "input": {
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
                            "provider": "twilio"
                        }
                    }
                }
            }
        }
    }
    
    client = TestClient(app)
    response = client.post("/assistant", json=params, headers=auth_headers)
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify restricted tools are removed
    tool_names = [tool["function"]["name"] for tool in result["assistant"]["model"]["tools"]]
    assert "journal_read" not in tool_names, "Non-Igor should not have access to journal_read"
    assert "journal_append" not in tool_names, "Non-Igor should not have access to journal_append"
    assert "library_arrivals" not in tool_names, "Non-Igor should not have access to library_arrivals"
    
    # Verify restrictions are added to prompt
    messages = result["assistant"]["model"]["messages"]
    assert any("<Restrictions>" in msg["content"] for msg in messages), "Restrictions should be added for non-Igor"
    assert not any("JournalContent" in msg["content"] for msg in messages), "Journal content should not be included for non-Igor"

def test_is_igor_caller():
    """Test the is_igor_caller function"""
    # Test Igor's number
    igor_input = {
        "input": {
            "message": {
                "call": {
                    "customer": {
                        "number": "+12068904339"
                    }
                }
            }
        }
    }
    assert is_igor_caller(igor_input) is True

    # Test different number
    other_input = {
        "input": {
            "message": {
                "call": {
                    "customer": {
                        "number": "+11234567890"
                    }
                }
            }
        }
    }
    assert is_igor_caller(other_input) is False

    # Test invalid input structure
    invalid_input = {"input": {"message": {}}}
    assert is_igor_caller(invalid_input) is False

def test_apply_caller_restrictions():
    """Test the apply_caller_restrictions function"""
    # Read the actual tony_assistant_spec.json
    tony_spec = json.loads(Path("modal_readonly/tony_assistant_spec.json").read_text())

    # Test Igor's access (no restrictions)
    igor_tony = apply_caller_restrictions(tony_spec.copy(), True)
    tool_names = [tool["function"]["name"] for tool in igor_tony["assistant"]["model"]["tools"]]
    assert "journal_read" in tool_names, "Igor should have access to journal_read"
    assert "journal_append" in tool_names, "Igor should have access to journal_append"
    assert "library_arrivals" in tool_names, "Igor should have access to library_arrivals"
    assert "search" in tool_names, "Igor should have access to search"
    assert "<Restrictions>" not in igor_tony["assistant"]["model"]["messages"][0]["content"]

    # Test non-Igor access (with restrictions)
    other_tony = apply_caller_restrictions(tony_spec.copy(), False)
    restricted_tool_names = [tool["function"]["name"] for tool in other_tony["assistant"]["model"]["tools"]]
    assert "journal_read" not in restricted_tool_names, "Non-Igor should not have access to journal_read"
    assert "journal_append" not in restricted_tool_names, "Non-Igor should not have access to journal_append"
    assert "library_arrivals" not in restricted_tool_names, "Non-Igor should not have access to library_arrivals"
    assert "search" in restricted_tool_names, "Non-Igor should still have access to search"
    assert "blog_info" in restricted_tool_names, "Non-Igor should still have access to blog_info"
    assert "blog_search" in restricted_tool_names, "Non-Igor should still have access to blog_search"
    assert "<Restrictions>" in other_tony["assistant"]["model"]["messages"][0]["content"]
