#!/usr/bin/env bash
# Small utility – clone **production** Supabase database into the **local** stack.
# Works with the free-tier CLI & Docker containers only.
#
# Prerequisites:
#   1. `supabase start` already ran at least once (local stack exists)
#   2. `.env` contains:
#        SUPABASE_PROJECT_REF  # e.g. skvbindjswygkaujiynw
#        SUPABASE_DB_PASSWORD  # the **database** password for your prod project
#   3. Virtual-env activated so `supabase` CLI is on $PATH  (source .venv/bin/activate)
#
# Usage:
#   ./clone_prod_to_local.sh   # ~30 seconds
#
set -euo pipefail

# --- sanity checks -----------------------------------------------------------
[[ -f .env ]] || { echo "❌ .env missing"; exit 1; }
source .env

: "${SUPABASE_PROJECT_REF?Need SUPABASE_PROJECT_REF in .env}"
: "${SUPABASE_DB_PASSWORD?Need SUPABASE_DB_PASSWORD in .env}"

export SUPABASE_DB_PASSWORD   # ensure it is exported for child processes

# Compose prod connection string
PROD_CONN="postgres://postgres:${SUPABASE_DB_PASSWORD}@db.${SUPABASE_PROJECT_REF}.supabase.co:5432/postgres"

# --- ensure local stack running ---------------------------------------------
echo "🚀 (Re)starting local Supabase stack …"
npx supabase start >/dev/null

# Identify local postgres container name (first that matches supabase_db_*)
LOCAL_DB_CONTAINER=$(docker ps --filter "name=supabase_db_" --format "{{.Names}}" | head -n1)
[[ -n "$LOCAL_DB_CONTAINER" ]] || { echo "❌ Local supabase_db container not found"; exit 1; }

echo "🔗 Linking CLI to prod project ($SUPABASE_PROJECT_REF) …"
# ignore errors if already linked
supabase link --project-ref "$SUPABASE_PROJECT_REF" 2>/dev/null || true

TMP_DUMP=tmp_prod_dump.sql

echo "📥 Dumping prod schema + data …"
supabase db dump --schema public -f "$TMP_DUMP" --stdout >/dev/null

echo "🗑️  Resetting local database …"
docker exec "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;" >/dev/null

echo "📦 Restoring into local …"
docker exec -i "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres < "$TMP_DUMP" >/dev/null

rm "$TMP_DUMP"

echo "✅ Local database now mirrors production!  Use it with: export SUPABASE_ENV=local"
