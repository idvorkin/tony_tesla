"""
Shared utilities and functions used by both tony_server and blog_server.
This module contains common code to avoid duplication and import dependencies.
"""

import os
import uuid
from typing import Dict
from fastapi import HTTPException, Request, status
from pydantic import BaseModel
from icecream import ic
from modal import Image

# Constants
TONY_API_KEY_NAME = "TONY_API_KEY"
X_VAPI_SECRET = "x-vapi-secret"

# Modal image configuration for blog server
modal_storage = "modal_readonly"
blog_image = (
    Image.debian_slim(python_version="3.12")
    .pip_install(
        [
            "icecream",
            "requests",
            "pydantic",
            "fastapi[standard]",
        ]
    )
    .add_local_file("shared.py", remote_path="/root/shared.py")
    .add_local_dir(modal_storage, remote_path="/" + modal_storage)
)


class FunctionCall(BaseModel):
    id: str
    name: str
    args: Dict


def make_vapi_response(call: FunctionCall, result: str):
    """Create a VAPI response format"""
    return {"results": [{"toolCallId": call.id, "result": result}]}


def parse_tool_call(function_name, params: Dict) -> FunctionCall:
    """Parse the call from VAPI or from the test tool."""
    # Handle simple format (used in tests and justfile commands)
    if not params.get("message"):
        args = {k: v for k, v in params.items() if v is not None}
        return FunctionCall(id=str(uuid.uuid4()), name=function_name, args=args)

    # Handle VAPI format
    message = params["message"]
    toolCalls = message.get("toolCalls", [])
    if not toolCalls:
        # If no toolCalls in message, treat the entire params as args
        return FunctionCall(id=str(uuid.uuid4()), name=function_name, args=params)

    tool = toolCalls[-1]
    return FunctionCall(
        id=tool["id"],
        name=tool["function"]["name"],
        args=tool["function"]["arguments"],
    )


def raise_if_not_authorized(headers: Dict):
    """Check if the request is authorized with the correct API key"""
    token = headers.get(X_VAPI_SECRET, "")
    if not token:
        ic(headers)
    if token != os.environ[TONY_API_KEY_NAME]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_headers(request: Request):
    """Extract headers from FastAPI request"""
    ic(dict(request.headers))
    return request.headers
