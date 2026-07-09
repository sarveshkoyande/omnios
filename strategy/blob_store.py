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

BLOB_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "blobs"


def _key(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_for(key: str) -> pathlib.Path:
    # Shard by the first 2 hex chars to avoid one giant directory.
    return BLOB_DIR / key[:2] / key


def put(data: bytes | str, *, mime_type: str = "application/octet-stream",
        original_name: str = "") -> dict:
    """Store bytes (or a str, encoded utf-8) and return a manifest dict:
    {blob_key, mime_type, byte_size, original_name, storage_uri}. Idempotent -- the same
    content yields the same key and is written at most once."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    key = _key(data)
    path = _path_for(key)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {
        "blob_key": key,
        "mime_type": mime_type,
        "byte_size": len(data),
        "original_name": original_name,
        "storage_uri": path.resolve().as_uri(),
    }


def get(key: str) -> bytes | None:
    path = _path_for(key)
    return path.read_bytes() if path.exists() else None


def get_text(key: str) -> str | None:
    data = get(key)
    return data.decode("utf-8") if data is not None else None


def uri_for(key: str) -> str:
    return _path_for(key).resolve().as_uri()


def exists(key: str) -> bool:
    return _path_for(key).exists()
