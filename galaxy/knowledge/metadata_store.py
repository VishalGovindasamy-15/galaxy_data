"""SQLite metadata store for sessions and datasets."""
import json
import time
import logging
import sqlite3
from pathlib import Path
from galaxy.config import Config

log = logging.getLogger("galaxy.knowledge")

DB_PATH = Config.PROJECT_DIR / "metadata.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            state TEXT,
            query TEXT,
            workspace_path TEXT,
            created_at REAL,
            updated_at REAL,
            progress TEXT DEFAULT '{}',
            error TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS datasets (
            hash TEXT PRIMARY KEY,
            path TEXT,
            source_id TEXT,
            source_url TEXT,
            format TEXT,
            size_bytes INTEGER,
            quality_score REAL,
            row_count INTEGER,
            schema TEXT DEFAULT '{}',
            license TEXT DEFAULT 'unknown',
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS query_cache (
            query_hash TEXT PRIMARY KEY,
            query_text TEXT,
            result_session_id TEXT,
            embedding_id TEXT,
            created_at REAL
        );
    """)
    conn.commit()
    conn.close()


def save_session(session_id: str, user_id: str, state: str, query: str, workspace: str):
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
        (session_id, user_id, state, query, workspace, now, now, "{}", "")
    )
    conn.commit()
    conn.close()


def update_session_state(session_id: str, state: str, error: str = ""):
    conn = _get_conn()
    conn.execute("UPDATE sessions SET state=?, updated_at=?, error=? WHERE session_id=?",
                 (state, time.time(), error, session_id))
    conn.commit()
    conn.close()


def save_dataset(hash: str, path: str, source_id: str, source_url: str, fmt: str,
                 size: int, quality: float, row_count: int, schema: dict, license: str):
    conn = _get_conn()
    conn.execute("INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (hash, path, source_id, source_url, fmt, size, quality, row_count,
                  json.dumps(schema), license, time.time()))
    conn.commit()
    conn.close()


def get_session(session_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# Initialize on import
init_db()
