"""
Analytics module for translation memory and bot performance tracking.
Provides comprehensive data collection for data science analysis and bot improvement.
"""

from __future__ import annotations

import os
import logging
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from supabase import create_client, Client  # type: ignore

logger = logging.getLogger(__name__)

# Use same Supabase client as vector_store
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

assert SUPABASE_URL, "SUPABASE_URL environment variable is required for analytics"
assert SUPABASE_KEY, "SUPABASE_KEY environment variable is required for analytics"

try:
    _analytics_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Analytics client initialized")
except Exception as e:
    raise RuntimeError(f"Analytics client initialization failed: {e}") from e

@dataclass
class TranslationSession:
    """Data class to track a complete translation session"""
    id: str
    message_id: Optional[str]
    session_start_time: datetime
    source_text: str
    source_text_length: int
    article_url: Optional[str] = None
    article_text_length: Optional[int] = None
    translation_text: Optional[str] = None
    translation_text_length: Optional[int] = None
    session_end_time: Optional[datetime] = None
    total_processing_time_ms: Optional[int] = None
    memory_query_time_ms: Optional[int] = None
    embedding_time_ms: Optional[int] = None
    translation_time_ms: Optional[int] = None
    memory_save_time_ms: Optional[int] = None
    memories_found: int = 0
    memories_used: int = 0
    avg_memory_similarity: Optional[float] = None
    max_memory_similarity: Optional[float] = None
    min_memory_similarity: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class MemoryUsage:
    """Data class to track individual memory usage with recency info"""
    session_id: str
    memory_pair_id: str
    similarity_score: float
    recency_score: float
    combined_score: float
    rank_position: int
    source_text_preview: str
    translation_text_preview: str

