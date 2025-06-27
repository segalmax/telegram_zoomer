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

BOT_LOG_FILE="bot_test.log"
TEST_TIMEOUT_SECONDS=75 # Reduced timeout

# Clean up any potential previous sessions and locks
cleanup() {
  echo "Cleaning up..."
  # Try to kill bot if it's running
  if ps -p $BOT_PID > /dev/null 2>&1; then # Check if PID exists
    echo "Stopping bot process (PID: $BOT_PID)..."
    kill $BOT_PID 2>/dev/null || true
    # Wait a bit for the process to terminate
    for i in {1..5}; do 
        if ! ps -p $BOT_PID > /dev/null 2>&1; then break; fi; 
        sleep 0.5; # Shorter sleep
    done
    if ps -p $BOT_PID > /dev/null 2>&1; then 
        echo "Bot process $BOT_PID did not terminate gracefully, sending SIGKILL."
        kill -9 $BOT_PID 2>/dev/null || true
    fi 
  else
    echo "Bot process (PID: $BOT_PID) already stopped or not started."
  fi
  
  # Clean up any journal files that might cause locks
  echo "Removing session journal files that might cause locks..."
  rm -f *.session-journal 2>/dev/null || true
  rm -f session/*.session-journal 2>/dev/null || true
  echo "Cleanup finished."
}

# Set up trap to clean up on exit or interrupt
trap cleanup EXIT SIGINT SIGTERM

echo "🧹 Cleaning up any previous session journal files and old logs..."
rm -f $BOT_LOG_FILE
cleanup 

# Run test_polling.py to get the unique message prefix AND SEND THE MESSAGE
echo "📬 Obtaining unique message prefix from test_polling.py (this also sends the message)..."
polling_output=$(python tests/test_polling.py)
MESSAGE_PREFIX=$(echo "$polling_output" | grep "MESSAGE_PREFIX_SENT:" | cut -d ':' -f2)

if [ -z "$MESSAGE_PREFIX" ]; then
  echo "❌ Error: Could not retrieve MESSAGE_PREFIX from test_polling.py."
  echo "Output was:"
  echo "$polling_output"
  exit 1
fi
echo "✔️ Using unique message prefix for this test run: $MESSAGE_PREFIX"

echo "⏱️ Waiting 3 seconds for message to propagate on Telegram before starting bot..."
sleep 3


echo "🚀 Starting Telegram Bot in test mode (background)..."
# Set environment variables and run the bot in test mode

export TEST_MODE=true
export TEST_RUN_MESSAGE_PREFIX="$MESSAGE_PREFIX"
python -m pytest tests/test_e2e_unified.py::test_run_bot_mode --bot-mode -s --log-cli-level=INFO > "$BOT_LOG_FILE" 2>&1 &
BOT_PID=$!

echo "⏳ Bot starting with PID $BOT_PID. Waiting for it to initialize and process the message (max ${TEST_TIMEOUT_SECONDS}s)..."

# Wait for the bot process to complete, with a timeout
SECONDS=0
while ps -p $BOT_PID > /dev/null 2>&1; do
  if [ "$SECONDS" -ge "$TEST_TIMEOUT_SECONDS" ]; then
    echo "⏰ Test timed out after ${TEST_TIMEOUT_SECONDS}s. Terminating bot process $BOT_PID."
    # cleanup function will handle killing the process via trap
    echo "--- Full Bot Log ($BOT_LOG_FILE) on TIMEOUT ---"
    cat "$BOT_LOG_FILE" # Show log on timeout
    echo "--------------------------------------------"
    exit 1 # Exit with error due to timeout
  fi
  sleep 0.5 # Shorter sleep in PID check loop
  SECONDS=$((SECONDS + 1))
done

# Wait for BOT_PID to ensure it has exited and get its status
wait $BOT_PID
BOT_EXIT_CODE=$?

echo "🤖 Bot process $BOT_PID finished with exit code: $BOT_EXIT_CODE"

# Check bot logs for success message
SUCCESS_MESSAGE_FOUND=false
if grep -q "Successfully processed test message with prefix: $MESSAGE_PREFIX" "$BOT_LOG_FILE"; then
  SUCCESS_MESSAGE_FOUND=true
fi 

# Determine test result
if [ "$BOT_EXIT_CODE" -eq 0 ] && [ "$SUCCESS_MESSAGE_FOUND" = true ]; then
  echo "🎉✅ Polling test PASSED! Bot processed the message with prefix $MESSAGE_PREFIX successfully."
  echo "--- Bot Log Tail (last 20 lines) ---"
  tail -n 20 "$BOT_LOG_FILE"
  echo "------------------------------------"
  exit 0
else
  echo "❌ Polling test FAILED."
  if [ "$BOT_EXIT_CODE" -ne 0 ]; then
    echo "  Error: Bot process exited with code $BOT_EXIT_CODE."
  fi
  if [ "$SUCCESS_MESSAGE_FOUND" = false ]; then
    echo "  Error: Success message for prefix $MESSAGE_PREFIX not found in bot log."
  fi
  echo "--- Full Bot Log ($BOT_LOG_FILE) ---"
  cat "$BOT_LOG_FILE"
  echo "----------------------------------"
  exit 1
fi 