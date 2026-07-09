"""Client brand-intelligence sweep (requested 2026-07-09).

For every flagship brand in config/client_brands.json (Bayer, Ipsen, Genmab, Novartis,
Pfizer, Incyte):
  1. merges the brand + therapy area into config/seed_terms.json so the chat agent and
     future scraper runs recognize them;
  2. scrapes real medical information into data/omni_kb.db -- PI/label (DailyMed SPLs +
     openFDA labels), clinical trials (ClinicalTrials.gov), literature (PubMed).
     Google Trends is skipped by default (currently rate-limited, HTTP 429);
  3. discovers competitors per brand from live ClinicalTrials.gov intervention data;
  4. writes the vault report 'Omni OS — Client Brand Intelligence.md' with per-client
     brand tables (stage read + rationale), discovered competitors, and the scraped
     document links.

Idempotent: re-running refreshes the KB and rewrites the report. A JSON checkpoint of
competitor discovery is kept next to the report data in data/client_brand_intel.json.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scrapers"))

import clinicaltrials  # noqa: E402
import dailymed  # noqa: E402
import openfda  # noqa: E402
import pubmed  # noqa: E402
from competitive.discovery import discover_competitors  # noqa: E402
from strategy.engine import _kb_grounding  # noqa: E402
from strategy.lifecycle import infer_persona_and_stage  # noqa: E402

VAULT_REPORT = BASE_DIR.parent / "Omni OS — Client Brand Intelligence.md"
CHECKPOINT = BASE_DIR / "data" / "client_brand_intel.json"

_LIFECYCLE_LABELS = {"launch": "Launch / pre-launch", "growth": "Growth", "mature": "Mature / in-line",
                     "loe": "LOE / defend"}


def merge_seeds(brands: list[str], therapy_areas: list[str]) -> None:
    path = BASE_DIR / "config" / "seed_terms.json"
    seeds = json.loads(path.read_text(encoding="utf-8"))
    seeds["drugs"] = sorted(set(seeds["drugs"]) | set(brands))
    seeds["therapy_areas"] = sorted(set(seeds["therapy_areas"]) | set(therapy_areas))
    path.write_text(json.dumps(seeds, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[seeds] merged -> {len(seeds['drugs'])} drugs, {len(seeds['therapy_areas'])} therapy areas")


def scrape(brands: list[str], therapy_areas: list[str]) -> dict:
    counts = {}
    print("=== DailyMed (PI / SPL) ===")
    counts["dailymed"] = dailymed.run(brands)
    print("=== openFDA (FDA labels) ===")
    counts["openfda"] = openfda.run(brands)
    print("=== ClinicalTrials.gov ===")
    counts["clinicaltrials"] = clinicaltrials.run(brands + therapy_areas)
    print("=== PubMed ===")
    counts["pubmed"] = pubmed.run(brands + therapy_areas)
    return counts


def _doc_lines(grounding: dict, source: str, label: str, limit: int = 2) -> list[str]:
    return [f"    - {label}: [{d['title']}]({d['url']})" for d in grounding.get(source, [])[:limit]]


def write_report(roster: dict, competitors: dict, counts: dict) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    scrape_line = ("Scrape totals this run: " + ", ".join(f"{k}: {v}" for k, v in counts.items())
                   if counts else "Report-only regeneration (knowledge base not re-scraped this run).")
    lines = [
        "# Omni OS — Client Brand Intelligence",
        "",
        f"*Generated {ts} by `scripts/client_brand_intel.py`. **A brand maps to one fixed therapy area; the "
        "variable dimension is the indication** — so each brand lists the indications the chat agent offers as "
        "choices once the brand is named. Lifecycle reads and indication lists are an editorial starting point "
        "from public information (approx. through the 2026-01 cutoff) — validate with each brand team. Competitors "
        "are discovered live from ClinicalTrials.gov intervention data. Document links are scraped into "
        "`data/omni_kb.db` (DailyMed PI, openFDA labels, ClinicalTrials.gov, PubMed) and ground every campaign "
        "plan the agent generates for these brands.*",
        "",
        scrape_line,
        "",
    ]
    for client, brands in roster.items():
        lines.append(f"## {client}")
        lines.append("")
        lines.append("| Brand | Generic | Therapy area (fixed) | Indications | Market stage | Why |")
        lines.append("|---|---|---|---|---|---|")
        for b in brands:
            stage = _LIFECYCLE_LABELS.get(b["lifecycle_key"], b["lifecycle_key"])
            inds = "; ".join(b.get("indications", [])) or "—"
            lines.append(f"| **{b['brand']}** | {b['generic']} | {b['therapy_area']} | {inds} | {stage} | {b['stage_rationale']} |")
        lines.append("")
        for b in brands:
            inferred = infer_persona_and_stage(b["lifecycle_key"])
            comps = competitors.get(b["brand"], [])
            g = _kb_grounding(b["brand"], limit=3)
            lines.append(f"### {b['brand']} ({client})")
            lines.append(f"- **Therapy area (fixed):** {b['therapy_area']}")
            inds = b.get("indications", [])
            if inds:
                lines.append(f"- **Indications the agent offers as choices:** " + "; ".join(inds))
            lines.append(f"- **Journey read:** {inferred['lifecycle_label']} → default persona "
                         f"*{inferred['persona']}*, journey stage *{inferred['stage_key']}*")
            lines.append(f"- **Discovered competitors (ClinicalTrials.gov, {b['therapy_area']}):** "
                         + (", ".join(comps) if comps else "none found in public trial data"))
            docs = (_doc_lines(g, "dailymed", "DailyMed PI") + _doc_lines(g, "openfda", "FDA label")
                    + _doc_lines(g, "clinicaltrials", "Trial") + _doc_lines(g, "pubmed", "PubMed"))
            if docs:
                lines.append("- **Scraped medical information:**")
                lines.extend(docs)
            else:
                lines.append("- **Scraped medical information:** none indexed yet for this exact term")
            lines.append("")
    VAULT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] wrote {VAULT_REPORT}")


def main() -> None:
    report_only = "--report-only" in sys.argv
    cfg = json.loads((BASE_DIR / "config" / "client_brands.json").read_text(encoding="utf-8"))
    roster = cfg["clients"]
    all_brands = [b["brand"] for brands in roster.values() for b in brands]
    all_tas = sorted({b["therapy_area"] for brands in roster.values() for b in brands})
    print(f"{len(all_brands)} brands across {len(roster)} clients; {len(all_tas)} therapy areas"
          + (" (report-only)" if report_only else ""))

    counts: dict = {}
    if not report_only:
        merge_seeds(all_brands, all_tas)
        counts = scrape(all_brands, all_tas)

    competitors: dict[str, list[str]] = {}
    if CHECKPOINT.exists():
        competitors = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    for brands in roster.values():
        for b in brands:
            if b["brand"] in competitors:
                continue
            try:
                competitors[b["brand"]] = discover_competitors(b["therapy_area"], b["brand"], limit=5)
                print(f"[competitors] {b['brand']}: {', '.join(competitors[b['brand']]) or '(none)'}")
            except Exception as e:  # noqa: BLE001 -- keep sweeping, note the failure
                print(f"[competitors] {b['brand']}: FAILED ({e})")
                competitors[b["brand"]] = []
            CHECKPOINT.write_text(json.dumps(competitors, indent=2, ensure_ascii=False), encoding="utf-8")

    write_report(roster, competitors, counts)


if __name__ == "__main__":
    main()
