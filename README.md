# Telegram NYT-to-Zoomer Translator

A bot that monitors a Telegram channel (NYT), translates messages to Russian Zoomer slang using OpenAI, and posts them to another channel.

## Features

- Automatic message monitoring from source channel
- OpenAI GPT-4o mini translation to Russian Zoomer slang
- Robust error handling with retries
- Persistent session storage
- Comprehensive logging
- Reliable megachannel polling using PTS (Position Token for Sequence)
- Heroku compatibility with ephemeral filesystem support

## Setup

### Prerequisites

- Python 3.8+
- Telegram API credentials (API ID and Hash) from [my.telegram.org](https://my.telegram.org/)
- OpenAI API key from [OpenAI dashboard](https://platform.openai.com/account/api-keys)

## Configuration

The bot is configured through environment variables set in a `.env` file or via Heroku config variables:

| Variable              | Description                                 | Required | Default Value |
|-----------------------|---------------------------------------------|----------|---------------|
| TG_API_ID             | Telegram API ID                             | Yes      | -             |
| TG_API_HASH           | Telegram API Hash                           | Yes      | -             |
| TG_PHONE              | Phone number for Telegram authentication    | Yes      | -             |
| OPENAI_API_KEY        | OpenAI API key                              | Yes      | -             |
| SRC_CHANNEL           | Source channel to monitor                   | Yes      | -             |
| DST_CHANNEL           | Destination channel to post translations    | Yes      | -             |
| TG_SESSION            | Path to session file (without .session ext) | No       | session/nyt_zoomer |
| GENERATE_IMAGES       | Whether to generate images for posts        | No       | true          |
| TRANSLATION_STYLE     | Translation style (only 'right' supported)  | No       | right         |
| CHECK_CHANNEL_INTERVAL| Interval for checking missed messages (sec) | No       | 300           |
| KEEP_ALIVE_INTERVAL   | Interval for keep-alive signals (sec)       | No       | 60            |
| MANUAL_POLL_INTERVAL  | Interval for manual polling (sec)           | No       | 180           |
| SESSION_DATA          | Base64 encoded session data (Heroku)        | No*      | -             |
| LAST_PROCESSED_STATE  | Base64 encoded message state (Heroku)       | No       | -             |
| CHANNEL_PTS_DATA      | JSON string with channel PTS values (Heroku)| No       | -             |
| PTS_DATA_FILE         | Path to PTS data file                       | No       | session/channel_pts.json |
| USE_ENV_PTS_STORAGE   | Force use of env vars for PTS (`true`/`false`)| No       | false         |

*Required for Heroku deployment (`SESSION_DATA`, `CHANNEL_PTS_DATA` typically provided by Heroku setup or `USE_ENV_PTS_STORAGE=true`)

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
    *   `TG_SESSION`: (Optional) Session file path. Defaults to `new_session.session` in the root. Recommended: `session/new_session` (ensure `session/` directory exists).
    *   `TRANSLATION_STYLE`, `GENERATE_IMAGES`, `USE_STABILITY_AI`, `STABILITY_AI_API_KEY`: See comments in example `.env`.

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
    To process N recent posts instead of listening for new ones:
    ```bash
    python -m app.bot --process-recent N
    ```

## First-time Authentication

On the first run, or if the session file is deleted/invalid, the bot will prompt for your phone number (if not in `.env` or if Telethon requires it) and then the verification code sent to your Telegram account. This happens directly in the terminal.

After successful authentication, the session file (e.g., `session/new_session.session` if configured, or `new_session.session` in the root) will be created. This file stores your session, so you won't need to log in every time.

If you configured `TG_SESSION=session/new_session`, ensure you move your existing `new_session.session` (if any from previous root runs) into the `session/` directory *before* running the bot, or allow it to create a new one there after authentication.

## Deployment

### Heroku Deployment

The bot is designed to work seamlessly on Heroku:

1. Clone the repository
2. Create a new Heroku app
3. Set up a local session by running the bot on your machine
4. Export the session and message state using the provided script:
   ```
   python export_session.py session/your_session_name
   ```
5. Use the setup script to configure Heroku:
   ```
   ./setup_heroku.sh your-heroku-app-name
   ```
6. Deploy to Heroku using Git:
   ```
   git push heroku main
   ```
7. Scale up the worker dyno:
   ```
   heroku ps:scale worker=1 --app your-heroku-app-name
   ```

The session and message state persistence is handled automatically, allowing the bot to maintain its state even when Heroku restarts dynos.

## Polling Mechanism

The bot uses a sophisticated polling mechanism to reliably receive updates from large Telegram channels (megachannels):

### How Polling Works

1. **PTS (Position Token for Sequence)**: Each channel has a PTS value that represents the latest update point.
2. **GetChannelDifferenceRequest**: The bot uses Telegram's API to request all updates since the last PTS.
3. **Persistence**: 
    - By default, PTS values are stored in a JSON file (defined by `PTS_DATA_FILE`, defaults to `session/channel_pts.json`).
    - For Heroku and other ephemeral environments, PTS can be stored in the `CHANNEL_PTS_DATA` environment variable (as a JSON string). This is automatically used if `CHANNEL_PTS_DATA` is found or if `USE_ENV_PTS_STORAGE` is set to `true`.
4. **Error Handling**: Special handling for "Persistent timestamp empty" errors during initialization.
5. **DB Lock Prevention**: Skips polling cycles during message processing to prevent database locks.

### Testing Polling

To test the polling mechanism:

```bash
# Start the bot in test mode (background)
./test_polling_flow.sh

# In another terminal, send a test message
python test_polling.py
```

The bot should detect the message via polling rather than event handlers.

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

### Monitoring and Maintenance

- Check logs:
  ```