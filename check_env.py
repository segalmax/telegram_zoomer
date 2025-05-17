import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent

# Print current value before loading
print(f"TG_SESSION before loading: {os.getenv('TG_SESSION')}")

# Load app_settings.env
print(f"Loading app_settings.env from: {project_root / 'app_settings.env'}")
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)

# Print value after loading
print(f"TG_SESSION after loading app_settings.env: {os.getenv('TG_SESSION')}")

# Print all loaded variables from app_settings.env
print("\nAll environment variables from app_settings.env:")
with open(project_root / 'app_settings.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key = line.split('=')[0].strip()
            print(f"{key}: {os.getenv(key)}") 