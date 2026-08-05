"""Cohort aggregation layer over the HCP 360 panel (hcp_360.db).

Everything the Reporting & Insights dashboard shows is counted here, out of the real
committed panel (`config/hcp_360/*.json` -> `hcp_360.db`, 7.9k synthetic HCPs), for the
exact filter combination the user picked. No number in this module is invented or
randomised: sizes are `COUNT(DISTINCT npi)`, affinities are `AVG(<score>_raw__c)` over the
filtered NPI set, send windows are the panel's own day/session preference columns, and
content demand is the panel's own preferred-content tags.

The rate model that turns these panel facts into campaign percentages lives one layer up in
`reporting_insights.py` -- this module only ever reports what the panel contains, so a
filter that changes the population provably changes every downstream number.

Every dimension name and column reaching SQL is allow-listed (`DIMENSIONS`) and every value
is parameterised; callers cannot reach arbitrary SQL. Segment values cross the boundary in
the therapy-relative vocabulary (`segment_labels`), matching `hcp_360.cross_tab`.
"""
from __future__ import annotations

import pathlib
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import db  # noqa: E402
import hcp_360  # noqa: E402
import segment_labels  # noqa: E402

# Filter/breakdown dimension -> (join alias, column). Same vocabulary the UI's filter bar
# offers, so a facet the UI can show is always a filter the SQL can apply.
DIMENSIONS: dict[str, tuple[str, str]] = {
    "specialty": ("d", "primary_specialty_description__c"),
    "state": ("d", "state_code__c"),
    "segment": ("tl", "segment__c"),
    "channel": ("ch", "preferred_channel__c"),
    "brand": ("tl", "brand__c"),
}

_BASE = "hcp_demographic_data__dlm d"
_JOINS = {
    "ch": ("global_channel_affinity_and_preference", "ch.npi_number__c = d.npi_number__c"),
    "tl": ("tbl_tl_data__dlm", "tl.npi_id__c = d.npi_number__c"),
    "dt": ("global_day_time_preference_data", "dt.npi_num__c = d.npi_number__c"),
    "ca": ("global_content_affinity_score_data", "ca.npi_num__c = d.npi_number__c"),
}

# Panel channel score columns -> the campaign channel each one grounds.
CHANNEL_SCORES = {
    "Email": "ch.emailscore_raw__c",
    "Digital": "ch.digitalscore_raw__c",
    "EHR": "ch.ehrscore_raw__c",
    "Prog": "ch.progscore_raw__c",
    "Tele": "ch.telescore_raw__c",
}
SCORE_MAX = 10.0  # raw scores are 0-10 in the committed seed

_SESSION_ORDER = ["Morning", "Afternoon", "Evening", "ooo_hours"]
SESSION_LABELS = {"Morning": "Morning", "Afternoon": "Afternoon",
                  "Evening": "Evening", "ooo_hours": "Out of hours"}
_DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


_load_lock = threading.Lock()
_loaded = False


def _ensure_loaded() -> None:
    """Seed the panel once per process.

    `hcp_360.load_hcp_360()` is idempotent but not cheap: its drift check JSON-parses the 8 MB
    demographic seed on every call. One dashboard payload opens ~17 connections, so calling it
    per connection cost ~9s a request — hence the process-level latch.
    """
    global _loaded
    if _loaded:
        return
    with _load_lock:
        if not _loaded:
            hcp_360.load_hcp_360()
            _loaded = True


def _conn():
    _ensure_loaded()
    return db.connect("hcp_360")


def clean_filters(raw: dict | None) -> dict[str, str]:
    """Drop unknown dimensions and blank values. The only entry point for user input."""
    return {k: str(v).strip() for k, v in (raw or {}).items()
            if k in DIMENSIONS and str(v or "").strip()}


def _scope(filters: dict[str, str], extra_aliases: tuple[str, ...] = ()) -> tuple[str, list, set[str]]:
    """WHERE fragment + params + the join aliases the query needs."""
    where: list[str] = []
    params: list = []
    aliases = set(extra_aliases)
    for dim, value in filters.items():
        alias, col = DIMENSIONS[dim]
        aliases.add(alias)
        where.append(f"LOWER({alias}.{col}) = LOWER(?)")
        params.append(segment_labels.to_raw(value) if dim == "segment" else value)
    aliases.discard("d")
    return (" WHERE " + " AND ".join(where)) if where else "", params, aliases


def _from(aliases: set[str]) -> str:
    sql = _BASE
    for alias in ("ch", "tl", "dt", "ca"):  # stable order
        if alias in aliases:
            table, predicate = _JOINS[alias]
            sql += f" LEFT JOIN {table} {alias} ON {predicate}"
    return sql


def _rows(sql: str, params: list) -> list[dict]:
    conn = _conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _one(sql: str, params: list) -> dict:
    out = _rows(sql, params)
    return out[0] if out else {}


def _f(value, default: float = 0.0) -> float:
    return float(value) if value is not None else default


