import os
import pytest
from fastapi.testclient import TestClient
from tony_server import app, parse_tool_call, make_vapi_response
from blog_server import app as blog_app
import json

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
