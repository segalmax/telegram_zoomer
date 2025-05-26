# Telegram News-to-Zoomer Bot - Project Tasks

## MVP Core Functionality
- [x] Basic bot script (`bot.py`)
- [x] Telegram client connection and authentication
- [x] Listen to `SRC_CHANNEL` for new messages
- [x] Extract text from messages
- [x] Basic error handling and logging

## Translation Module (`translator.py`)
- [x] Connect to OpenAI API
- [x] Implement translation function for "right" style
- [x] Allow selection of translation style (`TRANSLATION_STYLE` env var: `left`, `right`, `both`)
- [x] Add source attribution (original NYT link) to translations
- [x] Balance factual information with humor and sarcasm
- [x] Add Artemiy Lebedev style imitation for RIGHT translations
- [x] Increase temperature (0.85) for more creative and entertaining output

## Image Generation Module (`image_generator.py`)
- [x] Connect to OpenAI API (DALL-E)
- [x] Generate image based on post content
- [x] Option to disable image generation (`GENERATE_IMAGES` env var)
- [x] Integrate with Stability AI as an alternative
    - [x] Add `USE_STABILITY_AI` env var
    - [x] Focus on cartoon/caricature styles without text
    - [x] Optimize for exaggerated political figures with symbolic elements
    - [x] Create editorial cartoon-style visuals

## Posting to Destination
- [x] Post translated text to `DST_CHANNEL`
- [x] Post generated image along with translation
    - [x] Handle image as file upload
    - [x] Handle image as URL
- [x] Correctly format posts with RIGHT-BIDLO header followed by translated content
- [x] Handle Telegram message length limits (e.g., for captions)

## Batch Processing
- [x] Implement CLI argument `--process-recent N` to fetch and translate N last posts
- [x] Add timeouts and error handling for batch processing
- [x] Ensure each article is processed separately (no combining multiple news items)

## Reliability & Maintainability
- [x] Robust error handling throughout the application
- [x] Clear logging for diagnostics
- [x] Fix "database is locked" SQLite error (session file access)
- [x] Implement a keep-alive/ping mechanism for the Telegram connection
- [x] Multiple strategies for handling missed events:
    - [x] Periodic client.catch_up() calls to force update retrieval
    - [x] Manual channel polling with GetChannelDifferenceRequest for large channels
    - [x] Background tasks to check for new messages if events are missed
    - [x] Use UpdateStatusRequest to keep connections alive and receiving updates
    - [x] **Tests now fail automatically if *any* `ERROR` is logged** (added `_ErrorCounterHandler` in `test.py`)
    - [x] **Fixed OpenAI parameter typo** (`max_tokens` instead of `max_completion_tokens`) to eliminate `400 BadRequest` during translation
    - [x] **Image generation toggle (`GENERATE_IMAGES`) now evaluated at runtime** so CLI `--no-images` works even after modules are imported
    - [x] **Removed retry mechanism** from translation to expose errors immediately rather than hiding them
    - [x] **Added input validation for image generation** to properly handle short/test messages
    - [x] **Fixed await for get_peer_id** calls in the test.py to eliminate RuntimeWarnings
    - [x] **Enhanced test robustness** with more descriptive test content that meets APIs' requirements
    - [x] **Improved message formatting** by combining header with content instead of sending separate messages
    - [x] **Reverted to support both translation styles** (`TRANSLATION_STYLE=both`) for complete functionality
    - [x] **Implemented gzip compression for session data** to work within Heroku's 64KB config var size limit
    - [x] **Enhanced environment variable handling** with dual .env file support (`.env` for secrets, `app_settings.env` for settings)
    - [x] **Improved Heroku deployment script** to handle both .env files and compressed session data
    - [x] **Enhanced message entity processing** to extract and include links from Telegram messages:
        - [x] Identifies and extracts URLs from message entity objects
        - [x] Includes article links in the output alongside the original message link
        - [x] Added proper testing with Telegram message entities
        - [x] Updates translator prompts to clarify link handling
    - [x] **Implemented environment-aware session handling** to prevent session conflicts:
        - [x] Automatically detects if running on Heroku vs local environment
        - [x] Uses different session names based on environment
        - [x] Prevents "used from multiple IP addresses" authentication errors
        - [x] Allows easy local testing without interfering with production
