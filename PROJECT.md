# Telegram NYT-to-Zoomer Bot - Production Guide

## Current Progress
- [x] Create basic bot script
- [x] Set up error handling
- [x] Configure Docker deployment
- [x] Bot running in production
- [x] Multiple translation styles implemented
- [x] Sophisticated prompting for authentic slang
- [x] Fixed Docker volume permissions on macOS

## Step-by-Step Deployment Path

### 1. Setup API Credentials
- [x] Telegram API setup:
  - [x] Register app at my.telegram.org
  - [x] Get API ID and Hash
  - [x] Store in a text file temporarily
- [x] OpenAI API setup:
  - [x] Create API key in dashboard
  - [x] Set usage limits ($10/day recommended)
  - [x] Copy key to a secure location

### 2. Configure Environment
- [x] Create .env file with credentials:
  - [x] Copy from .env-example
  - [x] Add Telegram API_ID and API_HASH
  - [x] Add OPENAI_API_KEY
  - [x] Set SRC_CHANNEL and DST_CHANNEL values
  - [x] Set TG_SESSION name if needed
  - [x] Configure TRANSLATION_STYLE (LEFT, RIGHT, or BOTH)

### 3. Local Testing
- [x] Run initial Telegram authentication:
  - [x] Run `make run` for first-time setup
  - [x] Enter phone number when prompted
  - [x] Enter verification code sent to Telegram
  - [x] Verify session file created
- [x] Test basic translation:
  - [x] Check message received from source channel
  - [x] Verify translation to destination channel
  - [x] Confirm logs are working

### 4. Docker Deployment
- [x] Create directories:
  - [x] `mkdir -p logs session backups`
- [x] Set up Docker volumes properly:
  - [x] Create setup_docker.sh script for session file copying
  - [x] Update Makefile with setup-docker target
  - [x] Ensure bot.py can handle Docker non-interactive mode
- [x] Build Docker container:
  - [x] `make build`
- [x] Start service:
  - [x] `make start` (runs setup-docker automatically)
- [x] Check container logs:
  - [x] `make logs`
- [x] Verify bot is running properly
- [x] Fix Docker volume permissions on macOS with named volumes

### 5. Monitoring & Maintenance
- [x] Set up basic health check:
  - [x] Run `./healthcheck.py` to test bot status
  - [x] Schedule regular checks (cron job)
- [x] Create backup procedure:
  - [x] Test `./scripts/backup.sh`
  - [x] Schedule regular backups

### 6. Translation Styles
- [x] LEFT style (Progressive Russian zoomer):
  - [x] Modern slang with progressive undertones
  - [x] Authentic Gen-Z language patterns
  - [x] Edgy humor with trendy references
- [x] RIGHT style (Nationalist "bidlo"):
  - [x] More aggressive and nationalist tone
  - [x] Traditional values emphasis
  - [x] Rougher slang with attitude

## Docker Troubleshooting
- [x] Session file copying:
  - [x] Use setup_docker.sh script to copy session file to Docker volume
  - [x] Ensure session file exists locally before Docker deployment
- [x] Volume permissions:
  - [x] Use named volumes in docker-compose.yml
  - [x] Avoid direct bind mounts on macOS
- [x] Non-interactive mode:
  - [x] Bot.py detects Docker environment
  - [x] Skip interactive prompts when in container

## Production Checklist
- [x] Verified all environment variables
- [x] Tested authentication flow
- [x] Bot connected to correct channels
- [x] Translation working as expected
- [x] Logs capturing activity
- [x] Container restarts automatically
- [x] Backups configured
- [x] Multiple translation styles working
- [x] Docker deployment fully automated

## Troubleshooting Guide
- If authentication fails: Check API credentials
- If translations not working: Verify OpenAI key and model access
- If bot connects but no messages: Check channel permissions
- If container crashes: Check logs for error details
- If English text appears in translations: Adjust prompts to enforce full translation
- If Docker volumes have permission issues on macOS: Use named volumes in docker-compose.yml

## Quick Commands
```
# Build and start
make start

# Check logs
make logs

# Stop bot
make stop

# Check status
./healthcheck.py

# Test translations
python test_zoomer.py

# Setup Docker volume (done automatically by 'make start')
./setup_docker.sh
``` 