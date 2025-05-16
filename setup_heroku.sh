#!/bin/bash
# Script to set up Heroku environment variables from .env file

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Error: .env file not found"
  exit 1
fi

# Heroku app name
APP_NAME="nyt-zoomer-bot"

echo "Setting up environment variables for $APP_NAME..."

# Read each line from .env file
while read -r line; do
  # Skip empty lines and comments
  if [[ -z "$line" || "$line" == \#* ]]; then
    continue
  fi
  
  # Extract variable name and value
  var_name=$(echo "$line" | cut -d= -f1)
  
  # Set variable on Heroku (without showing the value)
  echo "Setting $var_name..."
  heroku config:set "$line" --app "$APP_NAME"
done < .env

echo "Environment variables set successfully!"
echo "Now scale up your worker dyno with: heroku ps:scale worker=1 --app $APP_NAME" 