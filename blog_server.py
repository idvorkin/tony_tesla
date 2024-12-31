import os
import json
import random
from typing import Dict, Optional
from pydantic import BaseModel
import requests, json
from icecream import ic
from modal import App, Image, Secret, web_endpoint, asgi_app
from fastapi import Depends, FastAPI, Request

class UrlInfo(BaseModel):
    url: str
    title: str = ""
    description: str = ""
    redirect_url: Optional[str] = None
    markdown_path: Optional[str] = None

def read_blog_post(markdown_path: str) -> str:
    """Read a specific blog post from GitHub given its path"""
    github_base = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/refs/heads/master/"
    markdown_url = github_base + markdown_path
    
    try:
        response = requests.get(markdown_url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        ic(f"Error fetching blog post: {e}")
        raise Exception(f"Error fetching blog post: {str(e)}")

from tony_server import (
    make_vapi_response, parse_tool_call, raise_if_not_authorized, 
    get_headers, default_image, X_VAPI_SECRET, TONY_API_KEY_NAME
)

app = FastAPI()
modal_app = App("modal-blog-server")

class BlogReader:
    def __init__(self):
        self.backlinks_url = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/refs/heads/master/back-links.json"
    
    def get_url_info(self) -> Dict[str, UrlInfo]:
        response = requests.get(self.backlinks_url)
        response.raise_for_status()
        
        data = response.json()
        url_info: Dict[str, UrlInfo] = {}
        
        for url, info in data.get("url_info", {}).items():
            if isinstance(info, dict):
                url_info[url] = UrlInfo(
                    url=url,
                    title=info.get("title", ""),
                    description=info.get("description", ""),
                    redirect_url=info.get("redirect_url", ""),
                    markdown_path=info.get("markdown_path", "")
                )
        
        return url_info

@app.post("/random_blog")
async def random_blog_endpoint(params: Dict, headers=Depends(get_headers)):
    """Get a random blog post with full content"""
    try:
        raise_if_not_authorized(headers)
        call = parse_tool_call("random_blog", params)
        
        blog = BlogReader()
        url_info = blog.get_url_info()
        posts_with_markdown = [info for info in url_info.values() if info.markdown_path]
        
        if not posts_with_markdown:
            return make_vapi_response(call, "No blog posts with markdown found")
        
        random_post = random.choice(posts_with_markdown)
        content = read_blog_post(random_post.markdown_path)
        
        result = {
            "content": content,
            "title": random_post.title,
            "url": f"https://idvork.in{random_post.url}",
            "markdown_path": random_post.markdown_path
        }
        
        return make_vapi_response(call, json.dumps(result))
    except Exception as e:
        ic(f"Error in random_blog: {str(e)}")
        raise

@app.post("/blog_info")
async def blog_info_endpoint(params: Dict, headers=Depends(get_headers)):
    """Get information about the first valid blog post"""
    try:
        raise_if_not_authorized(headers)
        call = parse_tool_call("blog_info", params)
        
        blog = BlogReader()
        url_info = blog.get_url_info()
        info = next(
            (info for info in url_info.values() if info.url and info.title), 
            None
        )
        
        if not info:
            return make_vapi_response(call, "No valid blog info found")
            
        result = {
            "url": f"https://idvork.in{info.url}",
            "title": info.title,
            "description": info.description,
            "markdown_path": info.markdown_path
        }
        
        return make_vapi_response(call, json.dumps(result))
    except Exception as e:
        ic(f"Error in blog_info: {str(e)}")
        raise

@app.post("/blog_post")
async def blog_post_endpoint(params: Dict, headers=Depends(get_headers)):
    """Get a specific blog post by markdown path"""
    try:
        raise_if_not_authorized(headers)
        call = parse_tool_call("blog_post_from_path", params)
        
        markdown_path = call.args.get("markdown_path")
        if not markdown_path or not markdown_path.endswith(".md"):
            return make_vapi_response(call, "Error: Valid markdown_path is required")
            
        content = read_blog_post(markdown_path)
        result = {
            "content": content,
            "markdown_path": markdown_path
        }
        
        return make_vapi_response(call, json.dumps(result))
    except Exception as e:
        ic(f"Error in blog_post: {str(e)}")
        raise

@app.post("/random_blog_url")
async def random_blog_url_endpoint(params: Dict, headers=Depends(get_headers)):
    """Get just the URL of a random blog post"""
    try:
        raise_if_not_authorized(headers)
        call = parse_tool_call("random_blog_url_only", params)
        
        blog = BlogReader()
        url_info = blog.get_url_info()
        posts_with_markdown = [info for info in url_info.values() if info.markdown_path]
        
        if not posts_with_markdown:
            return make_vapi_response(call, "No blog posts with markdown found")
        
        random_post = random.choice(posts_with_markdown)
        result = {
            "title": random_post.title,
            "url": f"https://idvork.in{random_post.url}"
        }
        
        return make_vapi_response(call, json.dumps(result))
    except Exception as e:
        ic(f"Error in random_blog_url: {str(e)}")
        raise

@modal_app.function(
    image=default_image,
    secrets=[Secret.from_name(TONY_API_KEY_NAME)],
)
@asgi_app()
def fastapi_app():
    return app