- [x] Implement persistent session handling to avoid frequent re-authentication
- [x] Comprehensive end-to-end automated testing
- [x] **Test Organization (Partial Task 17 - COMPLETED)**:
    - [x] Moved all tests to `tests/` directory with proper structure
    - [x] Created comprehensive `tests/README.md` documentation
    - [x] Fixed import paths and pytest compatibility
    - [x] Updated main `README.md` with new test structure
    - [x] All tests passing including shell script integration test
- [ ] Code cleanup and organization (ongoing)
- [x] Test Harness Improvement (TDD Style with Pytest):
    - [x] Create `tests/` directory and move test script to `tests/test_e2e_unified.py`.
    - [x] Implement `tests/conftest.py` for command-line options and shared fixtures (e.g., `test_args`, error handler).
    - [x] Refactor `tests/test_e2e_unified.py` to use `pytest` test functions and fixtures.
        - [x] Separate test scenarios (API, Telegram pipeline, Bot mode) into distinct `pytest` test functions.
        - [x] Adapt argument parsing to use `pytest` options.
        - [x] Integrate `ErrorCounterHandler` to fail tests if errors are logged globally.
        - [x] **Successfully converted to pytest-based TDD harness** - tests run green with same functionality as original `test.py`
        - [x] **Fixed f-string syntax error** in message verification logging
        - [x] **Maintained all original test capabilities** including bot mode, stability AI, and session management
        - [x] **Created VS Code/Cursor test configuration** - one-click test execution with detailed logging via `.vscode/launch.json`, `tasks.json`, and `settings.json`
    - [ ] Further refactor tests for granularity (e.g., separate API tests, Telegram client interaction tests).
    - [ ] Introduce unit tests with mocking for core components (e.g., `translator.py`, `image_generator.py`).

## Configuration
- [x] Use `.env` file for all configurations
- [x] Document all required environment variables in `README.md`

## Deployment & Operations
- [x] Basic `README.md` with setup and run instructions (reviewed/updated)
- [x] Heroku deployment configuration
    - [x] Procfile for worker process
    - [x] runtime.txt for Python version (3.10.12)
    - [x] Session persistence via `session_manager.py` for Heroku's ephemeral filesystem
    - [x] Environment-based session storage (using base64-encoded session data)
    - [x] Optimized authentication flow to use saved session without code prompts
- [x] Background keep-alive processes to maintain Telegram connection
- [x] End-to-end automated tests with Telegram authentication

## Task 12: Improve Post Quality ✅ COMPLETED
- [x] **Remove RIGHT-BIDLO header** - Cleaner post presentation without redundant headers
- [x] **Simplify translation style** - Streamlined to use only right-bidlo style for consistency
- [x] **Add safety check for translations** - Second LLM call to verify content appropriateness before posting
- [x] **Fix duplicate links issue** - Resolved duplicate "Оригинал" links, clean two-link structure
- [x] **Format links as hyperlinks** - Proper markdown hyperlinks hiding full URLs
- [x] **Upgrade translation model** - Migrated to Claude Sonnet 4 (May 2025) for superior translation quality

## Heroku Deployment Status
- [x] **Successfully deployed to Heroku**
- [x] **Compressed Session Handling**: Implemented gzip compression for session string to fit within Heroku's 64KB config var size limit
  - Session string compressed from ~28KB to ~1KB
  - Using `TG_COMPRESSED_SESSION_STRING` instead of `TG_SESSION_STRING`
  - Automatic fallback to uncompressed string if available
- [x] **Split Environment Configuration**: 
  - `.env` file for secrets (API keys, auth tokens)
  - `app_settings.env` for non-secret configuration (channels, features, session path)
  - Ensures sensitive data remains protected while settings are accessible
- [x] **Automated Heroku Setup**: Enhanced `setup_heroku.sh` script
  - Reads both `.env` and `app_settings.env` 
  - Sets all environment variables in Heroku
  - Compresses and exports session string
  - Removes obsolete variables
- [x] **Environment Loading**: All scripts now load from both config files
  - First `app_settings.env` with override=True for app settings
  - Then `.env` with override=False for secrets
- [x] **Runtime Feature Toggles**: Both `TRANSLATION_STYLE` and `GENERATE_IMAGES` can be changed through environment variables without code changes

## Heroku / State Persistence Details
- **Telethon Session**: The core Telegram session file (`.session`) is stored as a compressed Base64 encoded string in the `TG_COMPRESSED_SESSION_STRING` environment variable. 
  - Uses gzip compression to reduce size from ~28KB to ~1KB for Heroku's 64KB config var limit
  - `app.session_manager.setup_session()` decompresses and recreates the session file from this variable on startup
  - Falls back to the older uncompressed `TG_SESSION_STRING` format if `TG_COMPRESSED_SESSION_STRING` is not available