def cohort_profile(filters: dict[str, str] | None = None) -> dict:
    """The cohort's size, deliverable share and mean channel affinity -- the four panel facts
    every rate on the dashboard is derived from. `affinity` is a 0-1 index (raw score / 10)."""
    filters = clean_filters(filters)
    where, params, aliases = _scope(filters, ("ch",))
    row = _one(
        "SELECT COUNT(DISTINCT d.npi_number__c) size, "
        "SUM(CASE WHEN d.email__c IS NOT NULL AND d.email__c != '' THEN 1 ELSE 0 END) with_email, "
        + ", ".join(f"AVG({col}) AS score_{name.lower()}" for name, col in CHANNEL_SCORES.items())
        + f" FROM {_from(aliases)}{where}", params)
    size = int(row.get("size") or 0)
    return {
        "size": size,
        "with_email": int(row.get("with_email") or 0),
        "deliverable_pct": round(100 * (row.get("with_email") or 0) / size, 2) if size else 0.0,
        "affinity": {name: round(_f(row.get(f"score_{name.lower()}")) / SCORE_MAX, 4)
                     for name in CHANNEL_SCORES},
        "filters": filters,
    }


_baseline_cache: dict | None = None


def panel_baseline() -> dict:
    """Unfiltered panel means -- the denominator that makes a cohort's affinity a *lift*
    rather than an absolute, so an unfiltered view lands exactly on the benchmark.

    Cached per process: the panel is a committed seed that only changes on a redeploy, and
    this is read on every dashboard request."""
    global _baseline_cache
    if _baseline_cache is None:
        _baseline_cache = cohort_profile({})
    return dict(_baseline_cache)


def dimension_counts(dim: str, filters: dict[str, str] | None = None, limit: int = 40) -> list[dict]:
    """HCP counts per value of `dim` inside the current cohort, with that group's own mean
    email/digital affinity -- the breakdown behind every bar, map shade and asset row."""
    if dim not in DIMENSIONS:
        raise ValueError(f"unknown dimension '{dim}'")
    filters = clean_filters(filters)
    alias, col = DIMENSIONS[dim]
    where, params, aliases = _scope(filters, ("ch", alias))
    rows = _rows(
        f"SELECT {alias}.{col} AS value, COUNT(DISTINCT d.npi_number__c) AS count, "
        "AVG(ch.emailscore_raw__c) email_score, AVG(ch.digitalscore_raw__c) digital_score "
        f"FROM {_from(aliases)}{where}"
        f"{' AND' if where else ' WHERE'} {alias}.{col} IS NOT NULL AND {alias}.{col} != '' "
        f"GROUP BY {alias}.{col} ORDER BY count DESC LIMIT {int(limit)}", params)
    return [{
        "value": segment_labels.to_display(r["value"]) if dim == "segment" else r["value"],
        "count": int(r["count"]),
        "email_affinity": round(_f(r["email_score"]) / SCORE_MAX, 4),
        "digital_affinity": round(_f(r["digital_score"]) / SCORE_MAX, 4),
    } for r in rows]


def facets(filters: dict[str, str] | None = None) -> dict[str, list[dict]]:
    """Filter values the UI may offer, each counted with the *other* filters applied, so no
    drop-down ever offers a combination that returns an empty cohort."""
    filters = clean_filters(filters)
    out: dict[str, list[dict]] = {}
    for dim in DIMENSIONS:
        others = {k: v for k, v in filters.items() if k != dim}
        out[dim] = [{"value": r["value"], "count": r["count"]}
                    for r in dimension_counts(dim, others, limit=60)]
    return out


def send_windows(filters: dict[str, str] | None = None) -> dict:
    """Day x session send-window matrix from the panel's own email day/time preference
    columns: each cell is the share of the cohort whose most-preferred email window it is."""
    filters = clean_filters(filters)
    where, params, aliases = _scope(filters, ("dt",))
    rows = _rows(
        "SELECT dt.most_preferred_day_email__c day, dt.most_preferred_session_email__c session, "
        f"COUNT(DISTINCT d.npi_number__c) n FROM {_from(aliases)}{where}"
        f"{' AND' if where else ' WHERE'} dt.most_preferred_day_email__c IS NOT NULL "
        "AND dt.most_preferred_session_email__c IS NOT NULL "
        "GROUP BY day, session", params)
    # Multi-day values ("Wednesday,Thursday") are real in the seed -- credit every day named.
    grid: dict[tuple[str, str], int] = {}
    total = 0
    for r in rows:
        session = r["session"]
        if session not in _SESSION_ORDER:
            continue
        for day in str(r["day"]).split(","):
            day = day.strip()
            if day in _DAY_ORDER:
                grid[(day, session)] = grid.get((day, session), 0) + int(r["n"])
                total += int(r["n"])
    days = [d for d in _DAY_ORDER if any((d, s) in grid for s in _SESSION_ORDER)]
    counts = [[grid.get((day, s), 0) for s in _SESSION_ORDER] for day in days]
    flat = [c for row in counts for c in row]
    shares = _shares_to_100(flat, total)
    width = len(_SESSION_ORDER)
    return {
        "sessions": [SESSION_LABELS[s] for s in _SESSION_ORDER],
        "total": total,
        "rows": [{"day": day,
                  "cells": shares[i * width:(i + 1) * width],
                  "counts": counts[i]}
                 for i, day in enumerate(days)],
    }


