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

APP_STATE_FILE = Path("session/app_state.json")
# Ensure the session directory exists for APP_STATE_FILE
APP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Renamed LAST_PROCESSED_STATE to APP_STATE_ENV_VAR for clarity internally
APP_STATE_ENV_VAR = 'LAST_PROCESSED_STATE' 

def load_app_state():
    """
    Load the application state.
    Priority:
    1. LAST_PROCESSED_STATE environment variable (Base64 encoded JSON).
    2. Local APP_STATE_FILE (session/app_state.json, raw JSON).
    3. Default state (look back 5 minutes).

    Returns:
        dict: The application state.
    """
    state_data = None
    # 1. Try environment variable
    encoded_state_env = os.environ.get(APP_STATE_ENV_VAR)
    if encoded_state_env:
        try:
            state_data_json = base64.b64decode(encoded_state_env).decode()
            state_data = json.loads(state_data_json)
            logger.info(f"Loaded app state from environment variable {APP_STATE_ENV_VAR}")
        except Exception as e:
            logger.error(f"Failed to load state from {APP_STATE_ENV_VAR}: {e}. Will try local file.")
            state_data = None # Ensure fallback if env var is corrupt

    # 2. Try local file if not loaded from env var
    if state_data is None:
        if APP_STATE_FILE.exists():
            try:
                with open(APP_STATE_FILE, 'r') as f:
                    state_data = json.load(f)
                logger.info(f"Loaded app state from local file: {APP_STATE_FILE}")
            except Exception as e:
                logger.error(f"Failed to load state from {APP_STATE_FILE}: {e}. Will use default.")
                state_data = None # Ensure fallback if file is corrupt
        else:
            logger.info(f"Local state file {APP_STATE_FILE} not found.")

    # 3. Default state if not found or error
    if state_data is None:
        state_data = {
            "message_id": 0,
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "pts": 0,
            "channel_id": None,
            "updated_at": datetime.now().isoformat()
        }
        logger.info("No saved state found or loaded, using default (looking back 5 minutes)")

    # Ensure timestamp is a datetime object for internal use, if it's a string
    if isinstance(state_data.get("timestamp"), str):
        try:
            state_data["timestamp"] = datetime.fromisoformat(state_data["timestamp"])
        except ValueError:
            logger.warning(f"Could not parse timestamp string '{state_data['timestamp']}', using current time minus 5 mins.")
            state_data["timestamp"] = datetime.now() - timedelta(minutes=5)
            
    # Ensure pts is an int
    state_data["pts"] = int(state_data.get("pts", 0))

    return state_data

def save_app_state(state_data):
    """
    Save the application state.
    - Writes to local APP_STATE_FILE (session/app_state.json) as raw JSON.
    - Logs a Base64 encoded JSON string for the user to set as
      the LAST_PROCESSED_STATE environment variable on Heroku.

    Args:
        state_data (dict): The application state to save. 
                           Timestamp should be a datetime object or ISO string.
    """
    if not isinstance(state_data, dict):
        logger.error("Invalid state_data provided to save_app_state. Must be a dict.")
        return

    # Ensure 'updated_at' is always fresh and timestamp is ISO format for serialization
    current_time_iso = datetime.now().isoformat()
    state_to_save = state_data.copy() # Avoid modifying the original dict if it's passed around
    state_to_save["updated_at"] = current_time_iso
    if isinstance(state_to_save.get("timestamp"), datetime):
        state_to_save["timestamp"] = state_to_save["timestamp"].isoformat()
    
    # For pts, ensure it's there, default to 0 if not.
    state_to_save["pts"] = int(state_to_save.get("pts", 0))


    # 1. Save to local file (raw JSON)
    try:
        APP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_STATE_FILE, 'w') as f:
            json.dump(state_to_save, f, indent=4)
        logger.info(f"Saved app state to local file: {APP_STATE_FILE}")
    except Exception as e:
        logger.error(f"Error saving app state to {APP_STATE_FILE}: {e}")

    # 2. Prepare and log string for Heroku environment variable
    try:
        state_json_string = json.dumps(state_to_save)
        encoded_state_for_env = base64.b64encode(state_json_string.encode()).decode()
        logger.info(f"To persist application state (e.g., on Heroku), "
                    f"set the '{APP_STATE_ENV_VAR}' environment variable to:")
        print(f"{APP_STATE_ENV_VAR}_VALUE_START###{encoded_state_for_env}###{APP_STATE_ENV_VAR}_VALUE_END") # Make it easy to parse from logs
    except Exception as e:
        logger.error(f"Error preparing state for environment variable: {e}")

def update_pts_in_state(pts_value):
    """
    Helper function to update only the PTS value in the current state.
    Loads current state, updates PTS, and saves it back.
    Args:
        pts_value (int): The new PTS value.
    """
    current_state = load_app_state()
    current_state["pts"] = int(pts_value)
    save_app_state(current_state)
    logger.debug(f"PTS value updated to {pts_value} in app state.")

# Keep setup_session for Telethon's own session file, but ensure consistency in env var naming
# Standardize to TG_SESSION_STRING for the base64 encoded .session file
TELETHON_SESSION_ENV_VAR = 'TG_SESSION_STRING' # Changed from SESSION_DATA

def setup_session():
    """
    Set up the Telethon session file from environment variable if available.
    This checks for TG_SESSION_STRING environment variable and creates
    the .session file if available.
    
    Returns:
        str: The path to the session name (without .session extension)
    """
    session_name = os.environ.get('TG_SESSION', 'session/default_persistent_bot_session')
    
    session_dir = Path(session_name).parent
    session_dir.mkdir(parents=True, exist_ok=True)
    
    telethon_session_string = os.environ.get(TELETHON_SESSION_ENV_VAR)
    if telethon_session_string:
        try:
            decoded_data = base64.b64decode(telethon_session_string)
            
            session_file_path = Path(f"{session_name}.session")
            logger.info(f"Creating Telethon session file at {session_file_path} from '{TELETHON_SESSION_ENV_VAR}' environment variable.")
            with open(session_file_path, 'wb') as f:
                f.write(decoded_data)
            logger.info(f"Telethon session file {session_file_path} created successfully.")
        except Exception as e:
            logger.error(f"Failed to create Telethon session file from {TELETHON_SESSION_ENV_VAR}: {str(e)}")
    else:
        logger.info(f"No '{TELETHON_SESSION_ENV_VAR}' found in environment. "
                    f"Telethon will use/create '{session_name}.session' locally or prompt for auth if it doesn't exist.")
    
    return session_name # Return the base name for Telethon client

# Remove old functions that are now replaced by load_app_state and save_app_state
# Functions save_last_processed_state, get_last_processed_state, update_pts_value
# are effectively replaced or refactored.
# The new update_pts_in_state is an example of specific state modification.
# The old update_pts_value is renamed to update_pts_in_state and uses new load/save.

# Note: The original update_pts_value took multiple args, the new one only pts.
# If other fields needed updating simultaneously, the calling code should fetch state,
# modify, and then call save_app_state.
# The old save_last_processed_state and get_last_processed_state are fully replaced. 