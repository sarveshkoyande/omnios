"""DRAFT dual-dialect DB layer (SQLite local / Postgres on Render). NOT YET WIRED IN.

Status: this module is a prepared migration path for moving the writable stores off a
persistent disk (the current production setup) onto a managed Postgres. It is deliberately
NOT imported by any running code, so it cannot affect the live disk-backed deployment. Its
pure SQL-translation helpers are unit-tested at the bottom (`python strategy/db.py`), but
the Postgres query path itself has NOT been exercised against a real Postgres server yet
(the dev machine has no Docker/psql). Verify on a real Postgres before switching stores
over. See POSTGRES_MIGRATION.md for the step-by-step.

Design: keep every store's raw SQL exactly as written for SQLite (`?` placeholders,
`cur.lastrowid`, `INSERT OR IGNORE`) and translate on the way to Postgres, so the diff in
each store is just `sqlite3.connect(PATH)` -> `db.connect("campaigns")`. The SQLite branch
returns a real sqlite3 connection (zero behaviour change); the Postgres branch wraps
psycopg to mimic the small sqlite3 surface the stores use.

Selected by env: DATABASE_URL set to a postgres URL -> Postgres; otherwise SQLite.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import threading
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

# Tables whose surrogate PK is an autoincrement integer `id`. An INSERT into one of these
# gets `RETURNING id` appended on Postgres so `cursor.lastrowid` keeps working. Junction /
# natural-key tables (composite or TEXT PKs) are intentionally excluded.
ID_TABLES = {
    "client", "brand", "indication", "taxonomy_term", "ref_source", "claim",
    "content_module", "content_asset", "campaign", "campaign_version", "campaign_segment",
    "campaign_message", "campaign_channel", "campaign_kpi", "review_record",
    "brand_market_intel", "campaign_award",
    "sync_event",  # orchestration_store: id INTEGER PRIMARY KEY AUTOINCREMENT
}
# NOT id-tables: blob (TEXT pk), blob_data (TEXT pk), claim_reference / module_claim /
# asset_module / entity_tag (composite pk), projects / brand_memory / tab_chat / stub_item /
# external_binding / notification (TEXT or composite pk), and the hcp_360 tables (their
# integer PK is a natural NPI value inserted explicitly, not an autoincrement surrogate).


# --------------------------------------------------------------------- SQL translation ---

def to_pg_sql(sql: str) -> tuple[str, bool]:
    """Translate a SQLite DML/query string to Postgres. Returns (sql, appended_returning_id).

    - `?`               -> `%s`
    - `INSERT OR IGNORE INTO t ...`  -> `INSERT INTO t ... ON CONFLICT DO NOTHING`
    - plain `INSERT INTO <id-table> ...` with no RETURNING/ON CONFLICT -> append `RETURNING id`
      so the caller's `cursor.lastrowid` resolves to the new row id.
    """
    s = sql.replace("?", "%s")
    or_ignore = re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", s, re.IGNORECASE)
    if or_ignore:
        s = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", s, flags=re.IGNORECASE)
        if not re.search(r"\bON\s+CONFLICT\b", s, re.IGNORECASE):
            s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    # `INSERT OR REPLACE` is a SQLite upsert-on-PK. Its only caller (hcp_360's bulk load)
    # always inserts into a table it has just emptied (fresh load, or force=True which
    # DELETEs first), so no conflict ever occurs at runtime and a plain INSERT is faithful.
    # A generic `ON CONFLICT DO UPDATE` is impossible from the SQL text alone -- we don't
    # know the conflict-target columns -- so if a future caller relies on REPLACE overwriting
    # an *existing* row on Postgres, it must add an explicit ON CONFLICT clause itself.
    s = re.sub(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", "INSERT INTO", s, flags=re.IGNORECASE)

    appended = False
    m = re.match(r"\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.IGNORECASE)
    if (m and m.group(1).lower() in ID_TABLES
            and not re.search(r"\bRETURNING\b", s, re.IGNORECASE)
            and not re.search(r"\bON\s+CONFLICT\b", s, re.IGNORECASE)):
        s = s.rstrip().rstrip(";") + " RETURNING id"
        appended = True
    return s, appended


def _translate_pk(match: "re.Match") -> str:
    """Column-aware `<col> INTEGER PRIMARY KEY [AUTOINCREMENT]` translation.

    Only a surrogate column literally named `id` becomes an auto-generated IDENTITY (this
    is exactly the set of columns whose callers read `cursor.lastrowid`; see ID_TABLES). A
    *natural* integer PK -- e.g. hcp_360's `npi_number__c`, whose value is a real NPI number
    inserted explicitly -- must stay a plain integer; making it an IDENTITY would be
    semantically wrong (Postgres would try to own the value). The SQLite-only trailing
    `AUTOINCREMENT` keyword is dropped in either case. Any `REFERENCES ...` tail is outside
    the match and is preserved verbatim."""
    col = match.group(1)
    if col.lower() == "id":
        return f"{col} BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
    return f"{col} BIGINT PRIMARY KEY"


def to_pg_ddl(script: str) -> list[str]:
    """Translate a SQLite DDL script into a list of Postgres statements."""
    out = []
    for raw in _split_statements(script):
        stmt = raw
        if re.match(r"\s*PRAGMA\b", stmt, re.IGNORECASE):
            continue
        stmt = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+INTEGER\s+PRIMARY\s+KEY(?:\s+AUTOINCREMENT)?\b",
                      _translate_pk, stmt, flags=re.IGNORECASE)
        stmt = re.sub(r"\bCREATE\s+VIEW\s+IF\s+NOT\s+EXISTS\b",
                      "CREATE OR REPLACE VIEW", stmt, flags=re.IGNORECASE)
        stmt = re.sub(r"\bBLOB\b", "BYTEA", stmt)  # only the type is uppercase; names are lowercase
        if stmt.strip():
            out.append(stmt.strip())
    return out


def _split_statements(script: str) -> list[str]:
    """Split a DDL script into statements. Strips `--` comments -- whole-line AND inline --
    BEFORE splitting on `;`, because an inline comment can itself contain a `;` (e.g.
    `created_at TEXT NOT NULL  -- ISO-8601 UTC; ORA: TIMESTAMP`), which would otherwise split
    a CREATE TABLE mid-statement and yield a truncated, syntactically invalid fragment. None
    of this schema's statements contain `--` or `;` inside a string literal, so cutting each
    line at its first `--` and then splitting on `;` is safe."""
    stripped = []
    for ln in script.splitlines():
        idx = ln.find("--")
        stripped.append(ln[:idx] if idx != -1 else ln)
    return [s for s in "\n".join(stripped).split(";") if s.strip()]


# --------------------------------------------------------------------- row adapter -------

class Row:
    """A row supporting the union of accesses the stores rely on from sqlite3.Row:
    positional `row[0]`, by-name `row["col"]`, `dict(row)`, and tuple unpacking."""
    __slots__ = ("_cols", "_vals")

    def __init__(self, cols, vals):
        self._cols, self._vals = cols, vals

    def __getitem__(self, k):
        return self._vals[k] if isinstance(k, int) else self._vals[self._cols.index(k)]

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)


def _pg_row_factory(cursor):
    cols = [d.name for d in cursor.description] if cursor.description else []
    def make(values):
        return Row(cols, list(values))
    return make


# --------------------------------------------------------------------- connections -------

class _PgCursor:
    def __init__(self, cur, appended_returning):
        self._cur = cur
        self.lastrowid = None
        if appended_returning:
            try:
                row = cur.fetchone()
                self.lastrowid = row[0] if row else None
            except Exception:  # noqa: BLE001
                self.lastrowid = None

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        # Some callers iterate the cursor directly (`for row in conn.execute(...)`) instead
        # of calling fetchall(); psycopg cursors are iterable, so delegate to the raw cursor
        # (which yields Row via the row_factory). sqlite3 cursors already support this.
        return iter(self._cur)


class _PgConn:
    """Thin wrapper over a psycopg connection exposing the sqlite3 surface the stores use."""

    def __init__(self, raw, pooled=False):
        self._raw = raw
        self._pooled = pooled
        self._returned = False

    def execute(self, sql, params=()):
        sql2, appended = to_pg_sql(sql)
        cur = self._raw.cursor()
        cur.execute(sql2, tuple(params))
        return _PgCursor(cur, appended)

    def executemany(self, sql, seq_of_params):
        sql2, _ = to_pg_sql(sql)
        cur = self._raw.cursor()
        cur.executemany(sql2, [tuple(p) for p in seq_of_params])
        return _PgCursor(cur, False)

    def executescript(self, script):
        for stmt in to_pg_ddl(script):
            with self._raw.cursor() as cur:
                cur.execute(stmt)
        return self

    def commit(self):
        self._raw.commit()

    def rollback(self):
        # Needed so a failed statement (e.g. an ALTER TABLE ADD COLUMN that hits an existing
        # column) doesn't leave the psycopg transaction in the aborted state, which would
        # make every following statement on this connection fail. sqlite3.Connection exposes
        # the same method, so callers can use it dialect-agnostically.
        self._raw.rollback()

    def close(self):
        # On the pooled Postgres path, "closing" returns the connection to the pool for
        # reuse instead of tearing down the (expensive, remote) socket. Idempotent so the
        # __del__ safety net below can't double-return.
        if self._returned:
            return
        self._returned = True
        if self._pooled:
            _put_pooled(self._raw)
        else:
            self._raw.close()

    def __del__(self):
        # Safety net against connection leaks. Many stores do `conn = _conn(); ...; close()`
        # without a try/finally, so an exception between open and close skips close() -- which
        # on a bounded pool would permanently lose that connection and, after a few, drain the
        # pool so every later call blocks until timeout (a full-app hang). Returning the
        # connection when the wrapper is garbage-collected makes a missed close() self-heal.
        if not self._returned:
            try:
                self.close()
            except Exception:  # noqa: BLE001 -- never raise from a finalizer
                pass


# --------------------------------------------------------------------- connection pool ---
# Over a REMOTE Postgres (e.g. Prisma) the stores' "open a connection, run one or two
# statements, close it" pattern -- which is essentially free on a local SQLite file -- is
# pathological: every call pays a TLS + auth handshake, and a low free-tier connection cap is
# quickly exhausted, so the whole app crawls, writes hang, and requests 500 under any
# concurrency. A process-wide pool keeps a small set of warm connections and hands them out
# instead. Created lazily so the SQLite path never imports psycopg_pool. Sized by DB_POOL_MAX
# (default 5) -- lower it if the managed Postgres rejects connections, raise it for more
# concurrency.
_pool = None
_pool_disabled = False
_pool_lock = threading.Lock()


def _get_pool():
    """The process-wide connection pool, or None if pooling is unavailable (psycopg_pool not
    installed -- e.g. a local one-off script). Callers fall back to a direct connection then."""
    global _pool, _pool_disabled
    if _pool_disabled:
        return None
    if _pool is None:
        with _pool_lock:
            if _pool is None and not _pool_disabled:
                try:
                    from psycopg_pool import ConnectionPool  # lazy: only needed on Postgres
                except Exception:  # noqa: BLE001 -- pool extra not installed; use direct conns
                    _pool_disabled = True
                    return None
                _pool = ConnectionPool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=int(os.environ.get("DB_POOL_MAX", "5") or "5"),
                    kwargs={"row_factory": _pg_row_factory},
                    max_lifetime=300,   # recycle every 5 min -- a remote host may drop idle conns
                    max_idle=60,
                    timeout=30,         # wait up to 30s for a free connection, then raise
                    open=False,
                )
                _pool.open()  # fills the pool in the background; getconn() waits as needed
    return _pool


def _put_pooled(raw):
    try:
        _get_pool().putconn(raw)
    except Exception:  # noqa: BLE001 -- returning a connection must never raise into a caller
        try:
            raw.close()
        except Exception:  # noqa: BLE001
            pass


def connect(db_name: str = "campaigns"):
    """Return a connection. SQLite: a real sqlite3 connection to <DATA_DIR>/<db_name>.db
    (unchanged behaviour). Postgres: a pooled psycopg connection to DATABASE_URL (all the
    logical DBs share one Postgres database; table names are already globally distinct).
    `conn.close()` returns the pooled connection for reuse rather than tearing it down."""
    if not IS_PG:
        conn = sqlite3.connect(data_path(f"{db_name}.db"))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    pool = _get_pool()
    if pool is not None:
        return _PgConn(pool.getconn(), pooled=True)
    import psycopg  # fallback when psycopg_pool isn't installed (e.g. a local one-off script)
    return _PgConn(psycopg.connect(DATABASE_URL, row_factory=_pg_row_factory), pooled=False)


def kb_connect():
    """Connection to the read-only knowledge base (`omni_kb`), or None when it isn't
    available. On Postgres the KB tables live in the shared database (loaded once by
    strategy/load_kb_to_pg.py) so this always returns a connection. On SQLite it's the
    data/omni_kb.db file; when that file is absent this returns None so callers degrade to
    empty results exactly as their old `if KB_DB.exists()` guard did (sqlite3.connect would
    otherwise create an empty file with no tables and make every query raise)."""
    if IS_PG:
        conn = connect("omni_kb")
        # Probe that the KB has actually been loaded (strategy/load_kb_to_pg.py). If the
        # tables aren't there yet, return None so every reader degrades to empty results
        # instead of raising a 500 -- this makes the deploy order-independent (the app can
        # ship before the one-time load runs, then light up once the data is present).
        try:
            conn.execute("SELECT 1 FROM documents LIMIT 1").fetchone()
            return conn
        except Exception:  # noqa: BLE001
            conn.rollback()
            conn.close()
            return None
    if not data_path("omni_kb.db").exists():
        return None
    return connect("omni_kb")


# --------------------------------------------------------------------- self-test ---------

def _selftest():
    # placeholders
    s, app = to_pg_sql("SELECT id FROM brand WHERE name=?")
    assert s == "SELECT id FROM brand WHERE name=%s" and not app, s
    # plain insert into an id-table -> RETURNING id appended
    s, app = to_pg_sql("INSERT INTO brand (name) VALUES (?)")
    assert s == "INSERT INTO brand (name) VALUES (%s) RETURNING id" and app, s
    # insert into a non-id (junction) table -> no RETURNING
    s, app = to_pg_sql("INSERT INTO claim_reference (claim_id, ref_id, locator) VALUES (?,?,?)")
    assert "RETURNING" not in s and not app, s
    # OR IGNORE -> ON CONFLICT DO NOTHING, and no RETURNING even on an id-table
    s, app = to_pg_sql("INSERT OR IGNORE INTO client (name) VALUES (?)")
    assert s == "INSERT INTO client (name) VALUES (%s) ON CONFLICT DO NOTHING" and not app, s
    s, _ = to_pg_sql("INSERT OR IGNORE INTO blob (blob_key, mime_type) VALUES (?,?)")
    assert s.endswith("ON CONFLICT DO NOTHING"), s
    # existing ON CONFLICT DO UPDATE is left intact (identical syntax in both dialects)
    s, app = to_pg_sql("INSERT INTO brand_memory (brand_key) VALUES (?) ON CONFLICT(brand_key) DO UPDATE SET brand_key=excluded.brand_key")
    assert "RETURNING" not in s and "ON CONFLICT(brand_key)" in s and not app, s
    # sync_event is a registered id-table (orchestration) -> RETURNING id appended
    s, app = to_pg_sql("INSERT INTO sync_event (project_id, created_at) VALUES (?,?)")
    assert s.endswith("RETURNING id") and app, s
    # INSERT OR REPLACE (hcp_360 bulk load) -> plain INSERT; non-id table, no RETURNING
    s, app = to_pg_sql("INSERT OR REPLACE INTO tbl_trx (a, b) VALUES (?,?)")
    assert s == "INSERT INTO tbl_trx (a, b) VALUES (%s,%s)" and not app, s
    # DDL translation
    ddl = to_pg_ddl("PRAGMA foreign_keys = ON;\nCREATE TABLE IF NOT EXISTS brand (id INTEGER PRIMARY KEY, name TEXT);\n"
                    "CREATE VIEW IF NOT EXISTS v AS SELECT 1;\nCREATE TABLE blob_data (blob_key TEXT PRIMARY KEY, data BLOB);")
    assert not any("PRAGMA" in d for d in ddl), ddl
    assert any("GENERATED BY DEFAULT AS IDENTITY" in d for d in ddl), ddl
    assert any(d.startswith("CREATE OR REPLACE VIEW") for d in ddl), ddl
    assert any("BYTEA" in d and "blob_key" in d for d in ddl), ddl  # type upcased, name preserved
    # AUTOINCREMENT (orchestration sync_event) -> IDENTITY, keyword dropped
    ddl = to_pg_ddl("CREATE TABLE sync_event (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT);")
    assert not any("AUTOINCREMENT" in d for d in ddl), ddl
    assert any("GENERATED BY DEFAULT AS IDENTITY" in d for d in ddl), ddl
    # natural integer PK (hcp_360 NPI) -> plain BIGINT, NOT an identity; REFERENCES preserved
    ddl = to_pg_ddl("CREATE TABLE t (npi_number__c INTEGER PRIMARY KEY REFERENCES d(npi_number__c), x TEXT);")
    assert not any("GENERATED BY DEFAULT AS IDENTITY" in d for d in ddl), ddl
    assert any("npi_number__c BIGINT PRIMARY KEY" in d and "REFERENCES d(npi_number__c)" in d for d in ddl), ddl
    # a `;` INSIDE an inline comment must not split the statement (real bug from the blob table)
    ddl = to_pg_ddl("CREATE TABLE blob (\n  a TEXT,\n  created_at TEXT NOT NULL   -- ISO-8601 UTC; ORA: TIMESTAMP\n);")
    assert len(ddl) == 1 and ddl[0].count("(") == ddl[0].count(")") == 1, ddl  # one balanced statement
    assert "ORA" not in ddl[0] and "ISO-8601" not in ddl[0], ddl  # inline comment stripped
    # Row adapter parity with sqlite3.Row expectations
    r = Row(["id", "name"], [7, "Nubeqa"])
    assert r[0] == 7 and r["name"] == "Nubeqa" and dict(r) == {"id": 7, "name": "Nubeqa"}
    a, b = r
    assert (a, b) == (7, "Nubeqa")
    print("db.py self-test passed (SQL/DDL translation + Row adapter). IS_PG =", IS_PG)


if __name__ == "__main__":
    _selftest()
