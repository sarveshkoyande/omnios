"""Local stand-in for Salesforce Data Cloud -- used when the DC_* settings aren't configured.

Builds a SQLite copy of the HCP segmentation data model object from the committed snapshot
(config/segmentation_dataset.json): the same table name and columns, filled with SYNTHETIC rows
whose values come from the snapshot's real value lists and ranges (deterministic seed). Segments
"created" here live in a local table, so the whole Segmentation Planner flow -- SQL, live count,
duplicate check, create, publish -- runs end to end without Salesforce. Everything is labelled as
local/synthetic in the UI; configure DC_* to use the real org.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import sys
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paths import data_path  # noqa: E402

from .dataset import DMO, load_snapshot  # noqa: E402

ROWS = 20_000
_LOCK = threading.Lock()
_DB: sqlite3.Connection | None = None

_DATE_COLS_HINT = "date"   # column names containing this hold YYYY-MM-DD values in the snapshot


def _conn() -> sqlite3.Connection:
    global _DB
    with _LOCK:
        if _DB is None:
            path = data_path("segmentation_local.db")
            path.parent.mkdir(parents=True, exist_ok=True)
            _DB = sqlite3.connect(str(path), check_same_thread=False)
            _DB.row_factory = sqlite3.Row
            _DB.execute("CREATE TABLE IF NOT EXISTS local_segments (id TEXT PRIMARY KEY, display_name TEXT, "
                        "developer_name TEXT, description TEXT, sql TEXT, published INTEGER, created_at TEXT)")
            if not _DB.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (DMO,)).fetchone():
                _generate(_DB)
        return _DB


def _generate(db: sqlite3.Connection) -> None:
    """Fill the DMO table with synthetic rows drawn from the snapshot's real values."""
    snap = load_snapshot()
    cols: dict = snap.get("columns") or {}
    rng = random.Random("omni-segmentation-local")
    names = list(cols)
    # hcp_id__c / KQ_hcp_id__c are the real DMO's key columns (not in the profiled snapshot).
    db.execute(f"CREATE TABLE {DMO} (hcp_id__c TEXT, KQ_hcp_id__c TEXT, " + ", ".join(f"{c} {'REAL' if _numeric(cols[c]) else 'TEXT'}" for c in names) + ")")
    rows = []
    for i in range(ROWS):
        row = [f"HCP{i:06d}", f"HCP{i:06d}"]
        for c in names:
            spec = cols[c]
            if spec.get("values"):
                vals = spec["values"]
                # earlier values are more frequent in the snapshot (ordered by frequency)
                weights = [1 / (k + 1) for k in range(len(vals))]
                row.append(rng.choices(vals, weights=weights)[0])
            elif spec.get("range"):
                lo, hi = spec["range"]
                if _DATE_COLS_HINT in c:
                    d0, d1 = date.fromisoformat(lo), date.fromisoformat(hi)
                    row.append((d0 + timedelta(days=rng.randint(0, max(0, (d1 - d0).days)))).isoformat())
                elif "." in lo or "." in hi:
                    row.append(round(rng.uniform(float(lo), float(hi)), 3))
                else:
                    row.append(rng.randint(int(lo), int(hi)))
            else:
                row.append(None)
        rows.append(row)
    db.executemany(f"INSERT INTO {DMO} VALUES ({', '.join('?' * (len(names) + 2))})", rows)
    db.commit()


def _numeric(spec: dict) -> bool:
    r = spec.get("range")
    if not r:
        return False
    try:
        float(r[0]); float(r[1])
        return True
    except ValueError:
        return False


# Data Cloud SQL is ANSI/Trino-like; translate the few date idioms SQLite lacks. This rewrites the
# generated SQL's syntax, not user text (rule R1 is about reading what people type).
_INTERVAL = re.compile(r"CURRENT_DATE\s*([-+])\s*INTERVAL\s*'(\d+)'\s*(DAY|MONTH|YEAR)S?", re.IGNORECASE)


def _to_sqlite(sql: str) -> str:
    s = _INTERVAL.sub(lambda m: f"date('now', '{m.group(1)}{m.group(2)} {m.group(3).lower()}')", sql)
    s = re.sub(r"\bCURRENT_DATE\b", "date('now')", s, flags=re.IGNORECASE)
    s = re.sub(r"\bILIKE\b", "LIKE", s, flags=re.IGNORECASE)
    return s


def query(sql: str) -> list[dict]:
    from .datacloud import DataCloudError
    try:
        cur = _conn().execute(_to_sqlite(sql))
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as exc:
        raise DataCloudError(f"Local dataset query failed: {exc}", 400, str(exc)) from exc


def segment_names() -> list[str]:
    return [r["display_name"] for r in _conn().execute("SELECT display_name FROM local_segments").fetchall()]


def create_segment(payload: dict) -> str:
    seg_id = "LOCAL-" + uuid.uuid4().hex[:10].upper()
    sql = ((((payload.get("includeDbt") or {}).get("models") or {}).get("models") or [{}])[0]).get("sql", "")
    db = _conn()
    db.execute("INSERT INTO local_segments VALUES (?,?,?,?,?,?,?)",
               (seg_id, payload.get("displayName"), payload.get("developerName"), payload.get("description"), sql, 0,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    db.commit()
    return seg_id


def publish(segment_id: str) -> None:
    db = _conn()
    db.execute("UPDATE local_segments SET published=1 WHERE id=?", (segment_id,))
    db.commit()


def segment_url(segment_id: str) -> str:
    return f"/api/segmentation-planner/local-segments/{segment_id}"


def get_segment(segment_id: str) -> dict | None:
    r = _conn().execute("SELECT * FROM local_segments WHERE id=?", (segment_id,)).fetchone()
    if not r:
        return None
    out = dict(r)
    try:
        out["count"] = (query(f"SELECT count(*) AS cnt FROM ({out['sql']}) seg") or [{}])[0].get("cnt")
    except Exception:  # noqa: BLE001
        out["count"] = None
    return out


def info() -> dict:
    return {"mode": "local", "rows": ROWS, "table": DMO,
            "note": "Data Cloud isn't connected: segments are sized and created against a generated local copy of the HCP table (synthetic rows, real value lists)."}
