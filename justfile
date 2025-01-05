# what is the syntax here - is it just toml

set export
tony_server := "tony_server.py"

install:
    uv pip install --editable .

global-install: install
    pipxu install -f . --editable --python $(which python3.12)

run-dev-server:
    modal serve {{tony_server}}::modal_app
deploy:
    modal deploy {{tony_server}}::modal_app

test-assistant:
    http POST https://idvorkin--modal-tony-server-assistant.modal.run notused="the cat in the hat" \
        x-vapi-secret:$TONY_API_KEY \

test-assistant-dev:
    http POST https://idvorkin--modal-tony-server-assistant-dev.modal.run notused="the cat in the hat" \
        x-vapi-secret:$TONY_API_KEY \

test-read:
    http POST https://idvorkin--modal-tony-server-journal-read.modal.run date="the cat in the hat" \
        x-vapi-secret:$TONY_API_KEY \

test-append:
    http POST https://idvorkin--modal-tony-server-journal-append.modal.run content="ignore this entry" \
        x-vapi-secret:$TONY_API_KEY \

test-blog-info:
    http POST https://idvorkin--modal-blog-server-blog-handler.modal.run \
        x-vapi-secret:$TONY_API_KEY

test-random-blog:
    http POST https://idvorkin--modal-blog-server-blog-handler.modal.run \
        x-vapi-secret:$TONY_API_KEY

test-read-blog-post:
    http POST https://idvorkin--modal-blog-server-read-blog-post.modal.run \
        x-vapi-secret:$TONY_API_KEY \
        path="_d/vim_tips.md"

deploy-all:
    just deploy
    just deploy-blog

deploy-blog:
    modal deploy blog_server.py::modal_app

run-dev-blog-server:
    modal serve blog_server.py

test-random-blog-url:
    http POST https://idvorkin--modal-blog-server-blog-handler.modal.run \
        x-vapi-secret:$TONY_API_KEY

# Test commands
test:
    pytest -n auto

test-debug:
    pytest -v

test-coverage:
    pytest -n auto --cov=. --cov-report=term-missing

test-unit:
    pytest tests/unit -n auto

test-integration: 
    pytest tests/integration -n auto --dist loadscope -v

test-e2e:
    pytest tests/e2e -n auto

search query="what is the weather in seattle":
    http POST https://idvorkin--modal-tony-server-fastapi-app.modal.run/search \
        x-vapi-secret:$TONY_API_KEY \
        question="{{query}}" | jq -r '.results[0].result'

blog-search query="Untangled":
    http POST https://idvorkin--modal-blog-server-fastapi-app.modal.run/blog_search \
        x-vapi-secret:$TONY_API_KEY \
        query="{{query}}" | jq -r '.results[0].result | fromjson | .[] | "Title: \(.title)\nURL: \(.url)\nContent: \(.content)\n"'

blog-info:
    http POST https://idvorkin--modal-blog-server-fastapi-app.modal.run/blog_info \
        x-vapi-secret:$TONY_API_KEY \
        <<< '{}'
