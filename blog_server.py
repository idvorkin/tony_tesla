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
    redirect_url: Optional[str] = ""
    markdown_path: Optional[str] = ""

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
    get_headers, default_image, X_VAPI_SECRET, TONY_API_KEY_NAME,
    FunctionCall, make_call
)

app = FastAPI()
modal_app = App("modal-blog-server")

@app.post("/blog_handler")
async def blog_handler_endpoint(params: Dict, headers=Depends(get_headers)):
    """Modal endpoint that calls the core logic"""
    try:
        return blog_handler_logic(params, headers)
    except Exception as e:
        ic(f"Error in blog_handler: {str(e)}")
        ic(f"Params: {params}")
        raise

@modal_app.function(
    image=default_image,
    secrets=[Secret.from_name(TONY_API_KEY_NAME)],
)
@asgi_app()
def fastapi_app():
    return app

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

def blog_handler_logic(params: Dict, headers: Dict) -> Dict:
    """The core logic of the blog handler, separated from Modal decorators"""
    raise_if_not_authorized(headers)
    
    # Get the message from params
    message = params.get("message", {})
    if message:
        # If we have a message, get the tool calls
        tool_calls = message.get("toolCalls", [])
        if tool_calls:
            # Get the last tool call
            tool = tool_calls[-1]
            # Get the actual function name from the tool call
            action = tool["function"]["name"]
            call = FunctionCall(
                id=tool["id"],
                name=action,
                args=json.loads(tool["function"]["arguments"])
            )
        else:
            return {"error": "No tool calls found in message"}
    else:
        # For testing, assume action based on params
        action = params.get("action", "blog_info")
        call = make_call(action, params)
    
    if action == "random_blog":
        import random
        blog = BlogReader()
        url_info = blog.get_url_info()
        
        posts_with_markdown = [
            info for info in url_info.values() 
            if info.markdown_path and info.url
        ]
        
        if not posts_with_markdown:
            return make_vapi_response(call, "No blog posts with markdown found")
        
        random_post = random.choice(posts_with_markdown)
        
        github_base = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/refs/heads/master/"
        markdown_url = github_base + random_post.markdown_path
        
        try:
            response = requests.get(markdown_url)
            response.raise_for_status()
            content = response.text
            
            result = {
                "title": random_post.title,
                "url": f"https://idvork.in{random_post.url}",
                "content": content
            }
            
            ic("Result before JSON serialization:", result)
            return make_vapi_response(call, json.dumps(result, ensure_ascii=False))
            
        except Exception as e:
            ic(f"Error fetching blog post: {e}")
            return make_vapi_response(call, f"Error fetching blog post: {str(e)}")

    elif action == "blog_info":
        blog = BlogReader()
        try:
            response = requests.get(blog.backlinks_url)
            url_info = blog.get_url_info()
            # Just return the first result for testing
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
            ic(f"Error getting blog info: {e}")
            return make_vapi_response(call, f"Error getting blog info: {str(e)}")
    
    elif action == "blog_post_from_path":
        try:
            markdown_path = call.args.get("markdown_path")
            if not markdown_path or not markdown_path.endswith(".md"):
                return make_vapi_response(call, "Error: Valid markdown_path is required")
                
            content = read_blog_post(markdown_path)
            result = {
                "content": content,
                "markdown_path": markdown_path
            }
            serialized_result = json.dumps(result, ensure_ascii=False)
            ic("Serialized JSON result:", serialized_result)
            return make_vapi_response(call, serialized_result)
            
        except Exception as e:
            ic(f"Error getting blog post: {e}")
            return make_vapi_response(call, f"Error getting blog post: {str(e)}")
    
    elif action == "random_blog_url_only":
        import random
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

    else:
        return make_vapi_response(call, f"Unknown action: {action}")
