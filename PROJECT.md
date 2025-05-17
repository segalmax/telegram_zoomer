# Telegram NYT-to-Zoomer Bot - Project Tasks

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
    - [x] **Simplified to use only RIGHT-BIDLO translation style** for better clarity and reliability
    - [x] **Improved message formatting** by combining header with content instead of sending separate messages
- [x] Implement persistent session handling to avoid frequent re-authentication
- [x] Comprehensive end-to-end automated testing
- [x] Code cleanup and organization (ongoing)

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

## Future Ideas / Nice-to-Haves (Backlog)
- [x] More sophisticated image generation prompts:
    - [x] Caricature style for political figures
    - [x] Editorial cartoon style without text
    - [x] Ensure visuals directly relate to news content with symbolism
- [ ] User command to trigger translation of a specific URL
- [ ] Interactive setup/auth script (was `scripts/complete_auth.py`)
- [ ] More advanced error recovery (e.g., retry mechanisms with backoff for API calls)
- [ ] Dashboard/UI to monitor bot activity and stats
- [ ] Support for other source news channels
- [ ] Store processed message IDs to avoid re-processing after restarts (if not already handled by fetching only new ones)
- [ ] Improve logging structure (e.g., JSON logs, more context)
- [ ] CI/CD pipeline for automated testing and deployment
- [ ] Add more unit and integration tests

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

### Translation and Posting Flow
```
FUNCTION translate_and_post(client, text, message_id, destination=DEFAULT_DEST):
    // Image generation (optional)
    IF image generation enabled AND OpenAI available:
        image_data = CALL generate_image_for_post(openai_client, text)
    
    // Translate text using OpenAI
    translated_text = CALL translate_text(openai_client, text, 'right')
    
    // Format message for posting
    full_content = COMBINE header with translated content
    IF original link found:
        ADD source attribution with link
    
    // Send to destination
    IF image available:
        SEND image with caption (up to 1024 chars)
        IF text longer than 1024 chars:
            SEND remaining text as separate message
    ELSE:
        SEND full text message
    
    RETURN success status
```

### Background Tasks
```
FUNCTION background_keep_alive(client):
    WHILE true:
        UPDATE online status
        LOG "Connection keep-alive"
        SLEEP for KEEP_ALIVE_INTERVAL
```

```
FUNCTION background_update_checker(client):
    INITIALIZE last_check_time
    WHILE true:
        TRY client.catch_up() to get any missed updates
        
        IF time since last check >= CHECK_CHANNEL_INTERVAL:
            GET recent messages from source channel
            FOR each message:
                IF message is new since last check AND not already processed:
                    PROCESS the message
            UPDATE last_check_time
        
        SLEEP for MANUAL_POLL_INTERVAL
```

```
FUNCTION background_channel_poller(client):
    WHILE true:
        GET channel entity
        CREATE input channel
        TRY to get channel difference:
            FOR each new message:
                PROCESS the message if it has text
        SLEEP for MANUAL_POLL_INTERVAL
```

### Recent Messages Processing Flow
```
FUNCTION process_recent_messages(client, count):
    GET most recent 'count' messages from source channel
    FOR each message in reverse order (oldest first):
        IF message has text:
            PROCESS the message
            SLEEP briefly to respect rate limits
    RETURN success status
```

## Component Interactions

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Source Channel │────▶│ Telegram Client │────▶│ OpenAI Service  │
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │                 │     │                 │
                        │  Message        │────▶│ Image Generation│
                        │  Translation    │     │  (Optional)     │
                        │                 │     │                 │
                        └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────────────────────────────┐
                        │                                         │
                        │        Destination Channel              │
                        │                                         │
                        └─────────────────────────────────────────┘
