import json
import os
import time
from typing import Any, Dict
import pytest
import requests
from icecream import ic
from requests.adapters import HTTPAdapter

# Configure icecream to limit string length
def clip_long_strings(output):
    max_length = 1000  # Set the maximum length for strings
    if isinstance(output, str) and len(output) > max_length:
        return output[:max_length] + '...'
    return output

ic.configureOutput(outputFunction=clip_long_strings)
from urllib3.util.retry import Retry

BLOG_SERVER_BASE = "https://idvorkin--modal-blog-server-fastapi-app.modal.run"

def create_session() -> requests.Session:
    """Create a session with retry logic"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def make_request(url: str, params: Dict[str, Any], headers: Dict[str, str]) -> requests.Response:
    """Make HTTP request with proper error handling"""
    session = create_session()
    try:
        ic("Making request to:", url)
        ic("With params:", params)
        ic("With headers:", headers)

        response = session.post(url, json=params, headers=headers)
        ic("Response status:", response.status_code)
        ic("Response headers:", dict(response.headers))

        # Try to parse JSON response, but handle cases where response might not be JSON
        try:
            result = response.json()
            ic("Response JSON:", result)
        except json.JSONDecodeError:
            ic("Response was not JSON:", response.text[:1000])  # Show first 1000 chars
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
    api_key = os.environ.get("TONY_API_KEY")
    if not api_key:
        pytest.skip("TONY_API_KEY environment variable not set")
    return {"x-vapi-secret": api_key}

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

@pytest.mark.e2e
def test_random_blog_e2e(auth_headers, base_params):
    """Test getting a random blog post with real HTTP requests"""
    ic("Starting random blog test")
    base_params["message"]["toolCalls"][0]["function"]["name"] = "random_blog"

    start_time = time.time()
    try:
        response = make_request(f"{BLOG_SERVER_BASE}/random_blog", base_params, auth_headers)
        response_time = time.time() - start_time
        
        result = response.json()
        assert isinstance(result, dict), f"Expected dict response, got {type(result)}"
        assert response_time < 5.0, "Response took too long"

        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str)
        assert "content" in result_dict, "Missing 'content' in result"
        assert "title" in result_dict, "Missing 'title' in result"
        assert "markdown_path" in result_dict, "Missing 'markdown_path' in result"
        assert "url" in result_dict, "Missing 'url' in result"
        assert result_dict["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
        assert len(result_dict["content"]) > 0, "Content should not be empty"
        
        return result

    except Exception as e:
        ic("Error in test:", str(e))
        raise

@pytest.mark.e2e
def test_blog_info_e2e(auth_headers, base_params):
    """Test getting blog info with real HTTP requests"""
    ic("Starting blog info test")
    base_params["message"]["toolCalls"][0]["function"]["name"] = "blog_info"

    try:
        response = make_request(f"{BLOG_SERVER_BASE}/blog_info", base_params, auth_headers)
        result = response.json()

        assert "results" in result, "Missing 'results' in response"
        assert len(result["results"]) > 0, "No results found in response"
        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str)
        
        assert isinstance(result_dict, list), "Result should be a list of blog posts"
        assert len(result_dict) > 100, f"Expected more than 100 blog posts, but got {len(result_dict)}"
        
        # Verify structure of first post
        first_post = result_dict[0]
        assert "url" in first_post, "Missing 'url' in first post"
        assert "title" in first_post, "Missing 'title' in first post"
        assert "description" in first_post, "Missing 'description' in first post"
        assert "markdown_path" in first_post, "Missing 'markdown_path' in first post"
        assert first_post["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
        assert len(first_post["title"]) > 0, "Title should not be empty"

    except Exception as e:
        ic("Error in test:", str(e))
        raise

@pytest.mark.e2e
def test_read_blog_post_e2e(auth_headers, base_params):
    """Test getting a specific blog post with real HTTP requests"""
    base_params["message"]["toolCalls"][0]["function"].update({
        "name": "read_blog_post",
        "arguments": {"path": "_d/vim_tips.md"}
    })

    try:
        response = make_request(f"{BLOG_SERVER_BASE}/read_blog_post", base_params, auth_headers)
        result = response.json()

        assert "results" in result, "Missing 'results' in response"
        assert len(result["results"]) > 0, "No results found in response"
        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str)
        
        assert "content" in result_dict, "Missing 'content' in result"
        assert "markdown_path" in result_dict, "Missing 'markdown_path' in result"
        assert len(result_dict["content"]) > 0, "Content should not be empty"
        assert result_dict["markdown_path"] == "_d/vim_tips.md", "Incorrect markdown path"
        assert isinstance(result_dict, dict), "Result should be a valid JSON object"

        # Test with URL path
        base_params["message"]["toolCalls"][0]["function"]["arguments"]["path"] = "/vim"
        response = make_request(f"{BLOG_SERVER_BASE}/read_blog_post", base_params, auth_headers)
        result = response.json()
        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str)
        
        assert "content" in result_dict, "Missing 'content' in result"
        assert "markdown_path" in result_dict, "Missing 'markdown_path' in result"
        assert len(result_dict["content"]) > 0, "Content should not be empty"
        assert result_dict["markdown_path"] == "_d/vim_tips.md", "Incorrect markdown path from URL"

    except Exception as e:
        ic("Error in test:", str(e))
        raise

@pytest.mark.e2e
def test_random_blog_url_e2e(auth_headers, base_params):
    """Test getting a random blog URL with real HTTP requests"""
    base_params["message"]["toolCalls"][0]["function"]["name"] = "random_blog_url_only"

    try:
        response = make_request(f"{BLOG_SERVER_BASE}/random_blog_url", base_params, auth_headers)
        result = response.json()

        assert "results" in result, "Missing 'results' in response"
        assert len(result["results"]) > 0, "No results found in response"
        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str)
        assert "title" in result_dict, "Missing 'title' in result"
        assert "url" in result_dict, "Missing 'url' in result"
        assert result_dict["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
        assert len(result_dict["title"]) > 0, "Title should not be empty"

    except Exception as e:
        ic("Error in test:", str(e))
        raise

@pytest.mark.e2e
def test_blog_search_e2e(auth_headers, base_params):
    """End-to-end test for blog search functionality"""
    ic("Starting blog search test")
    base_params["message"]["toolCalls"][0]["function"].update({
        "name": "blog_search",
        "arguments": {"query": "meditation"}
    })

    try:
        response = make_request(f"{BLOG_SERVER_BASE}/blog_search", base_params, auth_headers)
        result = response.json()
        
        assert "results" in result, "Expected 'results' key in response"
        assert len(result["results"]) > 0, "Expected at least one result"
        
        # Parse and verify search results
        search_results = json.loads(result["results"][0]["result"])
        assert isinstance(search_results, list), "Expected results to be a list"
        assert len(search_results) > 0, "Expected at least one search result"
        
        # Verify first result structure and content
        first_result = search_results[0]
        assert "title" in first_result, "Expected 'title' in search result"
        assert "url" in first_result, "Expected 'url' in search result"
        assert "content" in first_result, "Expected 'content' in search result"
        assert "collection" in first_result, "Expected 'collection' in search result"
        
        # Verify URL format
        assert first_result["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
        
        # Verify content relevance
        assert any("meditation" in result["content"].lower() for result in search_results), \
            "Expected at least one result to contain the search term in content"

    except Exception as e:
        ic("Error in test:", str(e))
        raise
