# Telegram NYT-to-Zoomer Bot - Production Guide

## Current Progress
- [x] Create basic bot script
- [x] Set up error handling
- [x] Configure Docker deployment
- [x] Bot running in production
- [x] Multiple translation styles implemented
- [x] Sophisticated prompting for authentic slang
- [x] Fixed Docker volume permissions on macOS
- [x] Added AI image generation based on post content
- [x] Added ability to process multiple recent posts
- [x] Added test channels for end-to-end testing
- [x] AWS deployment instructions

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
  - [x] Copy from env.sample
  - [x] Add Telegram API ID and API Hash
  - [x] Add OpenAI API key
  - [x] Set source and destination channels
  - [x] Configure translation style and image generation

### 3. Local Development
- [x] Set up virtual environment:
  - [x] Install Python 3.11+
  - [x] Install dependencies via pip
- [x] First run to create session file
- [x] Test basic functionality

### 4. Docker Setup
- [x] Build container
- [x] Configure volumes for session persistence
- [x] Set up Docker networking
- [x] Test Docker deployment
- [x] Create script for Docker volume setup

### 5. Production Deployment
- [x] Deploy to server
- [x] Configure systemd service or similar
- [x] Set up monitoring & healthchecks
- [x] Configure logging
- [x] Create backup strategy

### 6. Enhanced Features
- [x] Multiple translation styles:
  - [x] LEFT - progressive Russian zoomer slang
  - [x] RIGHT - nationalist "bidlo" style
  - [x] Choose style via TRANSLATION_STYLE env var
- [x] Image generation for posts:
  - [x] Using DALL-E 3 for context-aware images
  - [x] Control via GENERATE_IMAGES env var
- [x] Batch processing:
  - [x] Process N most recent posts from source channel
  - [x] Run with `python bot.py --process-recent 10`

### 7. Testing
- [x] Setup test channels:
  - [x] Test source channel for posting test content
  - [x] Test destination for verifying translations
- [x] Create test scripts:
  - [x] Run core test with `python test_core.py` (tests OpenAI integration)
  - [x] Run e2e test with `python test_e2e.py` (tests Telegram messaging)

## AWS Deployment Instructions

### Setup EC2 Instance
1. Launch an Amazon EC2 instance:
   - Recommended: t3.small or larger (2GB RAM minimum)
   - Ubuntu Server LTS (20.04 or newer)
   - Add at least 20GB of storage

2. Configure security groups:
   - Allow SSH (port 22) from your IP
   - Allow HTTPS (port 443) if using webhook mode
   - Allow any additional monitoring ports if needed

3. Connect to instance:
   ```
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

### Install Docker & Docker Compose
```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install docker.io -y
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install docker-compose -y