```

## Data Flow
1. Message detected in source channel
2. Message text extracted and sent to OpenAI for translation
3. Optionally, message context sent to OpenAI for image generation
4. Translated text (and optionally image) formatted with source attribution
5. Formatted content posted to destination channel

## Configuration Parameters
- API_ID, API_HASH: Telegram API credentials
- PHONE: Phone number for Telegram authentication
- SESSION_PATH: Path to store session data
- SRC_CHANNEL, DST_CHANNEL: Channel identifiers
- TRANSLATION_STYLE: Style of translation (currently fixed to 'right')
- GENERATE_IMAGES: Toggle for image generation
- OPENAI_KEY: OpenAI API key
- CHECK_CHANNEL_INTERVAL: How often to check for missed messages
- KEEP_ALIVE_INTERVAL: How often to update online status
- MANUAL_POLL_INTERVAL: How often to manually poll for updates

## Error Handling
- Connection issues: Automatic reconnection attempts
- Authentication failures: Proper logging and exit
- Message processing errors: Logged but doesn't stop the bot
- Timeout handling: For message fetching and processing

## Next Steps & Improvements
- Add support for multiple translation styles
- Implement more robust error handling and recovery
- Add telemetry and monitoring
- Implement rate limiting to prevent API throttling
- Add support for message editing and deletion 

## Reliability Features

| Feature                 | Purpose                                   | Implementation                                |
|-------------------------|-------------------------------------------|--------------------------------------------|
| Session Persistence     | Maintain authentication across restarts    | Store session in environment variables      |
| Channel Polling         | Backup mechanism if events are missed      | Regularly poll source channel with GetChannelDifferenceRequest |
| Update Checker          | Periodically check for recent messages     | Compare recent messages to processed ones   |
| Keep-Alive Mechanism    | Keep connection active and prevent timeouts| Regular status updates to telegram servers |
| Auto-Reconnection       | Handle temporary connection losses         | Detect and reestablish dropped connections  |
| Message State Persistence | Track last processed message across restarts | Store message ID and timestamp in environment variables |
| Recovery Upon Restart   | Process messages missed during downtime    | Check for messages newer than last processed ID at startup |

# Recent Improvements - Reliable Megachannel Polling

## PTS Management System
The bot now uses a robust Position Token for Sequence (PTS) management system that enables reliable polling for large Telegram channels (megachannels):

- Implemented a dedicated `pts_manager.py` module that manages channel-specific PTS values
- PTS values are persisted using JSON file storage with environment variable fallback for Heroku
- Properly handles the "Persistent timestamp empty" error during polling initialization

## Enhanced Polling Mechanism
The previous implementation used three separate background tasks for different types of polling. These have been consolidated into a single, more reliable approach:

```
FUNCTION poll_big_channel(client, channel_username):
    TRACK first poll status
    TRACK message processing status to prevent DB locks
    
    WHILE true:
        IF currently processing a message:
            BRIEF sleep to avoid DB locks
            CONTINUE
        
        TRY:
            GET channel entity
            CREATE input channel
            GET stored PTS value
            
            IF first poll AND no PTS value:
                GET latest message directly
                PROCESS latest message
                GET PTS from dialog entity
                SAVE initial PTS value
                MARK first poll as done
                CONTINUE
                
            POLL for channel differences using PTS
            SAVE updated PTS value
            
            FOR each new message:
                PROCESS message
                
            SLEEP based on recommended timeout or default interval
            
        CATCH database locked error:
            SLEEP longer to allow locks to clear
        CATCH other errors:
            LOG error
            SLEEP before retry
```

## Heroku Compatibility
The bot is now fully compatible with Heroku's ephemeral filesystem:

- Added patching mechanism to replace file-based PTS storage with environment variables (`CHANNEL_PTS_DATA` or by setting `USE_ENV_PTS_STORAGE=true`). This is now auto-detected in `app.pts_manager`.
- Implemented proper serialization/deserialization of PTS data via JSON.
- Created fallback mechanisms to ensure data persistence across dyno restarts.
- Updated Procfile with correct worker command

## Error Handling Improvements
- Added special handling for database lock errors with longer sleep periods
- Improved detection and recovery from "Persistent timestamp empty" errors
- Better handling of first-time polling initialization
- More robust message processing with completion tracking

## Database Lock Prevention
SQLite session files used by Telethon can encounter "database is locked" errors when accessed by multiple processes or during abnormal termination. Improvements include:

- **Message processing flag**: Added a `processing_message` flag to prevent polling during active message processing
- **Conditional polling**: Skip polling cycles if a message is currently being processed
- **Longer recovery sleeps**: Extended sleep times (120s) when database locks are detected to allow locks to clear
- **Session cleanup tools**: Added `scripts/unlock_sessions.sh` to help diagnose and fix session lock issues
- **Automatic cleanup**: Enhanced `test_polling_flow.sh` to automatically clean up session journal files

The database lock prevention system significantly improves reliability by:
1. Isolating database operations to prevent concurrent access
2. Adding proper detection and recovery for lock errors
3. Implementing graceful handling rather than crashing the process
4. Providing tools to diagnose and resolve persistent issues

## Testing Framework
- Added `test_polling.py` script to send test messages that trigger the polling mechanism
- Created `test_polling_flow.sh` to automate the testing process
- Made test mode compatible with the new polling mechanism
- Added extensive logging to track polling behavior

These improvements make the bot fully compatible with Telegram's April 2024 change that requires proper short-polling for large channels, while maintaining compatibility with Heroku's ephemeral filesystem environment.
