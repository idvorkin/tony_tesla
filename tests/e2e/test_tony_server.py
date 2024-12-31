import os
from typing import Dict, Any
import json
import pytest
import requests
from icecream import ic

TONY_SERVER_URL = "https://idvorkin--modal-tony-server-assistant.modal.run"

def make_request(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> requests.Response:
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
        ic("Response content:", getattr(e.response, 'content', None))
        raise

@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ["TONY_API_KEY"]}

@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {
        "input": {"message": "Test message"}
    }

def test_journal_read_e2e(auth_headers, base_params):
    """Test the journal_read endpoint with real HTTP requests"""
    ic("Starting journal read test")
    journal_read_url = "https://idvorkin--modal-tony-server-journal-read.modal.run"
    base_params["input"] = {"date": "2024-12-31"}

    response = make_request(journal_read_url, base_params, auth_headers)
    result = response.json()

    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    result_str = result["results"][0]["result"]
    assert isinstance(result_str, str), "Expected result to be a string."

def test_search_e2e(auth_headers, base_params):
    """Test the search endpoint with real HTTP requests"""
    ic("Starting search test")
    search_url = "https://idvorkin--modal-tony-server-search.modal.run"
    base_params["message"] = {
        "toolCalls": [{
            "function": {
                "arguments": {"question": "What is the weather in Seattle?"},
                "name": "search"
            },
            "id": "test_id",
            "type": "function"
        }]
    }

    try:
        response = make_request(search_url, base_params, auth_headers)
        result = response.json()

        assert "results" in result, "Expected 'results' key in response, but it was not found."
        assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
        result_str = result["results"][0]["result"]
        assert isinstance(result_str, str), "Expected result to be a string."
    except requests.exceptions.RequestException as e:
        ic("Request failed:", str(e))
        ic("Response content:", getattr(e.response, 'content', None))
        raise
    except json.JSONDecodeError as e:
        ic("JSON decode error:", str(e))
        ic("Response content:", response.content)
        raise

@pytest.mark.e2e
def test_assistant_e2e(auth_headers, base_params):
    """Test the assistant endpoint with real HTTP requests"""
    ic("Starting assistant test")

    response = make_request(TONY_SERVER_URL, base_params, auth_headers)
    result = response.json()

    assert "assistant" in result, "Expected 'assistant' key in response, but it was not found."
    assert isinstance(result["assistant"], dict), "Expected 'assistant' to be a dictionary."
    assert "firstMessage" in result["assistant"], "Expected 'firstMessage' in assistant response."
    assert isinstance(result["assistant"]["firstMessage"], str), "Expected 'firstMessage' to be a string."
