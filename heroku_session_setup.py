"""
Script to create a Telegram session file on Heroku
"""

import os
import sys

def create_session():
    """Create a hardcoded session file for Telegram"""
    
    # Make sure session directory exists
    os.makedirs("session", exist_ok=True)
    
    # Session file path
    session_path = os.path.join("session", "test_session_persistent.session")
    
    # Session data from the existing session file
    # This is a binary file, but we'll encode it as a hex string for this script
    # We'll convert this back to binary when writing the file
    
    # Read the session file from disk in binary mode and create a hex representation
    with open("session/test_session_persistent.session", "rb") as f:
        session_data = f.read().hex()
    
    # Convert hex string back to binary and write to file
    with open(session_path, "wb") as f:
        f.write(bytes.fromhex(session_data))
    
    print(f"Session file created at {session_path}")
    
if __name__ == "__main__":
    create_session() 