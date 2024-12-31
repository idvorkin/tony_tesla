import os
import pytest
import json
from fastapi.testclient import TestClient
from blog_server import app
from tony_server import make_call

@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}

@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {
        "message": {
            "toolCalls": [{
                "function": {
                    "name": "",  # To be filled by individual tests
                    "arguments": {}
                },
                "id": "test-id",
                "type": "function"
            }]
        }
    }

def test_random_blog(auth_headers, base_params):
    """Test the random blog endpoint"""
    client = TestClient(app)
    base_params["message"]["toolCalls"][0]["function"]["name"] = "random_blog"
    
    response = client.post("/random_blog", json=base_params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert "content" in result_dict
    assert "title" in result_dict
    assert "url" in result_dict
    assert "markdown_path" in result_dict

def test_blog_info(auth_headers, base_params):
    """Test the blog info endpoint"""
    client = TestClient(app)
    base_params["message"]["toolCalls"][0]["function"]["name"] = "blog_info"
    
    response = client.post("/blog_info", json=base_params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert isinstance(result_dict, list), "Result should be a list of blog posts"
    assert len(result_dict) > 100, f"Expected more than 100 blog posts, but got {len(result_dict)}"
    
    # Verify structure of first post
    first_post = result_dict[0]
    assert "url" in first_post, "Missing 'url' in result"
    assert "title" in first_post, "Missing 'title' in result"
    assert "description" in first_post, "Missing 'description' in result"
    assert "markdown_path" in first_post, "Missing 'markdown_path' in result"
    assert first_post["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
    assert len(first_post["title"]) > 0, "Title should not be empty"

def test_blog_post(auth_headers, base_params):
    """Test the blog post endpoint"""
    client = TestClient(app)
    base_params["message"]["toolCalls"][0]["function"].update({
        "name": "blog_post_from_path",
        "arguments": {"markdown_path": "_d/vim_tips.md"}
    })
    
    response = client.post("/blog_post", json=base_params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert "content" in result_dict
    assert "markdown_path" in result_dict
    assert len(result_dict["content"]) > 0

def test_random_blog_url(auth_headers, base_params):
    """Test the random blog URL endpoint"""
    client = TestClient(app)
    base_params["message"]["toolCalls"][0]["function"]["name"] = "random_blog_url_only"
    
    response = client.post("/random_blog_url", json=base_params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert "title" in result_dict
    assert "url" in result_dict
    assert result_dict["url"].startswith("https://idvork.in")
