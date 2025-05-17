#!/usr/bin/env python3
"""
Script to export a Telegram session file to base64 format for Heroku environment variable.

This is needed because Heroku has an ephemeral filesystem which loses all files on each restart.
By storing the session data in an environment variable, we can recreate it on each start.
It also prepares placeholder data for LAST_PROCESSED_STATE and CHANNEL_PTS_DATA.
"""

import base64
import os
import sys
import json
from datetime import datetime, timedelta
import logging

# Default location for the PTS data file, mirrors app/pts_manager.py
PTS_DATA_FILE = os.getenv("PTS_DATA_FILE", "session/channel_pts.json")

def export_session_to_base64(session_path):
    """
    Export a session file to base64 encoding
    
    Args:
        session_path (str): Path to the session file (without .session extension)
    
    Returns:
        str: Base64 encoded session data or None
    """
    session_file = f"{session_path}.session"
    
    if not os.path.exists(session_file):
        print(f"Error: Session file {session_file} not found.")
        return None
    
    try:
        with open(session_file, 'rb') as f:
            session_data = f.read()
        
        encoded_data = base64.b64encode(session_data).decode('utf-8')
        return encoded_data
    except Exception as e:
        print(f"Error exporting session: {str(e)}")
        return None

def get_current_pts_data_base64():
    """
    Reads the current PTS data from the PTS_DATA_FILE, 
    encodes it to JSON, and then to base64.
    Returns base64 encoded JSON string or a base64 encoded empty JSON object if file not found.
    """
    pts_content = {}
    if os.path.exists(PTS_DATA_FILE):
        try:
            with open(PTS_DATA_FILE, 'r') as f:
                pts_content = json.load(f)
            logger.info(f"Loaded PTS data from {PTS_DATA_FILE} for export.")
        except Exception as e:
            print(f"Warning: Could not read PTS data file {PTS_DATA_FILE}: {e}. Using empty PTS data for export.")
    else:
        print(f"Info: PTS data file {PTS_DATA_FILE} not found. Using empty PTS data for export.")
    
    try:
        return base64.b64encode(json.dumps(pts_content).encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"Error encoding PTS data: {str(e)}")
        return base64.b64encode(json.dumps({}).encode('utf-8')).decode('utf-8')

def create_export_commands(session_path):
    """
    Create Heroku CLI commands to set the session and state data as environment variables
    
    Args:
        session_path (str): Path to the session file (without .session extension)
    
    Returns:
        str: Heroku CLI command for setting environment variables or None
    """
    # Export the session data
    encoded_session = export_session_to_base64(session_path)
    if not encoded_session:
        return None
    
    # Prepare LAST_PROCESSED_STATE (placeholder if not set, as bot manages it)
    # This state is mostly managed by the bot itself via session_manager.py on Heroku.
    # We provide a default starting point.
    default_last_processed_state = {
        "message_id": 0,
        "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
        "pts": 0,
        "updated_at": datetime.now().isoformat()
    }
    encoded_last_processed_state = base64.b64encode(json.dumps(default_last_processed_state).encode('utf-8')).decode('utf-8')

    # Get current PTS data, base64 encoded
    encoded_channel_pts_data = get_current_pts_data_base64()
    
    # Display truncated data for confirmation
    session_display = f"{encoded_session[:30]}..." if len(encoded_session) > 30 else encoded_session
    state_display = f"{encoded_last_processed_state[:30]}..." if len(encoded_last_processed_state) > 30 else encoded_last_processed_state
    pts_display = f"{encoded_channel_pts_data[:30]}..." if len(encoded_channel_pts_data) > 30 else encoded_channel_pts_data

    print(f"Session data (SESSION_DATA): {session_display}")
    print(f"Initial last processed state (LAST_PROCESSED_STATE): {state_display}")
    print(f"Channel PTS data (CHANNEL_PTS_DATA): {pts_display}")
    
    # Use a single command to set all variables
    # Note: USE_ENV_PTS_STORAGE=true will also be set by setup_heroku.sh directly
    command = (
        f'heroku config:set SESSION_DATA="{encoded_session}" '
        f'LAST_PROCESSED_STATE="{encoded_last_processed_state}" '
        f'CHANNEL_PTS_DATA="{encoded_channel_pts_data}" --app YOUR_APP_NAME'
    )
    
    return command

if __name__ == "__main__":
    # Basic logger for info/warnings during export script execution
    # This is separate from the main app logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger = logging.getLogger('export_session')

    if len(sys.argv) < 2:
        print("Usage: python export_session.py <session_path_without_extension>")
        print("Example: python export_session.py session/new_session")
        sys.exit(1)
    
    session_path_arg = sys.argv[1]
    # Ensure TG_SESSION is respected if .env is loaded and this script is called with that value
    # However, for clarity, the argument directly dictates the session file to export.
    
    heroku_commands = create_export_commands(session_path_arg)
    
    if heroku_commands:
        print("\nRun the following command to set these environment variables on Heroku:")
        print(heroku_commands)
        print("\nReplace YOUR_APP_NAME with your actual Heroku app name.")
        print("Alternatively, setup_heroku.sh can use this script to set them automatically.")
    else:
        print("Failed to create export commands. Ensure the session file exists.")
        sys.exit(1) 