- **Application State**: Other application state, such as the last processed message ID, timestamp, and PTS (Poll Tracking State) for channel polling, is stored as a Base64 encoded JSON string in the `LAST_PROCESSED_STATE` environment variable.
  - `app.session_manager.load_app_state()` loads this state on startup, falling back to a local `session/app_state.json` file (for local development) or defaults if neither is found.
  - `app.session_manager.save_app_state(state_data)` saves the current state to `session/app_state.json` and also logs the Base64 encoded string that should be set as `LAST_PROCESSED_STATE` on Heroku. This ensures that even if the bot restarts, it can resume from where it left off.
- **Setup Script**: `setup_heroku.sh` automates setting these (and other) environment variables on Heroku. It uses `export_session.py` to generate the necessary Base64 strings from your local, authenticated session and current application state file.
  - Now reads settings from both `.env` (secrets) and `app_settings.env` (non-secrets)
  - Compresses the session data with gzip before Base64 encoding
  - Displays compression statistics to verify size reduction
- **Obsolete Variables**: `SESSION_DATA`, `CHANNEL_PTS_DATA`, `USE_ENV_PTS_STORAGE`, and `TG_SESSION_STRING` are now obsolete and are automatically removed from Heroku config by `setup_heroku.sh`.

## Future Ideas / Nice-to-Haves (Backlog)
- [x] More sophisticated image generation prompts:
    - [x] Caricature style for political figures
    - [x] Editorial cartoon style without text
    - [x] Ensure visuals directly relate to news content with symbolism
- [x] **Article Reading Capability (Task 16 - COMPLETED)**:
    - [x] Implemented article extraction using newspaper4k library
    - [x] Enhanced translation context from ~50 to 1630 characters (30x improvement)
    - [x] Created `app/article_extractor.py` with robust URL content extraction
    - [x] Integrated with bot.py to automatically extract article content when URLs detected
    - [x] Updated translator.py prompts to handle full article content effectively
    - [x] All tests passing including full integration test
- [x] Translation improvements:
    - [x] Remove the RIGHT-BIDLO header at the top of messages
    - [x] Simplify code to use only right-bidlo style (no if-else for translation styles)
    - [ ] Be sensitive when there is a sad post and adjust tone when jokes are inappropriate
- [ ] Image generation improvements:
    - [ ] Troubleshoot occasional issues with images not showing
    - [ ] Investigate cases where images fail to generate
- [ ] Link handling enhancements:
    - [ ] Fix duplicate links issue (Ссылка из статьи and Оригинал are currently the same link)
    - [ ] Format links as proper hyperlinks without showing the full URL
- [ ] User command to trigger translation of a specific URL
- [ ] Interactive setup/auth script (was `scripts/complete_auth.py`)
- [ ] More advanced error recovery (e.g., retry mechanisms with backoff for API calls)
- [ ] Dashboard/UI to monitor bot activity and stats
- [ ] Support for other source news channels
- [ ] Store processed message IDs to avoid re-processing after restarts (if not already handled by fetching only new ones)
- [ ] Improve logging structure (e.g., JSON logs, more context)
- [ ] CI/CD pipeline for automated testing and deployment
- [ ] Add more unit and integration tests 
- [ ] Review and document the safety of APP_STATE_FILE in ephemeral container environments

# Testing Documentation

## Testing Approach

```
┌────────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│                    │   │                   │   │                   │
│ API Integration    │──▶│ Telegram Pipeline │──▶│ End-to-End        │
│ Tests              │   │ Tests             │   │ Verification      │
│                    │   │                   │   │                   │
└────────────────────┘   └───────────────────┘   └───────────────────┘
```

The testing strategy uses real API calls with dedicated test channels rather than mocks. This approach tests the actual integration points while isolating tests from production environments.

## Test vs Production Environment

| Aspect                   | Test Environment                    | Production Environment       |
|--------------------------|-------------------------------------|------------------------------|
| Channels                 | TEST_SRC_CHANNEL, TEST_DST_CHANNEL  | SRC_CHANNEL, DST_CHANNEL     |
| Messages                 | Pre-defined test content            | Real NYT articles            |
| OpenAI API               | Same API with minimal prompts       | Full article processing      |
| Session Management       | Persistent or temporary test session| Environment-based on Heroku  |
| Image Generation         | Optional (--no-images flag)         | Enabled by default           |
| Error Handling           | Fails on ANY error logged           | Logs errors, continues running |
| Execution                | Single run with assertions          | Continuous running daemon    |
| Test Data                | Predefined complex test message     | Real NYT content             |
| Test Finalization        | Cleanup of temporary sessions       | Persistent session management|

