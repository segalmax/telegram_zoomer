"""
Single source of truth for database configuration across the entire system.
Both Django ORM and ConfigLoader REST API use this.
"""

import os
from typing import Dict, Any


def get_database_config() -> Dict[str, Any]:
    """
    Returns database configuration based on SUPABASE_ENV.
    
    Returns:
        Dict with keys: host, port, user, password, database, url, api_key, headers
    """
    supabase_env = os.getenv("SUPABASE_ENV", "prod")
    
    if supabase_env == "local":
        # Local Docker Supabase (consistent with supabase start defaults)
        return {
            # Django connection details
            "host": "127.0.0.1",
            "port": "54322",  # Default Docker postgres port
            "user": "postgres",
            "password": "postgres",  # Default Docker password
            "database": "postgres",
            
            # REST API details
            "url": "http://127.0.0.1:54321",  # Default Docker API port
            "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",
            
            # Environment indicator
            "env": "local",
            "description": "🐳 Local Docker Supabase"
        }
    else:
        # Production Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        supabase_db_password = os.getenv("SUPABASE_DB_PASSWORD")

        if not supabase_url or not supabase_key or not supabase_db_password:
            raise ValueError(
                "Production Supabase requires: SUPABASE_URL, SUPABASE_KEY, SUPABASE_DB_PASSWORD"
            )

        # Extract project ID from URL for database host and pooler routing
        import urllib.parse
        parsed = urllib.parse.urlparse(supabase_url)
        project_id = parsed.hostname.split('.')[0]

        # Prefer pooler host if provided (more reliable from some platforms and reduces connection churn)
        pooler_host = os.getenv("SUPABASE_DB_HOST")
        if pooler_host:
            db_host = pooler_host
            db_port = os.getenv("SUPABASE_DB_PORT", "6543")
            description = "☁️ Production Supabase (pooler)"
        else:
            db_host = f"db.{project_id}.supabase.co"
            db_port = "5432"
            description = "☁️ Production Supabase"

        return {
            # Django connection details
            "host": db_host,
            "port": db_port,
            "user": "postgres",
            "password": supabase_db_password,
            "database": "postgres",
            # Psycopg2 startup options (only when using pooler) – Supabase pooler expects "-c project=<ref>"
            **({"psycopg2_options": f"-c project={project_id}"} if pooler_host else {}),

            # REST API details
            "url": supabase_url,
            "api_key": supabase_key,

            # Environment indicator
            "env": "prod",
            "description": description
        }


def get_rest_headers(config: Dict[str, Any] = None) -> Dict[str, str]:
    """Get HTTP headers for Supabase REST API calls."""
    if config is None:
        config = get_database_config()
    
    return {
        "apikey": config["api_key"],
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }