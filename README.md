# Tony the tesla

[![Python Tests](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml/badge.svg?cache=bust)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Unit Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-unit.json&cache=bust1)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Integration Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-integration.json&cache=bust1)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-coverage.json&cache=bust3)](https://htmlpreview.github.io/?https://github.com/idvorkin/tony_tesla/blob/test-results/test-results/python/coverage/index.html)

This is my callable life coach! Lots of fun idea to be played with here.

- Life Coach
- Callable Agents
- Memory

## Example Conversation

### Igor after a a hard day

![](https://raw.githubusercontent.com/idvorkin/ipaste/main/20250501_060212.webp)

### Igor rationalizing his car free identity with driving a Tesla

🎧 [Listen to Igor work through his identity crisis with Tony, his AI life coach](https://github.com/idvorkin/blob/raw/master/blog/bike-vs-tony.mp3)

![](https://raw.githubusercontent.com/idvorkin/ipaste/main/20250914_164425.webp)

**The Story:** Igor was a dedicated cyclist (3,000+ miles in 2022) who prided himself on being car-free. After buying a Tesla, his cycling dropped to under 30 miles. Through conversations with his AI coach Tony (with a Tony Soprano personality), Igor realized that identity isn't about rigid adherence to past choices, but staying true to core values while adapting methods. He learned to use both bicycle and Tesla based on specific needs rather than seeing them as mutually exclusive.

[Read the full story at idvork.in/bike-tesla-identity](https://idvork.in/bike-tesla-identity)

### Bob (not his real name), trying Tony for the first time

![](https://raw.githubusercontent.com/idvorkin/ipaste/main/20250501_061105.webp)

## Tech

modal deploy tony_server
point vapi server API at modal serve

### Blog tools now via MCP

The blog tools (`blog_info`, `random_blog`, `read_blog_post`, `random_blog_url`, `blog_search`) are no longer served by our FastAPI app. They are provided by the Blog MCP server instead.

- Repo: [idvorkin/idvorkin-blog-mcp](https://github.com/idvorkin/idvorkin-blog-mcp)
- Live MCP endpoint: `https://idvorkin-blog-and-repo.fastmcp.app/mcp`

To enable these in the assistant, ensure `modal_readonly/tony_assistant_spec.json` contains the MCP tool entry in `assistant.model.tools`:

```json
{
  "type": "mcp",
  "function": { "name": "mcpTools" },
  "server": {
    "url": "https://idvorkin-blog-and-repo.fastmcp.app/mcp",
    "secret": "SHOULD_BE_REPLACED_BY_ASSISTANT"
  }
}
```

If you're configuring via a generic config snippet, it should look like:

```json
{
  "tools": [
    {
      "type": "mcp",
      "function": { "name": "mcpTools" },
      "server": { "url": "https://mcp.zapier.com/api/mcp/s/********/mcp" }
    }
  ]
}
```

Notes:

- Replace `secret` at runtime; `tony_server.py` injects `x-vapi-secret` for tools.
- Remove any legacy blog endpoints; they have been deleted from this repo.

## Sequence Diagram

```mermaid
sequenceDiagram
    actor Igor as User (Igor)
    participant VAPI as VAPI Client
    participant Server as tony_server.py
    participant CosmosDB as Azure Cosmos DB
    participant ModalStorage as modal_readonly
    participant PerplexityAI as Perplexity AI

    Igor->>VAPI: Makes a phone call
    alt Initialization
        VAPI->>Server: POST request to /assistant
        Server->>ModalStorage: Read tony_assistant_spec.json
        Server->>ModalStorage: Read tony_system_prompt.md
        Server->>CosmosDB: Load starting journal context
        Server-->>VAPI: Initialize assistant with Tony's definition
    end

    alt Weather Inquiry
        Igor->>VAPI: "What's the weather like today?"
        VAPI->>Server: POST request to /search
        Server->>PerplexityAI: Interact for search operations
        Server-->>VAPI: Send weather response
        VAPI-->>Igor: Provide weather information
        note right of Igor: Tony says, "The weather is sunny with a chance of rain."
    end

    alt Gratefulness Recording
        Igor->>VAPI: "I'd like to record my gratefulness."
        VAPI->>Server: POST request to /journal_append
        Server->>CosmosDB: Interact for journal operations
        Server-->>VAPI: Confirm journal entry
        VAPI-->>Igor: Confirm gratefulness recorded
        note right of Igor: Tony says, "Your gratefulness has been recorded."
    end
```
