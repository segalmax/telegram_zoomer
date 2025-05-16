"""
Export the session file as a base64 string that can be used in a Heroku config var
"""

import base64
import os

# Read the session file
with open("session/test_session_persistent.session", "rb") as f:
    session_data = f.read()

# Encode as base64
encoded = base64.b64encode(session_data).decode('utf-8')

# Print the encoded data
print(f"SESSION_DATA={encoded}")
print(f"\nLength: {len(encoded)} characters")
print("\nCopy the above and run: heroku config:set SESSION_DATA=<data> --app nyt-zoomer-bot") 