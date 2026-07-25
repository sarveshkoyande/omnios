"""Content-addressed blob store for campaign artefacts and content assets.

A minimal, dependency-free stand-in for cloud blob storage (Azure Blob / S3). Bytes are
stored once, keyed by their sha256 (so identical content de-duplicates), under
``data/blobs/``; a manifest row is written to the campaign DB's ``blob`` table via the
caller (campaign_store persists the manifest). The public surface -- ``put``, ``get``,
``uri_for`` -- is deliberately the same shape you'd implement against azure-storage-blob
later, so swapping the backend is a one-file change: today ``storage_uri`` is
``file://.../data/blobs/<key>``; in cloud it becomes ``azure://<container>/<key>``.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402
import db  # noqa: E402  (dual-dialect layer; on Postgres there is no persistent disk so
#                          blob bytes live in the DB's blob_data (BYTEA) table instead)

BLOB_DIR = data_path("blobs")


def _key(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_for(key: str) -> pathlib.Path:
    # Shard by the first 2 hex chars to avoid one giant directory.
    return BLOB_DIR / key[:2] / key


_pg_schema_ready = False


def _pg_ready() -> None:
    """Ensure the campaigns schema (which owns the blob_data table) exists on Postgres.
    Run once per process. campaign_store is imported lazily because it imports this module,
    so a top-level import would be circular."""
    global _pg_schema_ready
    if _pg_schema_ready:
        return
    import campaign_store  # noqa: E402
    campaign_store.init_db()
    _pg_schema_ready = True


def put(data: bytes | str, *, mime_type: str = "application/octet-stream",
        original_name: str = "") -> dict:
    """Store bytes (or a str, encoded utf-8) and return a manifest dict:
    {blob_key, mime_type, byte_size, original_name, storage_uri}. Idempotent -- the same
    content yields the same key and is written at most once. On Postgres the bytes are
    written to blob_data (BYTEA) and storage_uri is a pg://blob/<key> pointer; on SQLite the
    bytes go to data/blobs/<key> and storage_uri is a file:// URI (unchanged behaviour)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    key = _key(data)
    if db.IS_PG:
        _pg_ready()
        conn = db.connect("campaigns")
        try:
            conn.execute("INSERT OR IGNORE INTO blob_data (blob_key, data) VALUES (?,?)", (key, data))
            conn.commit()
        finally:
            conn.close()
        storage_uri = f"pg://blob/{key}"
    else:
        path = _path_for(key)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        storage_uri = path.resolve().as_uri()
    return {
        "blob_key": key,
        "mime_type": mime_type,
        "byte_size": len(data),
        "original_name": original_name,
        "storage_uri": storage_uri,
    }


def get(key: str) -> bytes | None:
    if db.IS_PG:
        _pg_ready()
        conn = db.connect("campaigns")
        try:
            row = conn.execute("SELECT data FROM blob_data WHERE blob_key=?", (key,)).fetchone()
        finally:
            conn.close()
        if row is None or row[0] is None:
            return None
        return bytes(row[0])  # psycopg returns bytes/memoryview for BYTEA -> normalise
    path = _path_for(key)
    return path.read_bytes() if path.exists() else None


def get_text(key: str) -> str | None:
    data = get(key)
    return data.decode("utf-8") if data is not None else None


def uri_for(key: str) -> str:
    if db.IS_PG:
        return f"pg://blob/{key}"
    return _path_for(key).resolve().as_uri()


def exists(key: str) -> bool:
    if db.IS_PG:
        _pg_ready()
        conn = db.connect("campaigns")
        try:
            return conn.execute("SELECT 1 FROM blob_data WHERE blob_key=?", (key,)).fetchone() is not None
        finally:
            conn.close()
    return _path_for(key).exists()
