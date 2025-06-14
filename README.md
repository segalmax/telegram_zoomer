# Telegram News-to-Zoomer Translator

A bot that monitors news Telegram channels, translates messages to Russian Zoomer slang using OpenAI, and posts them to another channel. Currently configured for ynet.co.il content.

## Features

- Automatic message monitoring from source channel
- OpenAI GPT-4o mini translation to Russian Zoomer slang (website-agnostic)
- **Article content extraction** for enhanced translation context (30x improvement)
- Robust error handling with retries
- Persistent session storage
- Comprehensive logging
- Reliable megachannel polling using PTS (Position Token for Sequence)
- Heroku compatibility with ephemeral filesystem support

## Development Workflow

### ⚠️ Pre-Commit Requirements
**ALWAYS RUN TESTS BEFORE COMMITS!**

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

## Setup

### Prerequisites

- Python 3.8+
- Telegram API credentials (API ID and Hash) from [my.telegram.org](https://my.telegram.org/)
- OpenAI API key from [OpenAI dashboard](https://platform.openai.com/account/api-keys)

## Configuration

The bot is configured through environment variables set in `.env` and `app_settings.env` files or via Heroku config variables:

| Variable              | Description                                 | Required | Default Value | Location      |
|-----------------------|---------------------------------------------|----------|---------------|---------------|
| TG_API_ID             | Telegram API ID                             | Yes      | -             | `.env`        |
| TG_API_HASH           | Telegram API Hash                           | Yes      | -             | `.env`        |
| TG_PHONE              | Phone number for Telegram authentication    | Yes      | -             | `.env`        |
| OPENAI_API_KEY        | OpenAI API key                              | Yes      | -             | `.env`        |
| STABILITY_AI_API_KEY  | Stability AI API key (if used)              | No       | -             | `.env`        |
| SRC_CHANNEL           | Source channel to monitor                   | Yes      | -             | `app_settings.env` |
| DST_CHANNEL           | Destination channel to post translations    | Yes      | -             | `app_settings.env` |
| GENERATE_IMAGES       | Whether to generate images for posts        | No       | true          | `app_settings.env` |
| TRANSLATION_STYLE     | Translation style ('left', 'right', 'both') | No       | both          | `app_settings.env` |
| HEROKU_APP_NAME       | Name of your Heroku app                     | No*      | -             | `app_settings.env` |
| TG_COMPRESSED_SESSION_STRING | Compressed Base64 encoded Telethon session (Heroku) | No*      | -             | (set by `setup_heroku.sh`) |
| LAST_PROCESSED_STATE  | Base64 encoded application state (Heroku)   | No*      | -             | (set by `setup_heroku.sh`) |

*`TG_COMPRESSED_SESSION_STRING` and `LAST_PROCESSED_STATE` are automatically handled by `setup_heroku.sh` for Heroku deployment.

### Environment Setup

The application uses a dual environment file approach for better security and configuration management:

1. **Create an `.env` file** for sensitive credentials:
   ```
   # .env - SENSITIVE CREDENTIALS (gitignored)
   TG_API_ID=your_telegram_api_id
   TG_API_HASH=your_telegram_api_hash
   TG_PHONE=your_phone_number_for_initial_auth
   OPENAI_API_KEY=your_openai_api_key
   STABILITY_AI_API_KEY=your_stability_ai_key  # Optional
   ```

2. **Create an `app_settings.env` file** for non-sensitive application settings:
   ```
   # app_settings.env - APPLICATION SETTINGS (accessible to tools)
   SRC_CHANNEL=source_channel_username_or_id
   DST_CHANNEL=destination_channel_username_or_id
   TEST_SRC_CHANNEL=test_source_channel  # For testing
   TEST_DST_CHANNEL=test_destination_channel  # For testing
   TRANSLATION_STYLE=both  # 'left', 'right', or 'both'
   GENERATE_IMAGES=true  # 'true' or 'false'
   HEROKU_APP_NAME=your-heroku-app-name  # Used by setup_heroku.sh
   ```

3. **Ensure proper .gitignore settings**:
   The repository includes a `.gitignore` that excludes `.env` (to protect secrets) but includes an exception for `app_settings.env` to allow non-sensitive configuration to be shared.

### Configuration

1.  Create a `.env` file in the project root.
    ```
    # Example .env content:
    TG_API_ID=your_telegram_api_id
    TG_API_HASH=your_telegram_api_hash
    OPENAI_API_KEY=your_openai_api_key
    # TG_PHONE=your_phone_number_for_initial_auth # Optional, bot will prompt if needed
    SRC_CHANNEL=source_channel_username_or_id
    DST_CHANNEL=destination_channel_username_or_id
    
    # Recommended for cleaner project root:
    TG_SESSION=session/new_session 
    
    # Optional overrides:
    # TRANSLATION_STYLE=both # 'left', 'right', or 'both' (default)
    # GENERATE_IMAGES=true # 'true' or 'false' (default)
    # USE_STABILITY_AI=false # 'true' or 'false' (default)
    # STABILITY_AI_API_KEY=your_stability_ai_key # Required if USE_STABILITY_AI is true
    ```

2.  Fill in your actual credentials and desired channel names in the `.env` file.
    Ensure the `session/` directory exists if you set `TG_SESSION=session/new_session`.

    **Important Environment Variables:**
    *   `TG_API_ID`, `TG_API_HASH`: Your Telegram application credentials.
    *   `OPENAI_API_KEY`: Your OpenAI API key.
    *   `SRC_CHANNEL`: The username or ID of the Telegram channel to monitor.
    *   `DST_CHANNEL`: The username or ID of the Telegram channel to post translations to.
    *   `TG_PHONE`: (Optional, for first auth) Your phone number (e.g., +1234567890). Bot will prompt if needed.
    *   `TG_SESSION`: (Optional) Session file name (without .session extension) used for local runs. Example: `session/my_bot_session`. The `setup_heroku.sh` script will use this to find your local session file for export.
    *   `TRANSLATION_STYLE`, `GENERATE_IMAGES`, `USE_STABILITY_AI`, `STABILITY_AI_KEY`: See comments in example `.env`.
    *   `TG_SESSION_STRING`: (Heroku) Contains the Base64 encoded string of your Telethon session file. Managed by `setup_heroku.sh`.
    *   `LAST_PROCESSED_STATE`: (Heroku) Contains the Base64 encoded JSON string of the application's last known state (last message ID, timestamp, PTS). Managed by `setup_heroku.sh` and updated by the bot during operation (bot logs the new string to be updated on Heroku).

### Running the Bot

1.  **Install requirements:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **(Recommended for first run if using `session/` for session file):** Create the session directory:
    ```bash
    mkdir -p session
    ```

3.  **Run the bot:**
    ```bash
    python -m app.bot
    ```
    When the bot saves application state (e.g., after processing messages or updating PTS), if it detects it might be in a Heroku-like environment (or if `LAST_PROCESSED_STATE` is set), it will log a message like:
    `INFO: To persist application state (e.g., on Heroku), set the 'LAST_PROCESSED_STATE' environment variable to: LAST_PROCESSED_STATE_VALUE_START###<base64_string>###LAST_PROCESSED_STATE_VALUE_END`
    You should update the `LAST_PROCESSED_STATE` config var on Heroku with this new `<base64_string>`. The `setup_heroku.sh` script handles the initial setup.

    To process N recent posts instead of listening for new ones:
    ```bash
    python -m app.bot --process-recent N
    ```

## First-time Authentication

On the first run, or if the session file is deleted/invalid, the bot will prompt for your phone number (if not in `.env` or if Telethon requires it) and then the verification code sent to your Telegram account. This happens directly in the terminal.

After successful authentication, the session file (e.g., `session/new_session.session` if configured, or `new_session.session` in the root) will be created. This file stores your session, so you won't need to log in every time.

The bot automatically uses `session/local_bot_session.session` for local development. No configuration needed.

## Deployment

### Heroku Deployment

The bot is designed to work seamlessly on Heroku:

1. **Set up local environment**:
   - Create both `.env` and `app_settings.env` as described above
   - Set `HEROKU_APP_NAME` in `app_settings.env` to your Heroku app name

2. **Create a local session** by running the bot locally first:
   ```
   python create_heroku_session.py
   ```
   This will create and authorize a session file specifically for Heroku use.

3. **Deploy configuration to Heroku** using the enhanced setup script:
   ```
   bash setup_heroku.sh
   ```
   This script:
   - Reads the app name from `app_settings.env`
   - Reads and sets all environment variables from both `.env` and `app_settings.env`
   - Exports and compresses the Telethon session to fit within Heroku's 64KB config var size limit
   - Sets `TG_COMPRESSED_SESSION_STRING` for Heroku deployment
   - Removes obsolete environment variables

4. **Deploy to Heroku** using Git:
   ```
   heroku git:remote -a your-heroku-app-name
   git push heroku main
   ```

5. **Scale up the worker dyno**:
   ```
   heroku ps:scale worker=1 -a your-heroku-app-name
   ```

### Session Management

The bot uses simple interactive sessions:
- **Local development**: `session/local_bot_session.session` (created interactively)
- **Heroku production**: `session/heroku_bot_session.session` (created interactively on Heroku)
- **Testing**: `session/sender_test_session.session` (created interactively)
- No session transfers or compression - each environment creates its own session

### Heroku Configuration Updates

**NEVER manually set Heroku config vars with `heroku config:set`!**
**ALWAYS use the dedicated setup script: `./setup_heroku.sh`**

The setup_heroku.sh script:
- Automatically reads from both .env (secrets) and app_settings.env (settings)
- Deploys ALL environment variables to Heroku in one command
- Cleans up obsolete variables
- Is the ONLY way to update Heroku environment variables
- Sessions are created interactively on first Heroku run

## Polling Mechanism

The bot uses a sophisticated polling mechanism to reliably receive updates from large Telegram channels (megachannels):

### How Polling Works

1. **Application State**: The bot maintains an application state that includes:
    - `pts`: The last known PTS (Position Token for Sequence) for the source channel.
    - `message_id`: The ID of the last successfully processed message.
    - `timestamp`: The timestamp of the last successfully processed message.
    - `channel_id`: The ID of the source channel being monitored.
2. **Persistence**: This application state is managed by `app.session_manager.py`:
    - **Local**: Saved in `session/app_state.json`.
    - **Heroku**: Loaded from the `LAST_PROCESSED_STATE` environment variable (a Base64 encoded JSON string of the state). When the state is updated, the bot logs the new Base64 string, which should be manually updated in Heroku config vars for persistence.
3. **GetChannelDifferenceRequest**: The bot uses Telegram's API to request all updates since the last known PTS from the application state.
4. **State Updates**: After fetching and processing messages, or after getting a new PTS from Telegram, the bot updates its application state and saves it (locally to file, and logs the string for Heroku).

### Testing

The project includes comprehensive tests in the `tests/` directory:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_article_extractor.py -v  # Article extraction tests
python -m pytest tests/test_integration.py -v       # Integration tests
python -m pytest tests/test_e2e_unified.py -v       # End-to-end tests

# Run individual test files directly
python tests/test_article_extractor.py
python tests/test_integration.py
```

#### Testing Polling

To test the polling mechanism specifically:

```bash
# Start the bot in test mode (background)
./test_polling_flow.sh

# In another terminal, send a test message
python tests/test_polling.py
```

The bot should detect the message via polling rather than event handlers.

See `tests/README.md` for detailed testing documentation.

## Troubleshooting

### Database Lock Issues

Telegram's Telethon library uses SQLite for session storage, which can occasionally lead to "database is locked" errors, especially when:
- Multiple bot instances are running simultaneously
- A process was terminated abnormally
- Session files are being accessed from different processes

To resolve database lock issues:

1. Run the provided troubleshooting script:
   ```bash
   ./scripts/unlock_sessions.sh
   ```

2. Manually clean up session journal files:
   ```bash
   # Remove all session journal files
   find . -name "*.session-journal" -type f -delete
   ```

3. If issues persist, try using a new session:
   ```bash
   # Run with a new temporary session
   python test.py --new-session
   ```

4. Ensure all bot processes are fully terminated before starting new ones.

### Session Authentication Errors

If you encounter errors like "The authorization key (session file) was used under two different IP addresses simultaneously", it means you're trying to use the same Telegram session from multiple locations (e.g., your local machine and Heroku):

1. The bot now handles this automatically by using different session paths for local vs. Heroku environments
2. When running locally, it uses `session/local_bot_session`
3. When running on Heroku, it uses `session/heroku_bot_session`
4. This separation prevents the conflicts between environments

If you still encounter this error:
```bash
# Delete the corrupted session file
rm session/local_bot_session.session

# Run the bot to create a new session
python -m app.bot

# Update Heroku with the setup script after authentication
./setup_heroku.sh
```

This ensures both environments have separate, valid sessions.

### Monitoring and Maintenance

- Check logs:
  ```