#!uv run
/// script
dependencies = [
    "fastapi", # fastmcp might still need/use some fastapi components or it's good to keep for uvicorn
    "modal",
    "pydantic", # fastmcp likely uses pydantic
    "icecream",
    "fastmcp",  # Changed from mcp
    "starlette" # Added for middleware
]
///

import os
from modal import App, Image, Secret, asgi_app
from fastmcp import FastMCP # Changed from mcp.server.fastmcp
# Starlette imports for middleware
from starlette.middleware import Middleware # For constructing middleware list
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request # Use Starlette's Request
from starlette.responses import Response

# Constants for API key and secret - ensure these are correctly defined and used
TONY_API_KEY_NAME = "TONY_API_KEY" # Environment variable name for the server's secret
X_VAPI_SECRET = "x-vapi-secret"    # Header name for the client's secret

# Modal Image definition
default_image = Image.debian_slim().pip_install(
    "fastapi", # For uvicorn, and fastmcp might depend on it
    "uvicorn",
    "pydantic",
    "icecream",
    "python-dotenv",
    "fastmcp",  # Changed from mcp
    "starlette" # Added
)

# Modal App instance
modal_app = App("fortune-mcp-server", image=default_image)

# Authentication Middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow MCP discovery/listing without auth, if desired, by checking request.url.path
        # For now, all paths under this app, including /mcp, will be authenticated.
        # FastMCP typically serves on /mcp, so requests to /mcp/tools.list will also be authenticated.
        # If FastMCP's list_tools is implicitly available at a path that should be unauthenticated,
        # this logic would need adjustment (e.g. if request.url.path == "/mcp" and body indicates list_tools).
        # However, the prompt implies general header auth for the service.

        expected_secret = os.environ.get(TONY_API_KEY_NAME)
        if not expected_secret:
            # Log this issue for server admin
            print(f"CRITICAL: Authentication secret {TONY_API_KEY_NAME} is not configured on the server.")
            return Response("Internal server error: Auth secret not configured", status_code=500)

        client_secret = request.headers.get(X_VAPI_SECRET)
        if not client_secret or client_secret != expected_secret:
            # Log failed auth attempt (optional, consider security implications)
            # print(f"Failed auth attempt: client_secret {'present' if client_secret else 'missing'}")
            return Response("Unauthorized", status_code=401)
        
        response = await call_next(request)
        return response

# Instantiate FastMCP server
mcp = FastMCP(
    "FortuneServer", # Name of the MCP service
    title="Fortune MCP Server", 
    description="Provides fortunes via MCP.",
    # prefix="/mcp" # This is the default in fastmcp
)

# Define the fortune tool using the @mcp.tool decorator
@mcp.tool(
    name="fortune", 
    title="Fortune Teller", 
    description="Tells you your fortune."
    # input_schema is inferred from type hints (none for this simple tool)
    # output_schema is inferred from return type hint (str for this simple tool)
)
async def get_fortune() -> str:
    """
    This tool returns a simple fortune string.
    It takes no arguments.
    """
    return "You are going to hvae a great day"

# Configure ASGI App with Middleware for Modal
# The list of middleware to apply
auth_middleware_config = [Middleware(AuthMiddleware)]

# Get the Starlette ASGI app from FastMCP, with middleware applied
# FastMCP's http_app() creates a Starlette application.
mcp_asgi_app = mcp.http_app(middleware=auth_middleware_config)


@modal_app.function(
    secrets=[Secret.from_dotenv(__file__)], # Loads .env for TONY_API_KEY_NAME
    # gpu="any",
    # keep_warm=1,
    # allow_concurrent_inputs=10,
    # timeout=600,
)
@asgi_app()
def fastapi_app(): # Name can remain fastapi_app, or change to something like 'mcp_app_entrypoint'
    # This now returns the FastMCP Starlette app, wrapped with auth middleware
    return mcp_asgi_app
