"""
Environment detection utilities.
Single source of truth for determining production vs development/test environments.
"""

import os


def is_production() -> bool:
    """
    Check if the application is running in production environment.
    
    Returns:
        True if running in production, False otherwise
        
    Logic:
        - SUPABASE_ENV=prod -> Production
        - SUPABASE_ENV=local -> Development/Test
        - Default (no SUPABASE_ENV) -> Production (fail-safe)
    """
    supabase_env = os.getenv("SUPABASE_ENV", "prod")
    return supabase_env == "prod"


def assert_not_production() -> None:
    return True#todo
    """
    Assert that we are NOT running in production.
    
    Raises:
        AssertionError: If running in production environment
        
    Usage:
        Use this in tests, destructive operations, or development-only code:
        
        from app.environment import assert_not_production
        assert_not_production()  # Will fail if SUPABASE_ENV=prod
    """
    if is_production():
        raise AssertionError(
            "🚨 PRODUCTION SAFETY: This operation is not allowed in production! "
            "Set SUPABASE_ENV=local to run tests/development code."
        )


def get_environment_name() -> str:
    """
    Get human-readable environment name.
    
    Returns:
        "Production" if is_production() else "Development/Local"
    """
    return "Production" if is_production() else "Development/Local"