## Test Implementation

```
FUNCTION main():
    // Parse command line arguments
    PARSE --stability, --no-images, --new-session flags
    
    // Run API Integration Tests
    RUN test_translations()
    IF image generation enabled:
        IF stability flag:
            RUN test_stability_ai_image_generation()
        ELSE:
            RUN test_image_generation()
    
    // Run Telegram Pipeline Tests
    CREATE Telegram client with test session
    AUTHENTICATE with Telegram
    SEND test message to TEST_SRC_CHANNEL
    PROCESS message with translate_and_post()
    VERIFY message appears in TEST_DST_CHANNEL
    VERIFY message contains RIGHT-BIDLO translation
    VERIFY message contains source attribution
    IF image generation enabled:
        VERIFY media was posted
    
    // Clean up
    DISCONNECT client
    IF using temporary session:
        DELETE session files
```

## Error Detection System

The _ErrorCounterHandler is a custom logging handler that:
1. Attaches to the root logger at ERROR level
2. Counts any ERROR or higher level logs
3. Automatically fails tests if any errors are detected

```python
class _ErrorCounterHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.error_count = 0

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.error_count += 1
```

This approach ensures that any error, even those not explicitly checked in assertions, will cause tests to fail, creating a strict zero-error policy.

## Test Data Generation

The tests use a carefully crafted test message designed to:

```python
TEST_MESSAGE = (
    "BREAKING NEWS: Scientists discover remarkable new species of bioluminescent deep-sea creatures "
    "near hydrothermal vents in the Pacific Ocean. The colorful organisms have evolved unique "
    "adaptations to extreme pressure and toxic chemicals that could provide insights into early life on Earth. "
    "Read more at https://www.nytimes.com/2023/05/06/science/deep-sea-creatures.html"
)
```

This test message:
1. Has sufficient complexity for OpenAI translation
2. Contains enough detail for image generation
3. Includes a realistic NYT-style URL
4. Simulates an actual news article format
5. Has unique phrases that can be verified in output

## API Integration Tests

Tests for OpenAI and Stability AI APIs:

1. **Translation Testing**
   - Tests RIGHT-BIDLO translation style
   - Verifies output has sufficient length
   - Ensures translation maintains key content

2. **Image Generation Testing**
   - Tests DALL-E or Stability AI integration based on flags
   - Verifies image data is returned
   - Validates image has proper size/format

## Telegram Pipeline Testing

The pipeline test follows this process:

1. Establishes real connection to Telegram API using test credentials
2. Sends test message to test source channel
3. Processes the message through the same pipeline used in production
4. Verifies translation appears in test destination channel
5. Checks for RIGHT-BIDLO header in posted content
6. Validates source attribution appears
7. Confirms image attachment if enabled

## Message Verification

The verification process checks:
```python
async def verify_message_in_channel(client, channel, content_fragment, timeout=300, limit=10):
    # Checks both media captions and text messages
    # Polls repeatedly until timeout
    # Returns successful match or failure
```

This function allows the test to confirm message delivery and content without requiring event handlers.

## Session Management

Tests can use:
- Persistent test session (`session/test_session_persistent`) for faster repeated runs
- Temporary sessions with `--new-session` flag for clean environment testing

## How to Run Tests

```bash
# Run basic tests
python test.py

# Test with Stability AI instead of DALL-E
python test.py --stability

# Run without image generation
python test.py --no-images

# Force new authentication session
python test.py --new-session
```

## Development Workflow Rules

### Pre-Commit Requirements
⚠️ **ALWAYS RUN TESTS BEFORE COMMITS!**

```bash
# Required before any git commit:
source .env && tests/test_polling_flow.sh
# OR
pytest tests/
```

All tests must pass before committing changes. This prevents regressions and ensures production stability.

### Deployment Process
When "push" is mentioned, it means:

1. **Push to GitHub**: `git push origin main`
2. **Deploy to Heroku**: `git push heroku main`
3. **Verify Deployment**: Check Heroku logs for successful deployment and runtime status

```bash
# Complete deployment workflow:
git push origin main
git push heroku main
heroku logs --tail --app nyt-zoomer-bot
```

Monitor logs for:
- ✅ Successful build and deployment
- ✅ Bot startup without errors
- ✅ Telegram connection established
- ❌ Any runtime errors or authentication issues

## Configuration for Tests

```python
# Test environment uses:
TEST_SRC_CHANNEL = "@test_source_channel"  # Test incoming channel
TEST_DST_CHANNEL = "@test_destination_channel"  # Test outgoing channel

# Test sessions are stored in:
PERSISTENT_TEST_SESSION = "session/test_session_persistent"
# Or temporary session with:
test_session = f"session/test_session_{uuid.uuid4().hex[:8]}"
```

# Telegram Zoomer Bot - Project Flow Documentation

## Project Overview
The Telegram Zoomer Bot monitors messages from a source Telegram channel, translates them into a "zoomer slang" style using OpenAI, optionally generates images related to the content, and posts the translated content to a destination channel.

## Technical Flow (Pseudocode)

### Main Program Flow
```
FUNCTION main():
    // Initialize environment and configuration
    LOAD environment variables (.env)
    SETUP logging
    
    // Initialize clients
    INITIALIZE Telegram client with API_ID, API_HASH and SESSION
    INITIALIZE OpenAI client with API_KEY
    
    // Authenticate with Telegram
    TRY to connect using saved session
    IF not authenticated:
        START authentication with phone number
        HANDLE verification code/2FA if required
    
    // Set up event handlers
    REGISTER event_handler for new messages in source channel
    
    // Start background tasks
    START background_keep_alive task
    START background_update_checker task  
    START background_channel_poller task
    
    // Process any recent messages if requested
    IF process_recent parameter:
        PROCESS last N messages from source channel
    
    // Keep the bot running
    RUN client until disconnected
```

### Event Handling Flow
```
FUNCTION handle_new_message(event):
    GET message text from event
    IF message contains text:
        LOG "Processing new message"
        CALL translate_and_post(client, text, message_id)
```

## Testing

### Running All Tests
```bash
# Run standard pytest tests
python -m pytest tests/ -v

# Run polling test (tests the full bot polling mechanism)
./tests/test_polling_flow.sh
```

### Test Types
- **Unit Tests**: `test_article_extractor.py`, `test_integration.py`
- **E2E Tests**: `test_e2e_unified.py` (includes API, image generation, telegram pipeline)
- **Polling Test**: `test_polling_flow.sh` (full bot polling mechanism with real message sending)

**Important**: The polling test requires the shell script `test_polling_flow.sh` which:
1. Sends a test message to the test channel with a unique prefix
2. Starts the bot in background with test mode enabled
3. Bot only processes messages with the test prefix (optimized for speed)
4. Verifies the bot processes the message via polling
5. Cleans up processes and sessions

**Note**: The bot is optimized for test mode - when `TEST_RUN_MESSAGE_PREFIX` is set, it only processes messages containing that prefix, making tests fast and reliable.

## Development Rules & Learnings

### Testing Protocol
1. **Always run ALL tests before commits**:
   ```bash
   # Standard pytest tests
   python -m pytest tests/ -v
   
   # Polling mechanism test (shell script, not pytest)
   ./tests/test_polling_flow.sh
   ```

2. **Test Types Understanding**:
   - **pytest tests**: Unit/integration tests in `tests/` directory
   - **Polling test**: Shell script that runs bot in background + sends test message
   - **NOT related**: Polling test is NOT a pytest test, it's a separate shell script

3. **Test Optimization Approach**:
   - When tests timeout, check if they're processing too many messages
   - Use test mode filtering (e.g., `TEST_RUN_MESSAGE_PREFIX`) to process only relevant messages
   - Optimize for speed by skipping unrelated processing during tests

### Link Formatting Implementation
1. **Hyperlink format**: Use `[text](url)` markdown format with `parse_mode='md'`
2. **Testing hyperlinks**: Don't check for "hidden URLs" - markdown still contains URLs in `[text](url)` format
3. **Correct test logic**: Check for absence of bare URLs, not absence of URLs entirely

### Task Management Workflow
1. **Update subtasks as you complete them**: Mark subtasks as "done" immediately after completion
2. **Document progress**: Update PROJECT.md when significant changes are made
3. **MVP focus**: Remove non-essential features (like "monitoring" headers) to focus on core functionality

### Code Quality Practices
1. **Remove redundant headers**: Clean up output by removing unnecessary prefixes like "RIGHT-BIDLO VERSION:"
2. **Simplify configuration**: Use single translation style instead of complex if/else logic
3. **Fix duplicate issues**: Identify root cause (e.g., LLM prompts adding links + bot adding links)
4. **Consistent formatting**: Use markdown hyperlinks throughout for better UX

