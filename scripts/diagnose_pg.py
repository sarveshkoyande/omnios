"""Diagnose the /api/home 500 against the live Postgres. Read-only except idempotent
schema init. Run locally with the Prisma URL set:

    # PowerShell
    $env:DATABASE_URL = "postgres://...prisma..."
    python scripts/diagnose_pg.py

It exercises each piece of /api/home (and a couple of core store calls) and prints the exact
traceback for whichever one fails, so the real error is visible instead of a bare 500.
"""
import os
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "strategy"))

import db  # noqa: E402

print("DATABASE_URL set:", bool(os.environ.get("DATABASE_URL")))
print("db.IS_PG:", db.IS_PG)
if not db.IS_PG:
    sys.exit("DATABASE_URL is not set (or not a postgres URL) in this shell -- set it first.")


def check(name, fn):
    try:
        result = fn()
        preview = str(result)
        print(f"OK    {name}  ->  {preview[:140]}")
    except Exception:
        print(f"\n=====  FAIL: {name}  =====")
        traceback.print_exc()
        print("=" * (13 + len(name)) + "\n")


# Which KB / store tables actually exist in Postgres?
def list_tables():
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ).fetchall()
        names = [r[0] for r in rows]
        return f"{len(names)} tables: {', '.join(names[:60])}"
    finally:
        conn.close()


check("list public tables", list_tables)

import dashboard  # noqa: E402
import feed  # noqa: E402
import campaign_store  # noqa: E402
import projects  # noqa: E402

check("kb_connect() (documents probe)", lambda: db.kb_connect() is not None)
check("campaign_store.init_db() (creates campaigns schema)", campaign_store.init_db)
check("campaign_store.library_stats()", campaign_store.library_stats)
check("campaign_store.campaign_counts_by_brand()", campaign_store.campaign_counts_by_brand)
check("feed.build_feed()  [/api/home part 2]", feed.build_feed)
check("dashboard.brand_performance()  [/api/home part 1]", dashboard.brand_performance)
check("projects.list_projects()", projects.list_projects)

print("\nDone. Paste everything above (especially any FAIL traceback).")