class AnalyticsTracker:
    """Main analytics tracking class"""
    
    def __init__(self):
        self.current_session: Optional[TranslationSession] = None
        self.session_start_time: Optional[float] = None
    
    def start_session(self, message_id: Optional[str], source_text: str, article_url: Optional[str] = None) -> str:
        """Start a new translation session"""
        session_id = str(uuid.uuid4())
        self.session_start_time = time.time()
        
        self.current_session = TranslationSession(
            id=session_id,
            message_id=message_id,
            session_start_time=datetime.now(),
            source_text=source_text,
            source_text_length=len(source_text),
            article_url=article_url
        )
        
        logger.info(f"📊 Started analytics session: {session_id}")
        return session_id
    
    def set_article_content(self, article_text: str):
        """Set article content length"""
        if self.current_session:
            self.current_session.article_text_length = len(article_text)
            logger.debug(f"📊 Set article length: {len(article_text)} chars")
    
    def set_memory_metrics(self, memories: List[Dict[str, Any]], query_time_ms: int):
        """Set memory query results and timing"""
        if not self.current_session:
            return
        
        self.current_session.memories_found = len(memories)
        self.current_session.memory_query_time_ms = query_time_ms
        
        if memories:
            similarities = [m.get('similarity', 0.0) for m in memories]
            self.current_session.avg_memory_similarity = sum(similarities) / len(similarities)
            self.current_session.max_memory_similarity = max(similarities)
            self.current_session.min_memory_similarity = min(similarities)
            self.current_session.memories_used = len(memories)
            
            logger.debug(f"📊 Memory metrics: found={len(memories)}, avg_sim={self.current_session.avg_memory_similarity:.3f}")
    
    def set_translation_result(self, translation_text: str, translation_time_ms: int):
        """Set translation result and timing"""
        if not self.current_session:
            return
        
        self.current_session.translation_text = translation_text
        self.current_session.translation_text_length = len(translation_text)
        self.current_session.translation_time_ms = translation_time_ms
        
        logger.debug(f"📊 Translation result: {len(translation_text)} chars in {translation_time_ms}ms")
    
    def set_memory_save_time(self, save_time_ms: int):
        """Set memory save timing"""
        if self.current_session:
            self.current_session.memory_save_time_ms = save_time_ms
            logger.debug(f"📊 Memory save time: {save_time_ms}ms")
    
    def set_error(self, error_message: str):
        """Mark session as failed with error"""
        if self.current_session:
            self.current_session.success = False
            self.current_session.error_message = error_message
            logger.warning(f"📊 Session error: {error_message}")
    
    def end_session(self) -> Optional[str]:
        """End the current session and save to database"""
        if not self.current_session or not self.session_start_time:
            return None
        
        # Calculate total processing time
        total_time_ms = int((time.time() - self.session_start_time) * 1000)
        self.current_session.total_processing_time_ms = total_time_ms
        self.current_session.session_end_time = datetime.now()
        
        session_id = self.current_session.id
        
        # Save to database
        try:
            self._save_session_to_db(self.current_session)
            logger.info(f"📊 Session completed: {session_id}, total_time={total_time_ms}ms")
        except Exception as e:
            logger.error(f"📊 Failed to save session {session_id}: {e}")
        
        # Reset for next session
        self.current_session = None
        self.session_start_time = None
        
        return session_id
    
    def track_memory_usage(self, session_id: str, memories: List[Dict[str, Any]]):
        """Track individual memory usage for analysis"""
        if not memories:
            return
        
        # Only track memory usage if we have a current session (ensures session exists in DB)
        if not self.current_session or self.current_session.id != session_id:
            logger.debug(f"📊 Skipping memory usage tracking - no active session for {session_id}")
            return
        
        # Store memory usage data for later insertion (after session is saved)
        if not hasattr(self.current_session, '_pending_memory_usage'):
            self.current_session._pending_memory_usage = []
        
        for i, memory in enumerate(memories, 1):
            usage = MemoryUsage(
                session_id=session_id,
                memory_pair_id=memory.get('id', ''),
                similarity_score=memory.get('similarity', 0.0),
                recency_score=memory.get('recency_score', 0.0),
                combined_score=memory.get('combined_score', 0.0),
                rank_position=i,
                source_text_preview=memory.get('source_text', '')[:100],
                translation_text_preview=memory.get('translation_text', '')[:100]
            )
            self.current_session._pending_memory_usage.append(asdict(usage))
        
        logger.debug(f"📊 Queued {len(memories)} memory usage records for later insertion")
    
    def _save_session_to_db(self, session: TranslationSession):
        """Save session to database"""
        
        try:
            session_data = asdict(session)
            # Convert datetime objects to ISO strings
            session_data['session_start_time'] = session.session_start_time.isoformat()
            if session.session_end_time:
                session_data['session_end_time'] = session.session_end_time.isoformat()
            
            # Remove the pending memory usage from session data (it's not a DB field)
            session_data.pop('_pending_memory_usage', None)
            
            _analytics_client.table("translation_sessions").insert(session_data).execute()
            logger.debug(f"📊 Saved session to database: {session.id}")
            
            # Now save pending memory usage records (after session exists in DB)
            if hasattr(session, '_pending_memory_usage') and session._pending_memory_usage:
                try:
                    _analytics_client.table("memory_usage_analytics").insert(session._pending_memory_usage).execute()
                    logger.debug(f"📊 Saved {len(session._pending_memory_usage)} memory usage records")
                except Exception as e:
                    logger.error(f"📊 Failed to save memory usage records: {e}")
            
        except Exception as e:
            logger.error(f"📊 Database save failed for session {session.id}: {e}")

# Global analytics tracker instance
analytics = AnalyticsTracker()

def get_analytics_summary(days: int = 7) -> Dict[str, Any]:
    """Get analytics summary for the last N days"""
    
    try:
        # Get session statistics
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        sessions_result = _analytics_client.table("translation_sessions").select("*").gte(
            "created_at", cutoff_date
        ).execute()
        
        sessions = sessions_result.data or []
        
        if not sessions:
            return {"message": f"No sessions found in the last {days} days"}
        
        # Calculate summary statistics
        total_sessions = len(sessions)
        successful_sessions = len([s for s in sessions if s.get('success', True)])
        failed_sessions = total_sessions - successful_sessions
        
        processing_times = [s.get('total_processing_time_ms', 0) for s in sessions if s.get('total_processing_time_ms')]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        memory_similarities = [s.get('avg_memory_similarity', 0) for s in sessions if s.get('avg_memory_similarity')]
        avg_memory_similarity = sum(memory_similarities) / len(memory_similarities) if memory_similarities else 0
        
        return {
            "period_days": days,
            "total_sessions": total_sessions,
            "successful_sessions": successful_sessions,
            "failed_sessions": failed_sessions,
            "success_rate": successful_sessions / total_sessions if total_sessions > 0 else 0,
            "avg_processing_time_ms": avg_processing_time,
            "avg_memory_similarity": avg_memory_similarity,
            "sessions": sessions[:10]  # Return last 10 sessions as examples
        }
        
    except Exception as e:
        logger.error(f"📊 Failed to get analytics summary: {e}")
        return {"error": str(e)} 