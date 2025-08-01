# Local Development Database Guide

This guide shows you how to work with your local Supabase development database that's completely isolated from production.

## 🚀 Quick Start

### 1. Use Local Development Database

**Single command to switch to local:**
```bash
export SUPABASE_ENV=local
python app/bot.py
```

**Switch back to production:**
```bash
export SUPABASE_ENV=prod
python app/bot.py
```

**Make it permanent in your session:**
```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
echo 'export SUPABASE_ENV=local' >> ~/.zshrc
source ~/.zshrc
```

## 🔄 Refresh Database from Production

### Option 1: Quick Refresh Script

Run this script to completely refresh your local database with production data:

```bash
./refresh_local_db.sh
```

### Option 2: Manual Step-by-Step

If you prefer to do it manually or the script fails:

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Set database password
export SUPABASE_DB_PASSWORD=jkllg222isSDDW

# 3. Ensure local Supabase is running
npx supabase start

# 4. Link to production (if not already linked)
npx supabase link --project-ref skvbindjswygkaujiynw

# 5. Drop local database and recreate fresh
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 6. Enable vector extension
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 7. Import fresh schema
npx supabase db dump --schema public -f temp_schema.sql
docker exec -i supabase_db_telegram_zoomer psql -U postgres -d postgres < temp_schema.sql

# 8. Import fresh data
python refresh_data.py

# 9. Clean up
rm -f temp_schema.sql
```

## 🛠️ Troubleshooting

### Local Supabase Not Running
```bash
npx supabase start
```

### Database Connection Issues
```bash
# Check if containers are running
docker ps | grep supabase

# Restart if needed
npx supabase stop
npx supabase start
```

### Password Changed in Production
1. Update the password in `.env` file
2. Export the new password: `export SUPABASE_DB_PASSWORD=new_password`
3. Unlink and relink: `npx supabase unlink && npx supabase link --project-ref skvbindjswygkaujiynw`

### Vector Extension Issues
```bash
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 📍 Local Database Access

- **API URL**: `http://127.0.0.1:54321`
- **Database URL**: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`
- **Studio (Web UI)**: `http://127.0.0.1:54323`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0`

## 📋 Key Tables After Refresh

Your local database will have:
- `article_chunks`: Vector embeddings and article content
- `telegram_sessions`: Session management data  
- `streamlit_conversations`: Conversation history
- `bot_config_*`: All Django admin configuration tables

## 💡 Tips

1. **Always activate venv first**: `source .venv/bin/activate`
2. **Check your environment**: `echo $SUPABASE_ENV`
3. **Verify data**: Visit `http://127.0.0.1:54323` to browse tables
4. **Safe testing**: Local changes never affect production
5. **Fresh start**: Run refresh script whenever you want clean production data

## ⚠️ Important Notes

- Local database changes are **completely isolated** from production
- Refreshing **overwrites all local data** with production data
- Keep the local Supabase containers running during development
- The refresh process takes ~2-3 minutes depending on data size