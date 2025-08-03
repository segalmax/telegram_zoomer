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
npx supabase link --project-ref "$SUPABASE_PROJECT_REF" 2>/dev/null || true

TMP_DUMP=$(mktemp -t prod_dump_XXXX.sql)

echo "📥 Dumping prod schema + data (public schema only) …"
PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump \
  --no-owner --no-acl \
  --schema=public \
  --encoding=UTF8 \
  --dbname="$PROD_CONN" \
  > "$TMP_DUMP"

echo "🗑️  Resetting local database …"
docker exec "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;" >/dev/null

echo "🔧 Enabling vector extension …"
docker exec "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null

echo "📦 Restoring into local …"
# Filter out CREATE SCHEMA public; line to avoid conflict
grep -v "^CREATE SCHEMA public;$" "$TMP_DUMP" | docker exec -i "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres -q >/dev/null 2>&1

echo "🔒 Setting up permissions for service_role …"
docker exec "$LOCAL_DB_CONTAINER" psql -U postgres -d postgres -c "GRANT ALL ON SCHEMA public TO service_role; GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;" >/dev/null

rm "$TMP_DUMP"

echo "✅ Local database now mirrors production!  Use it with: export SUPABASE_ENV=local"
