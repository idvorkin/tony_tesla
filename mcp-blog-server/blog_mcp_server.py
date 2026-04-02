#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastmcp>=2.0.0",
#     "requests>=2.31.0",
# ]
# ///
"""
MCP Server for Igor's Blog Operations
Built with FastMCP for Model Context Protocol
Deployable to FastMCP cloud hosting
"""

import json
import random
from typing import Dict, List, Optional, Any
import requests
from fastmcp import FastMCP

# Configuration
GITHUB_BASE = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/main/"
BACKLINKS_URL = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/main/back-links.json"
BLOG_BASE_URL = "https://idvork.in"
ALGOLIA_APP_ID = "RY6D0RNCA3"
ALGOLIA_API_KEY = "d4bae7d1d6328352ce13c0978ca620e9"
ALGOLIA_INDEX_NAME = "jekyll"


class BlogReader:
    """Handles blog post retrieval and management"""
    
    def __init__(self):
        self.backlinks_url = BACKLINKS_URL
        self._url_info_cache = None
    
    def get_url_info(self) -> Dict[str, Dict]:
        """Fetch and cache URL information from the blog"""
        if self._url_info_cache is None:
            response = requests.get(self.backlinks_url)
            response.raise_for_status()
            data = response.json()
            
            url_info = {}
            for url, info in data.get("url_info", {}).items():
                if isinstance(info, dict):
                    url_info[url] = {
                        "url": url,
                        "title": info.get("title", ""),
                        "description": info.get("description", ""),
                        "redirect_url": info.get("redirect_url", ""),
                        "markdown_path": info.get("markdown_path", ""),
                    }
            self._url_info_cache = url_info
        
        return self._url_info_cache
    
    def url_to_markdown_path(self, url: str) -> Optional[str]:
        """Convert a blog URL to its corresponding markdown path"""
        # Strip the domain if present
        if url.startswith("https://idvork.in"):
            url = url[len("https://idvork.in"):]
        
        # Get URL info and find the matching entry
        url_info = self.get_url_info()
        if url in url_info and url_info[url].get("markdown_path"):
            return url_info[url]["markdown_path"]
        return None
    
    def read_blog_post(self, markdown_path: str) -> str:
        """Read a specific blog post from GitHub given its path"""
        markdown_url = GITHUB_BASE + markdown_path
        response = requests.get(markdown_url)
        response.raise_for_status()
        return response.text


# Create the MCP server with HTTP support for cloud hosting
mcp = FastMCP("blog-server")

# Initialize blog reader
blog_reader = BlogReader()


@mcp.tool
def blog_info() -> str:
    """Get information about all blog posts including URLs, titles, and descriptions"""
    try:
        url_info = blog_reader.get_url_info()
        posts = [
            {
                "url": f"{BLOG_BASE_URL}{info['url']}",
                "title": info["title"],
                "description": info["description"],
                "markdown_path": info.get("markdown_path", ""),
            }
            for info in url_info.values()
            if info.get("url") and info.get("title")
        ]
        
        if not posts:
            return json.dumps({"error": "No valid blog info found"})
        
        return json.dumps(posts, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error fetching blog info: {str(e)}"})


@mcp.tool
def random_blog() -> str:
    """Get the full content of a random blog post"""
    try:
        url_info = blog_reader.get_url_info()
        posts_with_markdown = [
            info for info in url_info.values() 
            if info.get("markdown_path")
        ]
        
        if not posts_with_markdown:
            return json.dumps({"error": "No blog posts with markdown found"})
        
        random_post = random.choice(posts_with_markdown)
        content = blog_reader.read_blog_post(random_post["markdown_path"])
        
        result = {
            "content": content,
            "title": random_post["title"],
            "url": f"{BLOG_BASE_URL}{random_post['url']}",
            "markdown_path": random_post["markdown_path"],
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error fetching random blog: {str(e)}"})


@mcp.tool
def read_blog_post(path: str) -> str:
    """
    Get the content of a specific blog post by markdown path or URL
    
    Args:
        path: The path to the blog post - can be either a markdown file path 
              (e.g., '_d/vim_tips.md') or a URL path (e.g., '/vim')
    """
    try:
        if not path:
            return json.dumps({"error": "Valid path is required"})
        
        markdown_path = path
        
        # If it looks like a URL, try to convert it to a markdown path
        if path.startswith("http") or path.startswith("/"):
            converted = blog_reader.url_to_markdown_path(path)
            if not converted:
                return json.dumps({
                    "error": f"Could not find markdown path for URL: {path}"
                })
            markdown_path = converted
        
        # Append .md if not present
        if not markdown_path.endswith(".md"):
            markdown_path = f"{markdown_path}.md"
        
        content = blog_reader.read_blog_post(markdown_path)
        result = {
            "content": content,
            "markdown_path": markdown_path
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error reading blog post: {str(e)}"})


@mcp.tool
def random_blog_url() -> str:
    """Get just the URL and title of a random blog post without its content"""
    try:
        url_info = blog_reader.get_url_info()
        posts_with_markdown = [
            info for info in url_info.values() 
            if info.get("markdown_path")
        ]
        
        if not posts_with_markdown:
            return json.dumps({"error": "No blog posts with markdown found"})
        
        random_post = random.choice(posts_with_markdown)
        result = {
            "title": random_post["title"],
            "url": f"{BLOG_BASE_URL}{random_post['url']}",
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error fetching random blog URL: {str(e)}"})


@mcp.tool
def blog_search(query: str) -> str:
    """
    Search blog posts using keywords with Algolia
    
    Args:
        query: The search query to find relevant blog posts
    """
    try:
        if not query:
            return json.dumps({"error": "Search query is required"})
        
        # Prepare Algolia search request
        url = f"https://{ALGOLIA_APP_ID.lower()}-1.algolianet.com/1/indexes/{ALGOLIA_INDEX_NAME}/query"
        headers = {
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json",
        }
        
        # Make the search request with filters to exclude ig66 collection
        payload = {
            "query": query,
            "hitsPerPage": 5,  # Limit results to top 5
            "filters": "NOT collection:ig66",  # Exclude ig66 collection
        }
        
        search_response = requests.post(url, headers=headers, json=payload)
        search_response.raise_for_status()
        
        # Process and format the results
        results = search_response.json()
        hits = results.get("hits", [])
        
        formatted_results = []
        for hit in hits:
            formatted_hit = {
                "title": hit.get("title", ""),
                "url": f"{BLOG_BASE_URL}{hit.get('url', '')}",
                "content": hit.get("content", ""),
                "collection": hit.get("collection", ""),
            }
            formatted_results.append(formatted_hit)
        
        return json.dumps(formatted_results, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error searching blog: {str(e)}"})


# The tools are automatically registered via the @mcp.tool decorator

if __name__ == "__main__":
    # Run the server - defaults to stdio for local use
    # For cloud hosting, FastMCP will automatically handle HTTP transport
    import sys
    import os
    
    # Check if running in FastMCP cloud environment  
    if os.environ.get("FASTMCP_ENV") == "production":
        # Cloud hosting mode - will be handled by FastMCP infrastructure
        mcp.run()
    else:
        # Local development mode - use stdio
        mcp.run()