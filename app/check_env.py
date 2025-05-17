import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Print the current module and file paths
print(f"Module path: {__file__}")
print(f"Current working directory: {os.getcwd()}")

# Calculate project root from __file__ path
project_root = Path(__file__).resolve().parent.parent
print(f"Project root calculated as: {project_root}")

# Print current value before loading
print(f"\nTG_SESSION before loading: {os.getenv('TG_SESSION')}")

# Check if app_settings.env exists
app_settings_path = project_root / 'app_settings.env'
print(f"app_settings.env path: {app_settings_path}")
print(f"app_settings.env exists: {app_settings_path.exists()}")

# Load app_settings.env
print(f"Loading app_settings.env from: {app_settings_path}")
load_dotenv(dotenv_path=app_settings_path, override=True)

# Print value after loading
print(f"TG_SESSION after loading app_settings.env: {os.getenv('TG_SESSION')}")

# Print also SESSION_PATH variable as used in the app
SESSION_PATH = os.getenv('TG_SESSION', 'session/nyt_zoomer')
print(f"SESSION_PATH (from os.getenv with default): {SESSION_PATH}")

# Check if .env exists
env_path = project_root / '.env'
print(f"\n.env path: {env_path}")
print(f".env exists: {env_path.exists()}")
if env_path.exists():
    print("Loading .env file...")
    load_dotenv(dotenv_path=env_path, override=False)
else:
    print(".env file doesn't exist (which is normal if secret values are set directly in the environment)")

# Print TG_API_ID which should come from .env
print(f"TG_API_ID after loading .env: {os.getenv('TG_API_ID')}")

print("\nAll current environment variables related to the bot:")
for key in ['TG_SESSION', 'SRC_CHANNEL', 'DST_CHANNEL', 'TG_API_ID', 'TG_API_HASH', 'OPENAI_API_KEY']:
    print(f"{key}: {os.getenv(key)}") 