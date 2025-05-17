#!/bin/bash
# Test Polling Flow
# 
# This script tests the full polling mechanism:
# 1. Runs the bot in test mode (background)
# 2. Sends a test message to trigger the polling mechanism
# 3. Shows how to monitor logs from both processes
#
# Usage:
#   ./test_polling_flow.sh

# Ensure script fails on error
set -e

echo "🚀 Starting Telegram Bot in test mode (background)..."
# Set environment variables and run the bot in test mode
export GENERATE_IMAGES=false
export TEST_MODE=true
python test.py --bot-mode > bot_test.log 2>&1 &
BOT_PID=$!

echo "⏳ Waiting 10 seconds for bot to initialize..."
sleep 10

echo "📩 Sending test message to test source channel..."
python test_polling.py

echo "🔍 Bot is running with PID $BOT_PID"
echo "🎯 Test message sent. The bot should detect it via polling."
echo ""
echo "  To monitor bot logs: tail -f bot_test.log"
echo "  To stop the bot:     kill $BOT_PID"
echo ""
echo "The bot will continue running in the background until you stop it." 