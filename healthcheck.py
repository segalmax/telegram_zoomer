#!/usr/bin/env python3
"""
Health check script for the Telegram zoomer bot.
Verifies the bot is running and has created log entries within the expected timeframe.
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

def check_log_file(log_file="bot.log", max_age_minutes=15):
    """Check if the log file exists and has recent entries."""
    if not os.path.exists(log_file):
        print(f"ERROR: Log file {log_file} does not exist")
        return False
    
    # Check file modification time
    mtime = os.path.getmtime(log_file)
    last_modified = datetime.fromtimestamp(mtime)
    now = datetime.now()
    
    if now - last_modified > timedelta(minutes=max_age_minutes):
        print(f"ERROR: Log file not updated in the last {max_age_minutes} minutes")
        print(f"Last update: {last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
        return False
    
    # Check last few lines for errors
    try:
        with open(log_file, 'r') as f:
            # Read last 10 lines
            lines = f.readlines()[-10:]
            for line in lines:
                if "ERROR" in line:
                    print(f"WARNING: Recent error found in logs: {line.strip()}")
                    # Don't fail on errors, just warn
    except Exception as e:
        print(f"ERROR: Failed to read log file: {str(e)}")
        return False
    
    print(f"SUCCESS: Bot appears to be running, last log update: {last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Health check for Telegram Zoomer bot")
    parser.add_argument("--log-file", default="bot.log", help="Path to log file")
    parser.add_argument("--max-age", type=int, default=15, help="Maximum age of log file in minutes")
    
    args = parser.parse_args()
    
    if not check_log_file(args.log_file, args.max_age):
        sys.exit(1)
    
    sys.exit(0) 