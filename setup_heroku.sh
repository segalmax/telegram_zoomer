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

# Determine session path: Use TG_SESSION from .env if set, otherwise default
SESSION_PATH_FROM_ENV=$(grep "^TG_SESSION=" "$ENV_FILE" 2>/dev/null | cut -d '=' -f2-)
if [ -z "$SESSION_PATH_FROM_ENV" ]; then
  # Fallback if TG_SESSION not in .env, though it's expected for this project
  # The python export_session.py script takes the session path as an argument
  # For this shell script, we need a reliable way to know which session to export.
  # Defaulting to 'new_session' as per user's .env configuration for the main bot.
  ACTUAL_SESSION_PATH="new_session"
  echo "Warning: TG_SESSION not found in $ENV_FILE. Assuming session path is '$ACTUAL_SESSION_PATH' for export."
else
  ACTUAL_SESSION_PATH="$SESSION_PATH_FROM_ENV"
  echo "Using session path from TG_SESSION in $ENV_FILE: $ACTUAL_SESSION_PATH"
fi

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found at $ENV_FILE"
  exit 1
fi

# Check if the determined session file exists
if [ ! -f "${ACTUAL_SESSION_PATH}.session" ]; then
  echo "Error: Session file ${ACTUAL_SESSION_PATH}.session not found"
  echo "Please run the bot locally (python -m app.bot) with TG_SESSION=${ACTUAL_SESSION_PATH} in your .env to create and authorize this session file."
  exit 1
fi

# Export session and other state data to base64
echo "Exporting data from ${ACTUAL_SESSION_PATH}.session and PTS file..."
# The export_session.py script now prints each variable on a new line with a clear key
EXPORT_OUTPUT=$(python3 export_session.py "$ACTUAL_SESSION_PATH")

if [[ $EXPORT_OUTPUT == *"Error:"* ]]; then
  echo "Error during export_session.py execution:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

# Extract data using grep and cut from the new output format
# Assuming output like: 
# Session data (SESSION_DATA): base64stuff...
# Initial last processed state (LAST_PROCESSED_STATE): base64stuff...
# Channel PTS data (CHANNEL_PTS_DATA): base64stuff...

SESSION_DATA_LINE=$(echo "$EXPORT_OUTPUT" | grep "Session data (SESSION_DATA):")
LAST_PROCESSED_STATE_LINE=$(echo "$EXPORT_OUTPUT" | grep "Initial last processed state (LAST_PROCESSED_STATE):")
CHANNEL_PTS_DATA_LINE=$(echo "$EXPORT_OUTPUT" | grep "Channel PTS data (CHANNEL_PTS_DATA):")

HEROKU_COMMAND_LINE=$(echo "$EXPORT_OUTPUT" | grep "heroku config:set")

SESSION_DATA=$(echo "$SESSION_DATA_LINE" | sed 's/Session data (SESSION_DATA): //' | sed 's/\.\.\.$//')
LAST_PROCESSED_STATE=$(echo "$LAST_PROCESSED_STATE_LINE" | sed 's/Initial last processed state (LAST_PROCESSED_STATE): //' | sed 's/\.\.\.$//')
CHANNEL_PTS_DATA=$(echo "$CHANNEL_PTS_DATA_LINE" | sed 's/Channel PTS data (CHANNEL_PTS_DATA): //' | sed 's/\.\.\.$//')

# If sed couldn't remove ..., it means the string was short, so use the full value from the command line
# This is a bit fragile; ideally export_session.py would output raw values for easier parsing.
# For now, we will use the direct values from the heroku command line that script suggests.

CONFIG_VARS_TO_SET=$(echo "$HEROKU_COMMAND_LINE" | sed "s/heroku config:set //" | sed "s/ --app YOUR_APP_NAME//")

if [ -z "$CONFIG_VARS_TO_SET" ]; then
  echo "Error: Failed to extract necessary data from export_session.py output."
  echo "Full output:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

# Set Heroku config vars from .env file (excluding TG_SESSION, SESSION_DATA, etc.)
echo "Setting general environment variables from $ENV_FILE on Heroku app: $APP_NAME"
EXCLUDED_VARS="^(TG_SESSION|SESSION_DATA|LAST_PROCESSED_STATE|CHANNEL_PTS_DATA|USE_ENV_PTS_STORAGE)=.*"

while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip empty lines, comments, and excluded vars
  if [[ -z "$line" || "$line" == \#* || "$line" =~ $EXCLUDED_VARS ]]; then
    continue
  fi
  
  echo "Setting: $line"
  heroku config:set "$line" --app "$APP_NAME"
done < "$ENV_FILE"

# Set the crucial exported data
echo "Setting exported data (SESSION_DATA, LAST_PROCESSED_STATE, CHANNEL_PTS_DATA)..."
# The CONFIG_VARS_TO_SET already contains the key=value pairs format
heroku config:set $CONFIG_VARS_TO_SET --app "$APP_NAME"

# Explicitly set USE_ENV_PTS_STORAGE to true for Heroku
echo "Setting USE_ENV_PTS_STORAGE=true..."
heroku config:set USE_ENV_PTS_STORAGE=true --app "$APP_NAME"

echo "Done! Heroku environment is now configured for app: $APP_NAME" 