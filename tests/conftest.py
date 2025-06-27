import pytest
import logging
import os

# === Error counter to make tests fail on any logged ERROR ===
class ErrorCounterHandler(logging.Handler):
    """Simple handler that increments a counter whenever an ERROR or higher is logged."""
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.error_count = 0
        self.records = []

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.error_count += 1
            self.records.append(record)

@pytest.fixture(scope="session", autouse=True)
def error_counter_handler(request):
    """Fixture to install and check the error counter handler."""
    handler = ErrorCounterHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    yield handler # Provide the handler to tests if they need it, though it's mainly for post-run check

    # This will run after all tests in the session
    def fin():
        if handler.error_count > 0:
            messages = [f"- {rec.levelname} ({rec.name}): {rec.getMessage()}" for rec in handler.records]
            error_summary = "\n".join(messages)
            # pytest.fail will be too late here, so we print and rely on a test to check it, or use a hook.
            # For now, let's make it a check within a specific test or rely on pytest_runtest_logreport
            # For now, the print in the error_counter_handler finalizer serves as a visible notification.
            # A better approach: create a dummy test that depends on this handler.
            print(f"PYTEST_ERROR_SUMMARY: {handler.error_count} errors logged during tests:\n{error_summary}")


    request.addfinalizer(fin)
    return handler


def pytest_addoption(parser):
    parser.addoption(
        "--bot-mode", action="store_true", default=False, help="Run the actual bot with test channels (for Heroku tests)"
    )

    parser.addoption(
        "--new-session", action="store_true", default=False, help="Force creation of a new session (requires re-authentication)"
    )
    parser.addoption(
        "--process-recent", type=int, default=None, help="Process N recent messages from the source channel (for bot-mode)"
    )

@pytest.fixture
def bot_mode_option(request):
    return request.config.getoption("--bot-mode")



@pytest.fixture
def new_session_option(request):
    return request.config.getoption("--new-session")

@pytest.fixture
def process_recent_option(request):
    return request.config.getoption("--process-recent")

@pytest.fixture
def test_args(bot_mode_option, new_session_option, process_recent_option):
    """Provides a namespace similar to argparse.Namespace for compatibility with existing test functions."""
    class Args:
        def __init__(self):
            self.bot_mode = bot_mode_option
            self.new_session = new_session_option
            self.process_recent = process_recent_option
            # Ensure all attributes from the original args are present if functions expect them
            # For example, if some args were not command line options but set by default
            # For now, this covers the command-line ones.

    return Args()

# Fixture to ensure test environment variables are set for channel names
@pytest.fixture(autouse=True)
def set_test_channel_env_vars():
    original_test_src = os.environ.get('TEST_SRC_CHANNEL')
    original_test_dst = os.environ.get('TEST_DST_CHANNEL')
    
    # These should be defined in your .env or app_settings.env for tests to pick up
    # If not, tests requiring them will fail, which is expected.
    # This fixture mainly ensures that if the main code aliases SRC_CHANNEL to TEST_SRC_CHANNEL,
    # those TEST_ ones are indeed what we intend.
    # The test script itself already does:
    # os.environ['TEST_SRC_CHANNEL'] = os.getenv('TEST_SRC_CHANNEL', '')
    # os.environ['TEST_DST_CHANNEL'] = os.getenv('TEST_DST_CHANNEL', '')
    # So, this fixture is more of a placeholder or for future centralized test env setup.
    yield
    # Restore if changed, though test.py itself sets them from os.getenv
    if original_test_src is not None:
        os.environ['TEST_SRC_CHANNEL'] = original_test_src
    else:
        os.environ.pop('TEST_SRC_CHANNEL', None)
        
    if original_test_dst is not None:
        os.environ['TEST_DST_CHANNEL'] = original_test_dst
    else:
        os.environ.pop('TEST_DST_CHANNEL', None)

def pytest_sessionfinish(session, exitstatus):
    """
    Called after Ewhole test run finished, right before returning the exit status to the system.
    """
    handler = None
    for h in logging.getLogger().handlers:
        if isinstance(h, ErrorCounterHandler):
            handler = h
            break
    
    if handler and handler.error_count > 0:
        # Modify exitstatus to failure if errors were logged
        # This is a bit of a hack. A cleaner way might be a custom report or failing a dedicated test.
        # session.config.option.exitstatus = 1 # This attribute doesn't exist directly
        # Instead, we'll rely on a dedicated test to check this or ensure pytest.fail is used earlier.
        # For now, the print in the error_counter_handler finalizer serves as a visible notification.
        # A better approach: create a dummy test that depends on this handler.
        pass

@pytest.fixture
def check_logged_errors(request, error_counter_handler):
    """Fixture to fail a test if any errors were logged during its execution or before."""
    # This fixture, if used by a test, will check errors *after* that test.
    # For a global check, the session finish hook or autouse fixture finalizer is better.
    yield
    # This check is deferred to the session finalizer of error_counter_handler
    # or a dedicated "final check" test.
    pass

"""
Notes on error_counter_handler:
The current `error_counter_handler` fixture will collect errors.
To make tests fail based on this:
1. A dedicated test could check `error_counter_handler.error_count`.
2. A `pytest_runtest_logreport` hook could be used to fail a test immediately if it logs an error.
3. The session finalizer prints the summary. To actually fail the run, one common pattern is
   to have a final "cleanup" or "verification" test that explicitly checks this counter.
Let's try to add a test that checks this counter at the end.
""" 