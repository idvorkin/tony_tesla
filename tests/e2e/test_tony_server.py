import os
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

        result = response.json()
        ic("Response JSON:", result)

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

@pytest.mark.e2e
def test_assistant_e2e(auth_headers, base_params):
    """Test the assistant endpoint with real HTTP requests"""
    ic("Starting assistant test")

    response = make_request(TONY_SERVER_URL, base_params, auth_headers)
    result = response.json()

    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert isinstance(result_dict, dict), "Result is not a valid JSON object"
