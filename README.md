# Telegram NYT-to-Zoomer Translator

A bot that monitors a Telegram channel (NYT), translates messages to Russian Zoomer slang using OpenAI, and posts them to another channel.

## Features

- Automatic message monitoring from source channel
- OpenAI GPT-4o mini translation to Russian Zoomer slang
- Robust error handling with retries
- Persistent session storage
- Comprehensive logging

## Setup

### Prerequisites

- Python 3.8+
- Telegram API credentials (API ID and Hash) from [my.telegram.org](https://my.telegram.org/)
- OpenAI API key from [OpenAI dashboard](https://platform.openai.com/account/api-keys)

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

## Heroku Deployment

### Initial Setup

1. **Create a Heroku app:**
   ```bash
   heroku create your-app-name
   ```

2. **Set up the required environment variables:**
   ```bash
   heroku config:set TG_API_ID=your_value --app your-app-name
   heroku config:set TG_API_HASH=your_value --app your-app-name
   heroku config:set OPENAI_API_KEY=your_value --app your-app-name
   heroku config:set SRC_CHANNEL=your_value --app your-app-name
   heroku config:set DST_CHANNEL=your_value --app your-app-name
   heroku config:set TG_SESSION=session/test_session_persistent --app your-app-name
   ```

3. **Handle Session Persistence:**
   Since Heroku has an ephemeral filesystem (resets every 24 hours), we store session data in environment variables which are permanent:
   
   a. Export your session from your local machine:
   ```bash
   python export_session.py
   ```
   
   b. Set the SESSION_DATA environment variable on Heroku:
   ```bash
   heroku config:set SESSION_DATA="your_base64_session_data" --app your-app-name
   ```
   
   c. How it works:
   - The `SESSION_DATA` environment variable permanently stores your Telegram credentials
   - When the bot starts on Heroku, `session_manager.py` automatically:
     - Reads the `SESSION_DATA` environment variable
     - Decodes the session data from base64
     - Creates a temporary session file for the current dyno
   - This happens automatically whenever the dyno restarts (daily or on deployments)
   - No manual intervention needed after initial setup

4. **Deploy to Heroku:**
   ```bash
   git push heroku main
   ```

5. **Start the worker dyno:**
   ```bash
   heroku ps:scale worker=1 --app your-app-name
   ```

### Monitoring and Maintenance

- Check logs:
  ```bash
  heroku logs --tail --app your-app-name
  ```

- Restart the worker if needed:
  ```bash
  heroku ps:restart worker --app your-app-name
  ```

- View environment variables:
  ```bash
  heroku config --app your-app-name
  ```

- Update session data (if needed):
  ```bash
  # Generate new base64 session data on local machine
  python export_session.py
  
  # Update on Heroku with new session data
  heroku config:set SESSION_DATA="your_new_base64_session_data" --app your-app-name
  ```

## Maintenance

- Logs are stored in the `logs/` directory (ensure this directory exists or is created by the bot, e.g., via `mkdir -p logs`).
- The session file is stored as per `TG_SESSION` (recommended: `session/new_session.session`).
- To update the bot, pull the latest code from your repository:
  ```bash
  git pull
  # then re-run the bot
  ```

## License

MIT 