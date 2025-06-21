"""
Database-backed session manager for Telegram client sessions

Stores sessions and app state (including PTS) in Supabase database for persistence across Heroku deployments.
- Local development: Uses database with 'local' environment tag
- Heroku production: Uses database with 'production' environment tag  
- Tests: Uses database with 'test' environment tag

No file-based sessions or state, everything in database for true persistence.
"""

import os
import logging
import json
import base64
import gzip
from datetime import datetime, timedelta
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

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
            
            # Prepare payload
            data = {
                'session_name': self.session_name,
                'session_data': compressed,
                'environment': self.environment,
                'updated_at': datetime.now().isoformat()
            }
            
            # Upsert session using POST with Prefer header for upsert
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

def _get_environment():
    """Determine current environment for database operations"""
    is_heroku = os.getenv('DYNO') is not None
    is_test = os.getenv('TEST_MODE') == 'true'
    
    if is_test:
        return "test"
    elif is_heroku:
        return "production"
    else:
        return "local"

def load_app_state():
    """Load the application state from Supabase database (no filesystem fallback)."""
    environment = _get_environment()
    
    # Try to load from database first
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if supabase_url and supabase_key:
        try:
            import httpx
            
            headers = {
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}'
            }
            
            response = httpx.get(
                f"{supabase_url}/rest/v1/app_state",
                headers=headers,
                params={
                    'environment': f'eq.{environment}',
                    'select': '*',
                    'limit': '1'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    state_data = data[0]
                    # Convert timestamp string to datetime object
                    if isinstance(state_data.get("timestamp"), str):
                        state_data["timestamp"] = datetime.fromisoformat(state_data["timestamp"])
                    
                    logger.info(f"Loaded app state from Supabase database (environment: {environment})")
                    logger.info(f"App state PTS: {state_data.get('pts', 0)}")
                    return state_data
                else:
                    logger.info(f"No app state found in database for environment: {environment}")
            else:
                logger.warning(f"Failed to load app state from database: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error loading app state from database: {e}")
    
    # Default state if database unavailable
    state_data = {
        "message_id": 0,
        "timestamp": datetime.now() - timedelta(minutes=5),
        "pts": 0,
        "channel_id": None,
        "updated_at": datetime.now().isoformat(),
        "environment": environment
    }
    logger.info(f"Using default app state (looking back 5 minutes) for environment: {environment}")
    return state_data

def save_app_state(state_data):
    """Save the application state to Supabase database (no filesystem backup)."""
    if not isinstance(state_data, dict):
        logger.error("Invalid state_data provided to save_app_state. Must be a dict.")
        return

    environment = _get_environment()
    
    # Prepare state for saving
    state_to_save = state_data.copy()
    state_to_save["updated_at"] = datetime.now().isoformat()
    state_to_save["environment"] = environment
    
    # Convert datetime to ISO string for JSON serialization
    if isinstance(state_to_save.get("timestamp"), datetime):
        state_to_save["timestamp"] = state_to_save["timestamp"].isoformat()
    
    state_to_save["pts"] = int(state_to_save.get("pts", 0))

    # Save to database first
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    database_success = False
    
    if supabase_url and supabase_key:
        try:
            import httpx
            
            headers = {
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates'
            }
            
            # Use PATCH with environment filter for proper upsert
            response = httpx.patch(
                f"{supabase_url}/rest/v1/app_state",
                headers=headers,
                params={'environment': f'eq.{environment}'},
                json=state_to_save
            )
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Saved app state to database (environment: {environment}, PTS: {state_to_save['pts']})")
                database_success = True
            else:
                logger.error(f"Failed to save app state to database: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error saving app state to database: {e}")
    
    if not database_success:
        logger.error("App state was NOT saved to database – state persistence lost!")

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

def reset_pts(environment=None):
    """
    Reset PTS to 0 for graceful recovery from PersistentTimestampEmptyError.
    This forces the bot to start fresh with channel polling.
    
    Args:
        environment: Specific environment to reset, or None for current environment
    """
    if environment is None:
        environment = _get_environment()
    
    logger.warning(f"Resetting PTS to 0 for environment: {environment}")
    
    # Load current state
    current_state = load_app_state()
    
    # Reset PTS and update timestamp
    current_state['pts'] = 0
    current_state['message_id'] = 0
    current_state['timestamp'] = datetime.now() - timedelta(minutes=5)
    
    # Save updated state
    save_app_state(current_state)
    
    logger.info(f"PTS reset complete for environment: {environment}")

def get_pts_info():
    """Get current PTS information for debugging"""
    environment = _get_environment()
    state = load_app_state()
    
    return {
        'environment': environment,
        'pts': state.get('pts', 0),
        'message_id': state.get('message_id', 0),
        'timestamp': state.get('timestamp'),
        'updated_at': state.get('updated_at'),
        'has_supabase': bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY'))
    } 