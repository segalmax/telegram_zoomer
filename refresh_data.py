#!/usr/bin/env python3
"""
Standalone script to refresh local Supabase database with production data.
This is the data export portion separated for manual use.
"""
import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def get_all_tables():
    """Get list of all tables to export from production"""
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
    """Export all data from a specific table"""
    try:
        print(f"  Exporting {table_name}...")
        response = supabase.table(table_name).select("*").execute()
        print(f"    ✅ {len(response.data)} records")
        return response.data
    except Exception as e:
        print(f"    ⚠️  Warning: Could not export {table_name}: {e}")
        return []

def format_sql_value(val):
    """Format a Python value for SQL insertion"""
    if val is None:
        return 'NULL'
    elif isinstance(val, str):
        # Escape single quotes
        escaped = val.replace("'", "''")
        return f"'{escaped}'"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    elif isinstance(val, list):
        # For arrays/json columns
        escaped = json.dumps(val).replace("'", "''")
        return f"'{escaped}'::jsonb"
    else:
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"

def main():
    """Main export function"""
    print("🚀 Connecting to production Supabase...")
    
    # Connect to production
    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    
    tables = get_all_tables()
    total_records = 0
    
    print(f"📊 Exporting data from {len(tables)} tables...")
    
    with open('temp_data_export.sql', 'w') as f:
        f.write("-- Production data export for local development\n")
        f.write("-- Generated automatically\n\n")
        
        for table_name in tables:
            data = export_table_data(supabase, table_name)
            
            if data:
                f.write(f"\n-- Data for table: {table_name}\n")
                for record in data:
                    columns = list(record.keys())
                    values = [format_sql_value(record[col]) for col in columns]
                    
                    columns_str = ', '.join([f'"{col}"' for col in columns])
                    values_str = ', '.join(values)
                    f.write(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str}) ON CONFLICT DO NOTHING;\n")
                
                total_records += len(data)
    
    print(f"\n✅ Export complete!")
    print(f"📈 Total records exported: {total_records}")
    print(f"📄 SQL file: temp_data_export.sql")
    print("\n🔄 To load into local database:")
    print("   docker exec -i supabase_db_telegram_zoomer psql -U postgres -d postgres < temp_data_export.sql")

if __name__ == "__main__":
    main()