"""
Database-backed session manager for Telegram client sessions

Stores sessions in Supabase database for persistence across Heroku deployments.
- Local development: Uses database with 'local' environment tag
- Heroku production: Uses database with 'production' environment tag  
- Tests: Uses database with 'test' environment tag

No file-based sessions, no compression, just clean database storage.
"""

import os
import logging
import json
import base64
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

APP_STATE_FILE = Path("session/app_state.json")
APP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

class DatabaseSession:
    """Telegram session stored in database"""
    
    def __init__(self, session_name, environment='production'):
        self.session_name = session_name
        self.environment = environment
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = os.environ.get('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase credentials not found, falling back to file-based sessions")
            self.use_database = False
        else:
            self.use_database = True
    
    def save_session(self, session_string):
        """Save session string to database"""
        if not self.use_database:
            return False
            
        try:
            import httpx
            
            # Compress the session string
            compressed = base64.b64encode(gzip.compress(session_string.encode())).decode()
            
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'session_name': self.session_name,
                'session_data': compressed,
                'environment': self.environment,
                'updated_at': datetime.now().isoformat()
            }
            
            # Upsert session using PUT with Prefer header for upsert
            headers['Prefer'] = 'resolution=merge-duplicates'
            response = httpx.post(
                f"{self.supabase_url}/rest/v1/telegram_sessions",
                headers=headers,
                json=data
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Session {self.session_name} saved to database")
                return True
            else:
                logger.error(f"Failed to save session: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving session to database: {e}")
            return False
    
    def load_session(self):
        """Load session string from database"""
        if not self.use_database:
            return None
            
        try:
            import httpx
            
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}'
            }
            
            response = httpx.get(
                f"{self.supabase_url}/rest/v1/telegram_sessions",
                headers=headers,
                params={
                    'session_name': f'eq.{self.session_name}',
                    'environment': f'eq.{self.environment}',
                    'select': 'session_data'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    # Decompress the session string
                    compressed = data[0]['session_data']
                    session_string = gzip.decompress(base64.b64decode(compressed)).decode()
                    logger.info(f"Session {self.session_name} loaded from database")
                    return session_string
                else:
                    logger.info(f"No session found for {self.session_name}")
                    return None
            else:
                logger.error(f"Failed to load session: {response.status_code} {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading session from database: {e}")
            return None

def load_app_state():
    """Load the application state from local file only."""
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
    """Save the application state to local file."""
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
    Set up the Telethon session using database storage.
    
    Returns:
        StringSession: Session for TelegramClient
    """
    # Determine environment and session name
    is_heroku = os.getenv('DYNO') is not None
    is_test = os.getenv('TEST_MODE') == 'true'
    
    if is_test:
        session_name = "test_session"
        environment = "test"
        logger.info("Using test session from database")
    elif is_heroku:
        session_name = "heroku_bot_session"
        environment = "production"
        logger.info("Using production session from database")
    else:
        session_name = "local_bot_session"
        environment = "local"
        logger.info("Using local session from database")
    
    # Try to load session from database
    db_session = DatabaseSession(session_name, environment)
    session_string = db_session.load_session()
    
    if session_string:
        # Return existing session
        return StringSession(session_string)
    else:
        # Return empty StringSession (will prompt for auth and we'll save it)
        logger.info(f"No existing session found, will create new {session_name} session")
        return StringSession()

def save_session_after_auth(client, session_name=None, environment=None):
    """
    Save session to database after successful authentication.
    Call this after client.start() completes successfully.
    """
    if session_name is None or environment is None:
        # Auto-detect based on environment
        is_heroku = os.getenv('DYNO') is not None
        is_test = os.getenv('TEST_MODE') == 'true'
        
        if is_test:
            session_name = "test_session"
            environment = "test"
        elif is_heroku:
            session_name = "heroku_bot_session"
            environment = "production"
        else:
            session_name = "local_bot_session"
            environment = "local"
    
    try:
        # Check if session already exists
        db_session = DatabaseSession(session_name, environment)
        existing_session = db_session.load_session()
        
        if existing_session:
            logger.info(f"Session {session_name} already exists in database, skipping save")
            return
        
        # Save new session
        session_string = client.session.save()
        success = db_session.save_session(session_string)
        
        if success:
            logger.info(f"Session {session_name} saved to database successfully")
        else:
            logger.warning(f"Failed to save session {session_name} to database")
            
    except Exception as e:
        logger.error(f"Error saving session after auth: {e}") 