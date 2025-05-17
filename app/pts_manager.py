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

def load_pts(channel_username):
    """
    Load the latest PTS value for a specific channel
    
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
                logger.debug(f"Loaded PTS={pts} for channel {channel_username}")
                return pts
        else:
            logger.info(f"No PTS data file found at {path}, returning 0")
            return 0
                
    except Exception as e:
        logger.error(f"Error loading PTS for {channel_username}: {str(e)}")
        return 0

def save_pts(channel_username, pts):
    """
    Save the PTS value for a specific channel
    
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
            with open(path, 'r') as f:
                data = json.load(f)
        
        # Update with new PTS value
        data[channel_username] = pts
        
        # Save back to file
        with open(path, 'w') as f:
            json.dump(data, f)
            
        logger.debug(f"Saved PTS={pts} for channel {channel_username}")
        
    except Exception as e:
        logger.error(f"Error saving PTS for {channel_username}: {str(e)}") 