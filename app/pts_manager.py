"""
PTS Manager for Telegram channel polling

This module handles loading and saving PTS (Position Token for Sequence) values
for Telegram channels, enabling reliable polling and preventing redundant downloads.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default location for the PTS data file
PTS_DATA_FILE = os.getenv("PTS_DATA_FILE", "session/channel_pts.json")


def load_pts_from_file(channel_username):
    """
    Load the latest PTS value for a specific channel from file.
    
    Args:
        channel_username (str): The username of the channel
        
    Returns:
        int: The stored PTS value or 0 if not found
    """
    try:
        # Create directory if it doesn't exist
        path = Path(PTS_DATA_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data if file exists
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
                pts = data.get(channel_username, 0)
                logger.debug(f"Loaded PTS={pts} for channel {channel_username} from file: {path}")
                return pts
        else:
            logger.info(f"No PTS data file found at {path}, returning 0 for {channel_username}")
            return 0
                
    except Exception as e:
        logger.error(f"Error loading PTS from file for {channel_username}: {str(e)}")
        return 0

def save_pts_to_file(channel_username, pts):
    """
    Save the PTS value for a specific channel to file.
    
    Args:
        channel_username (str): The username of the channel
        pts (int): The PTS value to save
    """
    try:
        # Create directory if it doesn't exist
        path = Path(PTS_DATA_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        data = {}
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from {path}, starting with empty PTS data.")
        
        # Update with new PTS value
        data[channel_username] = pts
        
        # Save back to file
        with open(path, 'w') as f:
            json.dump(data, f)
            
        logger.debug(f"Saved PTS={pts} for channel {channel_username} to file: {path}")
        
    except Exception as e:
        logger.error(f"Error saving PTS to file for {channel_username}: {str(e)}")

# --- Heroku specific PTS management using environment variables ---

def save_pts_to_env(channel_username, pts):
    """Store PTS in environment variable for Heroku's ephemeral filesystem"""
    try:
        pts_data = {}
        if 'CHANNEL_PTS_DATA' in os.environ:
            try:
                pts_data = json.loads(os.environ['CHANNEL_PTS_DATA'])
            except json.JSONDecodeError:
                logger.warning("Could not decode JSON from CHANNEL_PTS_DATA, starting fresh.")
        
        pts_data[channel_username] = pts
        os.environ['CHANNEL_PTS_DATA'] = json.dumps(pts_data)
        logger.debug(f"Saved PTS={pts} for {channel_username} to CHANNEL_PTS_DATA environment variable")
    except Exception as e:
        logger.error(f"Error saving PTS to environment: {e}")

def load_pts_from_env(channel_username):
    """Load PTS from environment variable for Heroku's ephemeral filesystem"""
    try:
        if 'CHANNEL_PTS_DATA' in os.environ:
            try:
                pts_data = json.loads(os.environ['CHANNEL_PTS_DATA'])
                pts = pts_data.get(channel_username, 0)
                logger.debug(f"Loaded PTS={pts} for {channel_username} from CHANNEL_PTS_DATA environment variable")
                return pts
            except json.JSONDecodeError:
                logger.warning("Could not decode JSON from CHANNEL_PTS_DATA when loading PTS.")
    except Exception as e:
        logger.error(f"Error loading PTS from environment: {e}")
    return 0

# --- Generic load/save functions that will be patched ---
# By default, they point to the file-based versions.
load_pts = load_pts_from_file
save_pts = save_pts_to_file

def patch_pts_functions_for_env_vars():
    """Replace the file-based PTS storage with environment variable storage."""
    global load_pts, save_pts
    load_pts = load_pts_from_env
    save_pts = save_pts_to_env
    logger.info("Patched PTS storage functions to use environment variables (CHANNEL_PTS_DATA).")

# --- Auto-detection for patching ---
# If CHANNEL_PTS_DATA exists or a specific override flag is set, patch automatically.
# This makes the main bot.py Heroku-friendly without explicit calls in bot.py itself.
if 'CHANNEL_PTS_DATA' in os.environ or os.getenv('USE_ENV_PTS_STORAGE', 'false').lower() == 'true':
    patch_pts_functions_for_env_vars() 