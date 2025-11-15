# Telegram News-to-Zoomer Bot

> **Converts news posts into zoomer slang with AI-powered context linking**

🎯 **Event-driven bot** with Claude Sonnet 4 translation + semantic memory system

## 🚀 Quick Setup

### Prerequisites
- Python 3.10+, Telegram API credentials, Anthropic Claude API key, Supabase account

### Get Running (5 minutes)
```bash
# 1. Setup Environment
git clone <repo> && cd telegram_zoomer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env && cp app_settings.env.example app_settings.env
# Edit both files with your API keys and channel names

# 3. Validate Setup  
python -m pytest tests/ -v                    # Unit/Integration tests
./tests/test_polling_flow.sh                  # End-to-end Telegram test

# 4. Run Locally
python app/bot.py --process-recent 1          # Test with last post

# 5. Deploy to Heroku
./setup_heroku.sh && git push heroku main     # Deploy + monitor logs
```

## 🧠 How It Works
1. **Listens** → Source Telegram channel for new messages
2. **Extracts** → Full article content if URLs present
3. **Recalls** → Similar past translations for context (semantic memory)
4. **Translates** → Claude Sonnet 4 with modern Lurkmore style for Israeli Russian audience + context linking
5. **Posts** → Result to destination channel with embedded related links

## 🏗️ Key Features
- **Real-time processing** → Event-driven, no polling delays
- **Translation memory** → Semantic similarity search (pgvector)
- **Smart linking** → Auto-inserts links to related past posts
- **Database persistence** → All state in Supabase (Heroku-safe)
- **Comprehensive testing** → Unit + real Telegram integration tests

## 📚 Documentation

**→ [📚 Full Documentation Index](docs/INDEX.md)** ← Start here for learning

### Quick Navigation
- **🏗️ System Overview** → [docs/SYSTEM-DESIGN.md](docs/SYSTEM-DESIGN.md)
- **🧠 AI Translation** → [docs/AI-TRANSLATION.md](docs/AI-TRANSLATION.md) 
- **📡 Telegram Integration** → [docs/TELEGRAM-LAYER.md](docs/TELEGRAM-LAYER.md)
- **💾 Database Design** → [docs/DATA-ARCHITECTURE.md](docs/DATA-ARCHITECTURE.md)
- **🧪 Testing** → [docs/TESTING-STRATEGY.md](docs/TESTING-STRATEGY.md)
- **🚀 Deployment** → [docs/DEPLOYMENT-ARCHITECTURE.md](docs/DEPLOYMENT-ARCHITECTURE.md)

## 🎯 Essential Commands
```bash
# Development workflow
source .venv/bin/activate && python -m pytest tests/ -v && ./tests/test_polling_flow.sh

# Deploy to production  
./setup_heroku.sh && git push heroku main && heroku logs --tail --app <app>

# Monitor performance
# Analytics system has been removed
```

---
**💡 TL;DR**: Event-driven Telegram bot with AI translation, vector-based memory, and production-ready Heroku deployment.
