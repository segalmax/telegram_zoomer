"""
Session manager for Telegram client sessions on Heroku

This module provides functions to load session data from environment 
variables, allowing session persistence on ephemeral Heroku dynos.
"""

import os
import base64
import logging
from pathlib import Path

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