#!/bin/bash
# Test runner for MCP Blog Server

set -e

echo "🧪 Running MCP Blog Server E2E Tests"
echo "===================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Run tests with different verbosity levels
if [ "$1" == "-v" ] || [ "$1" == "--verbose" ]; then
    echo "Running in verbose mode..."
    TEST_VERBOSE=true uv run pytest test_blog_mcp_e2e.py -v -s
elif [ "$1" == "-q" ] || [ "$1" == "--quiet" ]; then
    echo "Running in quiet mode..."
    uv run pytest test_blog_mcp_e2e.py -q
else
    echo "Running standard tests..."
    uv run pytest test_blog_mcp_e2e.py
fi

echo ""
echo "✅ Tests completed!"