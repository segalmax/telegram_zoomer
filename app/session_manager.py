"""
Session manager for Telegram client sessions on Heroku

This module provides functions to load session data from environment 
variables, allowing session persistence on ephemeral Heroku dynos.
It also handles persistence of message state for reliability.
"""

import os
import base64
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def setup_session():
    """
    Set up the Telegram session from environment variable if available.
    
    This checks for SESSION_DATA environment variable and creates
    the session file if available.
    
    Returns:
        str: The path to the session file
    """
    # Default session path from environment or use default
    session_path = os.environ.get('TG_SESSION', 'session/test_session_persistent')
    
    # Create directory if it doesn't exist
    session_dir = os.path.dirname(session_path)
    if session_dir:
        os.makedirs(session_dir, exist_ok=True)
    
    # Check if we have session data in environment variable
    session_data = os.environ.get('SESSION_DATA')
    if session_data:
        try:
            # Decode session data from base64
            decoded_data = base64.b64decode(session_data)
            
            # Write to the session file
            session_file = f"{session_path}.session"
            logger.info(f"Creating session file at {session_file} from environment variable")
            with open(session_file, 'wb') as f:
                f.write(decoded_data)
            
            logger.info("Session file created successfully")
        except Exception as e:
            logger.error(f"Failed to create session file: {str(e)}")
    else:
        logger.info(f"No SESSION_DATA found in environment, will use existing session file or authenticate")
    
    return session_path 

def save_last_processed_state(message_id, timestamp, pts=0, channel_id=None):
    """
    Save the last processed message state to environment variables
    
    Args:
        message_id (int): The ID of the last processed message
        timestamp (datetime): The timestamp of the last processed message
        pts (int, optional): The PTS value from Telegram updates
        channel_id (int, optional): The channel ID the message belongs to
    """
    try:
        state_data = {
            "message_id": message_id,
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "pts": pts,
            "channel_id": channel_id,
            "updated_at": datetime.now().isoformat()
        }
        encoded_state = base64.b64encode(json.dumps(state_data).encode()).decode()
        os.environ['LAST_PROCESSED_STATE'] = encoded_state
        logger.debug(f"Saved state: message_id={message_id}, timestamp={timestamp}, pts={pts}")
    except Exception as e:
        logger.error(f"Error saving message state: {e}")

def get_last_processed_state():
    """
    Get the last processed message state from environment variables
    
    Returns:
        dict: A dictionary containing message_id, timestamp, and pts
    """
    if 'LAST_PROCESSED_STATE' in os.environ:
        try:
            encoded_state = os.environ['LAST_PROCESSED_STATE']
            state_data = json.loads(base64.b64decode(encoded_state).decode())
            
            # Convert timestamp string back to datetime if needed
            if isinstance(state_data.get("timestamp"), str):
                try:
                    state_data["timestamp"] = datetime.fromisoformat(state_data["timestamp"])
                except ValueError:
                    # Handle timestamp that can't be parsed
                    state_data["timestamp"] = datetime.now() - timedelta(minutes=5)
            
            logger.info(f"Loaded last message state: ID={state_data.get('message_id')}, "
                       f"Time={state_data.get('timestamp')}, PTS={state_data.get('pts')}")
            return state_data
        except Exception as e:
            logger.error(f"Error loading message state: {e}")
    
    # Default state if not found
    default_state = {
        "message_id": 0,
        "timestamp": datetime.now() - timedelta(minutes=5),  # Look back 5 minutes by default
        "pts": 0,
        "channel_id": None,
        "updated_at": datetime.now().isoformat()
    }
    logger.info(f"No saved state found, using default (looking back 5 minutes)")
    return default_state

def update_pts_value(pts):
    """
    Update just the PTS value while keeping other state the same
    
    Args:
        pts (int): The new PTS value to store
    """
    state = get_last_processed_state()
    save_last_processed_state(
        state.get("message_id", 0),
        state.get("timestamp", datetime.now() - timedelta(minutes=5)),
        pts,
        state.get("channel_id")
    ) 