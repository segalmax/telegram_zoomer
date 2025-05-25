# Tests Directory

This directory contains all tests for the Telegram Zoomer Bot project.

## Test Files

### Core Tests
- **`test_e2e_unified.py`** - End-to-end tests covering the full bot pipeline including translation, image generation, and Telegram integration
- **`conftest.py`** - Pytest configuration and fixtures

### Feature Tests  
- **`test_article_extractor.py`** - Tests for the article extraction functionality (Task 16)
- **`test_integration.py`** - Integration tests between article extraction and translation
- **`test_polling.py`** - Tests for the Telegram polling mechanism

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test Files
```bash
python -m pytest tests/test_article_extractor.py -v
python -m pytest tests/test_integration.py -v
```

### Run Individual Test Files Directly
```bash
python tests/test_article_extractor.py
python tests/test_integration.py
```

### Run Tests with Special Options
```bash
# Run with image generation disabled
python -m pytest tests/ --no-images

# Run with Stability AI enabled
python -m pytest tests/ --stability

# Run in bot mode (requires test channels)
python -m pytest tests/ --bot-mode
```

## Test Requirements

- **Environment Variables**: Tests require proper `.env` configuration with API keys and test channels
- **OpenAI API Key**: Required for translation and image generation tests
- **Telegram Credentials**: Required for end-to-end tests
- **Test Channels**: `TEST_SRC_CHANNEL` and `TEST_DST_CHANNEL` must be configured

## Test Coverage

- ✅ Article extraction from ynet.co.il
- ✅ Error handling for invalid URLs
- ✅ Translation with enhanced context
- ✅ Image generation (DALL-E and Stability AI)
- ✅ Telegram bot pipeline
- ✅ Polling mechanism
- ✅ Integration between components

## Notes

- Tests automatically handle graceful fallbacks for missing API keys
- Error logging is monitored - any ERROR level logs will fail tests
- Tests use persistent sessions to avoid repeated authentication 