def _shares_to_100(counts: list[int], total: int) -> list[float]:
    """Percentages that add up to exactly 100.00.

    Rounding each cell independently leaves the grid summing to 99.4-ish, which reads as a
    bug on a matrix that is by definition a full split of the cohort. Largest-remainder
    apportionment instead: floor every cell at 2dp, then hand the leftover hundredths to the
    cells with the biggest truncated fractions.
    """
    if not counts or total <= 0:
        return [0.0 for _ in counts]
    exact = [c * 10000 / total for c in counts]  # hundredths of a percent
    floors = [int(v) for v in exact]
    leftover = 10000 - sum(floors)
    order = sorted(range(len(counts)), key=lambda i: exact[i] - floors[i], reverse=True)
    for i in order[:max(0, leftover)]:
        floors[i] += 1
    return [round(v / 100, 2) for v in floors]


def content_demand(filters: dict[str, str] | None = None, limit: int = 8) -> list[dict]:
    """The cohort's most-preferred content tags, with each tag group's own affinity means --
    what the top-performing-asset table ranks on."""
    filters = clean_filters(filters)
    where, params, aliases = _scope(filters, ("ch", "ca"))
    rows = _rows(
        "SELECT ca.most_preferred_content_tag__c tag, COUNT(DISTINCT d.npi_number__c) n, "
        "AVG(ch.emailscore_raw__c) email_score, AVG(ch.digitalscore_raw__c) digital_score "
        f"FROM {_from(aliases)}{where}"
        f"{' AND' if where else ' WHERE'} ca.most_preferred_content_tag__c IS NOT NULL "
        f"GROUP BY tag ORDER BY n DESC LIMIT {int(limit)}", params)
    return [{"tag": r["tag"], "count": int(r["n"]),
             "email_affinity": round(_f(r["email_score"]) / SCORE_MAX, 4),
             "digital_affinity": round(_f(r["digital_score"]) / SCORE_MAX, 4)} for r in rows]


def wave_profile(filters: dict[str, str] | None = None, months: int = 6) -> list[dict]:
    """The cohort split into `months` disjoint monthly send waves.

    The panel is a single point-in-time snapshot -- it carries no send history -- so a month
    over-month trend has to come from somewhere real rather than a random walk. The flight
    model here rotates the cohort: wave `i` is the panel members whose NPI mod `months` is
    `i`, and that month's audience size and affinity are that subgroup's own measured values.
    Deterministic (NPI is stable), disjoint, and it sums back to the whole cohort.
    """
    filters = clean_filters(filters)
    months = max(1, min(int(months), 24))
    where, params, aliases = _scope(filters, ("ch",))
    rows = _rows(
        f"SELECT (d.npi_number__c % {months}) AS wave, COUNT(DISTINCT d.npi_number__c) n, "
        "SUM(CASE WHEN d.email__c IS NOT NULL AND d.email__c != '' THEN 1 ELSE 0 END) with_email, "
        + ", ".join(f"AVG({col}) AS score_{name.lower()}" for name, col in CHANNEL_SCORES.items())
        + f" FROM {_from(aliases)}{where} GROUP BY wave ORDER BY wave", params)
    by_wave = {int(r["wave"]): r for r in rows}
    out = []
    for i in range(months):
        r = by_wave.get(i) or {}
        n = int(r.get("n") or 0)
        out.append({
            "wave": i,
            "size": n,
            "deliverable_pct": round(100 * (r.get("with_email") or 0) / n, 2) if n else 0.0,
            "affinity": {name: round(_f(r.get(f"score_{name.lower()}")) / SCORE_MAX, 4)
                         for name in CHANNEL_SCORES},
        })
    return out


def prescribing_volume(filters: dict[str, str] | None = None) -> dict:
    """Total TRx behind the cohort -- the commercial denominator the conversion KPI reads."""
    filters = clean_filters(filters)
    where, params, aliases = _scope(filters)
    aliases.add("trx")
    sql = (_BASE + "".join(
        f" LEFT JOIN {_JOINS[a][0]} {a} ON {_JOINS[a][1]}" for a in ("ch", "tl", "dt", "ca") if a in aliases)
        + " LEFT JOIN tbl_trx_therapeutic_data__dlm trx ON trx.npi_number__c = d.npi_number__c")
    row = _one("SELECT COALESCE(SUM(trx.trx_count__c), 0) trx, "
               "COUNT(DISTINCT trx.npi_number__c) writers "
               f"FROM {sql}{where}", params)
    return {"trx_total": int(row.get("trx") or 0), "writers": int(row.get("writers") or 0)}


if __name__ == "__main__":
    import json
    print(json.dumps(cohort_profile({"specialty": "Medical Oncology"}), indent=2))
    print(json.dumps(send_windows({"specialty": "Medical Oncology"})["rows"][:2], indent=2))
