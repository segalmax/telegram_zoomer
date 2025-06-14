import os
import uuid
import pytest
from dotenv import load_dotenv
load_dotenv()
from app import vector_store

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

pytestmark = pytest.mark.skipif(
    not (SUPABASE_URL and SUPABASE_KEY),
    reason="Supabase env vars not set; skipping TM test."
)

def test_save_and_recall_pair():
    src = f"Test source {uuid.uuid4()}"
    tgt = f"Test translation {uuid.uuid4()}"
    pair_id = f"pytest-{uuid.uuid4()}"
    # Save the pair
    vector_store.save_pair(src, tgt, pair_id)
    # Recall
    results = vector_store.recall(src, k=3)
    # Should find at least one with our src/tgt
    found = any(r.get("id") == pair_id and r.get("translation_text") == tgt for r in results)
    assert found, f"Did not find saved pair in recall results: {results}"
    # Optionally: clean up (delete row) if you want, but not required for MVP 