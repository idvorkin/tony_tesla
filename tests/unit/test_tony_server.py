from tony_server import extract_failure_reason


def test_extract_failure_reason_assistant_request_error():
    input_msg = {
        "message": {
            "timestamp": 1737157773126,
            "type": "status-update",
            "status": "ended",
            "endedReason": "assistant-request-returned-invalid-assistant",
            "inboundPhoneCallDebuggingArtifacts": {
                "error": "Couldn't Get Assistant...",
                "assistantRequestError": 'Invalid Assistant. Errors: [\n  "assistant.model.All fallbackModels\'s elements must be unique"\n]',
                "assistantRequestResponse": {"assistant": {"name": "Tony"}},
            },
        }
    }

    result = extract_failure_reason(input_msg)
    assert (
        result
        == 'Invalid Assistant. Errors: [\n  "assistant.model.All fallbackModels\'s elements must be unique"\n]'
    )


def test_extract_failure_reason_general_error():
    input_msg = {
        "message": {
            "type": "status-update",
            "status": "ended",
            "endedReason": "some-reason",
            "inboundPhoneCallDebuggingArtifacts": {"error": "General error occurred"},
        }
    }

    result = extract_failure_reason(input_msg)
    assert result == "General error occurred"


def test_extract_failure_reason_ended_reason():
    input_msg = {
        "message": {
            "type": "status-update",
            "status": "ended",
            "endedReason": "some-specific-reason",
        }
    }

    result = extract_failure_reason(input_msg)
    assert result == "some-specific-reason"


def test_extract_failure_reason_not_status_update():
    input_msg = {"message": {"type": "something-else", "status": "ended"}}

    result = extract_failure_reason(input_msg)
    assert result is None


def test_extract_failure_reason_not_ended():
    input_msg = {"message": {"type": "status-update", "status": "in-progress"}}

    result = extract_failure_reason(input_msg)
    assert result is None


def test_extract_failure_reason_empty_input():
    input_msg = {}
    result = extract_failure_reason(input_msg)
    assert result is None
