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

### TL;DR
• One script to sync env vars (`setup_heroku.sh`).  
• One command to run tests.  
• Bot translates NYT → zoomer Russian with optional cartoons.  
• Everything must pass tests; keep it simple and production-first.