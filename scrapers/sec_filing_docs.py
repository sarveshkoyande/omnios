"""Download latest annual SEC filing documents for mapped top-pharma companies."""
from __future__ import annotations

import hashlib
import time

import requests

from storage import get_db, save_blob, upsert_document

USER_AGENT = "OmniDataHubResearchBot/0.1 research-contact@example.com"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,text/plain,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


def run(limit: int | None = None) -> int:
    conn = get_db()
    conn.row_factory = None
    saved = 0
    try:
        rows = conn.execute(
            """
            SELECT sf.company, sf.ticker, sf.cik, sf.form, sf.filing_date, sf.accession_number,
                   sf.primary_document, sf.filing_url
            FROM sec_filing sf
            JOIN (
                SELECT cik, MAX(filing_date) AS latest_filing_date
                FROM sec_filing
                WHERE form IN ('10-K','20-F') AND filing_url <> ''
                GROUP BY cik
            ) latest ON latest.cik=sf.cik AND latest.latest_filing_date=sf.filing_date
            WHERE sf.form IN ('10-K','20-F') AND sf.filing_url <> ''
            ORDER BY sf.company
            """
        ).fetchall()
        if limit:
            rows = rows[:limit]
        for company, ticker, cik, form, filing_date, accession, primary_document, url in rows:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=60)
                if resp.status_code in {401, 403, 404}:
                    print(f"[sec_filing_docs] {ticker}: http_{resp.status_code}")
                    continue
                resp.raise_for_status()
                text = resp.text
                digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
                blob_path = save_blob("sec_filing_docs", f"{cik}_{filing_date}_{digest}.html", text)
                upsert_document(
                    conn,
                    source="sec_edgar:annual_filing_document",
                    external_id=f"{cik}:{accession}:{primary_document}",
                    search_term=company,
                    title=f"{company} {form} annual filing {filing_date}",
                    doc_type="sec_annual_filing_html",
                    url=url,
                    blob_path=blob_path,
                    metadata={
                        "company": company,
                        "ticker": ticker,
                        "cik": cik,
                        "form": form,
                        "filing_date": filing_date,
                        "accession_number": accession,
                        "primary_document": primary_document,
                    },
                )
                saved += 1
                print(f"[sec_filing_docs] {ticker}: saved {form} {filing_date}")
            except Exception as exc:
                print(f"[sec_filing_docs] {ticker}: FAILED ({exc})")
            time.sleep(0.25)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run()
