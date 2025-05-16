#!/bin/bash
# Script to set up Heroku environment variables for Telegram Zoomer Bot

set -e # Exit on error

# Check if app name is provided
if [ -z "$1" ]; then
  echo "Usage: ./setup_heroku.sh <heroku-app-name>"
  exit 1
fi

APP_NAME="$1"
ENV_FILE=".env"
SESSION_PATH=$(grep "TG_SESSION" .env | cut -d "=" -f2)

# Default session path if not found in .env
if [ -z "$SESSION_PATH" ]; then
  SESSION_PATH="session/test_session_persistent"
  echo "Using default session path: $SESSION_PATH"
fi

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found"
  exit 1
fi

# Check if session file exists
if [ ! -f "${SESSION_PATH}.session" ]; then
  echo "Error: Session file ${SESSION_PATH}.session not found"
  echo "Please run the bot locally first to create a session file"
  exit 1
fi

# Export session to base64
echo "Exporting session from ${SESSION_PATH}.session..."
RESULT=$(python3 export_session.py "$SESSION_PATH")

if [[ $RESULT == *"Error"* ]]; then
  echo "$RESULT"
  exit 1
fi

# Extract session data from the output
SESSION_DATA=$(echo "$RESULT" | grep "SESSION_DATA=" | head -1 | cut -d "=" -f2)
STATE_DATA=$(grep "LAST_PROCESSED_STATE=" <<<"$RESULT" | head -1 | cut -d "=" -f2- | tr -d '"')

if [ -z "$SESSION_DATA" ]; then
  echo "Error: Failed to extract session data from export script"
  exit 1
fi

# Set Heroku config vars from .env file
echo "Setting environment variables on Heroku app: $APP_NAME"
while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip empty lines and comments
  if [[ -z "$line" || "$line" == \#* ]]; then
    continue
  fi
  
  # Set each environment variable
  echo "Setting: $line"
  heroku config:set "$line" --app "$APP_NAME"
done < "$ENV_FILE"

# Set the session data separately to avoid issues with special characters
echo "Setting SESSION_DATA..."
heroku config:set "SESSION_DATA=$SESSION_DATA" --app "$APP_NAME"

# Set the last processed message state if available
if [ -n "$STATE_DATA" ]; then
  echo "Setting LAST_PROCESSED_STATE..."
  heroku config:set "LAST_PROCESSED_STATE=$STATE_DATA" --app "$APP_NAME"
fi

echo "Done! Heroku environment is now configured." 