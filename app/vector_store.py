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

from supabase import create_client, Client  # type: ignore
import openai  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_KEY, "OPENAI_API_KEY environment variable is required"
_openai_client = openai.OpenAI(api_key=OPENAI_KEY)

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")

# ---------------------------------------------------------------------------
# Supabase client (REQUIRED)
# ---------------------------------------------------------------------------
assert SUPABASE_URL, "SUPABASE_URL environment variable is required"
assert SUPABASE_KEY, "SUPABASE_KEY environment variable is required"

try:
    # Try creating client without any extra options first
    _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase vector store enabled")
except TypeError as e:
    # Handle proxy parameter issue in older versions
    try:
        import inspect
        sig = inspect.signature(create_client)
        if 'options' in sig.parameters:
            _sb = create_client(SUPABASE_URL, SUPABASE_KEY, options={})
        else:
            _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase vector store enabled (fallback)")
    except Exception as e2:
        raise RuntimeError(f"Failed to create Supabase client even with fallback: {e2}") from e2
except Exception as e:
    raise RuntimeError(f"Failed to create Supabase client: {e}") from e

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> List[float]:
    """Return embedding vector using OpenAI embeddings. Fails if OpenAI unavailable."""
    try:
        response = _openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=text,
            timeout=30
        )
        return response.data[0].embedding
    except Exception as e:
        raise RuntimeError(f"Embedding generation failed: {e}") from e

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_pair(
    src: str, 
    tgt: str, 
    pair_id: str | None = None,
    message_id: int | None = None,
    channel_name: str | None = None,
    message_url: str | None = None
) -> None:
    """Upsert one (source, translation) pair into Supabase. Fails if store unavailable or invalid input."""
    assert src, "Source text is required for save_pair"
    assert tgt, "Target text is required for save_pair"
    
    pair_id = pair_id or str(uuid.uuid4())
    logger.debug(f"💾 Starting save_pair: id={pair_id}, src_len={len(src)}, tgt_len={len(tgt)}, message_id={message_id}, url={message_url}")
    
    try:
        # Generate embedding
        embed_start = time.time()
        vec = _embed(src)
        embed_time = time.time() - embed_start
        logger.debug(f"🔢 Generated embedding in {embed_time:.3f}s: {len(vec)} dimensions")
        
        # Prepare data
        data = {
            "id": pair_id,
            "source_text": src,
            "translation_text": tgt,
            "embedding": vec,
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        
        # Add optional message metadata
        if message_id is not None:
            data["message_id"] = message_id
        if channel_name is not None:
            data["channel_name"] = channel_name
        if message_url is not None:
            data["message_url"] = message_url
        
        # Save to database
        db_start = time.time()
        result = _sb.table("article_chunks").upsert(data).execute()  # type: ignore
        db_time = time.time() - db_start
        
        logger.debug(f"💾 Database upsert completed in {db_time:.3f}s")
        logger.info(f"💾 Successfully saved pair {pair_id}: embed={embed_time:.3f}s, db={db_time:.3f}s, url={message_url}")
        
    except Exception as e:
        logger.error(f"💥 vector_store.save_pair failed for {pair_id}: {e}", exc_info=True)


def recall(src: str, k: int = 10) -> List[Dict[str, Any]]:
    """Return ≤k most relevant past pairs. Fails if store unavailable or invalid input."""
    assert src, "Source text is required for recall"
    
    logger.debug(f"🧠 Starting recall: k={k}, src_len={len(src)}")
    
    try:
        # Generate embedding for query
        embed_start = time.time()
        vec = _embed(src)
        embed_time = time.time() - embed_start
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
        raise RuntimeError(f"Vector store recall failed: {e}") from e 