"""Gathers comparable, quantifiable signals for a brand from the local knowledge
repository -- refreshing live from the public APIs first if nothing's cached yet."""
from __future__ import annotations

import datetime
import json
import pathlib
import sqlite3
import sys

SCRAPERS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scrapers"
sys.path.insert(0, str(SCRAPERS_DIR))

import clinicaltrials  # noqa: E402
import dailymed  # noqa: E402
import google_trends  # noqa: E402
import openfda  # noqa: E402
import pubmed  # noqa: E402
from storage import get_db  # noqa: E402

ACTIVE_STATUSES = {"RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"}
STOPPED_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
COMPLETED_STATUSES = {"COMPLETED"}


def _refresh_brand(conn: sqlite3.Connection, brand: str, limit: int = 10) -> None:
    """Best-effort live refresh -- ignores failures so one down source doesn't block the analysis."""
    for fn, kwargs in [
        (dailymed.fetch_for_term, {"limit": limit}),
        (openfda.fetch_for_term, {"limit": min(limit, 5)}),
        (clinicaltrials.fetch_for_term, {"limit": limit}),
        (pubmed.fetch_for_term, {"limit": limit}),
    ]:
        try:
            fn(conn, brand, **kwargs)
        except Exception as e:
            print(f"[metrics] refresh failed for {brand} ({fn.__module__}): {e}")
    try:
        google_trends.fetch_for_term(conn, brand)
    except Exception as e:
        print(f"[metrics] google_trends refresh failed for {brand}: {e}")


def _docs_for(conn: sqlite3.Connection, source: str, brand: str) -> list[dict]:
    rows = conn.execute(
        "SELECT title, url, metadata_json FROM documents WHERE source = ? AND search_term LIKE ?",
        (source, f"%{brand}%"),
    ).fetchall()
    out = []
    for title, url, metadata_json in rows:
        try:
            meta = json.loads(metadata_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        out.append({"title": title, "url": url, "metadata": meta})
    return out


def gather_brand_metrics(brand: str, refresh: bool = True, limit: int = 10) -> dict:
    conn = get_db()
    if refresh:
        _refresh_brand(conn, brand, limit=limit)

    fda_docs = _docs_for(conn, "openfda", brand)
    trial_docs = _docs_for(conn, "clinicaltrials", brand)
    pubmed_docs = _docs_for(conn, "pubmed", brand)
    trends_docs = _docs_for(conn, "google_trends", brand)
    dailymed_docs = _docs_for(conn, "dailymed", brand)
    conn.close()

    manufacturers = set()
    indications_snippet = None
    for d in fda_docs:
        mfr = d["metadata"].get("manufacturer") or []
        manufacturers.update(mfr)
        if not indications_snippet:
            ind = d["metadata"].get("indications_and_usage")
            if ind:
                text = ind[0] if isinstance(ind, list) else str(ind)
                indications_snippet = text[:300]

    status_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    for d in trial_docs:
        status = d["metadata"].get("status")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        phases = d["metadata"].get("phase") or []
        for p in phases:
            phase_counts[p] = phase_counts.get(p, 0) + 1

    trials_active = sum(v for k, v in status_counts.items() if k in ACTIVE_STATUSES)
    trials_completed = sum(v for k, v in status_counts.items() if k in COMPLETED_STATUSES)
    trials_stopped = sum(v for k, v in status_counts.items() if k in STOPPED_STATUSES)

    current_year = datetime.datetime.now().year
    pubmed_recent = sum(
        1 for d in pubmed_docs
        if str(d["metadata"].get("year") or "").isdigit() and current_year - int(d["metadata"]["year"]) <= 2
    )

    trends_interest = None
    if trends_docs:
        trends_interest = trends_docs[0]["metadata"].get("avg_interest_12mo")

    return {
        "brand": brand,
        "manufacturer": sorted(manufacturers) or None,
        "fda_label_count": len(fda_docs),
        "fda_indications_snippet": indications_snippet,
        "trials_total": len(trial_docs),
        "trials_active": trials_active,
        "trials_completed": trials_completed,
        "trials_stopped": trials_stopped,
        "trials_phase_mix": phase_counts,
        "pubmed_total": len(pubmed_docs),
        "pubmed_recent_2yr": pubmed_recent,
        "trends_avg_interest": trends_interest,
        "dailymed_label_count": len(dailymed_docs),
    }
