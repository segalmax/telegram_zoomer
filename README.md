# Telegram NYT-to-Zoomer Translator

A bot that monitors a Telegram channel (NYT), translates messages to Russian Zoomer slang using OpenAI, and posts them to another channel.

## Features

- Automatic message monitoring from source channel
- OpenAI GPT-4o mini translation to Russian Zoomer slang
- Robust error handling with retries
- Containerized deployment with Docker
- Persistent session storage
- Comprehensive logging

## Setup

### Prerequisites

- Telegram API credentials (API ID and Hash) from [my.telegram.org](https://my.telegram.org/)
- OpenAI API key from [OpenAI dashboard](https://platform.openai.com/account/api-keys)
- Docker and Docker Compose (recommended)

### Configuration

1. Copy the sample environment file:
   ```
   cp env.sample .env
   ```

2. Edit `.env` with your credentials:
   ```
   TG_API_ID=your_telegram_api_id
   TG_API_HASH=your_telegram_api_hash
   OPENAI_API_KEY=your_openai_api_key
   SRC_CHANNEL=source_channel_username_or_id
   DST_CHANNEL=destination_channel_username_or_id
   TG_SESSION=nyt_to_zoom
   ```

### Running with Docker (recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Running without Docker

```bash
# Install requirements
pip install -r requirements.txt

# Run the bot
python bot.py
```

## First-time Authentication

On first run, the bot will prompt for phone number and verification code in terminal to authenticate with Telegram. After authentication, the session is saved for future runs.

For headless servers, start the bot locally first to create the session file, then copy it to the server.

## Authentication

This bot uses Telethon to authenticate with Telegram. The authentication process has been redesigned for reliability:

1. First, clear any existing sessions: `python scripts/reset_all_sessions.py`
2. Create a new authenticated session: `python test_minimal.py`
   - You'll be prompted for the authentication code sent to your Telegram account
3. Once authenticated, run the bot normally: `python bot.py` or `make start`

If authentication fails or times out, check the troubleshooting section in PROJECT.md.

## Maintenance

- Logs are stored in `logs/` directory
- Session files are stored in `session/` directory
- To update the bot, pull the latest code and restart the container:
  ```
  git pull
  docker-compose up -d --build
  ```

## License

MIT 