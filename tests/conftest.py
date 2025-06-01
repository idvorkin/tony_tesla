import os
import pytest


@pytest.fixture(autouse=True)
def setup_test_environment(request):
    """Set up test environment variables for unit and integration tests.
    
    E2E tests are skipped to allow them to use real environment variables.
    """
    # Skip environment setup for e2e tests - they need real API keys
    if "e2e" in request.node.nodeid:
        yield
        return
        
    original_environ = dict(os.environ)

    # Set up test environment variables
    os.environ["TONY_API_KEY"] = "test_secret"
    os.environ["PPLX_API_KEY"] = "test_pplx_key"
    os.environ["ONEBUSAWAY_API_KEY"] = "test_onebusaway_key"
    os.environ["TONY_STORAGE_SERVER_API_KEY"] = "test_storage_key"
    os.environ["TWILIO_ACCOUNT_SID"] = "test_twilio_sid"
    os.environ["TWILIO_AUTH_TOKEN"] = "test_twilio_token"
    os.environ["TWILIO_FROM_NUMBER"] = "+13203734339"
    os.environ["IFTTT_WEBHOOK_KEY"] = "test_key"
    os.environ["IFTTT_WEBHOOK_SMS_EVENT"] = "test_event"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_environ)
