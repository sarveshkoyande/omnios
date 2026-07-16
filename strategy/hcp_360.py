"""HCP 360 data store: demographics, channel affinity, content affinity, TRx therapeutic
history, day/time preferences and target-list/writer status for synthetic HCPs, joined by
NPI. Loaded from the committed JSON seed files under config/hcp_360/ into hcp_360.db
(db/hcp_360_schema.sql, SQLite via strategy/paths.py -- same DATA_DIR every other store
uses).

The six JSON files and the schema mirror an Oracle 19c package designed for the same
reference data (see this conversation's plsql/ deliverables) -- table and column names
match 1:1, so this is that dataset made queryable in the app rather than sitting as dead
static files.

`load_hcp_360()` (idempotent -- skips if already loaded, pass force=True to reload) reads
the JSON and bulk-inserts each table. `get_hcp()`, `list_hcps()` and `stats()` are the read
API the rest of the app should use instead of touching sqlite3 directly.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config" / "hcp_360"
SCHEMA_PATH = BASE_DIR / "db" / "hcp_360_schema.sql"
DB_PATH = data_path("hcp_360.db")

# Load order matters: demographic first -- every other table's npi column REFERENCES it.
_FILES = [
    ("pfizer_demographic_data__dlm", "pfizer_demographic_data__dlm.json"),
    ("global_channel_affinity_and_preference", "global_channel_affinity_and_preference.json"),
    ("pf_global_content_affinity_score_data", "pf_global_content_affinity_score_data.json"),
    ("tbl_trx_therapeutic_data__dlm", "tbl_trx_therapeutic_data__dlm.json"),
    ("global_day_time_preference_data", "global_day_time_preference_data.json"),
    ("tbl_pfizer_tl_data__dlm", "tbl_pfizer_tl_data__dlm.json"),
]


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if missing (idempotent)."""
    conn = _conn()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _load_table(conn: sqlite3.Connection, json_path: pathlib.Path, table: str) -> int:
    if not json_path.exists():
        return 0
    rows = json.loads(json_path.read_text(encoding="utf-8"))
    if not rows:
        return 0
    cols = list(rows[0].keys())
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
    conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
    return len(rows)


def load_hcp_360(force: bool = False) -> dict:
    """Bulk-load the six JSON files into hcp_360.db. Idempotent: no-ops if the
    demographic table already has rows, unless force=True (which deletes all six tables,
    children first, then reloads)."""
    init_db()
    conn = _conn()
    try:
        already = conn.execute(
            "SELECT COUNT(*) n FROM pfizer_demographic_data__dlm"
        ).fetchone()["n"]
        if already and not force:
            return {"loaded": False, "reason": "already loaded", "npi_count": already}
        if force:
            for table, _ in reversed(_FILES):
                conn.execute(f"DELETE FROM {table}")
        counts = {}
        for table, filename in _FILES:
            counts[table] = _load_table(conn, CONFIG_DIR / filename, table)
        conn.commit()
        return {"loaded": True, "counts": counts}
    finally:
        conn.close()


# --------------------------------------------------------------------- read API -------

def get_hcp(npi: int) -> dict | None:
    """A single HCP's full 360 view: demographic fields at the top level, plus nested
    channel_affinity, content_affinity, day_time_preference, writer_status and a trx list.
    Returns None if the NPI isn't found."""
    conn = _conn()
    try:
        d = conn.execute(
            "SELECT * FROM pfizer_demographic_data__dlm WHERE npi_number__c=?", (npi,)
        ).fetchone()
        if not d:
            return None
        out = dict(d)
        c = conn.execute(
            "SELECT * FROM global_channel_affinity_and_preference WHERE npi_number__c=?", (npi,)
        ).fetchone()
        out["channel_affinity"] = dict(c) if c else None
        k = conn.execute(
            "SELECT * FROM pf_global_content_affinity_score_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["content_affinity"] = dict(k) if k else None
        dt = conn.execute(
            "SELECT * FROM global_day_time_preference_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["day_time_preference"] = dict(dt) if dt else None
        tl = conn.execute(
            "SELECT * FROM tbl_pfizer_tl_data__dlm WHERE npi_id__c=?", (npi,)
        ).fetchone()
        out["writer_status"] = dict(tl) if tl else None
        trx_rows = conn.execute(
            "SELECT * FROM tbl_trx_therapeutic_data__dlm WHERE npi_number__c=? "
            "ORDER BY trx_count__c DESC",
            (npi,),
        ).fetchall()
        out["trx"] = [dict(r) for r in trx_rows]
        return out
    finally:
        conn.close()


def list_hcps(specialty: str | None = None, state: str | None = None,
              brand_writer: str | None = None, limit: int = 50) -> list[dict]:
    """Filtered roster (demographic summary rows only -- call get_hcp() for the full
    record). brand_writer filters to HCPs whose TL brand__c matches (e.g. 'Xalkori')."""
    conn = _conn()
    try:
        sql = ("SELECT npi_number__c, first_name__c, last_name__c, "
               "primary_specialty_description__c, state_code__c, city__c "
               "FROM pfizer_demographic_data__dlm WHERE 1=1")
        params: list = []
        if specialty:
            sql += " AND primary_specialty_description__c = ?"
            params.append(specialty)
        if state:
            sql += " AND state_code__c = ?"
            params.append(state)
        if brand_writer:
            sql += (" AND npi_number__c IN "
                     "(SELECT npi_id__c FROM tbl_pfizer_tl_data__dlm WHERE brand__c = ?)")
            params.append(brand_writer)
        sql += " ORDER BY npi_number__c LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def stats() -> dict:
    """Row counts per table -- a quick health check / dashboard rollup."""
    conn = _conn()
    try:
        return {table: conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
                for table, _ in _FILES}
    finally:
        conn.close()


if __name__ == "__main__":
    print(load_hcp_360())
    print(stats())
    s = list_hcps(limit=3)
    print(s)
    if s:
        print(get_hcp(s[0]["npi_number__c"]))
