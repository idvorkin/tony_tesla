import os
import pytest
import json
from fastapi.testclient import TestClient
from blog_server import blog_handler_logic, app
from tony_server import make_call

@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}

@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {
        "action": "blog_post_from_path",
        "markdown_path": "_d/vim_tips.md"
    }

from fastapi.encoders import jsonable_encoder

def test_blog_handler_jsonable_encoder(auth_headers, base_params):
    """Test the blog_handler_logic with jsonable_encoder simulation"""
    # First test the direct logic
    result = blog_handler_logic(base_params, auth_headers)
    encoded_result = jsonable_encoder(result)
    
    assert "results" in encoded_result, "Expected 'results' key in encoded result, but it was not found."
    assert len(encoded_result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    
    result_str = encoded_result["results"][0]["result"]
    result_dict = json.loads(result_str)
    
    assert "content" in result_dict, "Expected 'content' key in result, but it was not found."
    assert "markdown_path" in result_dict, "Expected 'markdown_path' key in result, but it was not found."
    assert len(result_dict["content"]) > 0, "Expected non-empty content, but it was empty."

    # Then test the endpoint
    client = TestClient(app)
    response = client.post("/blog_handler", json=base_params, headers=auth_headers)
    
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    result = response.json()
    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    
    assert "content" in result_dict, "Expected 'content' key in result, but it was not found."
    assert "markdown_path" in result_dict, "Expected 'markdown_path' key in result, but it was not found."
    assert len(result_dict["content"]) > 0, "Expected non-empty content, but it was empty."
