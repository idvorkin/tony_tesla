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

BLOG_SERVER_URL = "https://idvorkin--modal-blog-server-blog-handler.modal.run"

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
        "action": ""  # To be filled by individual tests
    }

@pytest.mark.e2e
def test_sanity_prints():
    """Sanity test to print to stdout and stderr"""
    print("This is a stdout message")
    import sys
    print("This is a stderr message", file=sys.stderr)
@pytest.mark.parametrize("n", ["auto"])
def test_random_blog_e2e(auth_headers, base_params, n):
    """Test getting a random blog post with real HTTP requests"""
    ic("Starting random blog test")
    base_params["action"] = "random_blog"

    start_time = time.time()
    try:
        ic("Sending request with params:", base_params)
        ic("Headers:", auth_headers)
        response = make_request(BLOG_SERVER_URL, base_params, auth_headers)
        response_time = time.time() - start_time
        ic(f"Response time: {response_time:.2f} seconds")
        ic("Status code:", response.status_code)
        ic("Response headers:", dict(response.headers))

        # Try to get JSON response even if status code is error
        try:
            result = response.json()
            ic("Response JSON:", result)
        except json.JSONDecodeError:
            ic("Raw response content:", response.content)

        response.raise_for_status()

        if not isinstance(result, dict):
            raise ValueError(f"Expected dict response, got {type(result)}")

        return result

    except requests.exceptions.HTTPError as e:
        ic("HTTP Error occurred")
        ic("Request URL:", response.url)
        ic("Request method:", response.request.method)
        ic("Request headers:", dict(response.request.headers))
        ic("Request body:", response.request.body)
        ic("Response status:", response.status_code)
        ic("Response content:", response.content)
        ic("Error:", str(e))
        raise
    except json.JSONDecodeError as e:
        ic("JSON decode error")
        ic("Raw content:", response.content)
        ic("Error:", str(e))
        raise
    except Exception as e:
        ic("Unexpected error:", str(e))
        ic("Response content:", response.content)
        raise

    assert response_time < 5.0, "Response took too long"

    # Ensure the response contains the 'results' key
    assert "results" in result, "Missing 'results' in response"
    # Ensure there is at least one result
    assert len(result["results"]) > 0, "No results found in response"
    try:
        result_str = result["results"][0]["result"]
        result_dict = json.loads(result_str.replace("'", '"'))
    except json.JSONDecodeError as e:
        ic("JSON decode error:", str(e))
        ic("Problematic JSON string:", result_str)
        raise
    assert "title" in result_dict, "Missing 'title' in result"
    assert "url" in result_dict, "Missing 'url' in result"
    # Verify the expected fields are present in the result
    assert "content" in result_dict, "Missing 'content' in result"
    assert result_dict["url"].startswith("https://idvork.in")

@pytest.mark.e2e
def test_blog_info_e2e(auth_headers, base_params):
    """Test getting blog info with real HTTP requests"""
    ic("Starting blog info test")
    base_params["action"] = "blog_info"

    try:
        ic("Sending request with params:", base_params)
        response = requests.post(BLOG_SERVER_URL, json=base_params, headers=auth_headers)
        ic("Status code:", response.status_code)
        ic("Response headers:", dict(response.headers))

        try:
            result = response.json()
            ic("Response JSON:", result)
        except json.JSONDecodeError:
            ic("Raw response content:", response.content)
            raise

        response.raise_for_status()

        assert "results" in result, "Missing 'results' in response"
        assert len(result["results"]) > 0, "No results found in response"
        result_str = result["results"][0]["result"]
        # HACK: Instead of parsing the JSON, we check for specific content in the result string
        # because the server response uses single quotes which are not valid JSON.
        assert "https://idvork.in" in result_str, "Expected URL in the content, but it was not found."
        assert "title" in result_str, "Expected 'title' in the content, but it was not found."

    except requests.exceptions.HTTPError as e:
        ic("HTTP Error occurred")
        ic("Request URL:", response.url)
        ic("Request method:", response.request.method)
        ic("Request headers:", dict(response.request.headers))
        ic("Request body:", response.request.body)
        ic("Response status:", response.status_code)
        ic("Response content:", response.content)
        ic("Error:", str(e))
        raise
    except Exception as e:
        ic("Unexpected error:", str(e))
        ic("Response content:", response.content)
        raise

@pytest.mark.e2e
def test_blog_post_from_path_e2e(auth_headers, base_params):
    """Test getting a specific blog post with real HTTP requests

    This test verifies that the blog server can return a specific blog post
    when provided with a valid markdown path. It checks that the response
    contains the expected fields and that the content is not empty.
    """
    base_params.update({
        "action": "blog_post_from_path",
        "markdown_path": "_d/vim_tips.md"
    })
    ic("Running test_blog_post_from_path_e2e")

    response = make_request(BLOG_SERVER_URL, base_params, auth_headers)
    result = response.json()

    assert "results" in result, "Expected 'results' key in response, but it was not found."
    assert len(result["results"]) > 0, "Expected at least one result in 'results', but none were found."
    result_str = result["results"][0]["result"]
    print("Result string:", result_str)
    # HACK: Instead of parsing the JSON, we check for specific content in the result string
    # because the server response uses single quotes which are not valid JSON.
    assert "Igors Vim Tips" in result_str, "Expected 'Igors Vim Tips' in the content, but it was not found."
    assert "_d/vim_tips.md" in result_str, "Expected '_d/vim_tips.md' in the content, but it was not found."

@pytest.mark.e2e
def test_random_blog_url_only_e2e(auth_headers, base_params):
    """Test getting a random blog URL with real HTTP requests"""
    base_params["action"] = "random_blog_url_only"

    response = make_request(BLOG_SERVER_URL, base_params, auth_headers)
    result = response.json()

    assert "results" in result
    assert len(result["results"]) > 0
    result_dict = json.loads(result["results"][0]["result"].replace("'", '"'))
    assert "title" in result_dict
    assert "url" in result_dict
    assert result_dict["url"].startswith("https://idvork.in")
