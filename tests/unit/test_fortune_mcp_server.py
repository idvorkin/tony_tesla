import pytest
from starlette.testclient import TestClient  # Changed from fastapi.testclient

# Import the configured Starlette ASGI app and constants from the server file
from fortune_mcp_server import (
    mcp_asgi_app,
    TONY_API_KEY_NAME,
    X_VAPI_SECRET as X_VAPI_SECRET_HEADER_NAME_CONST,
)

# MCP_ENDPOINT_PATH is typically /mcp by default in fastmcp
MCP_ENDPOINT_PATH = "/mcp"

client = TestClient(mcp_asgi_app)


# Helper to create consistent MCP request bodies
def _mcp_request_body(method: str, params: dict = None, request_id: str = "1"):
    payload = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params:
        payload["params"] = params
    return payload


# --- Tests for tools/list ---


def test_list_tools_success(monkeypatch):
    """Tests successful listing of tools with correct authentication."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: test_secret},
        json=_mcp_request_body(method="tools/list"),
    )
    assert response.status_code == 200
    response_json = response.json()

    assert response_json.get("jsonrpc") == "2.0"
    assert response_json.get("id") == "1"
    assert "result" in response_json
    assert "error" not in response_json

    result = response_json["result"]
    assert isinstance(result, list)
    assert len(result) == 1

    tool = result[0]
    assert tool["name"] == "fortune"
    assert tool["title"] == "Fortune Teller"
    assert tool["description"] == "Tells you your fortune."
    # For fastmcp with no input args, inputSchema might be empty or default.
    # Let's assume it might be missing or an empty dict. If it's strictly defined, adjust.
    assert tool.get("inputSchema", {}) == {}  # Or specific if fastmcp generates one
    assert tool.get("outputSchema") == {"type": "string"}


def test_list_tools_auth_failure_wrong_secret(monkeypatch):
    """Tests tools/list auth failure due to wrong secret."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: "wrong_secret_value"},
        json=_mcp_request_body(method="tools/list"),
    )
    assert response.status_code == 401
    assert response.text == "Unauthorized"


def test_list_tools_auth_failure_missing_header(monkeypatch):
    """Tests tools/list auth failure due to missing auth header."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        # No auth header
        json=_mcp_request_body(method="tools/list"),
    )
    assert response.status_code == 401
    assert response.text == "Unauthorized"


def test_list_tools_server_secret_misconfigured(monkeypatch):
    """Tests tools/list error when server-side API key (secret) is not configured."""
    monkeypatch.delenv(TONY_API_KEY_NAME, raising=False)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: "any_secret_value"},
        json=_mcp_request_body(method="tools/list"),
    )
    assert response.status_code == 500
    assert response.text == "Internal server error: Auth secret not configured"


# --- Tests for tools/call (fortune tool) ---


def test_call_fortune_tool_success(monkeypatch):
    """Tests successful call to the 'fortune' tool with correct authentication."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: test_secret},
        json=_mcp_request_body(
            method="tools/call", params={"name": "fortune", "arguments": {}}
        ),  # arguments: {} for no-arg tool
    )
    assert response.status_code == 200
    response_json = response.json()

    assert response_json.get("jsonrpc") == "2.0"
    assert response_json.get("id") == "1"
    assert "result" in response_json
    assert (
        response_json["result"] == "You are going to hvae a great day"
    )  # fastmcp returns tool output directly
    assert "error" not in response_json


def test_call_fortune_tool_auth_failure_wrong_secret(monkeypatch):
    """Tests tools/call auth failure due to wrong secret."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: "wrong_secret_value"},
        json=_mcp_request_body(
            method="tools/call", params={"name": "fortune", "arguments": {}}
        ),
    )
    assert response.status_code == 401
    assert response.text == "Unauthorized"


def test_call_fortune_tool_auth_failure_missing_header(monkeypatch):
    """Tests tools/call auth failure due to missing auth header."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        # No auth header
        json=_mcp_request_body(
            method="tools/call", params={"name": "fortune", "arguments": {}}
        ),
    )
    assert response.status_code == 401
    assert response.text == "Unauthorized"


def test_call_tool_server_secret_misconfigured(monkeypatch):
    """Tests tools/call error when server-side API key (secret) is not configured."""
    monkeypatch.delenv(TONY_API_KEY_NAME, raising=False)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: "any_secret_value"},
        json=_mcp_request_body(
            method="tools/call", params={"name": "fortune", "arguments": {}}
        ),
    )
    assert response.status_code == 500
    assert response.text == "Internal server error: Auth secret not configured"


def test_call_unknown_tool(monkeypatch):
    """Tests calling an unknown tool with correct authentication."""
    test_secret = "super_secret_key"
    monkeypatch.setenv(TONY_API_KEY_NAME, test_secret)

    response = client.post(
        MCP_ENDPOINT_PATH,
        headers={X_VAPI_SECRET_HEADER_NAME_CONST: test_secret},
        json=_mcp_request_body(
            method="tools/call", params={"name": "unknown_tool_name", "arguments": {}}
        ),
    )
    assert (
        response.status_code == 200
    )  # Request is authenticated, MCP handles the tool not found
    response_json = response.json()

    assert response_json.get("jsonrpc") == "2.0"
    assert response_json.get("id") == "1"
    assert "error" in response_json
    assert "result" not in response_json

    error_details = response_json["error"]
    assert (
        error_details["code"] == -32601
    )  # Standard JSON-RPC error code for Method not found
    assert (
        "Method not found" in error_details["message"]
    )  # fastmcp might add more detail
    # Example: "Method not found: Tool 'unknown_tool_name' not registered."
    assert (
        "unknown_tool_name" in error_details.get("data", {}).get("details", "")
        or "unknown_tool_name" in error_details["message"]
    )


pytest.main(["-v"])
