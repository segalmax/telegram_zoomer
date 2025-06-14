#!/bin/bash

# Heroku Environment Setup Script
# Deploys environment variables to Heroku app
# Sessions are now stored in database, no file transfers needed

set -e

APP_NAME="nyt-zoomer-bot"

echo "🚀 Setting up Heroku environment for $APP_NAME..."

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI not found. Please install it first."
    exit 1
fi

# Check if logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "❌ Not logged in to Heroku. Please run 'heroku login' first."
    exit 1
fi

# Deploy environment variables from .env (secrets)
if [ -f ".env" ]; then
    echo "📦 Deploying secrets from .env..."
    # Read .env and set each variable
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        if [[ -n "$key" && ! "$key" =~ ^[[:space:]]*# ]]; then
            # Remove quotes from value if present
            value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
            echo "Setting $key..."
            heroku config:set "$key=$value" --app "$APP_NAME"
        fi
    done < .env
else
    echo "⚠️  No .env file found - skipping secrets deployment"
fi

# Deploy environment variables from app_settings.env (settings)
if [ -f "app_settings.env" ]; then
    echo "📦 Deploying settings from app_settings.env..."
    # Read app_settings.env and set each variable
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        if [[ -n "$key" && ! "$key" =~ ^[[:space:]]*# ]]; then
            # Remove quotes from value if present
            value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
            echo "Setting $key..."
            heroku config:set "$key=$value" --app "$APP_NAME"
        fi
    done < app_settings.env
else
    echo "⚠️  No app_settings.env file found - skipping settings deployment"
fi

echo "✅ Environment variables deployed successfully!"
echo "📊 Current Heroku config:"
heroku config --app "$APP_NAME"

echo ""
echo "🎯 Deployment complete! Sessions are stored in database."
echo "🔄 Restart the worker dyno to apply changes:"
echo "   heroku ps:restart worker --app $APP_NAME" 