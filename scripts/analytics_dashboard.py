#!/usr/bin/env python3
"""
Analytics Dashboard for Translation Memory Bot

Displays comprehensive analytics and metrics for data science analysis.

Usage:
    python scripts/analytics_dashboard.py [--days 7] [--export]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / "app_settings.env", override=True)
load_dotenv(project_root / ".env", override=False)

from app.analytics import get_analytics_summary, _analytics_client

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'-'*40}")
    print(f"  {title}")
    print(f"{'-'*40}")

def format_time(ms: float) -> str:
    """Format milliseconds to human readable"""
    if ms < 1000:
        return f"{ms:.0f}ms"
    else:
        return f"{ms/1000:.2f}s"

def display_summary(summary: dict):
    """Display analytics summary"""
    print_header("📊 TRANSLATION MEMORY ANALYTICS DASHBOARD")
    
    if "error" in summary:
        print(f"❌ Error: {summary['error']}")
        return
    
    if "message" in summary:
        print(f"ℹ️  {summary['message']}")
        return
    
    # Overview metrics
    print_section("📈 Overview Metrics")
    print(f"Period: Last {summary['period_days']} days")
    print(f"Total Sessions: {summary['total_sessions']}")
    print(f"Successful: {summary['successful_sessions']} ({summary['success_rate']:.1%})")
    print(f"Failed: {summary['failed_sessions']}")
    print(f"Average Processing Time: {format_time(summary['avg_processing_time_ms'])}")
    print(f"Average Memory Similarity: {summary['avg_memory_similarity']:.3f}")
    
    # Recent sessions
    if summary.get('sessions'):
        print_section("🕒 Recent Sessions")
        for i, session in enumerate(summary['sessions'][:5], 1):
            status = "✅" if session.get('success', True) else "❌"
            msg_id = session.get('message_id', 'N/A')
            processing_time = format_time(session.get('total_processing_time_ms', 0))
            memories = session.get('memories_found', 0)
            similarity = session.get('avg_memory_similarity', 0)
            
            print(f"{i}. {status} Message {msg_id} | {processing_time} | {memories} memories | sim={similarity:.3f}")

def get_detailed_analytics(days: int = 7):
    """Get detailed analytics from database"""
    if not _analytics_client:
        return {"error": "Analytics client not available"}
    
    try:
        # Get translation sessions
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        sessions_result = _analytics_client.table("translation_sessions").select("*").gte(
            "created_at", cutoff_date
        ).order("created_at", desc=True).execute()
        
        sessions = sessions_result.data or []
        
        # Get memory usage analytics
        memory_result = _analytics_client.table("memory_usage_analytics").select("*").gte(
            "created_at", cutoff_date
        ).execute()
        
        memory_usage = memory_result.data or []
        
        return {
            "sessions": sessions,
            "memory_usage": memory_usage,
            "period_days": days
        }
        
    except Exception as e:
        return {"error": str(e)}

def display_detailed_analytics(data: dict):
    """Display detailed analytics"""
    if "error" in data:
        print(f"❌ Error: {data['error']}")
        return
    
    sessions = data.get('sessions', [])
    memory_usage = data.get('memory_usage', [])
    
    print_section("🔍 Detailed Session Analysis")
    
    if not sessions:
        print("No sessions found in the specified period.")
        return
    
    # Processing time analysis
    processing_times = [s.get('total_processing_time_ms', 0) for s in sessions if s.get('total_processing_time_ms')]
    if processing_times:
        avg_time = sum(processing_times) / len(processing_times)
        max_time = max(processing_times)
        min_time = min(processing_times)
        print(f"Processing Times: avg={format_time(avg_time)}, max={format_time(max_time)}, min={format_time(min_time)}")
    
    # Memory effectiveness
    memory_sessions = [s for s in sessions if s.get('memories_found', 0) > 0]
    if memory_sessions:
        avg_memories = sum(s.get('memories_found', 0) for s in memory_sessions) / len(memory_sessions)
        avg_similarity = sum(s.get('avg_memory_similarity', 0) for s in memory_sessions) / len(memory_sessions)
        print(f"Memory Usage: {len(memory_sessions)}/{len(sessions)} sessions used memory")
        print(f"Average Memories Found: {avg_memories:.1f}")
        print(f"Average Similarity: {avg_similarity:.3f}")
    
    # Translation statistics (single bidlo style only)
    total_translations = len([s for s in sessions if s.get('translation_text')])
    print(f"Total Translations: {total_translations}")
    
    # Error analysis
    failed_sessions = [s for s in sessions if not s.get('success', True)]
    if failed_sessions:
        print(f"\n❌ Failed Sessions: {len(failed_sessions)}")
        for session in failed_sessions[:3]:
            error = session.get('error_message', 'Unknown error')
            print(f"  - {session.get('message_id', 'N/A')}: {error}")
    
    # Memory usage patterns
    if memory_usage:
        print_section("🧠 Memory Usage Patterns")
        
        # Top similar memories
        top_memories = sorted(memory_usage, key=lambda x: x.get('similarity_score', 0), reverse=True)[:5]
        print("Top Similar Memories Used:")
        for i, mem in enumerate(top_memories, 1):
            similarity = mem.get('similarity_score', 0)
            source_preview = mem.get('source_text_preview', '')[:50] + "..."
            print(f"  {i}. Similarity: {similarity:.3f} | {source_preview}")

def export_data(data: dict, filename: str):
    """Export analytics data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Data exported to: {filename}")
    except Exception as e:
        print(f"❌ Export failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Translation Memory Analytics Dashboard")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
    parser.add_argument("--export", action="store_true", help="Export data to JSON file")
    parser.add_argument("--detailed", action="store_true", help="Show detailed analytics")
    args = parser.parse_args()
    
    # Get summary analytics
    summary = get_analytics_summary(args.days)
    display_summary(summary)
    
    # Get detailed analytics if requested
    if args.detailed:
        detailed_data = get_detailed_analytics(args.days)
        display_detailed_analytics(detailed_data)
        
        if args.export:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analytics_export_{timestamp}.json"
            export_data(detailed_data, filename)
    
    elif args.export:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analytics_summary_{timestamp}.json"
        export_data(summary, filename)

if __name__ == "__main__":
    main() 