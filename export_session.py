#!/usr/bin/env python3
"""
Script to export a Telegram session file to base64 format for Heroku environment variable.

This is needed because Heroku has an ephemeral filesystem which loses all files on each restart.
By storing the session data in an environment variable, we can recreate it on each start.
"""

import base64
import os
import sys
import json
from datetime import datetime

def export_session(session_path):
    """
    Export a session file to base64 encoding
    
    Args:
        session_path (str): Path to the session file (without .session extension)
    
    Returns:
        str: Base64 encoded session data
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

def create_export_commands(session_path):
    """
    Create Heroku CLI commands to set the session data as environment variables
    
    Args:
        session_path (str): Path to the session file (without .session extension)
    
    Returns:
        str: Heroku CLI command for setting environment variables
    """
    # Export the session data
    encoded_session = export_session(session_path)
    if not encoded_session:
        return None
    
    # Check if LAST_PROCESSED_STATE exists in environment
    state_data = None
    if 'LAST_PROCESSED_STATE' in os.environ:
        state_data = os.environ['LAST_PROCESSED_STATE']
    else:
        # Create a default state if none exists
        default_state = {
            "message_id": 0,
            "timestamp": datetime.now().isoformat(),
            "pts": 0,
            "updated_at": datetime.now().isoformat()
        }
        state_data = base64.b64encode(json.dumps(default_state).encode()).decode()
    
    # Ensure state_data isn't too long for display
    state_display = f"{state_data[:30]}..." if len(state_data) > 30 else state_data
    
    print(f"Session data: {encoded_session[:30]}...")
    print(f"State data: {state_display}")
    
    # Use a single command to set both variables
    command = f'heroku config:set SESSION_DATA="{encoded_session}" LAST_PROCESSED_STATE="{state_data}" --app YOUR_APP_NAME'
    
    return command

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_session.py <session_path>")
        print("Example: python export_session.py session/bot_session")
        sys.exit(1)
    
    session_path = sys.argv[1]
    commands = create_export_commands(session_path)
    
    if commands:
        print("\nRun the following command to set the environment variables on Heroku:")
        print(commands)
        print("\nReplace YOUR_APP_NAME with your actual Heroku app name.")
        print("Or use setup_heroku.sh to set these automatically.")
    else:
        print("Failed to create export commands.")
        sys.exit(1) 