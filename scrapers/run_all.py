"""Runs every scraper against the configured seed terms and prints a summary."""
from __future__ import annotations

import json
import pathlib

import awards
import asco_abstracts
import brand_sites
import clinicaltrials
import dailymed
import drugs_fda
import ema_medicines
import fda_opdp
import fda_oncology_approvals
import google_trends
import openfda
import orange_book
import pharma_intel
import pubmed
import public_web
import purple_book
import sec_edgar
import sec_filing_docs
import seer_statfacts

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    seeds = json.loads((BASE_DIR / "config" / "seed_terms.json").read_text())
    drugs = seeds["drugs"]
    therapy_areas = seeds["therapy_areas"]
    award_sources = json.loads((BASE_DIR / "config" / "award_sources.json").read_text())
    pharma_intel_seeds = json.loads((BASE_DIR / "config" / "pharma_intel_seed_terms.json").read_text())
    priority_oncology_terms = (
        pharma_intel_seeds.get("priority_oncology_brands", [])[:12]
        + pharma_intel_seeds.get("priority_therapy_areas", [])[:8]
    )

    results = {}
    print("=== DailyMed ===")
    results["dailymed"] = dailymed.run(drugs)
    print("=== openFDA ===")
    results["openfda"] = openfda.run(drugs)
    print("=== ClinicalTrials.gov ===")
    results["clinicaltrials"] = clinicaltrials.run(drugs + therapy_areas)
    print("=== PubMed ===")
    results["pubmed"] = pubmed.run(drugs + therapy_areas)
    print("=== Google Trends ===")
    results["google_trends"] = google_trends.run(drugs + therapy_areas)
    print("=== Award-winning campaigns ===")
    results["awards"] = awards.run(award_sources)
    print("=== Public pharma intelligence pages ===")
    results["public_web"] = public_web.run()
    print("=== ASCO annual meeting abstracts ===")
    results["asco_abstracts"] = asco_abstracts.run()
    print("=== NCI SEER Cancer Stat Facts ===")
    results["seer_statfacts"] = seer_statfacts.run()
    print("=== Official oncology brand sites ===")
    results["brand_sites"] = brand_sites.run()
    print("=== FDA OPDP promotional compliance ===")
    results["fda_opdp"] = fda_opdp.run()
    print("=== FDA oncology approval notifications ===")
    results["fda_oncology_approvals"] = fda_oncology_approvals.run()
    print("=== FDA Orange Book lifecycle data ===")
    results["orange_book"] = orange_book.run()
    print("=== FDA Purple Book biologics data ===")
    results["purple_book"] = purple_book.run()
    print("=== Drugs@FDA approval data ===")
    results["drugs_fda"] = drugs_fda.run()
    print("=== EMA medicines data ===")
    results["ema_medicines"] = ema_medicines.run()
    print("=== SEC EDGAR company filings ===")
    results["sec_edgar"] = sec_edgar.run()
    print("=== SEC EDGAR annual filing documents ===")
    results["sec_filing_docs"] = sec_filing_docs.run()
    print("=== Oncology-priority public labels/trials/literature ===")
    results["oncology_dailymed"] = dailymed.run(priority_oncology_terms[:12])
    results["oncology_openfda"] = openfda.run(priority_oncology_terms[:12])
    results["oncology_clinicaltrials"] = clinicaltrials.run(priority_oncology_terms)
    results["oncology_pubmed"] = pubmed.run(priority_oncology_terms)
    print("=== Structured pharma intelligence warehouse ===")
    results["pharma_intel"] = sum(pharma_intel.build().values())

    print("\n=== Summary ===")
    for source, count in results.items():
        print(f"{source}: {count} documents")
    print(f"\nTotal: {sum(results.values())} documents saved to {BASE_DIR / 'data'}")


if __name__ == "__main__":
    main()
