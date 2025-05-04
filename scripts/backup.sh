#!/bin/bash

# Simple backup script for Telegram session files
# Usage: ./backup.sh [destination_directory]

# Set default backup destination
BACKUP_DIR="${1:-./backups}"
SESSION_DIR="./session"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="telegram_session_backup_${DATE}.tar.gz"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create the backup
if [ -d "$SESSION_DIR" ]; then
  tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" -C "$SESSION_DIR" .
  echo "Backup created: ${BACKUP_DIR}/${BACKUP_FILE}"
else
  echo "Error: Session directory not found at $SESSION_DIR"
  exit 1
fi

# Keep only the 5 most recent backups
if [ "$(ls -1 "${BACKUP_DIR}"/telegram_session_backup_*.tar.gz 2>/dev/null | wc -l)" -gt 5 ]; then
  echo "Removing old backups..."
  ls -tr "${BACKUP_DIR}"/telegram_session_backup_*.tar.gz | head -n -5 | xargs rm -f
fi

echo "Backup completed successfully." 