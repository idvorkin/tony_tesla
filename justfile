#!python3

set export
tony_server := "tony_server.py"

default:
    @just --list

# Required for pre-commit hook
fast-test:
    @echo "Fast tests - Environment needs setup. Use 'just install' then 'uv pip install -e .[dev]' first."

install:
    uv pip install --editable .

global-install: install
    uv tool install --force --editable .

run-dev-server:
    modal serve {{tony_server}}::modal_app
deploy:
    uv run modal deploy {{tony_server}}::modal_app

test-assistant:
    echo '{"message": {"type": "assistant-request"}}' | http POST https://idvorkin--modal-tony-server-fastapi-app.modal.run/assistant \
        x-vapi-secret:$TONY_API_KEY

test-assistant-dev:
    echo '{"message": {"type": "assistant-request"}}' | http POST https://idvorkin--modal-tony-server-dev-fastapi-app.modal.run/assistant \
        x-vapi-secret:$TONY_API_KEY

test-read:
    http POST https://idvorkin--modal-tony-server-journal-read.modal.run date="the cat in the hat" \
        x-vapi-secret:$TONY_API_KEY \

test-append:
    http POST https://idvorkin--modal-tony-server-fastapi-app.modal.run/journal-append content="ignore this entry" \
        x-vapi-secret:$TONY_API_KEY \

# Test commands
test:
test-debug:
    uv run pytest -v

test-coverage:
    uv run pytest -n auto --cov=. --cov-report=xml --cov-report=term-missing

test-unit:
    uv run pytest tests/unit -n auto

test-integration:
    uv run pytest tests/integration -n auto --dist loadscope -v

test-e2e:
    uv run pytest tests/e2e -n auto

test-send-text:
    http POST https://idvorkin--modal-tony-server-fastapi-app.modal.run/send-text \
        x-vapi-secret:$TONY_API_KEY \
        text="Test message" \
        to_number="+12068904339"

search query="what is the weather in seattle":
    http POST https://idvorkin--modal-tony-server-fastapi-app.modal.run/search \
        x-vapi-secret:$TONY_API_KEY \
        question="{{query}}" | jq -r '.results[0].result' | /bin/cat

logs:
    modal app logs modal-tony-server | /bin/cat

