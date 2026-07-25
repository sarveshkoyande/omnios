"""
Per-brand memory of previously captured chat details (indication, lifecycle stage,
budget, CX-maturity notes) so a returning user planning the same brand again is
asked whether those details still hold, instead of being re-interrogated from
scratch. Most-recent capture wins; conversation.py reads/writes this.

Stored in a small local SQLite table (data/brand_memory.db) -- same "never commit
project data" treatment as the other data/*.db stores (see .gitignore).
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = data_path("brand_memory.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS brand_memory (
    brand_key TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    indication TEXT,
    lifecycle_key TEXT,
    budget REAL,
    maturity_notes TEXT,
    updated_at TEXT NOT NULL
);
"""


def _conn():
    conn = db.connect("brand_memory")
    conn.execute(_SCHEMA)
    return conn


def save_brand_memory(brand: str, slots: dict) -> None:
    """Persist the captured slots for `brand` as the new 'last known' details.
    Skipped when nothing worth remembering was actually captured."""
    if not brand:
        return
    if not (slots.get("indication") or slots.get("lifecycle_key") or slots.get("budget") or slots.get("maturity_notes")):
        return
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO brand_memory (brand_key, brand, indication, lifecycle_key, budget, maturity_notes, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(brand_key) DO UPDATE SET brand=excluded.brand, indication=excluded.indication, "
            "lifecycle_key=excluded.lifecycle_key, budget=excluded.budget, maturity_notes=excluded.maturity_notes, "
            "updated_at=excluded.updated_at",
            (
                brand.strip().lower(), brand,
                slots.get("indication") or "", slots.get("lifecycle_key") or "",
                float(slots.get("budget") or 0.0), (slots.get("maturity_notes") or "")[-2000:],
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_brand_memory(brand: str) -> dict | None:
    """The last captured details for `brand`, or None if we've never planned for it
    (or nothing worth recalling was captured last time)."""
    if not brand:
        return None
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT indication, lifecycle_key, budget, maturity_notes, updated_at "
            "FROM brand_memory WHERE brand_key = ?",
            (brand.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    indication, lifecycle_key, budget, maturity_notes, updated_at = row
    if not (indication or lifecycle_key or budget or maturity_notes):
        return None
    return {
        "indication": indication or "",
        "lifecycle_key": lifecycle_key or "",
        "budget": budget or 0.0,
        "maturity_notes": maturity_notes or "",
        "updated_at": updated_at,
    }
