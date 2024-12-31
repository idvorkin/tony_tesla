import os
import pytest
from fastapi.testclient import TestClient
from tony_server import app

@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}

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
    """Test the search function with a mock request"""
    client = TestClient(app)
    response = client.post("/search", json=base_params, headers=auth_headers)
    
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    result = response.json()
    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    
    result_str = result["results"][0]["result"]
    assert isinstance(result_str, str), "Expected result to be a string."
