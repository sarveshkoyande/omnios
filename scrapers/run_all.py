"""Runs every scraper against the configured seed terms and prints a summary."""
from __future__ import annotations

import json
import pathlib

import awards
import clinicaltrials
import dailymed
import google_trends
import openfda
import pubmed

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def main() -> None:
    seeds = json.loads((BASE_DIR / "config" / "seed_terms.json").read_text())
    drugs = seeds["drugs"]
    therapy_areas = seeds["therapy_areas"]
    award_sources = json.loads((BASE_DIR / "config" / "award_sources.json").read_text())

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

    print("\n=== Summary ===")
    for source, count in results.items():
        print(f"{source}: {count} documents")
    print(f"\nTotal: {sum(results.values())} documents saved to {BASE_DIR / 'data'}")


if __name__ == "__main__":
    main()
