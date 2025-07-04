# 🧪 Testing Strategy

## 🎯 Test Philosophy
Validate core functionality with minimal setup - article extraction, API integration, and end-to-end flow

## 🏗️ Test Architecture

### Test Suites (6 tests total)
```python
pytest tests/ -v
# ✅ 6 passed, 0 skipped, 0 failed
```

## 📋 Test Coverage

### Core Components
| Test Module | Coverage | Purpose |
|-------------|----------|---------|
| `test_article_extractor.py` | Article extraction | URL → content validation |
| `test_integration.py` | API integration | Supabase + OpenAI connectivity |
| `test_e2e_unified.py` | End-to-end flow | Complete translation pipeline |

### Test Details
```python
# Article Extraction (2 tests)
test_article_extraction()      # Basic URL extraction
test_error_handling()         # 404/invalid URL handling

# Integration (1 test) 
test_article_extraction_integration()  # Real API calls

# End-to-End (3 tests)
test_api_translations()       # Translation API flow
test_telegram_pipeline()     # Full bot pipeline
test_verify_no_errors_logged()  # Error validation
```

## 🔧 Test Configuration

### Session Isolation [[memory:326849]]
```python
# Separate test sessions to avoid AuthKeyDuplicatedError
# Main bot: TG_COMPRESSED_SESSION_STRING
# Tests: TG_SENDER_COMPRESSED_SESSION_STRING
```

### Environment Setup
```bash
# Test mode activation
TEST_MODE=true
TEST_SRC_CHANNEL=@test_source
TEST_DST_CHANNEL=@test_destination

# Test session
TG_SENDER_COMPRESSED_SESSION_STRING=AQAAAIGBAWQBAYDd...
```

## 🚀 Running Tests

### Local Development
```bash
# Full test suite
python -m pytest tests/ -v

# Individual test files
python -m pytest tests/test_article_extractor.py -v
python -m pytest tests/test_e2e_unified.py -v
```

### Virtual Environment
```python
# Ensure .venv is active
which python  # Should show .venv path
pip install -r requirements.txt  # If packages missing
```

## 📊 Test Results Analysis

### Success Criteria
- **6/6 tests pass**: Core functionality working
- **No skipped tests**: Full coverage validation
- **Clean error logs**: No unexpected failures

### Common Issues
```python
# Missing packages
pip install pytest anthropic supabase openai

# Session conflicts
# Use separate TG_SENDER_COMPRESSED_SESSION_STRING for tests

# Network timeouts
# Tests include real API calls - retry if needed
```

## 🔍 Validation Checks

### Article Extraction
```python
# Valid URL processing
assert len(extracted_text) > 50
assert 'error' not in extracted_text.lower()

# Error handling
invalid_urls = ['', 'invalid', 'http://404.example']
for url in invalid_urls:
    assert extract_article(url) == ""
```

### Translation Pipeline
```python
# API connectivity
assert anthropic_client is not None
assert supabase_client is not None

# Memory system
memories = recall("test query", k=5)
assert isinstance(memories, list)
```

## 🛠️ Debugging

### Test Failures
```bash
# Verbose output
python -m pytest tests/ -v -s

# Specific test debugging
python -m pytest tests/test_e2e_unified.py::test_api_translations -v -s
```

### Log Analysis
```python
# Test logs show:
# - API response times
# - Memory query results  
# - Translation success/failure
# - Database operations
```

## 📈 Performance Targets
- **Test execution**: <60s total
- **API response**: <30s per translation
- **Memory queries**: <1s
- **Success rate**: 100% in clean environment 