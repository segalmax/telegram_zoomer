#!/bin/bash
# Session Database Lock Troubleshooter
#
# This script helps resolve "database is locked" errors by:
# 1. Finding and removing all session journal files
# 2. Checking for running Telegram processes
# 3. Providing guidance on fixing lock issues
#
# Usage:
#   ./scripts/unlock_sessions.sh

echo "🔍 Session Database Lock Troubleshooter"
echo ""

# Check if any session journal files exist
echo "Checking for session journal files..."
session_journals=$(find . -name "*.session-journal" -type f | sort)

if [ -n "$session_journals" ]; then
  echo "Found the following session journal files:"
  echo "$session_journals"
  echo ""
  
  read -p "Do you want to remove these journal files? (y/n): " confirm
  if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
    echo "Removing session journal files..."
    find . -name "*.session-journal" -type f -delete
    echo "Done."
  else
    echo "Skipping journal file removal."
  fi
else
  echo "✅ No session journal files found."
fi

# Check for running Telegram processes
echo ""
echo "Checking for running Telegram processes..."
telegram_processes=$(ps aux | grep -E "python.*bot\.py|python.*test\.py" | grep -v grep)

if [ -n "$telegram_processes" ]; then
  echo "Found the following Telegram processes:"
  echo "$telegram_processes"
  echo ""
  echo "These processes might be locking the session database."
  echo "You can terminate them with: kill <PID>"
  echo ""
else
  echo "✅ No running Telegram processes found."
fi

# Provide manual steps for resolving lock issues
echo ""
echo "📋 Steps to resolve database lock issues:"
echo "1. Ensure all bot and test processes are stopped"
echo "2. Remove all *.session-journal files"
echo "3. Wait a few seconds for any file system locks to clear"
echo "4. If needed, create a new test session: python test.py --new-session"
echo ""
echo "For persistent issues, try:"
echo "- Using a different session name in your .env file"
echo "- Temporarily backing up and removing existing session files"
echo "- Running a separate instance with the --new-session flag"
echo ""
echo "✅ Troubleshooting complete!" 