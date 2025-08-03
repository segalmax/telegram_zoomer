#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config_admin.settings')
    
    # Show current environment and actual database URL
    supabase_env = os.getenv('SUPABASE_ENV', 'prod')
    from app.config_loader import get_config_loader
    config = get_config_loader()
    db_url = config.supabase_url
    
    print(f"🌍 Django running with SUPABASE_ENV={supabase_env} → {db_url}")
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
