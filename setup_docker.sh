#!/bin/bash

echo "Setting up Docker volumes for Telegram Zoomer Bot"

# Make script executable
chmod +x setup_docker.sh

# Create a temporary container with the volumes attached
echo "Creating temporary container to copy session file..."
docker run --name temp_container -v telegram_zoomer_telegram_session:/session alpine /bin/sh -c "mkdir -p /session"

# Copy the session file to the container
echo "Copying nyt_to_zoom.session to Docker volume..."
docker cp nyt_to_zoom.session temp_container:/session/

# Clean up
echo "Cleaning up temporary container..."
docker rm temp_container

echo "Setup complete! You can now run 'make start' to start the bot in Docker." 