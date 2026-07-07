"""
Local 'blob storage + metadata DB' layer for the Omni Data Hub.

Mimics an S3-style bucket/key layout on the local filesystem (data/raw/<bucket>/<key>)
and uses SQLite as the lightweight structured/queryable store (no server needed).
If this ever needs to move to real S3 + Postgres, only this module has to change --
scrapers and the strategy engine only call the functions below.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "omni_kb.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT,
    search_term TEXT,
    title TEXT,
    doc_type TEXT,
    url TEXT,
    blob_path TEXT,
    fetched_at TEXT NOT NULL,
    metadata_json TEXT,
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_term ON documents(search_term);
"""


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_blob(bucket: str, key: str, content: bytes | str) -> str:
    """Writes content to data/raw/<bucket>/<key> and returns the path (as a string)."""
    path = RAW_DIR / bucket / key
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if isinstance(content, str) else "wb"
    encoding = "utf-8" if isinstance(content, str) else None
    with open(path, mode, encoding=encoding) as f:
        f.write(content)
    return str(path.relative_to(BASE_DIR))


def upsert_document(
    conn: sqlite3.Connection,
    source: str,
    external_id: str,
    search_term: str,
    title: str,
    doc_type: str,
    url: str,
    blob_path: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO documents (source, external_id, search_term, title, doc_type, url, blob_path, fetched_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            search_term=excluded.search_term,
            title=excluded.title,
            doc_type=excluded.doc_type,
            url=excluded.url,
            blob_path=excluded.blob_path,
            fetched_at=excluded.fetched_at,
            metadata_json=excluded.metadata_json
        """,
        (
            source,
            external_id,
            search_term,
            title,
            doc_type,
            url,
            blob_path,
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
