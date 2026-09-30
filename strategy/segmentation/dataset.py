"""The data model object segments are built on, and what's really in it.

Camille's prompt hard-coded the columns and their values. The column catalogue (names, types,
descriptions) is kept exactly as Camille wrote it; the values and ranges come from the data:
profiled live from Data Cloud with the Query API (cached for a few hours), else the committed
snapshot in config/segmentation_dataset.json. Only values that really occur are offered to the
model, so a request can't be turned into a filter on a value the data doesn't have.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path

DMO = "hcp_segmentation_dummy_dataset_camille__dlm"

_SNAPSHOT = Path(__file__).resolve().parents[2] / "config" / "segmentation_dataset.json"
_TTL_S = 6 * 3600
_MAX_VALUES = 50  # a text column with more distinct values than this is described, not listed

# Camille's column list (segmentationAgent.js), in its order and words. `kind` drives how the
# prompt shows it: identifier / text (with its values) / number and date (with their range) / system.
COLUMNS: list[dict] = [
    {"name": "hcp_id__c", "type": "Text", "kind": "identifier", "description": 'HCP identifier, primary key (e.g., "HCP00001", "HCP00002")'},
    {"name": "KQ_hcp_id__c", "type": "Text", "kind": "identifier", "description": "key qualifier for hcp_id. MUST ALWAYS be included in SELECT alongside hcp_id__c"},
    {"name": "npi_number__c", "type": "Number", "kind": "identifier", "description": "NPI number (e.g., 1100000001)"},

    {"name": "brand__c", "type": "Text", "kind": "text", "description": "brand name"},
    {"name": "speciality__c", "type": "Text", "kind": "text", "description": "HCP specialty (IMPORTANT: spelled \"speciality__c\" with an 'i', NOT \"specialty__c\")"},
    {"name": "sub_specialty__c", "type": "Text", "kind": "text", "description": "HCP sub-specialty"},
    {"name": "indication__c", "type": "Text", "kind": "text", "description": "therapeutic indication"},
    {"name": "state__c", "type": "Text", "kind": "text", "description": "US state abbreviation"},
    {"name": "practice_setting__c", "type": "Text", "kind": "text", "description": "practice setting type"},
    {"name": "email_consent_status__c", "type": "Text", "kind": "text", "description": "email consent status"},
    {"name": "sms_consent_status__c", "type": "Text", "kind": "text", "description": "SMS consent status"},
    {"name": "rep_contact_allowed__c", "type": "Text", "kind": "text", "description": "whether rep contact is allowed"},
    {"name": "current_segment__c", "type": "Text", "kind": "text", "description": "current HCP segment"},
    {"name": "hcp_status__c", "type": "Text", "kind": "text", "description": "HCP active/inactive status"},
    {"name": "active_journey_flag__c", "type": "Text", "kind": "text", "description": "whether the HCP is in an active journey"},
    {"name": "preferred_channel__c", "type": "Text", "kind": "text", "description": "HCP's preferred communication channel"},

    {"name": "years_in_practice__c", "type": "Number", "kind": "number", "description": "years in practice"},
    {"name": "decile__c", "type": "Number", "kind": "number", "description": "decile ranking"},
    {"name": "trx_last_month__c", "type": "Number", "kind": "number", "description": "total prescriptions last month"},
    {"name": "trx_prev_6_months__c", "type": "Number", "kind": "number", "description": "total prescriptions previous 6 months"},
    {"name": "nrx_last_month__c", "type": "Number", "kind": "number", "description": "new prescriptions last month"},
    {"name": "brand_trx_12m__c", "type": "Number", "kind": "number", "description": "brand total prescriptions last 12 months"},
    {"name": "category_trx_12m__c", "type": "Number", "kind": "number", "description": "category total prescriptions last 12 months"},
    {"name": "competitor_trx_12m__c", "type": "Number", "kind": "number", "description": "competitor total prescriptions last 12 months"},
    {"name": "trx_growth_rate__c", "type": "Number", "kind": "number", "description": "total Rx growth rate, can be negative"},
    {"name": "emails_delivered__c", "type": "Number", "kind": "number", "description": "emails delivered count"},
    {"name": "email_opens__c", "type": "Number", "kind": "number", "description": "email opens count"},
    {"name": "email_clicks__c", "type": "Number", "kind": "number", "description": "email clicks count"},
    {"name": "ehr_impressions__c", "type": "Number", "kind": "number", "description": "EHR impressions count"},
    {"name": "prog_impressions__c", "type": "Number", "kind": "number", "description": "programmatic ad impressions"},
    {"name": "prog_clicks__c", "type": "Number", "kind": "number", "description": "programmatic ad clicks"},
    {"name": "web_visits__c", "type": "Number", "kind": "number", "description": "website visits"},
    {"name": "rep_calls__c", "type": "Number", "kind": "number", "description": "rep calls count"},
    {"name": "channels_engaged__c", "type": "Number", "kind": "number", "description": "number of channels engaged"},
    {"name": "engagement_score__c", "type": "Number", "kind": "number", "description": "engagement score (decimal e.g. 7.5, 12.13)"},
    {"name": "days_since_last_engagement__c", "type": "Number", "kind": "number", "description": "days since last engagement"},

    {"name": "last_campaign_date__c", "type": "Date", "kind": "date", "description": "date of last campaign interaction"},
    {"name": "last_engagement_date__c", "type": "Date", "kind": "date", "description": "date of last engagement"},
    {"name": "suppression_until_date__c", "type": "Date", "kind": "date", "description": "suppression end date"},

    {"name": "cdp_sys_SourceVersion__c", "type": "Text", "kind": "system", "description": ""},
    {"name": "DataSource__c", "type": "Text", "kind": "system", "description": ""},
    {"name": "DataSourceObject__c", "type": "Text", "kind": "system", "description": ""},
    {"name": "InternalOrganization__c", "type": "Text", "kind": "system", "description": ""},
]
COLUMN_NAMES = {c["name"] for c in COLUMNS}

# Camille's consent options (SegmentationAgent.js CONSENT_OPTIONS), used until the data says otherwise.
DEFAULT_CONSENT = ["Opted In", "Opted Out", "No Response"]

_LOCK = threading.Lock()
_CACHE: dict = {"at": 0.0, "profile": None}


def _plain(v) -> str:
    """A Data Cloud number ("40.000000000000000000", "0E-18") as plain text ("40", "0")."""
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return str(v)
    if d == 0:
        return "0"
    text = format(d.normalize(), "f")
    if "." in text:
        head, tail = text.split(".", 1)
        text = f"{head}.{tail[:4]}".rstrip("0").rstrip(".")
    return text


def load_snapshot() -> dict:
    try:
        return json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"dmo": DMO, "columns": {}}


def _merge(found: dict, source: str, profiled_at: str | None, row_count) -> dict:
    cols = []
    for c in COLUMNS:
        info = (found.get(c["name"]) or {}) if c["kind"] in ("text", "number", "date") else {}
        cols.append({**c, "values": info.get("values"), "range": info.get("range")})
    return {"dmo": DMO, "source": source, "profiled_at": profiled_at, "row_count": row_count, "columns": cols}


def _from_snapshot() -> dict:
    snap = load_snapshot()
    return _merge(snap.get("columns") or {}, "snapshot", snap.get("profiled_at"), snap.get("row_count"))


def _profile_live() -> dict:
    """Every text column's values (most common first) and every number/date column's range."""
    from . import datacloud
    found: dict[str, dict] = {}
    texts = [c["name"] for c in COLUMNS if c["kind"] == "text"]

    def values_of(col: str):
        rows = datacloud.query(f"SELECT {col} AS v, count(*) AS n FROM {DMO} GROUP BY {col} ORDER BY n DESC "
                               f"LIMIT {_MAX_VALUES + 1}")
        vals = [str(r["v"]) for r in rows if r.get("v") not in (None, "")]
        return col, (vals if len(vals) <= _MAX_VALUES else None)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for col, vals in pool.map(values_of, texts):
            found[col] = {"values": vals}
    ranged = [c["name"] for c in COLUMNS if c["kind"] in ("number", "date")]
    agg = ", ".join(f"min({c}) AS {c}_lo, max({c}) AS {c}_hi" for c in ranged)
    row = (datacloud.query(f"SELECT count(*) AS total_rows, {agg} FROM {DMO}") or [{}])[0]
    for c in ranged:
        lo, hi = row.get(f"{c}_lo"), row.get(f"{c}_hi")
        if lo is not None and hi is not None:
            found[c] = {"range": [_plain(lo), _plain(hi)]}
    total = row.get("total_rows")
    return _merge(found, "data_cloud", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  int(Decimal(str(total))) if total is not None else None)


def profile(refresh: bool = True, force: bool = False) -> dict:
    """The dataset as the prompt describes it. With `refresh`, a stale profile (any profile,
    with `force`) is re-read from Data Cloud first when it's configured; any failure falls back
    to the last good profile, then to the committed snapshot. Without `refresh` it never
    touches the network."""
    from . import datacloud
    with _LOCK:
        cached, at = _CACHE["profile"], _CACHE["at"]
        if cached and (not refresh or (not force and time.time() - at < _TTL_S)):
            return cached
        if refresh and datacloud.configured():
            try:
                live = _profile_live()
                _CACHE.update(profile=live, at=time.time())
                return live
            except Exception as exc:  # noqa: BLE001 -- the snapshot stands in; never block the planner
                print(f"[segmentation] dataset profile from Data Cloud failed, using the snapshot: {exc}")
        return cached or _from_snapshot()


def is_stale() -> bool:
    return not _CACHE["profile"] or time.time() - _CACHE["at"] >= _TTL_S


def column(prof: dict, name: str) -> dict | None:
    return next((c for c in prof["columns"] if c["name"] == name), None)


def consent_options(prof: dict | None = None) -> list[str]:
    col = column(prof or profile(refresh=False), "email_consent_status__c") or {}
    return list(col.get("values") or DEFAULT_CONSENT)


def columns_block(prof: dict) -> str:
    """The "Available columns" part of Camille's prompt, with the data's real values."""
    groups = [("IDENTIFIER FIELDS", "identifier"), ("CATEGORICAL / TEXT FIELDS", "text"),
              ("NUMERIC FIELDS", "number"), ("DATE FIELDS", "date")]
    lines: list[str] = []
    for title, kind in groups:
        lines.append(f"   {title}:")
        for c in (x for x in prof["columns"] if x["kind"] == kind):
            desc = f"   - {c['name']} ({c['type']}) — {c['description']}"
            if kind == "text" and c.get("values"):
                desc += ". Values: " + ", ".join(f'"{v}"' for v in c["values"])
            elif kind in ("number", "date") and c.get("range"):
                lo, hi = c["range"]
                desc += f" ({lo} to {hi})" if kind == "date" else f" ({lo}-{hi})"
            lines.append(desc)
        lines.append("")
    lines.append("   SYSTEM FIELDS (do not use in segmentation queries):")
    lines.append("   - " + ", ".join(c["name"] for c in prof["columns"] if c["kind"] == "system"))
    return "\n".join(lines)


def public(prof: dict) -> dict:
    """The profile for the Cockpit's Dataset tab."""
    return {"dmo": prof["dmo"], "source": prof["source"], "profiled_at": prof.get("profiled_at"),
            "row_count": prof.get("row_count"),
            "columns": [{k: c.get(k) for k in ("name", "type", "kind", "description", "values", "range")}
                        for c in prof["columns"] if c["kind"] != "system"]}


def write_snapshot() -> dict:
    """Re-profile Data Cloud and save it as the committed fallback (a maintenance helper)."""
    live = _profile_live()
    snap = {"dmo": DMO, "profiled_at": live["profiled_at"], "row_count": live["row_count"],
            "note": "Written by strategy.segmentation.dataset.write_snapshot() from the live Data Cloud data model object; "
                    "used when Data Cloud can't be reached. Values are in order of frequency.",
            "columns": {c["name"]: ({"values": c["values"]} if c["kind"] == "text" else {"range": c["range"]})
                        for c in live["columns"] if c["kind"] in ("text", "number", "date") and (c.get("values") or c.get("range"))}}
    _SNAPSHOT.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return snap
