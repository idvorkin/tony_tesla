import os
import pytest
from fastapi.testclient import TestClient
from tony_server import fastapi_app, parse_tool_call, make_vapi_response

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
    """Test the search function with FastAPI test client"""
    client = TestClient(fastapi_app)
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
