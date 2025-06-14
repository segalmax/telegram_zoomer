"""
Session manager for Telegram client sessions

Simple file-based sessions everywhere:
- Local development: session/local_bot_session.session
- Heroku: session/heroku_bot_session.session (created interactively on first run)
- Tests: session/sender_test_session.session (created interactively on first run)

No transfers, no compression, no environment variables - just clean interactive sessions.
"""

import os
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

APP_STATE_FILE = Path("session/app_state.json")
APP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_app_state():
    """
    Load the application state from local file only.
    """
    if APP_STATE_FILE.exists():
        try:
            with open(APP_STATE_FILE, 'r') as f:
                state_data = json.load(f)
            logger.info(f"Loaded app state from local file: {APP_STATE_FILE}")
            
            # Convert timestamp string to datetime object
            if isinstance(state_data.get("timestamp"), str):
                state_data["timestamp"] = datetime.fromisoformat(state_data["timestamp"])
            
            return state_data
        except Exception as e:
            logger.error(f"Failed to load state from {APP_STATE_FILE}: {e}")

    # Default state
    state_data = {
        "message_id": 0,
        "timestamp": datetime.now() - timedelta(minutes=5),
        "pts": 0,
        "channel_id": None,
        "updated_at": datetime.now().isoformat()
    }
    logger.info("Using default app state (looking back 5 minutes)")
    return state_data

def save_app_state(state_data):
    """
    Save the application state to local file.
    """
    if not isinstance(state_data, dict):
        logger.error("Invalid state_data provided to save_app_state. Must be a dict.")
        return

    # Prepare state for saving
    state_to_save = state_data.copy()
    state_to_save["updated_at"] = datetime.now().isoformat()
    
    # Convert datetime to ISO string for JSON serialization
    if isinstance(state_to_save.get("timestamp"), datetime):
        state_to_save["timestamp"] = state_to_save["timestamp"].isoformat()
    
    state_to_save["pts"] = int(state_to_save.get("pts", 0))

    # Save to local file
    try:
        APP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_STATE_FILE, 'w') as f:
            json.dump(state_to_save, f, indent=4)
        logger.info(f"Saved app state to local file: {APP_STATE_FILE}")
    except Exception as e:
        logger.error(f"Error saving app state to {APP_STATE_FILE}: {e}")

def setup_session():
    """
    Set up the Telethon session based on environment.
    
    Returns:
        str: Session file path (without .session extension)
    """
    # Check if running on Heroku
    is_heroku = os.getenv('DYNO') is not None
    
    if is_heroku:
        # Heroku: Use heroku_bot_session (will be created interactively on first run)
        session_path = "session/heroku_bot_session"
        logger.info("Running on Heroku - using session/heroku_bot_session.session")
    else:
        # Local development: Use local_bot_session
        session_path = "session/local_bot_session"
        logger.info("Running locally - using session/local_bot_session.session")
    
    # Ensure session directory exists
    session_dir = Path(session_path).parent
    session_dir.mkdir(parents=True, exist_ok=True)
    
    return session_path 