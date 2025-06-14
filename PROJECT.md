# Telegram News-to-Zoomer Bot – Concise Project Guide

> A Telegram bot that converts New York Times posts into edgy Russian zoomer slang (RIGHT-BIDLO style), optionally adds caricature images, and republishes them to a destination channel.  Focus: quick value delivery (MVP first), Heroku-friendly, fully tested.

---

## 1. Quick Start
1. **Clone & prepare**  
   ```bash
   git clone <repo>
   cd telegram_zoomer
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env && cp app_settings.env.example app_settings.env  # edit values
   ```
2. **Run locally**  
   ```bash
   python app/bot.py --process-recent 1   # test on last post
   ```
3. **Run all tests**  
   ```bash
   source .venv/bin/activate && python -m pytest tests/ -v && tests/test_polling_flow.sh
   ```
4. **Deploy to Heroku**  
```bash
   ./setup_heroku.sh && git push heroku main && heroku logs --tail --app <heroku-app>
   ```

---

## 2. Key Features
• Listens to `SRC_CHANNEL`, fetches full article text (newspaper4k) if URL present.  
• Translates via Claude Sonnet 4 (OpenAI compatible SDK) into right-bidlo tone.  
• Generates editorial cartoon images with DALL-E or Stability AI (`GENERATE_IMAGES`, `USE_STABILITY_AI`).  
• Posts formatted markdown with hidden hyperlinks to `DST_CHANNEL`.  
• Robust error handling—tests fail on any logged `ERROR`.  
• Persistent Telethon session compressed into env var for Heroku (≤64 KB).  
• CLI `--process-recent N`, `--no-images`, `--stability`, `--new-session`.

---

## 3. Directory Overview
```
app/               core modules
  bot.py           – main event loop
  translator.py    – OpenAI translation helper
  image_generator.py – DALLE / Stability helper
  article_extractor.py – newspaper4k wrapper
  session_manager.py – env/local session handling
scripts/           one-off utilities (auth, export_session)
session/           local *.session + app_state.json
tests/             pytest suite + shell polling test
tasks/             task-master AI tasks (roadmap)
setup_heroku.sh    env sync script (single source of truth)
``` 

---

## 4. Environment Variables
Secrets → `.env`; settings → `app_settings.env`.  
`setup_heroku.sh` reads *both* and pushes **all** vars—never call `heroku config:set` manually.

Required (excerpt):
```
API_ID, API_HASH, BOT_TOKEN           # Telegram
OPENAI_API_KEY, ANTHROPIC_API_KEY     # LLMs / images
SRC_CHANNEL, DST_CHANNEL              # Channel usernames
TRANSLATION_STYLE=right               # fixed style
GENERATE_IMAGES=true|false
USE_STABILITY_AI=true|false
TG_COMPRESSED_SESSION_STRING          # auto-generated
SUPABASE_URL, SUPABASE_KEY           # Supabase Postgres instance
EMBED_MODEL                           # optional, default text-embedding-ada-002
```

---

## 5. Development Workflow
• Always **activate `.venv`** before running anything.  
• Run **all tests** before commits; CI/CD pipeline pending.  
• Follow PEP8; keep PRs small, MVP-oriented.

### Testing Matrix
| Layer | Command | Notes |
|-------|---------|-------|
| Unit / Integration | `pytest tests/ -v` | strict `ERROR` handler |
| Polling end-to-end | `tests/test_polling_flow.sh` | real Telegram flow |

---

## 6. Deployment Notes (Heroku)
1. `runtime.txt` → Python 3.10.12 (to migrate to `.python-version`).  
2. Worker specified in `Procfile`: `python app/bot.py`.  
3. Session & app state live in config vars, recreated at startup.  
4. Logs: `heroku logs --tail --app <app>`.

---

## 7. Task Snapshot (abridged)
### ✅ Done (MVP)
- Core bot pipeline
- Translation & image modules
- Session compression, env split
- Robust pytest suite

### 🔄 In Progress / Next
- **Task 26**: Translation memory (Supabase pgvector) – HIGH PRIORITY
- **Task 13**: Analytics & feedback
- **Task 14**: CI + rate limiting
- **Task 15**: Multi-source news, preferences

(See `tasks/` or Task-Master AI for full tree.)

---

