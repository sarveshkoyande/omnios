"""Reset generated brand test state so a manual test run can start from scratch.

`--brand X` clears that brand's Agentic Brand Journey rows (every table in
brand_journey.db that has a `brand` column, matched case-insensitively).
`--purge-kit-update` clears the retired guided update flow's leftovers once (plan
docs/plans/2026-09-24-0629-feat-agentic-brand-journey-plan.md KTD8): every row in
kit_drafts.db and every `kit:`-prefixed chat row in tab_chat.db.

CLI-only, deliberately -- there is no route in app/server.py and nothing in the cockpit
UI calls this. Never touches config/brand_kits.json or anything else under config/ --
only strategy.db is imported. "Brand data" here means state the app generated for a
brand, never the committed brand kit itself.

Usage:
    python scripts/reset_test_data.py --brand Cardiovex
    python scripts/reset_test_data.py --purge-kit-update
    python scripts/reset_test_data.py --brand Cardiovex --yes   # skip the prompt
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "strategy"))
import db  # noqa: E402


def _brand_tables(conn) -> list[str]:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return [t for t in tables
            if any(c[1] == "brand" for c in conn.execute(f'PRAGMA table_info("{t}")'))]


def _journey_counts(conn, brand: str) -> dict[str, int]:
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE lower(brand) = lower(?)',
                            (brand,)).fetchone()[0]
            for t in _brand_tables(conn)}


_JOURNEY_FLOWS = ("FROM flow WHERE origin = 'journey' AND campaign_id IN (SELECT c.id FROM campaign c "
                  "JOIN brand b ON b.id = c.brand_id WHERE lower(b.kit_key) = lower(?))")


def clear_brand_journey(brand: str, dry_run: bool = False) -> dict[str, int]:
    """Delete (or with dry_run, only count) `brand`'s rows in brand_journey.db, and the
    flows its Journey built in campaigns.db (hierarchy R19; other campaigns and flows stay).
    Returns {table: rows}."""
    conn = db.connect("brand_journey")
    try:
        counts = _journey_counts(conn, brand)
        if not dry_run:
            for t in counts:
                conn.execute(f'DELETE FROM "{t}" WHERE lower(brand) = lower(?)', (brand,))
            conn.commit()
    finally:
        conn.close()
    camp = db.connect("campaigns")
    try:
        try:
            counts["campaigns.flow (journey)"] = camp.execute(f"SELECT COUNT(*) {_JOURNEY_FLOWS}", (brand,)).fetchone()[0]
        except Exception:  # noqa: BLE001 -- no hierarchy tables yet
            return counts
        if not dry_run and counts["campaigns.flow (journey)"]:
            camp.execute(f"DELETE {_JOURNEY_FLOWS}", (brand,))
            # A flows-only campaign left with no flows reads draft again.
            camp.execute("UPDATE campaign SET status = 'draft' WHERE project_id IS NULL AND status <> 'closed' "
                         "AND NOT EXISTS (SELECT 1 FROM flow WHERE flow.campaign_id = campaign.id)")
            camp.commit()
        return counts
    finally:
        camp.close()


def _count_or_zero(conn, sql: str) -> int:
    try:
        return conn.execute(sql).fetchone()[0]
    except Exception:  # noqa: BLE001 -- table doesn't exist on a fresh checkout
        return 0


def purge_kit_update(dry_run: bool = False) -> dict[str, int]:
    """Delete (or count) all retired guided-update drafts and `kit:` chat rows."""
    drafts = db.connect("kit_drafts")
    chat = db.connect("tab_chat")
    try:
        counts = {
            "kit_drafts.drafts": _count_or_zero(drafts, "SELECT COUNT(*) FROM drafts"),
            "tab_chat.messages (kit:)": _count_or_zero(
                chat, "SELECT COUNT(*) FROM messages WHERE stage_id LIKE 'kit:%'"),
        }
        if not dry_run:
            if counts["kit_drafts.drafts"]:
                drafts.execute("DELETE FROM drafts")
                drafts.commit()
            if counts["tab_chat.messages (kit:)"]:
                chat.execute("DELETE FROM messages WHERE stage_id LIKE 'kit:%'")
                chat.commit()
        return counts
    finally:
        drafts.close()
        chat.close()


def _report(label: str, counts: dict[str, int]) -> None:
    print(f"  {label}:")
    for t, n in counts.items():
        print(f"    {t}: {n} row(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--brand", default=None, help="Clear this brand's journey rows.")
    parser.add_argument("--purge-kit-update", action="store_true",
                        help="Clear all retired kit-update drafts and kit: chat rows.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()
    if not args.brand and not args.purge_kit_update:
        parser.error("pass --brand X and/or --purge-kit-update")

    print("About to delete:")
    if args.brand:
        _report(f"journey rows for brand '{args.brand}'", clear_brand_journey(args.brand, dry_run=True))
    if args.purge_kit_update:
        _report("retired kit-update state", purge_kit_update(dry_run=True))
    print("config/brand_kits.json and every other committed config file are never touched.")

    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        print("Cancelled -- nothing was deleted.")
        return

    print("Done. Cleared:")
    if args.brand:
        _report(f"journey rows for brand '{args.brand}'", clear_brand_journey(args.brand))
    if args.purge_kit_update:
        _report("retired kit-update state", purge_kit_update())


if __name__ == "__main__":
    main()
