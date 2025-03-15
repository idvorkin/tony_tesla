# Tony the tesla

[![Python Tests](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml/badge.svg)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Unit Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-unit.json)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Integration Tests](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-integration.json)](https://github.com/idvorkin/tony_tesla/actions/workflows/python-tests.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/idvorkin/tony_tesla/test-results/test-results/python/badge-coverage.json)](https://github.com/idvorkin/tony_tesla/tree/test-results/test-results/python/coverage)

This is my callable life coach! Lots of fun idea to be played with here.

* Life Coach
* Callable Agents
* Memory


## Tech

modal deploy tony_server
point vapi server API at modal serve

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

