"""Rebuild the committed knowledge-base seed (assets/seed/omni_kb.db, ~90MB) from the full
local master (assets/seed/omni_kb_full.db, ~170MB, gitignored).

Why a slim seed: the full KB is 170MB, over GitHub's 100MB per-file limit. Most of that is
large raw tables no app query or app-used view references. This drops exactly those (keeping
the dependency closure of everything the app reads), producing a ~90MB file that commits to
git normally (no LFS) and seeds to the persistent disk on boot.

Usage:  python scripts/build_slim_kb.py
        python scripts/build_slim_kb.py --src path/to/full.db --out assets/seed/omni_kb.db
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = ROOT / "assets" / "seed"

# Objects the app actually reads (app/server.py pharma-intel + dashboard/feed/engine). The
# dependency closure of these is kept; every other table is dropped, and any view that then
# dangles (references a dropped table but is never queried) is dropped too.
APP = {
    "documents", "pharma_source", "pharma_company", "oncology_brand_seed",
    "campaign_award_mention", "asco_abstract", "seer_cancer_stat", "opdp_letter_document",
    "cms_open_payment_general", "openfda_event_reaction_count", "openfda_drug_shortage",
    "openfda_drug_recall", "openfda_ndc_product", "openfda_ndc_package", "rxnorm_concept",
    "rxnorm_related_concept", "fda_srlc_labeling_change", "brand_message",
    "regulatory_label_message", "nci_drug_dictionary_entry", "nci_drug_dictionary_alias",
    "v_oncology_message_campaign_evidence", "v_oncology_clinical_trial_locations",
    "v_oncology_brand_evidence_summary", "v_dailymed_oncology_priority",
    "v_oncology_clinical_trials", "v_oncology_pubmed_articles", "v_asco_oncology_abstracts",
    "v_seer_oncology_market_context", "v_oncology_award_mentions",
    "v_opdp_oncology_letter_documents", "v_sec_oncology_brand_mentions",
    "v_openfda_oncology_drug_shortages", "v_openfda_oncology_drug_recalls",
    "v_openfda_oncology_ndc_products", "v_openfda_oncology_ndc_packages",
    "v_rxnorm_oncology_concepts", "v_rxnorm_oncology_related_concepts",
    "v_fda_srlc_oncology_labeling_changes", "v_nci_oncology_drug_dictionary",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SEED / "omni_kb_full.db"))
    ap.add_argument("--out", default=str(SEED / "omni_kb.db"))
    args = ap.parse_args()
    src, out = pathlib.Path(args.src), pathlib.Path(args.out)
    if not src.exists():
        raise SystemExit(f"full KB master not found: {src} (keep the 170MB file there, gitignored)")

    c = sqlite3.connect(src)
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
              if not r[0].startswith("sqlite_")}
    views = {r[0]: (r[1] or "") for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type='view'")}
    names = tables | set(views)
    c.close()

    def refs(sql: str) -> set[str]:
        return {m.group(1) for m in re.finditer(r'(?:FROM|JOIN)\s+"?([A-Za-z_]\w*)"?', sql, re.I)
                if m.group(1) in names}

    keep = {n for n in APP if n in names}
    changed = True
    while changed:
        changed = False
        for n in list(keep):
            if n in views:
                for r in refs(views[n]):
                    if r not in keep:
                        keep.add(r); changed = True

    drop_tables = sorted(t for t in tables if t not in keep)
    drop_views = sorted(set(views) - keep)

    shutil.copy2(src, out)
    w = sqlite3.connect(out)
    for v in drop_views:
        w.execute(f'DROP VIEW IF EXISTS "{v}"')
    for t in drop_tables:
        w.execute(f'DROP TABLE IF EXISTS "{t}"')
    w.commit(); w.execute("VACUUM"); w.commit()
    errors = []
    for obj in sorted(keep):
        try:
            w.execute(f'SELECT COUNT(*) FROM "{obj}"').fetchone()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{obj}: {e}")
    w.close()

    print(f"dropped {len(drop_tables)} tables, {len(drop_views)} dangling views")
    print("kept-object query errors:", errors or "NONE")
    print(f"full {round(src.stat().st_size/1048576,1)}MB -> slim {round(out.stat().st_size/1048576,1)}MB")
    if errors:
        raise SystemExit("kept objects failed to query -- do NOT commit this slim; investigate.")


if __name__ == "__main__":
    main()
