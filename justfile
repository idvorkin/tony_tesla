# what is the syntax here - is it just toml

set export
tony_server := "tony_server.py"

run-dev-server:
    modal serve {{tony_server}}
deploy:
    modal deploy {{tony_server}}

test-assistant:
    http POST https://idvorkin--modal-tony-server-assistant.modal.run notused="the cat in the hat"

test-prod-search:
    http POST https://idvorkin--modal-tony-server-search.modal.run \
        x-vapi-secret:$TONY_API_KEY \
        question="What is the weather in moscow"

test-dev-search:
    http POST https://idvorkin--modal-tony-server-search-dev.modal.run \
        x-vapi-secret:$TONY_API_KEY \
        question="What is the weather in moscow"
