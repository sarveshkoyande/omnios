"""Reset the brand-plan update flow's generated test state (kit_drafts.db and the
kit-update rows in tab_chat.db) so a manual test run can start from scratch.

CLI-only, deliberately -- there is no route in app/server.py and nothing in the cockpit
UI calls this. It is a developer tool for repeated manual ingestion testing (see
docs/plans/2026-09-21-1223-feat-detailed-persona-generation-plan.md), not a
product feature.

Never touches config/brand_kits.json or anything else under config/ -- only
strategy.db, argparse, and sys are imported. "Brand data" here means the drafts and
chat history this flow generated for a brand, never the committed brand kit itself.

Usage:
    python scripts/reset_test_data.py              # wipe every brand's test state
    python scripts/reset_test_data.py --brand Cardiovex
    python scripts/reset_test_data.py --yes         # skip the confirmation prompt
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "strategy"))
import db  # noqa: E402


def _count(conn, table: str, where: str = "", params: tuple = ()) -> int:
    sql = f"SELECT COUNT(*) AS n FROM {table}"
    if where:
        sql += f" WHERE {where}"
    try:
        return conn.execute(sql, params).fetchone()["n"]
    except Exception:  # noqa: BLE001 -- table doesn't exist yet on a fresh checkout
        return 0


def _delete(conn, table: str, where: str = "", params: tuple = ()) -> None:
    sql = f"DELETE FROM {table}"
    if where:
        sql += f" WHERE {where}"
    try:
        conn.execute(sql, params)
        conn.commit()
    except Exception:  # noqa: BLE001 -- table doesn't exist yet on a fresh checkout
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--brand", default=None, help="Scope the wipe to one brand's drafts and chat history only.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    drafts_conn = db.connect("kit_drafts")
    chat_conn = db.connect("tab_chat")

    if args.brand:
        drafts_where, drafts_params = "brand = ?", (args.brand,)
        chat_where, chat_params = "project_id = ? AND stage_id LIKE 'kit:%'", (args.brand,)
        scope_label = f"brand '{args.brand}'"
    else:
        drafts_where, drafts_params = "", ()
        chat_where, chat_params = "stage_id LIKE 'kit:%'", ()
        scope_label = "every brand"

    drafts_n = _count(drafts_conn, "drafts", drafts_where, drafts_params)
    chat_n = _count(chat_conn, "messages", chat_where, chat_params)

    print(f"About to wipe kit-update test state for {scope_label}:")
    print(f"  kit_drafts.db: {drafts_n} draft row(s)")
    print(f"  tab_chat.db:   {chat_n} kit-update chat message(s)")
    print("config/brand_kits.json and every other committed config file are never touched.")

    if not args.yes:
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("Cancelled -- nothing was deleted.")
            drafts_conn.close()
            chat_conn.close()
            return

    _delete(drafts_conn, "drafts", drafts_where, drafts_params)
    _delete(chat_conn, "messages", chat_where, chat_params)
    drafts_conn.close()
    chat_conn.close()

    print(f"Done. Cleared {drafts_n} draft row(s) and {chat_n} chat message(s) for {scope_label}.")


if __name__ == "__main__":
    main()
