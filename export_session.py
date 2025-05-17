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

# APP_STATE_FILE should be consistent with session_manager.py
APP_STATE_FILE = "session/app_state.json" 

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

def get_app_state_base64():
    """
    Reads the current application state from APP_STATE_FILE (session/app_state.json),
    encodes it to JSON, and then to base64.
    Returns base64 encoded JSON string or a base64 encoded default state if file not found or error.
    """
    app_state_content = None
    if os.path.exists(APP_STATE_FILE):
        try:
            with open(APP_STATE_FILE, 'r') as f:
                app_state_content = json.load(f)
            logger.info(f"Loaded application state from {APP_STATE_FILE} for export.")
        except Exception as e:
            print(f"Warning: Could not read app state file {APP_STATE_FILE}: {e}. Using default state for export.")
            app_state_content = None # Fallback to default
    else:
        print(f"Info: App state file {APP_STATE_FILE} not found. Using default state for export.")

    if app_state_content is None:
        # Provide a default starting point if file doesn't exist or is corrupt
        app_state_content = {
            "message_id": 0,
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(), # Look back 1 day for initial setup
            "pts": 0,
            "channel_id": None,
            "updated_at": datetime.now().isoformat()
        }
        logger.info("Using default initial application state for export.")
    
    try:
        # Ensure timestamp is string for JSON dump, if it was loaded as datetime by chance
        if isinstance(app_state_content.get("timestamp"), datetime):
             app_state_content["timestamp"] = app_state_content["timestamp"].isoformat()
        if isinstance(app_state_content.get("updated_at"), datetime):
             app_state_content["updated_at"] = app_state_content["updated_at"].isoformat()

        return base64.b64encode(json.dumps(app_state_content).encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"Error encoding application state: {str(e)}")
        # Fallback to a very basic default if encoding fails for some reason
        default_fallback = {"message_id": 0, "timestamp": datetime.now().isoformat(), "pts": 0}
        return base64.b64encode(json.dumps(default_fallback).encode('utf-8')).decode('utf-8')

def create_export_commands(session_path):
    """
    Create Heroku CLI commands to set the session and app state data as environment variables
    
    Args:
        session_path (str): Path to the session file (without .session extension)
    
    Returns:
        str: Heroku CLI command for setting environment variables or None
    """
    # Export the session data
    encoded_session = export_session_to_base64(session_path)
    if not encoded_session:
        return None
    
    # Get current application state, base64 encoded
    encoded_app_state = get_app_state_base64()
    
    # Display truncated data for confirmation
    session_display = f"{encoded_session[:30]}..." if len(encoded_session) > 30 else encoded_session
    app_state_display = f"{encoded_app_state[:30]}..." if len(encoded_app_state) > 30 else encoded_app_state

    # Standardizing on TG_SESSION_STRING for the session content itself
    print(f"Telethon session string (TG_SESSION_STRING): {session_display}") 
    print(f"Application state (LAST_PROCESSED_STATE): {app_state_display}")
    
    # Use a single command to set all variables
    command = (
        f'heroku config:set TG_SESSION_STRING="{encoded_session}" '
        f'LAST_PROCESSED_STATE="{encoded_app_state}" --app YOUR_APP_NAME'
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