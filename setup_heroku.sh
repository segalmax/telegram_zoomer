#!/bin/bash

# Heroku deployment script for Telegram Zoomer Bot
# Deploys environment variables only - sessions are created interactively on Heroku

set -e

# Configuration
ENV_FILE=".env"
APP_SETTINGS_ENV_FILE="app_settings.env"

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
  echo "Error: Heroku CLI is not installed. Please install it first."
  exit 1
fi

# Check if logged into Heroku
if ! heroku auth:whoami &> /dev/null; then
  echo "Error: Not logged into Heroku. Please run 'heroku login' first."
  exit 1
fi

# Get app name from app_settings.env
if [ ! -f "$APP_SETTINGS_ENV_FILE" ]; then
  echo "Error: $APP_SETTINGS_ENV_FILE not found"
  exit 1
fi

APP_NAME=$(grep "^HEROKU_APP_NAME=" "$APP_SETTINGS_ENV_FILE" | cut -d '=' -f2-)
if [ -z "$APP_NAME" ]; then
  echo "Error: HEROKU_APP_NAME not found in $APP_SETTINGS_ENV_FILE"
  exit 1
fi

echo "Deploying to Heroku app: $APP_NAME"

# Deploy environment variables from .env (secrets)
if [ -f "$ENV_FILE" ]; then
  echo "Deploying secrets from $ENV_FILE..."
  while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    
    # Remove any surrounding quotes from value
    value=$(echo "$value" | sed 's/^["'\'']//' | sed 's/["'\'']$//')
    
    echo "Setting $key"
    heroku config:set "$key=$value" --app "$APP_NAME"
  done < "$ENV_FILE"
else
  echo "Warning: $ENV_FILE not found, skipping secrets deployment"
fi

# Deploy environment variables from app_settings.env
echo "Deploying settings from $APP_SETTINGS_ENV_FILE..."
while IFS='=' read -r key value; do
  # Skip empty lines and comments
  [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
  
  # Skip HEROKU_APP_NAME (not needed on Heroku itself)
  [[ "$key" == "HEROKU_APP_NAME" ]] && continue
  
  # Remove any surrounding quotes from value
  value=$(echo "$value" | sed 's/^["'\'']//' | sed 's/["'\'']$//')
  
  echo "Setting $key"
  heroku config:set "$key=$value" --app "$APP_NAME"
done < "$APP_SETTINGS_ENV_FILE"

# Clean up obsolete variables
echo "Cleaning up obsolete variables..."
for var in SESSION_DATA TG_SESSION_STRING TG_COMPRESSED_SESSION_STRING LAST_PROCESSED_STATE; do
  if heroku config:get "$var" --app "$APP_NAME" >/dev/null 2>&1; then
    echo "Unsetting obsolete $var..."
    heroku config:unset "$var" --app "$APP_NAME"
  fi
done

echo "✅ Deployment complete!"
echo "📱 The bot will create its session interactively on first run on Heroku"
echo "📊 Check deployment: heroku logs --tail --app $APP_NAME" 