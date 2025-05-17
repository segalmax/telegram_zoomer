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
echo "Exporting Telethon session string and application state..."
EXPORT_OUTPUT=$(python3 export_session.py "$ACTUAL_SESSION_PATH")

if [[ $EXPORT_OUTPUT == *"Error:"* ]]; then
  echo "Error during export_session.py execution:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

# Extract the line containing the heroku config:set command suggestion
HEROKU_COMMAND_LINE=$(echo "$EXPORT_OUTPUT" | grep "heroku config:set")

# Extract only the 'KEY="VALUE" KEY2="VALUE2"' part
CONFIG_VARS_TO_SET=$(echo "$HEROKU_COMMAND_LINE" | sed -e "s/heroku config:set //" -e "s/ --app YOUR_APP_NAME//")

if [ -z "$CONFIG_VARS_TO_SET" ]; then
  echo "Error: Failed to extract necessary data from export_session.py output."
  echo "Full output from export_session.py:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

echo "Variables to set from export_session.py: $CONFIG_VARS_TO_SET"

# Set Heroku config vars from .env file (excluding TG_SESSION and others managed by export_session.py)
echo "Setting general environment variables from $ENV_FILE on Heroku app: $APP_NAME"
# Exclude TG_SESSION (session name for local client), TG_SESSION_STRING (actual session content),
# and LAST_PROCESSED_STATE (app state). These are handled by export_session.py output.
EXCLUDED_VARS="^(TG_SESSION|TG_SESSION_STRING|LAST_PROCESSED_STATE)=.*"

while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip empty lines, comments, and excluded vars
  if [[ -z "$line" || "$line" == \#* || "$line" =~ $EXCLUDED_VARS ]]; then
    continue
  fi
  
  echo "Setting: $line"
  heroku config:set "$line" --app "$APP_NAME"
done < "$ENV_FILE"

# Set the crucial exported data (TG_SESSION_STRING and LAST_PROCESSED_STATE)
echo "Setting exported Telethon session string and application state..."
heroku config:set $CONFIG_VARS_TO_SET --app "$APP_NAME"

# Remove obsolete variables if they exist on Heroku
# Check if CHANNEL_PTS_DATA is set and unset it
if heroku config:get CHANNEL_PTS_DATA --app "$APP_NAME" >/dev/null 2>&1; then
  echo "Unsetting obsolete CHANNEL_PTS_DATA variable..."
  heroku config:unset CHANNEL_PTS_DATA --app "$APP_NAME"
fi

# Check if USE_ENV_PTS_STORAGE is set and unset it
if heroku config:get USE_ENV_PTS_STORAGE --app "$APP_NAME" >/dev/null 2>&1; then
  echo "Unsetting obsolete USE_ENV_PTS_STORAGE variable..."
  heroku config:unset USE_ENV_PTS_STORAGE --app "$APP_NAME"
fi

# Check if old SESSION_DATA is set and unset it (replaced by TG_SESSION_STRING)
if heroku config:get SESSION_DATA --app "$APP_NAME" >/dev/null 2>&1; then
  echo "Unsetting obsolete SESSION_DATA variable (replaced by TG_SESSION_STRING)..."
  heroku config:unset SESSION_DATA --app "$APP_NAME"
fi

echo "Done! Heroku environment is now configured for app: $APP_NAME" 