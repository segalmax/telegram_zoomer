#!/bin/bash
# Script to set up Heroku environment variables for Telegram Zoomer Bot

set -e # Exit on error

APP_SETTINGS_ENV_FILE="app_settings.env"
SECRET_ENV_FILE=".env"

# Check if app_settings.env file exists
if [ ! -f "$APP_SETTINGS_ENV_FILE" ]; then
  echo "Error: App settings environment file '$APP_SETTINGS_ENV_FILE' not found."
  exit 1
fi

# Source Heroku App Name from app_settings.env
HEROKU_APP_NAME_FROM_SETTINGS=$(grep "^HEROKU_APP_NAME=" "$APP_SETTINGS_ENV_FILE" 2>/dev/null | cut -d '=' -f2-)
if [ -z "$HEROKU_APP_NAME_FROM_SETTINGS" ]; then
  echo "Error: HEROKU_APP_NAME not found in $APP_SETTINGS_ENV_FILE. Please add it."
  exit 1
fi
APP_NAME="$HEROKU_APP_NAME_FROM_SETTINGS"
echo "Using Heroku App Name from $APP_SETTINGS_ENV_FILE: [$APP_NAME]"

# Check if essential files exist
if [ ! -f "$SECRET_ENV_FILE" ]; then
  echo "Error: Secret environment file '$SECRET_ENV_FILE' not found."
  exit 1
fi
if [ ! -f "$APP_SETTINGS_ENV_FILE" ]; then
  echo "Error: App settings environment file '$APP_SETTINGS_ENV_FILE' not found."
  exit 1
fi

# Determine session path: Must come from app_settings.env
SESSION_PATH_FROM_APP_SETTINGS=$(grep "^TG_SESSION=" "$APP_SETTINGS_ENV_FILE" 2>/dev/null | cut -d '=' -f2-)
if [ -z "$SESSION_PATH_FROM_APP_SETTINGS" ]; then
  echo "Error: TG_SESSION not found in $APP_SETTINGS_ENV_FILE. This is required."
  exit 1
else
  ACTUAL_SESSION_PATH="$SESSION_PATH_FROM_APP_SETTINGS"
  echo "Using session path from TG_SESSION in $APP_SETTINGS_ENV_FILE: $ACTUAL_SESSION_PATH"
fi

# Check if the determined session file exists
if [ ! -f "${ACTUAL_SESSION_PATH}.session" ]; then
  echo "Error: Session file ${ACTUAL_SESSION_PATH}.session not found"
  echo "Please run create_heroku_session.py or ensure TG_SESSION in $APP_SETTINGS_ENV_FILE points to an existing session file."
  exit 1
fi

# Export session and other state data to base64
echo "Exporting Telethon session string and application state using session: $ACTUAL_SESSION_PATH ..."
EXPORT_OUTPUT=$(python3 export_session.py "$ACTUAL_SESSION_PATH")

if [[ $EXPORT_OUTPUT == *"Error:"* ]]; then
  echo "Error during export_session.py execution:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

# Extract the line containing the heroku config:set command suggestion
HEROKU_COMMAND_LINE=$(echo "$EXPORT_OUTPUT" | grep "heroku config:set")

# Extract only the 'KEY="VALUE" KEY2="VALUE2"' part, now expecting TG_COMPRESSED_SESSION_STRING
CONFIG_VARS_TO_SET=$(echo "$HEROKU_COMMAND_LINE" | sed -e "s/heroku config:set //" -e "s/ --app YOUR_APP_NAME//" | sed -e "s/TG_SESSION_STRING/TG_COMPRESSED_SESSION_STRING/g")

if [ -z "$CONFIG_VARS_TO_SET" ]; then
  echo "Error: Failed to extract necessary data from export_session.py output."
  echo "Full output from export_session.py:"
  echo "$EXPORT_OUTPUT"
  exit 1
fi

echo "Variables to set from export_session.py: $CONFIG_VARS_TO_SET"

# Function to set vars from a file
set_vars_from_file() {
  local file_to_process="$1"
  local excluded_vars="$2"
  echo "Processing $file_to_process for Heroku config vars..."
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip empty lines and comments
    if [[ -z "$line" || "$line" == \#* ]]; then
      continue
    fi
    # Skip excluded vars if any
    if [[ -n "$excluded_vars" && "$line" =~ $excluded_vars ]]; then
        echo "Skipping excluded var: $line"
        continue
    fi
    echo "Setting from $file_to_process: $line"
    heroku config:set "$line" --app "$APP_NAME"
  done < "$file_to_process"
}

# Set Heroku config vars from .env (secrets)
# Exclude TG_SESSION, TG_COMPRESSED_SESSION_STRING, TG_SESSION_STRING (old), LAST_PROCESSED_STATE
EXCLUDED_FOR_SECRET_ENV="^(TG_SESSION|TG_COMPRESSED_SESSION_STRING|TG_SESSION_STRING|LAST_PROCESSED_STATE)=.*"
echo "Setting secret environment variables from $SECRET_ENV_FILE on Heroku app: $APP_NAME"
set_vars_from_file "$SECRET_ENV_FILE" "$EXCLUDED_FOR_SECRET_ENV"

# Set Heroku config vars from app_settings.env (app configuration)
# Exclude TG_SESSION, TG_COMPRESSED_SESSION_STRING, TG_SESSION_STRING (old), LAST_PROCESSED_STATE
EXCLUDED_FOR_APP_SETTINGS="^(TG_SESSION|TG_COMPRESSED_SESSION_STRING|TG_SESSION_STRING|LAST_PROCESSED_STATE)=.*"
echo "Setting application settings from $APP_SETTINGS_ENV_FILE on Heroku app: $APP_NAME"
set_vars_from_file "$APP_SETTINGS_ENV_FILE" "$EXCLUDED_FOR_APP_SETTINGS"

# Set the crucial exported data (TG_COMPRESSED_SESSION_STRING and LAST_PROCESSED_STATE)
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

# Check if old SESSION_DATA is set and unset it (replaced by TG_COMPRESSED_SESSION_STRING or TG_SESSION_STRING)
if heroku config:get SESSION_DATA --app "$APP_NAME" >/dev/null 2>&1; then
  echo "Unsetting obsolete SESSION_DATA variable (replaced by TG_COMPRESSED_SESSION_STRING/TG_SESSION_STRING)..."
  heroku config:unset SESSION_DATA --app "$APP_NAME"
fi

# Also try to unset the uncompressed TG_SESSION_STRING if the compressed one is now primary
if heroku config:get TG_SESSION_STRING --app "$APP_NAME" >/dev/null 2>&1; then
  echo "Unsetting old TG_SESSION_STRING as TG_COMPRESSED_SESSION_STRING is now used..."
  heroku config:unset TG_SESSION_STRING --app "$APP_NAME"
fi

echo "Done! Heroku environment is now configured for app: $APP_NAME" 