"""One-time loader: copy the read-only knowledge base (omni_kb.db, SQLite) into Postgres.

Why this exists
---------------
The KB grew to ~170MB, which is too large for a normal git blob (GitHub's hard limit is
100MB) and broke when shipped via Git LFS (the host didn't pull the LFS object). Instead of
shipping the file, the KB now lives in the same managed Postgres the other stores use, and
the four KB readers (strategy/dashboard.py, feed.py, engine.py, app/server.py's pharma-intel
block) read it through strategy/db.py's dual-dialect layer. This script is what puts the data
there. See POSTGRES_MIGRATION.md.

Usage (run locally, where the real omni_kb.db exists, against the Prisma Postgres URL):

    DATABASE_URL=postgres://...  python strategy/load_kb_to_pg.py
    DATABASE_URL=postgres://...  python strategy/load_kb_to_pg.py --slim      # skip unused giants
    DATABASE_URL=postgres://...  python strategy/load_kb_to_pg.py --exclude drugs_fda_submission,sec_filing
    DATABASE_URL=postgres://...  python strategy/load_kb_to_pg.py --source path/to/omni_kb.db

It is idempotent: it drops each KB object and recreates it, so re-running reloads cleanly.
It is resilient: a failure on one table/index/view is reported and skipped, not fatal, so a
single problem object can't abort the whole load -- read the summary at the end.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import db  # noqa: E402
from paths import data_path  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Large tables that no app query or app-used view references -- droppable if the Postgres
# free tier is tight (--slim). Verified against the KB readers + the 35 views' dependencies.
SLIM_EXCLUDE = {
    "drugs_fda_submission", "drugs_fda_application_doc", "drugs_fda_product",
    "orange_book_product", "orange_book_patent", "sec_filing", "ema_medicine_document",
}
BATCH = 5000


# --------------------------------------------------------------------- translation ------

def _translate_group_concat(sql: str) -> str:
    """SQLite GROUP_CONCAT(DISTINCT? expr) -> Postgres string_agg(DISTINCT? (expr)::text, ',').
    The KB's group_concat calls contain no nested parens, so a non-greedy match to the first
    ')' captures the whole argument (including a parenthesis-free CASE expression)."""
    def repl(m: "re.Match") -> str:
        distinct = m.group(1) or ""
        expr = m.group(2).strip()
        return f"string_agg({distinct}({expr})::text, ',')"
    return re.sub(r"GROUP_CONCAT\s*\(\s*(DISTINCT\s+)?(.*?)\)", repl, sql, flags=re.IGNORECASE)


def _translate_round(sql: str) -> str:
    """ROUND(expr, n) -> ROUND((expr)::numeric, n). Postgres has no round(double precision,
    int) (only round(numeric, int)); a SUM/AVG of a REAL column is double precision, so the
    two-arg ROUND in the CMS open-payments views fails without a cast. Balanced-paren aware
    so a nested SUM(COALESCE(...)) argument is handled correctly."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        is_word = sql[i - 1].isalnum() or sql[i - 1] == "_" if i else False
        if sql[i:i + 5].lower() == "round" and not is_word:
            j = i + 5
            while j < n and sql[j].isspace():
                j += 1
            if j < n and sql[j] == "(":                    # find the matching close paren
                depth, k = 0, j
                while k < n:
                    depth += (sql[k] == "(") - (sql[k] == ")")
                    if depth == 0:
                        break
                    k += 1
                inner = sql[j + 1:k]
                d, comma = 0, -1                            # last top-level comma splits (expr, n)
                for p, ch in enumerate(inner):
                    d += (ch == "(") - (ch == ")")
                    if ch == "," and d == 0:
                        comma = p
                if comma != -1:
                    arg1, rest = inner[:comma].strip(), inner[comma:]
                    out.append(f"ROUND(({arg1})::numeric{rest})")
                    i = k + 1
                    continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def translate(sql: str, *, is_view: bool) -> str:
    """Translate one SQLite CREATE statement to Postgres. Reuses db.to_pg_ddl for the shared
    rules (INTEGER PRIMARY KEY -> IDENTITY / natural BIGINT, BLOB -> BYTEA, PRAGMA strip),
    then applies KB-specific fixes: view function differences, DATETIME, WITHOUT ROWID."""
    if is_view:
        sql = re.sub(r"\binstr\s*\(", "strpos(", sql, flags=re.IGNORECASE)  # same arg order/semantics
        sql = _translate_group_concat(sql)
        sql = _translate_round(sql)
    stmts = db.to_pg_ddl(sql) or [sql]
    out = []
    for s in stmts:
        s = re.sub(r"\bDATETIME\b", "TIMESTAMP", s, flags=re.IGNORECASE)  # not a Postgres type
        s = re.sub(r"\bWITHOUT\s+ROWID\b", "", s, flags=re.IGNORECASE)     # SQLite-only clause
        out.append(s.strip())
    return ";\n".join(out)


# --------------------------------------------------------------------- loader -----------