## 8. Reference Commands
```bash
# Export local session to env-string
python export_session.py --compress > app_settings.env

# Manual batch process last 5 posts without images
python app/bot.py --process-recent 5 --no-images
```

---

## 9. Translation Memory (🧠 Supabase + pgvector)
**Purpose**: keep the bot consistent by remembering past `source → translation` pairs and feeding semantically-similar examples into every new translation request.

### How it works
1. **Embed** – original Russian text → 1536-d vector via OpenAI `text-embedding-ada-002` (configurable via `EMBED_MODEL`).
2. **Store** – row inserted/updated in Supabase table `article_chunks`:
   | column | type | note |
   |--------|------|------|
   | `id` | text PK | `<msgId>-right` etc. |
   | `source_text` | text | original post |
   | `translation_text` | text | zoomer output |
   | `embedding` | vector(1536) | pgvector extension |
   | `created_at` | timestamptz | UTC |
3. **Recall** – before translating a new post the bot calls`match_article_chunks(query_embedding, k)` (SQL function) to fetch the **top k (default 5)** closest matches by cosine similarity.
4. **Context inject** – these matches are prepended to the prompt so Claude keeps terminology & tone consistent.

### Setup (already automated)
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS article_chunks (...);          -- created by migrations
CREATE FUNCTION match_article_chunks(...);               -- idem
```
### Environment knobs
* `SUPABASE_URL`, `SUPABASE_KEY` – point to the Postgres instance.
* `EMBED_MODEL` – override embedding model (must be 1536-d or adapt table).

### Analytics & Data Science (NEW)
**Enhanced debugging & metrics collection:**
- **k=10** memories retrieved (increased from 5)
- **Comprehensive logging** with emojis for easy parsing
- **Analytics tables**: `translation_sessions`, `memory_usage_analytics`, `performance_metrics`, `quality_metrics`
- **Real-time tracking**: processing times, memory effectiveness, similarity scores
- **Dashboard**: `python scripts/analytics_dashboard.py --detailed --export`

### Local testing
Run `pytest tests/test_vector_store.py -v` – saves + recalls a pair against the live db.

### Cleaning test data
```sql
DELETE FROM article_chunks WHERE id LIKE 'pytest-%' OR id LIKE 'debug-%';
```

### Analytics queries
```sql
-- View recent translation sessions
SELECT message_id, total_processing_time_ms, memories_found, avg_memory_similarity 
FROM translation_sessions ORDER BY created_at DESC LIMIT 10;

-- Memory effectiveness analysis
SELECT similarity_score, rank_position, source_text_preview 
FROM memory_usage_analytics ORDER BY similarity_score DESC LIMIT 20;
```

---

### TL;DR
Your TM lives in Supabase, learns automatically, and is 100 % covered by tests – no extra ops needed.

---

### TL;DR
• One script to sync env vars (`setup_heroku.sh`).  
• One command to run tests.  
• Bot translates NYT → zoomer Russian with optional cartoons.  
• Everything must pass tests; keep it simple and production-first.

## 10. Session Management - Simplified Interactive Approach (updated 2025-01-14)

**Philosophy**: No session transfers, no compression, no environment variables. Just clean interactive sessions.

### Session Strategy
1. **Local Development**
   • Uses `session/local_bot_session.session`
   • Created interactively on first run (prompts for phone/code)

2. **Heroku Production** 
   • Uses `session/heroku_bot_session.session`
   • Created interactively on first Heroku run (prompts for phone/code)
   • No session transfers from local to Heroku

3. **Testing**
   • Uses `session/sender_test_session.session`
   • Created interactively on first test run (prompts for phone/code)
   • Separate test account recommended to avoid conflicts

### Deployment Process
```bash
# Deploy to Heroku (no session handling)
./setup_heroku.sh

# First run on Heroku will prompt for authentication
heroku logs --tail --app your-app-name
```

### Benefits
- **No session corruption** from transfers/compression
- **Clean separation** between environments  
- **Interactive authentication** ensures sessions work properly
- **No complex environment variables** for session management
- **Easier debugging** - sessions are just local files

### Session Files
- `session/local_bot_session.session` - Local development
- `session/heroku_bot_session.session` - Heroku production (if exists locally)
- `session/sender_test_session.session` - Testing
- `session/app_state.json` - Application state (local only)