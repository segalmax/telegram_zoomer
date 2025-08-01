#!/bin/bash

# Local Supabase Database Refresh Script
# This script completely refreshes your local development database with production data

set -e  # Exit on any error

echo "🔄 Starting local database refresh from production..."

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Virtual environment not activated. Please run:"
    echo "   source .venv/bin/activate"
    exit 1
fi

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo "❌ .env file not found. Please ensure it exists with SUPABASE credentials."
    exit 1
fi

# Load environment variables
source .env

# Check if required environment variables are set
if [[ -z "$DB_PASSWORD" ]]; then
    echo "❌ DB_PASSWORD not found in .env file"
    exit 1
fi

echo "✅ Environment validated"

# Set database password for Supabase CLI
export SUPABASE_DB_PASSWORD="$DB_PASSWORD"

echo "🚀 Starting local Supabase (if not running)..."
npx supabase start

echo "🔗 Linking to production database..."
npx supabase unlink 2>/dev/null || true
npx supabase link --project-ref skvbindjswygkaujiynw

echo "🗑️  Dropping existing local database..."
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;" > /dev/null

echo "🔧 Enabling vector extension..."
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null

echo "📥 Downloading production schema..."
npx supabase db dump --schema public -f temp_schema.sql > /dev/null

echo "🏗️  Creating tables..."
docker exec -i supabase_db_telegram_zoomer psql -U postgres -d postgres < temp_schema.sql > /dev/null 2>&1

echo "📊 Exporting production data..."
cat > temp_export_data.py << 'EOF'
#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def get_all_tables():
    return [
        'bot_config_configsetting',
        'bot_config_translationprompt', 
        'bot_config_aimodelconfig',
        'bot_config_processinglimits',
        'bot_config_translationmemoryconfig',
        'bot_config_articleextractionconfig',
        'bot_config_messagetemplate',
        'bot_config_environmentconfig',
        'telegram_sessions',
        'article_chunks',
        'streamlit_conversations'
    ]

def export_table_data(supabase, table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data
    except Exception as e:
        print(f"Warning: Could not export {table_name}: {e}")
        return []

def main():
    # Connect to production
    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    
    tables = get_all_tables()
    
    with open('temp_data_export.sql', 'w') as f:
        for table_name in tables:
            data = export_table_data(supabase, table_name)
            if data:
                for record in data:
                    columns = list(record.keys())
                    values = []
                    for col in columns:
                        val = record[col]
                        if val is None:
                            values.append('NULL')
                        elif isinstance(val, str):
                            # Escape single quotes
                            escaped = val.replace("'", "''")
                            values.append(f"'{escaped}'")
                        elif isinstance(val, (int, float)):
                            values.append(str(val))
                        elif isinstance(val, bool):
                            values.append('TRUE' if val else 'FALSE')
                        elif isinstance(val, list):
                            # For arrays/json columns
                            escaped = json.dumps(val).replace("'", "''")
                            values.append(f"'{escaped}'::jsonb")
                        else:
                            escaped = str(val).replace("'", "''")
                            values.append(f"'{escaped}'")
                    
                    columns_str = ', '.join([f'"{col}"' for col in columns])
                    values_str = ', '.join(values)
                    f.write(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str}) ON CONFLICT DO NOTHING;\n")

if __name__ == "__main__":
    main()
EOF

python temp_export_data.py

echo "📥 Loading production data into local database..."
docker exec -i supabase_db_telegram_zoomer psql -U postgres -d postgres < temp_data_export.sql > /dev/null 2>&1

echo "🧹 Cleaning up temporary files..."
rm -f temp_schema.sql temp_data_export.sql temp_export_data.py

echo "✅ Local database refresh complete!"
echo ""
echo "📊 Checking data counts..."
docker exec supabase_db_telegram_zoomer psql -U postgres -d postgres -c "
SELECT 
    'article_chunks' as table_name, count(*) as records 
FROM article_chunks 
UNION ALL 
SELECT 'telegram_sessions', count(*) 
FROM telegram_sessions 
UNION ALL 
SELECT 'streamlit_conversations', count(*) 
FROM streamlit_conversations;"

echo ""
echo "🎯 To use local database, run:"
echo "   export SUPABASE_ENV=local"
echo "   python app/bot.py"
echo ""
echo "🌐 Access local Supabase Studio at: http://127.0.0.1:54323"