def _objects(src: sqlite3.Connection, kind: str) -> list[tuple[str, str]]:
    rows = src.execute(
        "SELECT name, sql FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%' "
        "AND sql IS NOT NULL ORDER BY name", (kind,)).fetchall()
    return [(n, s) for n, s in rows]


def _copy_table_data(src: sqlite3.Connection, pg, table: str) -> int:
    cols = [r[1] for r in src.execute(f'PRAGMA table_info("{table}")').fetchall()]
    if not cols:
        return 0
    qcols = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert = f'INSERT INTO "{table}" ({qcols}) VALUES ({placeholders})'
    cur = src.execute(f'SELECT {qcols} FROM "{table}"')
    total = 0
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        pg.executemany(insert, [tuple(r) for r in rows])
        total += len(rows)
    pg.commit()
    return total


def load(source: pathlib.Path, exclude: set[str], views_only: bool = False) -> None:
    if not db.IS_PG:
        sys.exit("DATABASE_URL is not set to a postgres:// URL -- nothing to load into. Aborting.")
    if not source.exists():
        sys.exit(f"Source KB not found: {source}")

    src = sqlite3.connect(source)
    pg = db.connect()  # shared Postgres database (db_name is ignored on the PG branch)

    tables = [(n, s) for n, s in _objects(src, "table") if n not in exclude]
    indexes = _objects(src, "index")
    views = _objects(src, "view")
    excluded = sorted(exclude)
    print(f"source={source}  {'VIEWS-ONLY  ' if views_only else ''}"
          f"tables={len(tables)}  indexes={len(indexes)}  views={len(views)}"
          + (f"  excluded={excluded}" if excluded else ""))

    failures: list[str] = []
    view_errors: dict[str, str] = {}

    # Always drop existing views first (they depend on tables). In views-only mode we stop
    # there and go straight to recreating them (fast, no data reload); a full run also
    # drops + rebuilds the tables, data and indexes.
    for n, _ in views:
        try:
            pg.execute(f'DROP VIEW IF EXISTS "{n}" CASCADE'); pg.commit()
        except Exception:  # noqa: BLE001
            pg.rollback()

    if not views_only:
        for n, _ in tables:
            try:
                pg.execute(f'DROP TABLE IF EXISTS "{n}" CASCADE'); pg.commit()
            except Exception:  # noqa: BLE001
                pg.rollback()

        # Create tables + copy data.
        for n, sql in tables:
            try:
                pg.execute(translate(sql, is_view=False)); pg.commit()
            except Exception as e:  # noqa: BLE001
                pg.rollback(); failures.append(f"CREATE TABLE {n}: {e}"); print(f"  ! table {n}: {e}"); continue
            try:
                rows = _copy_table_data(src, pg, n)
                print(f"  table {n}: {rows} rows")
            except Exception as e:  # noqa: BLE001
                pg.rollback(); failures.append(f"DATA {n}: {e}"); print(f"  ! data {n}: {e}")

        # Indexes (best-effort; skip-on-error).
        idx_ok = 0
        for n, sql in indexes:
            try:
                pg.execute(translate(sql, is_view=False)); pg.commit(); idx_ok += 1
            except Exception as e:  # noqa: BLE001
                pg.rollback(); failures.append(f"INDEX {n}: {e}")
        print(f"  indexes created: {idx_ok}/{len(indexes)}")

    # Views, retry-until-stable so view-on-view dependencies resolve regardless of order.
    pending = list(views)
    while pending:
        made_progress = False
        still: list[tuple[str, str]] = []
        for n, sql in pending:
            try:
                pg.execute(translate(sql, is_view=True)); pg.commit()
                made_progress = True
            except Exception as e:  # noqa: BLE001
                pg.rollback(); still.append((n, sql)); view_errors[n] = str(e)
        if not made_progress:
            for n, sql in still:
                failures.append(f"VIEW {n}: {view_errors.get(n, 'could not create')}")
                print(f"  ! view {n}: {view_errors.get(n, '')}")
            break
        pending = still
    print(f"  views created: {len(views) - len(pending)}/{len(views)}")

    src.close(); pg.close()

    print("\n=== summary ===")
    if failures:
        print(f"{len(failures)} object(s) failed (app still works if these aren't app-used):")
        for f in failures:
            print("  -", f)
    else:
        print("all KB objects loaded with no failures.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Load omni_kb.db (SQLite) into Postgres.")
    ap.add_argument("--source", default=str(ROOT / "assets" / "seed" / "omni_kb.db"),
                    help="path to the SQLite KB (default: assets/seed/omni_kb.db)")
    ap.add_argument("--exclude", default="", help="comma-separated table names to skip")
    ap.add_argument("--slim", action="store_true",
                    help="skip the large tables no app query/view uses (fits a smaller free tier)")
    ap.add_argument("--views-only", action="store_true",
                    help="only drop + recreate the views (fast; leaves loaded table data untouched)")
    args = ap.parse_args()
    exclude = {t.strip() for t in args.exclude.split(",") if t.strip()}
    if args.slim:
        exclude |= SLIM_EXCLUDE
    load(pathlib.Path(args.source), exclude, views_only=args.views_only)


if __name__ == "__main__":
    main()
