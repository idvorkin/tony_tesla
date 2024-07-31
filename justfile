# what is the syntax here - is it just toml

tony_server := "tony_server.py"

run-dev-server:
    modal serve {{tony_server}}
deploy:
    modal deploy {{tony_server}}

test-assistant:
    http POST https://idvorkin--modal-tony-server-assistant.modal.run notused="the cat in the hat"

test-prod-search:
    http POST https://idvorkin--modal-tony-server-search.modal.run question="What is the weather in moscow"

test-dev-search:
    http POST https://idvorkin--modal-tony-server-search-dev.modal.run question="What is the weather in moscow"
