"""Import the newest `chat_completions` runtime-log session into
AutoGen Studio's `session` & `message` tables so the conversation
shows up in the UI.

Run:
    python scripts/import_runtime_log.py

Prerequisites:
1. AutoGen Studio has been launched at least once so its SQLite DB
   (~/.autogenstudio/database.sqlite) exists with schema.
2. autogen_games.py (or any runtime_logging script) has just run and
   written rows to the `chat_completions` table.

The script is idempotent – if the session/messages were already
imported it exits silently.

Production Safety: Only runs in development environments.
"""

import sys
import os

# Add project root to path and check production safety
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.environment import assert_not_production
assert_not_production()

from __future__ import annotations

import datetime as _dt
import os
import sqlite3 as _sql
import sys
import uuid as _uuid

# --- new imports ---
import json
from typing import List, Tuple

DB_PATH = os.path.expanduser("~/.autogenstudio/database.sqlite")

if not os.path.isfile(DB_PATH):
    sys.exit(f"❌ Studio DB not found at {DB_PATH}. Run `autogenstudio ui` first.")

conn = _sql.connect(DB_PATH)
cur = conn.cursor()

# 1️⃣ Get newest runtime_logging session UUID
cur.execute(
    "SELECT session_id FROM chat_completions ORDER BY start_time DESC LIMIT 1"
)
row = cur.fetchone()
if row is None:
    sys.exit("❌ No chat_completions found. Run autogen_games.py first.")

runtime_uuid: str = row[0]

# 2️⃣ Determine (or create) Studio session row (uses AUTOINCREMENT id PK)
session_name = f"Runtime {runtime_uuid[:8]}"

cur.execute(
    "SELECT id FROM session WHERE name = ? AND description = 'Imported from runtime_logging'",
    (session_name,),
)
row = cur.fetchone()

if row:
    session_pk = row[0]
    print(f"ℹ️  Re-using existing Studio session id={session_pk} for {runtime_uuid}.")
else:
    now = _dt.datetime.utcnow().isoformat(" ")
    cur.execute(
        "INSERT INTO session (created_at, updated_at, user_id, workflow_id, name, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            now,
            now,
            "guestuser@gmail.com",
            2,  # default workflow "Chat" workflow
            session_name,
            "Imported from runtime_logging",
        ),
    )
    session_pk = cur.lastrowid
    conn.commit()
    print(f"🆕 Added Studio session id={session_pk} for runtime {runtime_uuid}.")

# 3️⃣ Skip if messages already imported
cur.execute("SELECT 1 FROM message WHERE session_id = ? LIMIT 1", (session_pk,))
if cur.fetchone():
    print("✔️  Messages already imported. Done.")
    conn.close()
    sys.exit(0)

# 4️⃣ Copy chat_completions rows into message table
cur.execute(
    "SELECT request, response, source_name, start_time "
    "FROM chat_completions WHERE session_id = ? ORDER BY start_time",
    (runtime_uuid,),
)

rows = cur.fetchall()
if not rows:
    sys.exit("❌ chat_completions present but empty for this session.")

def _extract_messages(req_json: str, res_json: str) -> List[Tuple[str, str]]:
    """Return list of (role, content) in chronological order for this completion."""
    out: List[Tuple[str, str]] = []

    try:
        req = json.loads(req_json)
        for m in req.get("messages", []):
            role = m.get("role", "assistant")
            content = m.get("content", "").strip()
            if content:
                out.append((role, content))
    except Exception:
        # fallback: skip unparseable
        pass

    try:
        res = json.loads(res_json)
        choice = res.get("choices", [{}])[0]
        m = choice.get("message", {})
        role = m.get("role", "assistant")
        content = m.get("content", "").strip()
        if content:
            out.append((role, content))
    except Exception:
        pass

    return out

# Keep track of inserted messages to deduplicate
inserted: set[Tuple[str, str]] = set()

for req_s, res_s, _source, ts in rows:
    for role, content in _extract_messages(req_s, res_s):
        if (role, content) in inserted:
            continue
        inserted.add((role, content))
        cur.execute(
            "INSERT INTO message (session_id, role, content, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_pk,
                role.lower(),
                content,
                ts,
                ts,
                "guestuser@gmail.com",
            ),
        )

conn.commit()
conn.close()
print(f"✅ Imported {len(inserted)} unique messages for session id={session_pk}. Refresh Studio UI ✨") 