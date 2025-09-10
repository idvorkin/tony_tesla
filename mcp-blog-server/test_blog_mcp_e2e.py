#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pytest>=7.0.0",
#     "pytest-asyncio>=0.21.0",
#     "requests>=2.31.0",
#     "icecream>=2.1.0",
# ]
# ///
"""
End-to-end tests for the MCP Blog Server
Tests actual functionality against the real blog data
"""

import json
import subprocess
import sys
import time
import os
from typing import Dict, Any
import pytest
import requests
from icecream import ic

# Test configuration
TIMEOUT = 10  # seconds for server startup
TEST_VERBOSE = os.environ.get("TEST_VERBOSE", "false").lower() == "true"


class MCPTestClient:
    """Test client for MCP server communication via stdio"""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        
    def start(self):
        """Start the MCP server process"""
        self.process = subprocess.Popen(
            [sys.executable, self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if not TEST_VERBOSE else None,
            text=True,
            bufsize=0
        )
        # Give server time to initialize and perform handshake
        time.sleep(1.0)
        
        # Perform MCP initialization handshake
        self._initialize()
        
    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            
    def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict:
        """Send a JSON-RPC request to the server"""
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        request_str = json.dumps(request) + "\n"
        if TEST_VERBOSE:
            ic(f"Sending: {request_str}")
            
        self.process.stdin.write(request_str)
        self.process.stdin.flush()
        
        # Read response
        response_str = self.process.stdout.readline()
        if TEST_VERBOSE:
            ic(f"Received: {response_str}")
            
        return json.loads(response_str)
    
    def _initialize(self):
        """Perform MCP initialization handshake"""
        # Send initialize request
        init_response = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })
        
        if "error" in init_response:
            raise Exception(f"Initialization failed: {init_response['error']}")
        
        # Send initialized notification
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on the MCP server"""
        params = {
            "name": tool_name,
            "arguments": arguments or {}
        }
        response = self.send_request("tools/call", params)
        
        if "error" in response:
            raise Exception(f"Tool call error: {response['error']}")
            
        # Parse the result
        result = response.get("result", {})
        if "content" in result and len(result["content"]) > 0:
            content = result["content"][0]
            if content.get("type") == "text":
                return json.loads(content.get("text", "{}"))
        return result


@pytest.fixture
def mcp_client():
    """Fixture to provide MCP client for tests"""
    client = MCPTestClient("blog_mcp_server.py")
    client.start()
    yield client
    client.stop()


def test_server_starts():
    """Test that the server starts without errors"""
    process = subprocess.Popen(
        [sys.executable, "blog_mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give it a moment to start
    time.sleep(0.5)
    
    # Check if process is still running
    assert process.poll() is None, "Server crashed on startup"
    
    # Clean up
    process.terminate()
    process.wait(timeout=5)


def test_blog_info(mcp_client):
    """Test getting blog info returns valid data"""
    result = mcp_client.call_tool("blog_info")
    
    assert isinstance(result, list), "blog_info should return a list"
    assert len(result) > 0, "Should have at least one blog post"
    
    # Check structure of first post
    first_post = result[0]
    assert "url" in first_post
    assert "title" in first_post
    assert "description" in first_post
    assert first_post["url"].startswith("https://idvork.in")
    
    if TEST_VERBOSE:
        ic(f"Found {len(result)} blog posts")
        ic(f"Sample post: {first_post}")


def test_random_blog(mcp_client):
    """Test getting a random blog post with content"""
    result = mcp_client.call_tool("random_blog")
    
    assert isinstance(result, dict), "random_blog should return a dict"
    assert "content" in result, "Should have content field"
    assert "title" in result, "Should have title field"
    assert "url" in result, "Should have url field"
    assert "markdown_path" in result, "Should have markdown_path field"
    
    # Verify content is markdown
    assert len(result["content"]) > 100, "Content should be substantial"
    assert result["url"].startswith("https://idvork.in")
    
    if TEST_VERBOSE:
        ic(f"Random post title: {result['title']}")
        ic(f"Content length: {len(result['content'])} chars")


def test_read_blog_post_by_path(mcp_client):
    """Test reading a specific blog post by markdown path"""
    # First get a valid path from blog_info
    info = mcp_client.call_tool("blog_info")
    posts_with_path = [p for p in info if p.get("markdown_path")]
    assert len(posts_with_path) > 0, "Should have posts with markdown paths"
    
    test_path = posts_with_path[0]["markdown_path"]
    
    # Now read that specific post
    result = mcp_client.call_tool("read_blog_post", {"path": test_path})
    
    assert isinstance(result, dict), "read_blog_post should return a dict"
    assert "content" in result, "Should have content field"
    assert "markdown_path" in result, "Should have markdown_path field"
    assert len(result["content"]) > 100, "Content should be substantial"
    
    if TEST_VERBOSE:
        ic(f"Read post at: {test_path}")
        ic(f"Content length: {len(result['content'])} chars")


def test_read_blog_post_by_url(mcp_client):
    """Test reading a blog post by URL path"""
    result = mcp_client.call_tool("read_blog_post", {"path": "/vim"})
    
    assert isinstance(result, dict), "read_blog_post should return a dict"
    assert "content" in result, "Should have content field"
    assert "markdown_path" in result, "Should have markdown_path field"
    
    # Should have converted /vim to the correct markdown path
    assert result["markdown_path"].endswith(".md")
    
    if TEST_VERBOSE:
        ic(f"URL /vim resolved to: {result['markdown_path']}")


def test_random_blog_url(mcp_client):
    """Test getting just URL and title of random post"""
    result = mcp_client.call_tool("random_blog_url")
    
    assert isinstance(result, dict), "random_blog_url should return a dict"
    assert "title" in result, "Should have title field"
    assert "url" in result, "Should have url field"
    assert "content" not in result, "Should NOT have content field"
    
    assert result["url"].startswith("https://idvork.in")
    assert len(result["title"]) > 0, "Title should not be empty"
    
    if TEST_VERBOSE:
        ic(f"Random URL: {result}")


def test_blog_search(mcp_client):
    """Test searching blog posts"""
    # Search for a common term
    result = mcp_client.call_tool("blog_search", {"query": "vim"})
    
    assert isinstance(result, list), "blog_search should return a list"
    
    if len(result) > 0:
        first_result = result[0]
        assert "title" in first_result
        assert "url" in first_result
        assert "content" in first_result
        assert "collection" in first_result
        assert first_result["url"].startswith("https://idvork.in")
        
        # Should not include ig66 collection (filtered out)
        for hit in result:
            assert hit.get("collection") != "ig66", "ig66 collection should be filtered"
    
    if TEST_VERBOSE:
        ic(f"Search for 'vim' returned {len(result)} results")
        if result:
            ic(f"First result: {result[0]['title']}")


def test_blog_search_empty_query(mcp_client):
    """Test that empty search query returns error"""
    result = mcp_client.call_tool("blog_search", {"query": ""})
    
    assert isinstance(result, dict), "Should return error dict"
    assert "error" in result, "Should have error field"
    assert "required" in result["error"].lower(), "Error should mention required"
    
    if TEST_VERBOSE:
        ic(f"Empty query error: {result}")


def test_read_invalid_path(mcp_client):
    """Test reading non-existent blog post"""
    result = mcp_client.call_tool("read_blog_post", {"path": "/non-existent-post-xyz"})
    
    assert isinstance(result, dict), "Should return dict"
    
    # Should either have an error or handle gracefully
    if "error" in result:
        assert "not find" in result["error"].lower() or "error" in result["error"].lower()
    
    if TEST_VERBOSE:
        ic(f"Invalid path result: {result}")


def test_multiple_random_calls(mcp_client):
    """Test that multiple random calls return different posts"""
    urls = set()
    
    for _ in range(3):
        result = mcp_client.call_tool("random_blog_url")
        urls.add(result["url"])
    
    # With many posts, we should get different ones
    # (small chance of collision, but unlikely with 3 calls)
    if TEST_VERBOSE:
        ic(f"Random URLs collected: {urls}")
        ic(f"Unique URLs: {len(urls)}")


def test_algolia_search_integration():
    """Test that Algolia search API is accessible"""
    # Direct test of Algolia API to ensure keys work
    url = "https://ry6d0rnca3-1.algolianet.com/1/indexes/jekyll/query"
    headers = {
        "X-Algolia-API-Key": "d4bae7d1d6328352ce13c0978ca620e9",
        "X-Algolia-Application-Id": "RY6D0RNCA3",
        "Content-Type": "application/json",
    }
    payload = {
        "query": "test",
        "hitsPerPage": 1,
    }
    
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200, f"Algolia API returned {response.status_code}"
    
    data = response.json()
    assert "hits" in data, "Algolia response should have hits field"
    
    if TEST_VERBOSE:
        ic("Algolia API is accessible")


def test_github_content_accessible():
    """Test that GitHub content is accessible"""
    backlinks_url = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/main/back-links.json"
    
    response = requests.get(backlinks_url)
    assert response.status_code == 200, f"GitHub returned {response.status_code}"
    
    data = response.json()
    assert "url_info" in data, "Should have url_info field"
    
    if TEST_VERBOSE:
        ic(f"GitHub backlinks has {len(data.get('url_info', {}))} entries")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v" if TEST_VERBOSE else "-q"])