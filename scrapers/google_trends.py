"""Google Trends scraper via pytrends -- unofficial but keyless public interest-over-time data."""
from __future__ import annotations

import json
import time

from storage import get_db, save_blob, upsert_document


def fetch_for_term(conn, term: str) -> int:
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([term], timeframe="today 12-m")
    df = pytrends.interest_over_time()
    if df is None or df.empty:
        return 0

    df = df.reset_index()
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    blob_path = save_blob("google_trends", f"trend_{term.replace(' ', '_')}.json", json.dumps(records, indent=2))

    avg_interest = round(df[term].mean(), 1) if term in df.columns else None
    upsert_document(
        conn,
        source="google_trends",
        external_id=f"trend_{term}",
        search_term=term,
        title=f"Google Trends interest: {term}",
        doc_type="search_interest_timeseries",
        url=f"https://trends.google.com/trends/explore?q={term.replace(' ', '%20')}",
        blob_path=blob_path,
        metadata={"avg_interest_12mo": avg_interest, "points": len(records)},
    )
    return 1


def run(terms: list[str]) -> int:
    conn = get_db()
    total = 0
    for term in terms:
        try:
            n = fetch_for_term(conn, term)
            print(f"[google_trends] {term}: {'ok' if n else 'no data'}")
            total += n
        except Exception as e:
            print(f"[google_trends] {term}: FAILED ({e})")
        time.sleep(1.0)
    conn.close()
    return total


if __name__ == "__main__":
    import pathlib

    seeds = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config" / "seed_terms.json").read_text())
    run(seeds["drugs"] + seeds["therapy_areas"])