### Debugging Approach
1. **Check logs carefully**: Look for actual errors vs expected behavior
2. **Test incrementally**: Fix one issue at a time and verify
3. **Use mock clients**: Create simple test clients to verify functionality without full integration
4. **Understand the flow**: Trace through the entire message processing pipeline

### Environment & Session Management
1. **Test vs Production**: Use different channels and sessions for testing
2. **Session persistence**: Understand how Telegram sessions work and persist across restarts
3. **Environment variables**: Use test-specific env vars to control behavior during testing

### Performance Optimization
1. **Identify bottlenecks**: Long-running operations (OpenAI calls, image generation) can cause timeouts
2. **Filter early**: Skip processing irrelevant messages as early as possible
3. **Use timeouts appropriately**: Set reasonable timeouts based on actual operation duration

### Key Technical Insights from Task 12 Implementation

#### Translation Model Upgrade (Subtask 12.20) ✅ COMPLETED & DEPLOYED TO PRODUCTION
- **Research**: Claude Sonnet 4 (May 2025) is the latest model with major improvements in coding, reasoning, and instruction following
- **Benefits**: 
  - Superior instruction following vs GPT-4o and Claude 3.5
  - More natural language output and reduced translation errors
  - Better coding capabilities and advanced reasoning
  - Improved memory and tool use capabilities
- **Cost**: Same pricing as Claude 3.5 ($3/$15 per million tokens) but significantly better quality
- **Implementation**: 
  ```python
  # Using latest Claude Sonnet 4
  from app.translator import get_anthropic_client, translate_text
  anthropic_client = get_anthropic_client(ANTHROPIC_KEY)
  # Now uses claude-sonnet-4-20250514 model
  translated_text = await translate_text(anthropic_client, text, 'right')
  ```
- **Environment**: Requires `ANTHROPIC_API_KEY` 
- **Dependencies**: `anthropic==0.40.0` (compatible with Claude Sonnet 4)
- **Production Deployment**: ✅ Deployed to Heroku using `./setup_heroku.sh`
- **Status**: ✅ Claude Sonnet 4 running in production, all tests passing, latest AI model active

#### Heroku Environment Variable Management
- **Process**: Always use `./setup_heroku.sh` script (documented in .cursor/rules/project-progress.mdc)
- **Never**: Manually set Heroku config vars with `heroku config:set`
- **Script Benefits**: Reads both .env and app_settings.env, handles compression, cleans obsolete vars

#### Hyperlink Formatting (Subtask 12.17)
- **Problem**: Links showed full URLs instead of clean hyperlinks
- **Solution**: Use `[text](url)` markdown format with `parse_mode='md'` in all `send_message` calls
- **Implementation**: 
  ```python
  source_footer = f"\n\n🔗 [Оригинал]({message_link})"
  if message_entity_urls:
      source_footer += f"\n🔗 [Ссылка из статьи]({message_entity_urls[0]})"
  await client.send_message(channel, text_content, parse_mode='md')
  ```
- **Testing gotcha**: Markdown hyperlinks still contain URLs in text - test for absence of bare URLs, not absence of URLs

#### Duplicate Links Fix (Subtask 12.16)
- **Problem**: Three links appeared instead of two (duplicate "Оригинал" links)
- **Root cause**: LLM translation prompts instructed to add "🔗 Оригинал: [URL]" while bot.py also added its own links
- **Solution**: Remove link instructions from ALL translation prompts (LEFT, RIGHT, DEFAULT styles) in translator.py
- **Result**: Clean two-link structure: Original message + Article link

#### Translation Style Simplification (Subtask 12.14)
- **Change**: Simplified from supporting both LEFT/RIGHT styles to only RIGHT style
- **Configuration**: Set `TRANSLATION_STYLE=right` in app_settings.env as default
- **Code cleanup**: Removed complex if/else logic for translation styles in bot.py

#### Header Removal (Subtask 12.13)
- **Removed**: "🔴 RIGHT-BIDLO VERSION:" header from posts
- **Reason**: MVP focus - cleaner, more professional appearance
- **Implementation**: Simply removed header concatenation in bot.py

#### Test Optimization Discovery
- **Problem**: Polling test processed ALL pending messages, causing timeouts
- **Solution**: Add test mode filtering using `TEST_RUN_MESSAGE_PREFIX` environment variable
- **Key insight**: Tests should be isolated and only process relevant test data
- **Performance**: Reduced test time from 75s timeout to ~17s completion
