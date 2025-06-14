"""
Vector store layer (Supabase + pgvector) – MVP
Keeps source ↔ translation pairs so the LLM can stay consistent.
"""

from __future__ import annotations

import os
import logging
import datetime as _dt
import time
import uuid
from typing import List, Dict, Any

try:
    from supabase import create_client, Client  # type: ignore
except ImportError:  # pragma: no cover
    # Supabase optional – we still want the bot to run if dependency missing during tests.
    create_client = None  # type: ignore
    Client = Any  # type: ignore

try:
    import openai  # type: ignore
except ImportError:  # pragma: no cover
    openai = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
openai_api_ready = openai is not None and OPENAI_KEY is not None
_openai_client = None
if openai_api_ready:
    _openai_client = openai.OpenAI(api_key=OPENAI_KEY)  # type: ignore

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")

# ---------------------------------------------------------------------------
# Supabase client (optional)
# ---------------------------------------------------------------------------
_sb: Client | None = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        # Try creating client without any extra options first
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
        logger.info("Supabase vector store enabled")
    except TypeError as e:
        # Handle proxy parameter issue in older versions
        try:
            import inspect
            sig = inspect.signature(create_client)
            if 'options' in sig.parameters:
                _sb = create_client(SUPABASE_URL, SUPABASE_KEY, options={})  # type: ignore
            else:
                _sb = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
            logger.info("Supabase vector store enabled (fallback)")
        except Exception as e2:
            logger.warning(f"Unable to create Supabase client – vector store disabled: {e2}")
            _sb = None
    except Exception as e:  # pragma: no cover
        logger.warning(f"Unable to create Supabase client – vector store disabled: {e}")
        _sb = None
else:
    logger.info("Supabase vector store disabled – missing env or dependency")
    logger.warning("Supabase vector store disabled – missing env vars or supabase library; running without TM")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> List[float]:
    """Return embedding vector using OpenAI embeddings. Falls back to empty list if not available."""
    if not openai_api_ready or _openai_client is None:
        logger.debug("OpenAI not configured; returning zero vector")
        return []
    try:
        response = _openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=text,
            timeout=30
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_pair(src: str, tgt: str, pair_id: str | None = None) -> None:
    """Upsert one (source, translation) pair into Supabase. No-op if store unavailable."""
    if _sb is None:
        logger.debug("💾 Supabase client not available, skipping save_pair")
        return
    if not src or not tgt:
        logger.warning(f"💾 Empty source or target text, skipping save_pair: src={bool(src)}, tgt={bool(tgt)}")
        return
    
    pair_id = pair_id or str(uuid.uuid4())
    logger.debug(f"💾 Starting save_pair: id={pair_id}, src_len={len(src)}, tgt_len={len(tgt)}")
    
    try:
        # Generate embedding
        embed_start = time.time()
        vec = _embed(src)
        embed_time = time.time() - embed_start
        
        if vec:
            logger.debug(f"🔢 Generated embedding in {embed_time:.3f}s: {len(vec)} dimensions")
        else:
            logger.warning(f"🔢 Failed to generate embedding in {embed_time:.3f}s")
        
        # Prepare data
        data = {
            "id": pair_id,
            "source_text": src,
            "translation_text": tgt,
            "embedding": vec if vec else None,
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        
        # Save to database
        db_start = time.time()
        result = _sb.table("article_chunks").upsert(data).execute()  # type: ignore
        db_time = time.time() - db_start
        
        logger.debug(f"💾 Database upsert completed in {db_time:.3f}s")
        logger.info(f"💾 Successfully saved pair {pair_id}: embed={embed_time:.3f}s, db={db_time:.3f}s")
        
    except Exception as e:
        logger.error(f"💥 vector_store.save_pair failed for {pair_id}: {e}", exc_info=True)


def recall(src: str, k: int = 10) -> List[Dict[str, Any]]:
    """Return ≤k most relevant past pairs. Empty list if store unavailable or error."""
    if _sb is None:
        logger.debug("🧠 Supabase client not available, returning empty recall")
        return []
    if not src:
        logger.warning("🧠 Empty source text provided to recall")
        return []
    
    logger.debug(f"🧠 Starting recall: k={k}, src_len={len(src)}")
    
    try:
        # Generate embedding for query
        embed_start = time.time()
        vec = _embed(src)
        embed_time = time.time() - embed_start
        
        if not vec:
            logger.warning(f"🧠 Failed to generate query embedding in {embed_time:.3f}s")
            return []
        
        logger.debug(f"🔢 Generated query embedding in {embed_time:.3f}s: {len(vec)} dimensions")
        
        # Query database
        db_start = time.time()
        # Fetch extra candidates to allow re-ranking by recency
        overfetch = int(k * 4)
        res = _sb.rpc(
            "match_article_chunks",
            {"query_embedding": vec, "match_count": overfetch},
        ).execute()  # type: ignore
        db_time = time.time() - db_start
        
        raw_results = res.data or []  # type: ignore
        logger.debug(f"🧠 DB query in {db_time:.3f}s, fetched {len(raw_results)} candidates for re-ranking")
        
        # ------------------------------------------------------------------
        # Combine similarity with recency to favour fresh translations
        # ------------------------------------------------------------------
        from datetime import datetime, timezone

        RECENCY_WEIGHT = float(os.getenv("TM_RECENCY_WEIGHT", "0.3"))  # 0 ≤ w ≤ 1
        SIM_WEIGHT = 1.0 - RECENCY_WEIGHT

        now = datetime.now(timezone.utc)

        re_ranked = []
        for r in raw_results:
            sim = r.get("similarity", 0.0)
            created_at_str = r.get("created_at") or r.get("created_at_ts")
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else now
            except Exception:
                created_at = now
            age_hours = max((now - created_at).total_seconds() / 3600.0, 0.0)
            # Recency score: 1 when just now, decays with age (half-life 24h)
            recency_score = 1.0 / (1.0 + age_hours / 24.0)
            combined = SIM_WEIGHT * sim + RECENCY_WEIGHT * recency_score
            r["combined_score"] = combined
            re_ranked.append(r)

        re_ranked.sort(key=lambda x: x["combined_score"], reverse=True)
        results = re_ranked[:k]

        # Log statistics
        if results:
            avg_sim = sum(r.get("similarity", 0.0) for r in results) / len(results)
            avg_rec = sum(r.get("combined_score", 0.0) for r in results) / len(results)
            logger.info(
                f"🧠 Recall re-ranked: returned {len(results)}/{k}, avg_similarity={avg_sim:.3f}, "
                f"avg_combined={avg_rec:.3f}, embed={embed_time:.3f}s, db={db_time:.3f}s"
            )
        else:
            logger.info(f"🧠 No results after re-ranking: embed={embed_time:.3f}s, db={db_time:.3f}s")

        return results
        
    except Exception as e:
        logger.error(f"💥 vector_store.recall failed: {e}", exc_info=True)
        return [] 