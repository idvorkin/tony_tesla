import json
import os
import pytest
import requests
from fastapi.testclient import TestClient
from blog_server import app, ALGOLIA_APP_ID, ALGOLIA_API_KEY, ALGOLIA_INDEX_NAME
from tony_server import make_call
from unittest.mock import patch, MagicMock

@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers"""
    return {"x-vapi-secret": os.environ.get("TONY_API_KEY", "test_secret")}

@pytest.fixture
def base_params():
    """Fixture for base parameters structure"""
    return {
        "path": None,  # For blog_post endpoint
        "query": None  # For blog_search endpoint
    }

def test_random_blog(auth_headers, base_params):
    """Test the random blog endpoint"""
    client = TestClient(app)
    response = client.post("/random_blog", json={}, headers=auth_headers)
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
    response = client.post("/blog_info", json={}, headers=auth_headers)
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

def test_read_blog_post(auth_headers, base_params):
    """Test the read blog post endpoint"""
    client = TestClient(app)
    
    # Test with markdown path - using a known existing post
    params = {"path": "_d/vim_tips.md"}
    response = client.post("/read_blog_post", json=params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    print(f"Response for markdown path: {result}")  # Debug print
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    print(f"Result string: {result_str}")  # Debug print
    result_dict = json.loads(result_str)
    assert "content" in result_dict
    assert "markdown_path" in result_dict
    assert len(result_dict["content"]) > 0
    assert result_dict["markdown_path"] == "_d/vim_tips.md"
    assert "vim" in result_dict["content"].lower()
    
    # Test with URL path
    params = {"path": "/vim"}
    response = client.post("/read_blog_post", json=params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    print(f"Response for URL path: {result}")  # Debug print
    result_str = result["results"][0]["result"]
    print(f"Result string for URL: {result_str}")  # Debug print
    result_dict = json.loads(result_str)
    assert "content" in result_dict
    assert "markdown_path" in result_dict
    assert result_dict["markdown_path"] == "_d/vim_tips.md"
    assert "vim" in result_dict["content"].lower()

def test_random_blog_url(auth_headers, base_params):
    """Test the random blog URL endpoint"""
    client = TestClient(app)
    response = client.post("/random_blog_url", json={}, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    result_dict = json.loads(result_str)
    assert "title" in result_dict
    assert "url" in result_dict
    assert result_dict["url"].startswith("https://idvork.in")

def test_blog_search(auth_headers, base_params):
    """Test the blog search endpoint"""
    client = TestClient(app)
    
    # First search directly with Algolia to confirm there are ig66 results for meditation
    algolia_url = f"https://{ALGOLIA_APP_ID.lower()}-1.algolianet.com/1/indexes/{ALGOLIA_INDEX_NAME}/query"
    algolia_headers = {
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "Content-Type": "application/json"
    }
    algolia_payload = {
        "query": "meditation",
        "hitsPerPage": 20  # Get more results to increase chance of finding ig66 content
    }
    
    algolia_response = requests.post(algolia_url, headers=algolia_headers, json=algolia_payload)
    algolia_response.raise_for_status()
    algolia_results = algolia_response.json()
    
    # Verify there are ig66 results in Algolia
    assert any(hit["collection"] == "ig66" for hit in algolia_results["hits"]), \
        "Should find at least one ig66 result for 'meditation' query in Algolia"
    
    # Now test our filtered endpoint
    params = {"query": "meditation"}
    response = client.post("/blog_search", json=params, headers=auth_headers)
    assert response.status_code == 200
    
    result = response.json()
    assert "results" in result
    assert len(result["results"]) > 0
    
    result_str = result["results"][0]["result"]
    filtered_results = json.loads(result_str)
    assert isinstance(filtered_results, list), "Result should be a list of search results"
    assert len(filtered_results) > 0, "Should have at least one search result"
    
    # Verify structure of first result
    first_result = filtered_results[0]
    assert "url" in first_result, "Missing 'url' in result"
    assert "title" in first_result, "Missing 'title' in result"
    assert "content" in first_result, "Missing 'content' in result"
    assert "collection" in first_result, "Missing 'collection' in result"
    assert first_result["url"].startswith("https://idvork.in"), "URL should start with https://idvork.in"
    
    # Verify no results are from ig66 collection
    assert all(result["collection"] != "ig66" for result in filtered_results), \
        "Search results should not include posts from ig66 collection"
    
    # Verify we still get non-ig66 results
    assert any(result["collection"] != "ig66" for result in filtered_results), \
        "Should still find non-ig66 results for 'meditation' query"
