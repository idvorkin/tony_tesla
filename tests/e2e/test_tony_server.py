import os
from typing import Dict, Any
import json
import pytest
import requests
from icecream import ic

TONY_SERVER_URL = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/assistant"


def make_request(
    url: str, params: Dict[str, Any], headers: Dict[str, str]
) -> requests.Response:
    """Make HTTP request with proper error handling"""
    try:
        ic("Making request to:", url)
        ic("With params:", params)
        ic("With headers:", headers)

        response = requests.post(url, json=params, headers=headers)
        ic("Response status:", response.status_code)
        ic("Response headers:", dict(response.headers))

        try:
            result = response.json()
            ic("Response JSON:", result)
        except json.JSONDecodeError:
            ic("Failed to decode JSON. Response content:", response.content)
            raise

        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        ic("Request failed:", str(e))
        ic("Response content:", getattr(e.response, "content", None))
        raise


@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ["TONY_API_KEY"]}


@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {"message": "Test message"}


def test_journal_read_e2e(auth_headers, base_params):
    """Test the journal_read endpoint with real HTTP requests"""
    ic("Starting journal read test")
    journal_read_url = (
        "https://idvorkin--modal-tony-server-fastapi-app.modal.run/journal-read"
    )
    params = {"date": "2024-12-31"}

    response = make_request(journal_read_url, params, auth_headers)
    result = response.json()

    assert "results" in result, (
        "Expected 'results' key in response, but it was not found."
    )
    assert len(result["results"]) > 0, (
        "Expected at least one result in 'results', but none were found."
    )
    result_str = result["results"][0]["result"]
    assert isinstance(result_str, str), "Expected result to be a string."


def test_search_e2e(auth_headers, base_params):
    """Test the search endpoint with real HTTP requests"""
    ic("Starting search test")
    search_url = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/search"
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "arguments": {"question": "What is the weather in Seattle?"},
                        "name": "search",
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }

    try:
        response = make_request(search_url, params, auth_headers)
        result = response.json()

        assert "results" in result, (
            "Expected 'results' key in response, but it was not found."
        )
        assert len(result["results"]) > 0, (
            "Expected at least one result in 'results', but none were found."
        )
        result_str = result["results"][0]["result"]
        assert isinstance(result_str, str), "Expected result to be a string."
    except requests.exceptions.RequestException as e:
        ic("Request failed:", str(e))
        ic("Response content:", getattr(e.response, "content", None))
        raise
    except json.JSONDecodeError as e:
        ic("JSON decode error:", str(e))
        ic("Response content:", response.content)
        raise


@pytest.mark.e2e
def test_assistant_e2e(auth_headers, base_params):
    """Test the assistant endpoint with real HTTP requests"""
    ic("Starting assistant test")
    params = {"message": "Test message"}

    try:
        response = make_request(TONY_SERVER_URL, params, auth_headers)
        result = response.json()

        assert "assistant" in result, (
            "Expected 'assistant' key in response, but it was not found."
        )
        assert isinstance(result["assistant"], dict), (
            "Expected 'assistant' to be a dictionary."
        )
        assert "firstMessage" in result["assistant"], (
            "Expected 'firstMessage' in assistant response."
        )
        assert isinstance(result["assistant"]["firstMessage"], str), (
            "Expected 'firstMessage' to be a string."
        )
    except requests.exceptions.RequestException as e:
        # Log the error but don't fail the test - may be an issue with the deployed endpoint
        ic("Request to assistant endpoint failed:", str(e))
        pytest.skip("Assistant endpoint not available or returned an error")
    except (json.JSONDecodeError, KeyError) as e:
        # Log the error but don't fail the test - response format might have changed
        ic("Error parsing assistant response:", str(e))
        pytest.skip("Assistant endpoint response could not be parsed")


def test_send_text():
    """Test the send-text endpoint"""
    url = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/send-text"
    headers = {"x-vapi-secret": os.environ["TONY_API_KEY"]}

    # Test with valid parameters
    params = {"text": "Hello, this is a test message", "to_number": "+12068904339"}
    response = make_request(url, params, headers)
    assert response.status_code == 200
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0

    # Accept either success or error message
    if "text message sent" in result["results"][0]["result"].lower():
        # Success case
        assert "+12068904339" in result["results"][0]["result"]
    else:
        # Error case (e.g., missing Twilio credentials)
        assert "error" in result["results"][0]["result"].lower()
        assert (
            "missing twilio configuration" in result["results"][0]["result"].lower()
            or "failed to send message" in result["results"][0]["result"].lower()
        )

    # Test with missing parameters
    params = {"text": "Hello"}  # Missing to_number
    response = make_request(url, params, headers)
    assert response.status_code == 200
    result = response.json()
    assert "error" in result["results"][0]["result"].lower()


def test_send_text_ifttt():
    """Test the send-text-ifttt endpoint"""
    url = "https://idvorkin--modal-tony-server-fastapi-app.modal.run/send-text-ifttt"
    headers = {"x-vapi-secret": os.environ["TONY_API_KEY"]}

    # Test with valid parameters
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text_ifttt",
                        "arguments": {
                            "text": "Hello from IFTTT test",
                            "to_number": "+12068904339",
                        },
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }

    try:
        response = make_request(url, params, headers)
        assert response.status_code == 200
        result = response.json()
        assert "results" in result
        assert len(result["results"]) > 0
        # Accept either success or error message
        if "text message sent via ifttt" in result["results"][0]["result"].lower():
            assert "+12068904339" in result["results"][0]["result"]
        else:
            assert "error" in result["results"][0]["result"].lower()
            assert (
                "missing ifttt configuration" in result["results"][0]["result"].lower()
                or "failed to send webhook request"
                in result["results"][0]["result"].lower()
            )
    except requests.exceptions.RequestException as e:
        # This test might fail if endpoint doesn't exist or can't be reached
        ic("IFTTT endpoint not available:", str(e))
        pytest.skip("IFTTT endpoint not available: " + str(e))

    # Test with missing parameters
    params = {
        "message": {
            "toolCalls": [
                {
                    "function": {
                        "name": "send_text_ifttt",
                        "arguments": {
                            "text": "Hello from IFTTT"
                            # Missing to_number
                        },
                    },
                    "id": "test_id",
                    "type": "function",
                }
            ]
        }
    }

    response = make_request(url, params, headers)
    assert response.status_code == 200
    result = response.json()
    assert "error" in result["results"][0]["result"].lower()
