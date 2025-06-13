"""
Vector store layer (Supabase + pgvector) – MVP
Keeps source ↔ translation pairs so the LLM can stay consistent.
"""

from __future__ import annotations

import os
import logging
import datetime as _dt
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
if openai_api_ready:
    openai.api_key = OPENAI_KEY  # type: ignore

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")

# ---------------------------------------------------------------------------
# Supabase client (optional)
# ---------------------------------------------------------------------------
_sb: Client | None = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
        logger.info("Supabase vector store enabled")
    except Exception as e:  # pragma: no cover
        logger.warning(f"Unable to create Supabase client – vector store disabled: {e}")
        _sb = None
else:
    logger.info("Supabase vector store disabled – missing env or dependency")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> List[float]:
    """Return embedding vector using OpenAI embeddings. Falls back to empty list if not available."""
    if not openai_api_ready:
        logger.debug("OpenAI not configured; returning zero vector")
        return []
    try:
        r = openai.Embedding.create(model=EMBED_MODEL, input=text, timeout=30)  # type: ignore
        return r["data"][0]["embedding"]  # type: ignore
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_pair(src: str, tgt: str, pair_id: str | None = None) -> None:
    """Upsert one (source, translation) pair into Supabase. No-op if store unavailable."""
    if _sb is None:
        return
    if not src or not tgt:
        return
    pair_id = pair_id or str(uuid.uuid4())
    try:
        vec = _embed(src)
        data = {
            "id": pair_id,
            "source_text": src,
            "translation_text": tgt,
            "embedding": vec if vec else None,
            "created_at": _dt.datetime.utcnow().isoformat(),
        }
        _sb.table("article_chunks").upsert(data).execute()  # type: ignore
    except Exception as e:
        logger.error(f"vector_store.save_pair failed: {e}")


def recall(src: str, k: int = 5) -> List[Dict[str, Any]]:
    """Return ≤k most relevant past pairs. Empty list if store unavailable or error."""
    if _sb is None or not src:
        return []
    try:
        vec = _embed(src)
        res = _sb.rpc(
            "match_article_chunks",
            {"query_embedding": vec, "match_count": k},
        ).execute()  # type: ignore
        return res.data or []  # type: ignore
    except Exception as e:
        logger.warning(f"vector_store.recall failed: {e}")
        return [] 