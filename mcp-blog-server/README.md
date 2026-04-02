# MCP Blog Server

A Python-based MCP (Model Context Protocol) server for Igor's blog operations, built with FastMCP. Can be deployed locally or to FastMCP cloud hosting.

## Features

The server provides the following tools:

- **blog_info**: Get information about all blog posts including URLs, titles, and descriptions
- **random_blog**: Get the full content of a random blog post
- **read_blog_post**: Get the content of a specific blog post by markdown path or URL
- **random_blog_url**: Get just the URL and title of a random blog post without its content  
- **blog_search**: Search blog posts using keywords with Algolia

## Installation

### Prerequisites

- Python 3.8 or higher
- uv (recommended) or pip

### Setup with uv (Recommended)

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone or navigate to the repository:
```bash
cd mcp-blog-server
```

3. Run directly with uv (auto-installs dependencies):
```bash
./blog_mcp_server.py
```

### Setup with pip (Alternative)

1. Clone or navigate to the repository:
```bash
cd mcp-blog-server
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Local Development

With uv (auto-installs dependencies):
```bash
./blog_mcp_server.py
```

Or with Python directly:
```bash
python blog_mcp_server.py
```

### Cloud Deployment (FastMCP Hosting)

1. **Deploy to FastMCP Cloud:**
   ```bash
   # Install FastMCP CLI if not already installed
   pip install fastmcp-cli
   
   # Deploy the server
   fastmcp deploy ./mcp-blog-server
   ```

2. **Your server will be available at:**
   ```
   https://api.fastmcp.com/v1/servers/[your-username]/blog-server
   ```

3. **Connect from Claude Desktop:**
   Add to your configuration:
   ```json
   {
     "mcpServers": {
       "blog-server": {
         "url": "https://api.fastmcp.com/v1/servers/[your-username]/blog-server"
       }
     }
   }
   ```

### Integration with Claude Desktop (Local)

Add the following to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

With uv (recommended):
```json
{
  "mcpServers": {
    "blog-server": {
      "command": "/path/to/mcp-blog-server/blog_mcp_server.py"
    }
  }
}
```

Or with Python:
```json
{
  "mcpServers": {
    "blog-server": {
      "command": "python",
      "args": ["/path/to/mcp-blog-server/blog_mcp_server.py"]
    }
  }
}
```

### Integration with Other MCP Clients

The server communicates via stdio and is compatible with any MCP client that supports the protocol.

## Tool Documentation

### blog_info()
Returns a JSON array of all blog posts with their metadata.

**Example Response:**
```json
[
  {
    "url": "https://idvork.in/vim",
    "title": "Vim Tips",
    "description": "Essential vim commands and tricks",
    "markdown_path": "_d/vim_tips.md"
  }
]
```

### random_blog()
Returns the full content of a randomly selected blog post.

**Example Response:**
```json
{
  "content": "# Blog Post Content...",
  "title": "Post Title",
  "url": "https://idvork.in/path",
  "markdown_path": "_d/post.md"
}
```

### read_blog_post(path)
Fetches a specific blog post by its path.

**Parameters:**
- `path` (string): Markdown file path (e.g., '_d/vim_tips.md') or URL path (e.g., '/vim')

**Example Response:**
```json
{
  "content": "# Blog Post Content...",
  "markdown_path": "_d/vim_tips.md"
}
```

### random_blog_url()
Returns just the URL and title of a random blog post.

**Example Response:**
```json
{
  "title": "Post Title",
  "url": "https://idvork.in/path"
}
```

### blog_search(query)
Searches blog posts using Algolia search.

**Parameters:**
- `query` (string): Search query

**Example Response:**
```json
[
  {
    "title": "Matching Post",
    "url": "https://idvork.in/path",
    "content": "Content snippet...",
    "collection": "main"
  }
]
```

## Configuration

The server is configured to access:
- **GitHub Repository**: `idvorkin/idvorkin.github.io`
- **Blog URL**: `https://idvork.in`
- **Algolia Search**: Pre-configured with search-only API keys (public, safe to expose)

### Environment Variables

For local development, copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

- `FASTMCP_ENV`: Set to "production" when deployed to FastMCP cloud
- The Algolia API keys included are search-only public keys and are safe to use

## Testing

### Running E2E Tests

The project includes comprehensive end-to-end tests that verify all functionality:

```bash
# Run all tests
./run_tests.sh

# Run with verbose output
./run_tests.sh -v

# Run quietly
./run_tests.sh -q

# Or directly with pytest
uv run pytest test_blog_mcp_e2e.py -v
```

The tests verify:
- All tool functions work correctly
- Blog content is accessible
- Search functionality works
- Error handling is proper
- Algolia and GitHub APIs are accessible

## Development

### Testing Individual Tools

You can test the server using the MCP inspector or by sending test messages via stdio:

```bash
# Start the server
./blog_mcp_server.py

# In another terminal, you can use mcp-cli or similar tools to test
```

### Modifying the Server

The main server code is in `blog_mcp_server.py`. The FastMCP framework handles:
- Protocol communication via stdio
- Tool registration and discovery
- Request/response handling

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you've installed all requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. **Connection issues**: Verify the GitHub repository is accessible and the backlinks.json file exists

3. **Search not working**: The Algolia API keys are read-only and specific to the blog index

## License

MIT