# Log out and back in to apply group changes
exit
# SSH back in
```

### Deploy the Bot
1. Set up project directory:
   ```bash
   mkdir -p ~/telegram_zoomer
   cd ~/telegram_zoomer
   ```

2. Clone the repository or upload files:
   ```bash
   # Option 1: Clone from repository
   git clone your-repository-url .
   
   # Option 2: Upload files via SCP
   # Run this from your local machine
   scp -i your-key.pem -r /path/to/telegram_zoomer/* ubuntu@your-instance-ip:~/telegram_zoomer/
   ```

3. Create .env file:
   ```bash
   cp env.sample .env
   nano .env
   # Add your API keys and channel information
   ```

4. Set up session file:
   - Copy your existing session file to the instance:
   ```bash
   # From local machine
   scp -i your-key.pem /path/to/nyt_to_zoom.session ubuntu@your-instance-ip:~/telegram_zoomer/
   ```

5. Start services:
   ```bash
   cd ~/telegram_zoomer
   chmod +x setup_docker.sh
   ./setup_docker.sh
   docker-compose up -d
   ```

### Monitoring and Maintenance
1. Set up a simple health check service:
   ```bash
   # Create a script to check if the container is running
   cat > /home/ubuntu/healthcheck.sh << 'EOL'
   #!/bin/bash
   if ! docker ps | grep telegram-zoomer > /dev/null; then
     cd /home/ubuntu/telegram_zoomer
     docker-compose up -d
     echo "Bot restarted at $(date)" >> /home/ubuntu/restart.log
   fi
   EOL
   
   chmod +x /home/ubuntu/healthcheck.sh

   # Add to crontab
   (crontab -l 2>/dev/null; echo "*/10 * * * * /home/ubuntu/healthcheck.sh") | crontab -
   ```

2. Set up log rotation:
   ```bash
   sudo apt install logrotate -y
   
   sudo cat > /etc/logrotate.d/telegram_zoomer << 'EOL'
   /home/ubuntu/telegram_zoomer/logs/bot.log {
     daily
     rotate 7
     compress
     delaycompress
     missingok
     notifempty
     create 640 ubuntu ubuntu
   }
   EOL
   ```

### Automated Backups to S3
1. Install AWS CLI:
   ```bash
   sudo apt install awscli -y
   ```

2. Configure AWS credentials:
   ```bash
   aws configure
   # Enter your AWS Access Key, Secret Key, region, and output format
   ```

3. Create a backup script:
   ```bash
   cat > /home/ubuntu/backup.sh << 'EOL'
   #!/bin/bash
   DATE=$(date +%Y-%m-%d_%H-%M-%S)
   BACKUP_DIR="/home/ubuntu/backups"
   mkdir -p $BACKUP_DIR
   
   # Backup session and logs
   tar -czf $BACKUP_DIR/telegram_zoomer_$DATE.tar.gz -C /home/ubuntu/telegram_zoomer session logs
   
   # Upload to S3
   aws s3 cp $BACKUP_DIR/telegram_zoomer_$DATE.tar.gz s3://your-bucket-name/backups/
   
   # Clean up old local backups (keep last 5)
   ls -t $BACKUP_DIR/*.tar.gz | tail -n +6 | xargs -r rm
   EOL
   
   chmod +x /home/ubuntu/backup.sh
   
   # Add to crontab for daily backup
   (crontab -l 2>/dev/null; echo "0 0 * * * /home/ubuntu/backup.sh") | crontab -
   ```

## Setup Commands Summary
```bash
# First-time setup
pip install -r requirements.txt
python bot.py  # Create session file

# Docker setup
make build
./setup_docker.sh  # Copy session to volume
make start

# Process recent posts
python bot.py --process-recent 10

# Testing
python test_core.py  # Test OpenAI integration
python test_e2e.py   # Test Telegram posting (requires authentication)
```

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
- [x] To pinpoint start/auth hang:
  - Disable image generation: set `GENERATE_IMAGES=false` to rule out the image path
  - Run in batch mode: `python bot.py --process-recent 1` to bypass live event loop
  - Test a minimal Telethon connect script that only loads the session and calls `client.connect()`

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
- For Telethon connection issues:
  - Use `ConnectionTcpAbridged` connection type
  - Provide `device_model`, `system_version`, and `app_version` parameters
  - Use connection timeout pattern with `create_task()` + `wait_for()`
  - Avoid global client variable, use function parameter instead

## Authentication Steps
1. Ensure you have the correct API credentials in your .env file
2. Run the bot with `python bot.py`
3. Enter the verification code when prompted

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

## Overview
A Telegram bot that monitors a source channel (NYT) and translates its posts into Russian zoomer slang, posting them to a destination channel with an optional AI-generated image illustration.

## Project Status
- ✅ Bot core functionality working
- ✅ Integration with OpenAI for translations (GPT-4o)
- ✅ Dual translation styles (LEFT and RIGHT zoomer slang)
- ✅ Image generation with DALL-E
- ✅ End-to-end testing completed with test source and destination channels
- ✅ Production deployment ready

## Project Structure
- `bot.py` - Main bot logic, handles Telegram connection and processing
- `translator.py` - Handles translation requests to OpenAI API
- `image_generator.py` - Handles image generation with DALL-E
- `test_core.py` - Non-Telegram tests for translation and image generation
- `test_e2e.py` - End-to-end tests with Telegram integration

## Configuration
- Environment variables in `.env` file
- Required fields:
  - `TG_API_ID` and `TG_API_HASH` - Telegram API credentials
  - `TG_SESSION` - Session file name
  - `TG_PHONE` - Phone number for authentication
  - `OPENAI_API_KEY` - OpenAI API key
  - `SRC_CHANNEL` and `DST_CHANNEL` - Telegram channel usernames
  - `TRANSLATION_STYLE` - "left", "right", or "both"
  - `GENERATE_IMAGES` - "true" or "false" 