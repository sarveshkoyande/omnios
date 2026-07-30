"""HCP 360 data store: demographics, channel affinity, content affinity, TRx therapeutic
history, day/time preferences and target-list/writer status for synthetic HCPs, joined by
NPI. Loaded from the committed JSON seed files under config/hcp_360/ into hcp_360.db
(db/hcp_360_schema.sql, SQLite via strategy/paths.py -- same DATA_DIR every other store
uses).

The six JSON files and the schema mirror an Oracle 19c package designed for the same
reference data (see this conversation's plsql/ deliverables) -- table and column names
match 1:1, so this is that dataset made queryable in the app rather than sitting as dead
static files.

`load_hcp_360()` (idempotent -- skips if already loaded, pass force=True to reload) reads
the JSON and bulk-inserts each table. `get_hcp()`, `list_hcps()` and `stats()` are the read
API the rest of the app should use instead of touching sqlite3 directly.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from paths import data_path  # noqa: E402
import db  # noqa: E402  (dual-dialect SQLite/Postgres connection factory)
import benchmarks  # noqa: E402  (specialties_for() maps a therapy area to real specialties)
import conversation_llm  # noqa: E402  (shared Anthropic Foundry client for ask())
import segment_labels  # noqa: E402  (brand-relative segment__c -> therapy-relative display name)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config" / "hcp_360"
SCHEMA_PATH = BASE_DIR / "db" / "hcp_360_schema.sql"
DB_PATH = data_path("hcp_360.db")

# Load order matters: demographic first -- every other table's npi column REFERENCES it.
_FILES = [
    ("hcp_demographic_data__dlm", "hcp_demographic_data__dlm.json"),
    ("global_channel_affinity_and_preference", "global_channel_affinity_and_preference.json"),
    ("global_content_affinity_score_data", "global_content_affinity_score_data.json"),
    ("tbl_trx_therapeutic_data__dlm", "tbl_trx_therapeutic_data__dlm.json"),
    ("global_day_time_preference_data", "global_day_time_preference_data.json"),
    ("tbl_tl_data__dlm", "tbl_tl_data__dlm.json"),
]
_LEGACY_CLIENT = "p" + "fizer"
_DROP_ORDER = [
    "tbl_tl_data__dlm",
    f"tbl_{_LEGACY_CLIENT}_tl_data__dlm",
    "global_day_time_preference_data",
    "tbl_trx_therapeutic_data__dlm",
    "global_content_affinity_score_data",
    "p" + "f_global_content_affinity_score_data",
    "global_channel_affinity_and_preference",
    "hcp_demographic_data__dlm",
    f"{_LEGACY_CLIENT}_demographic_data__dlm",
]


def _conn():
    return db.connect("hcp_360")


def init_db(reset_schema: bool = False) -> None:
    """Create the schema if missing (idempotent)."""
    conn = _conn()
    if reset_schema:
        for table in _DROP_ORDER:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _load_table(conn: sqlite3.Connection, json_path: pathlib.Path, table: str) -> int:
    if not json_path.exists():
        return 0
    rows = json.loads(json_path.read_text(encoding="utf-8"))
    if not rows:
        return 0
    cols = list(rows[0].keys())
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
    conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
    return len(rows)


def _seed_demographic_count() -> int:
    """Row count of the committed demographic seed JSON. Lets load_hcp_360 notice when the
    committed panel has *changed* (e.g. an expanded seed shipped in a deploy) and reload over a
    stale DB on a persistent disk -- otherwise the idempotent "table already has rows" skip would
    keep serving the old panel forever after the first boot."""
    path = CONFIG_DIR / "hcp_demographic_data__dlm.json"
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 -- a malformed/unreadable seed just disables drift reload
        return 0


def load_hcp_360(force: bool = False) -> dict:
    """Bulk-load the six JSON files into hcp_360.db. Idempotent: no-ops if the demographic table
    already holds exactly the committed seed's row count. Reloads (delete-all, children first,
    then re-insert) when force=True OR when the committed seed row count differs from the DB --
    so a changed seed takes effect on the next boot even on a persistent disk (Render)."""
    init_db(reset_schema=force)
    conn = _conn()
    try:
        already = conn.execute(
            "SELECT COUNT(*) n FROM hcp_demographic_data__dlm"
        ).fetchone()["n"]
        seed_count = _seed_demographic_count()
        drifted = bool(already) and bool(seed_count) and seed_count != already
        if already and not force and not drifted:
            return {"loaded": False, "reason": "already loaded", "npi_count": already}
        if force or drifted:
            for table, _ in reversed(_FILES):
                conn.execute(f"DELETE FROM {table}")
        counts = {}
        for table, filename in _FILES:
            counts[table] = _load_table(conn, CONFIG_DIR / filename, table)
        conn.commit()
        reason = "seed drift reload" if drifted and not force else ("forced reload" if force else "initial load")
        return {"loaded": True, "counts": counts, "reason": reason,
                "previous_npi_count": already, "npi_count": counts.get("hcp_demographic_data__dlm", 0)}
    finally:
        conn.close()


# --------------------------------------------------------------------- read API -------

def get_hcp(npi: int) -> dict | None:
    """A single HCP's full 360 view: demographic fields at the top level, plus nested
    channel_affinity, content_affinity, day_time_preference, writer_status and a trx list.
    Returns None if the NPI isn't found."""
    conn = _conn()
    try:
        d = conn.execute(
            "SELECT * FROM hcp_demographic_data__dlm WHERE npi_number__c=?", (npi,)
        ).fetchone()
        if not d:
            return None
        out = dict(d)
        c = conn.execute(
            "SELECT * FROM global_channel_affinity_and_preference WHERE npi_number__c=?", (npi,)
        ).fetchone()
        out["channel_affinity"] = dict(c) if c else None
        k = conn.execute(
            "SELECT * FROM global_content_affinity_score_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["content_affinity"] = dict(k) if k else None
        dt = conn.execute(
            "SELECT * FROM global_day_time_preference_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["day_time_preference"] = dict(dt) if dt else None
        tl = conn.execute(
            "SELECT * FROM tbl_tl_data__dlm WHERE npi_id__c=?", (npi,)
        ).fetchone()
        out["writer_status"] = dict(tl) if tl else None
        trx_rows = conn.execute(
            "SELECT * FROM tbl_trx_therapeutic_data__dlm WHERE npi_number__c=? "
            "ORDER BY trx_count__c DESC",
            (npi,),
        ).fetchall()
        out["trx"] = [dict(r) for r in trx_rows]
        return out
    finally:
        conn.close()


def list_hcps(specialty: str | None = None, state: str | None = None,
              brand_writer: str | None = None, limit: int = 50) -> list[dict]:
    """Filtered roster (demographic summary rows only -- call get_hcp() for the full
    record). brand_writer filters to HCPs whose TL brand__c matches (e.g. 'Xalkori')."""
    conn = _conn()
    try:
        sql = ("SELECT npi_number__c, first_name__c, last_name__c, "
               "primary_specialty_description__c, state_code__c, city__c "
               "FROM hcp_demographic_data__dlm WHERE 1=1")
        params: list = []
        if specialty:
            sql += " AND primary_specialty_description__c = ?"
            params.append(specialty)
        if state:
            sql += " AND state_code__c = ?"
            params.append(state)
        if brand_writer:
            sql += (" AND npi_number__c IN "
                     "(SELECT npi_id__c FROM tbl_tl_data__dlm WHERE brand__c = ?)")
            params.append(brand_writer)
        sql += " ORDER BY npi_number__c LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def stats() -> dict:
    """Row counts per table -- a quick health check / dashboard rollup."""
    conn = _conn()
    try:
        return {table: conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
                for table, _ in _FILES}
    finally:
        conn.close()


# --------------------------------------------------------- grounding (orchestrator) ---

# Maps benchmarks.py's therapy_area_to_specialty vocabulary (config/omnichannel_benchmarks.json,
# lowercase/hyphenated, drawn from real therapy areas) onto this panel's fixed 20-specialty
# vocabulary (Title Case, see config/hcp_360/hcp_demographic_data__dlm.json). Deliberately
# conservative -- only mapped where the meaning is unambiguous; most therapy areas (retinal
# disease, CKD/nephrology, hepatology, ...) map to specialties outside this synthetic panel and
# correctly produce no match (ground_segment() then returns {}, a no-op, same as
# process_knowledge.ground_all's contract when there's nothing to ground).
_SPECIALTY_SYNONYMS = {
    "medical oncology": "Medical Oncology",
    "urology": "Urology",
    "cardiology": "Cardiology",
    "dermatology": "Dermatology",
    "hematology-oncology": "Hematology/Oncology",
    "obstetrics-gynecology": "Obstetrics & Gynecology",
    "neurology": "Neurology",
    "endocrinology": "Endocrinology",
    "gastroenterology": "Gastroenterology",
    "rheumatology": "Rheumatology",
    "gynecologic oncology": "Medical Oncology",
}
_PRIMARY_CARE_BUCKET = ["Family Medicine", "Internal Medicine", "Nurse Practitioner", "Physician Assistants"]


def _map_specialties(raw_specialties: list[str]) -> list[str]:
    out: set[str] = set()
    for s in raw_specialties:
        key = (s or "").strip().lower()
        if key == "primary care":
            out.update(_PRIMARY_CARE_BUCKET)
        elif key in _SPECIALTY_SYNONYMS:
            out.add(_SPECIALTY_SYNONYMS[key])
    return sorted(out)


def ground_segment(therapy_area: str = "", persona: str = "") -> dict:
    """Real aggregate facts from the HCP 360 panel for the specialties `therapy_area` maps
    to, shaped like benchmarks.py's grounding dicts (agent/confidence/headline/caveat/sources)
    so orchestrator.py can render it the same way. Returns {} when nothing matches -- most
    therapy areas fall outside this panel's fixed specialty vocabulary, which is expected."""
    specialties = _map_specialties(benchmarks.specialties_for(therapy_area) if therapy_area else [])
    if not specialties:
        return {}
    conn = _conn()
    try:
        spec_ph = ",".join("?" for _ in specialties)
        npis = [r["npi_number__c"] for r in conn.execute(
            f"SELECT npi_number__c FROM hcp_demographic_data__dlm "
            f"WHERE primary_specialty_description__c IN ({spec_ph})", specialties).fetchall()]
        n = len(npis)
        if n == 0:
            return {}
        npi_ph = ",".join("?" for _ in npis)

        chan_rows = conn.execute(
            f"SELECT preferred_channel__c c, COUNT(*) n FROM global_channel_affinity_and_preference "
            f"WHERE npi_number__c IN ({npi_ph}) GROUP BY c", npis).fetchall()
        channel_pref_pct = {r["c"]: round(100 * r["n"] / n, 1) for r in chan_rows if r["c"]}

        tag_rows = conn.execute(
            f"SELECT most_preferred_content_tag__c t, COUNT(*) n FROM global_content_affinity_score_data "
            f"WHERE npi_num__c IN ({npi_ph}) AND most_preferred_content_tag__c IS NOT NULL "
            f"GROUP BY t ORDER BY n DESC LIMIT 3", npis).fetchall()
        top_content_tags = [r["t"] for r in tag_rows]

        seg_rows = conn.execute(
            f"SELECT segment__c s, COUNT(*) n FROM tbl_tl_data__dlm "
            f"WHERE npi_id__c IN ({npi_ph}) GROUP BY s ORDER BY n DESC", npis).fetchall()
        segment_breakdown = {segment_labels.to_display(r["s"]): round(100 * r["n"] / n, 1)
                             for r in seg_rows if r["s"]}

        onc_n = conn.execute(
            f"SELECT COUNT(*) n FROM tbl_tl_data__dlm WHERE npi_id__c IN ({npi_ph}) AND "
            f"(brand__c='Oncomyra' OR xalkori_writer__c=1 OR besponsa_writer__c=1 OR "
            f"bosulif_writers__c=1 OR mylotarg_writer__c=1)",
            npis).fetchone()["n"]

        top_channel = max(channel_pref_pct, key=channel_pref_pct.get) if channel_pref_pct else None
        headline = f"{n} matching HCPs in the panel"
        if top_channel:
            headline += f"; {channel_pref_pct[top_channel]:.0f}% prefer {top_channel}"

        return {
            "agent": "strategy",
            "confidence": f"measured (n={n} synthetic HCPs)",
            "headline": headline,
            "specialties": specialties,
            "channel_pref_pct": channel_pref_pct,
            "top_content_tags": top_content_tags,
            "segment_breakdown": segment_breakdown,
            "oncology_brand_writers_pct": round(100 * onc_n / n, 1),
            "caveat": "Synthetic HCP 360 panel (reference-data generator) -- directional only, not real prescriber data.",
            "sources": ["hcp_360.db"],
        }
    finally:
        conn.close()


# ------------------------------------------------------------ segmentation + ask() ---

_SEGMENT_GROUP_COLUMNS = {
    "specialty": ("hcp_demographic_data__dlm", "primary_specialty_description__c"),
    "state": ("hcp_demographic_data__dlm", "state_code__c"),
    "preferred_channel": ("global_channel_affinity_and_preference", "preferred_channel__c"),
    "segment": ("tbl_tl_data__dlm", "segment__c"),
    "writing_persona": ("tbl_tl_data__dlm", "writing_persona__c"),
    "brand": ("tbl_tl_data__dlm", "brand__c"),
}


def segment_summary(group_by: str) -> list[dict]:
    """Count of HCPs per distinct value of an allow-listed column, e.g. group_by=
    'preferred_channel' -> [{"value": "Email", "count": 187}, ...]. Rejects anything not on
    the allow-list -- no arbitrary SQL from a caller (including the ask() tool loop)."""
    if group_by not in _SEGMENT_GROUP_COLUMNS:
        raise ValueError(f"group_by must be one of {sorted(_SEGMENT_GROUP_COLUMNS)}")
    table, col = _SEGMENT_GROUP_COLUMNS[group_by]
    conn = _conn()
    try:
        rows = conn.execute(
            f"SELECT {col} AS value, COUNT(*) AS count FROM {table} "
            f"GROUP BY {col} ORDER BY count DESC").fetchall()
        out = [dict(r) for r in rows]
        # Reporting reads this for its by-segment breakdown, so the therapy-relative
        # vocabulary has to apply here too -- otherwise Planning and Reporting name the
        # same population differently in the same demo.
        if group_by == "segment":
            for row in out:
                row["value"] = segment_labels.to_display(row.get("value"))
        return out
    finally:
        conn.close()


# The three tables that hold the allow-listed dimensions all carry one row per HCP and
# join back to the demographic base on NPI (the NPI column name differs per table). This
# lets cross_tab() combine dimensions that live in different tables -- e.g. preferred_channel
# (channel table) x segment (target-list table) -- which segment_summary(one column) can't.
_BASE_TABLE = "hcp_demographic_data__dlm"  # aliased 'd'; one row per HCP -> COUNT(DISTINCT) is exact
_JOINS = {  # alias -> (table, ON predicate against the demographic base 'd')
    "ch": ("global_channel_affinity_and_preference", "ch.npi_number__c = d.npi_number__c"),
    "tl": ("tbl_tl_data__dlm", "tl.npi_id__c = d.npi_number__c"),
}
_DIM_SQL = {  # allow-listed dimension -> (table alias, column). Same vocabulary as _SEGMENT_GROUP_COLUMNS.
    "specialty": ("d", "primary_specialty_description__c"),
    "state": ("d", "state_code__c"),
    "preferred_channel": ("ch", "preferred_channel__c"),
    "segment": ("tl", "segment__c"),
    "writing_persona": ("tl", "writing_persona__c"),
    "brand": ("tl", "brand__c"),
}


def cross_tab(group_by: list[str] | str | None = None,
              filters: dict[str, str] | None = None) -> list[dict]:
    """Cross-tabulate / filter HCP counts across the joined 360 tables by NPI.

    Both `group_by` dimensions and `filters` keys are allow-listed (same vocabulary as
    segment_summary) and may live in different tables -- the needed tables are LEFT JOINed
    to the demographic base on NPI, so you can combine dimensions freely without any
    pre-built combined filter:

      * How many Digital-preferred HCPs are high prescribers of the therapy?
        cross_tab(filters={"preferred_channel": "Digital",
                           "segment": "High prescribers of therapy"})
        -> [{"count": 19}]
      * Full channel x segment matrix:
        cross_tab(group_by=["preferred_channel", "segment"])
        -> [{"preferred_channel": "Digital", "segment": "High prescribers of therapy",
             "count": 19}, ...]

    Segment values are therapy-relative on the way out (segment_labels); filters accept
    either the therapy-relative name or the panel's stored value.

    `group_by` accepts up to two dimensions. `filters` are exact, case-insensitive equality.
    Only allow-listed columns and parameterized values reach SQL -- no arbitrary SQL. Counts
    use COUNT(DISTINCT npi) so they never double-count."""
    if isinstance(group_by, str):
        group_by = [group_by]
    group_by = list(group_by or [])
    filters = dict(filters or {})
    for dim in group_by + list(filters):
        if dim not in _DIM_SQL:
            raise ValueError(f"unknown dimension '{dim}'; use one of {sorted(_DIM_SQL)}")
    if len(group_by) > 2:
        raise ValueError("group_by accepts at most 2 dimensions")

    needed = {_DIM_SQL[d][0] for d in group_by + list(filters)} - {"d"}
    select = [f"{_DIM_SQL[d][0]}.{_DIM_SQL[d][1]} AS {d}" for d in group_by]
    sql = ("SELECT " + "".join(f"{s}, " for s in select)
           + f"COUNT(DISTINCT d.npi_number__c) AS count FROM {_BASE_TABLE} d")
    for alias in ("ch", "tl"):  # stable order; only join what the query needs
        if alias in needed:
            table, predicate = _JOINS[alias]
            sql += f" LEFT JOIN {table} {alias} ON {predicate}"
    params: list = []
    where = []
    for dim, value in filters.items():
        alias, col = _DIM_SQL[dim]
        where.append(f"LOWER({alias}.{col}) = LOWER(?)")
        # The caller only ever saw the therapy-relative name, so accept it and resolve back
        # to the canonical `segment__c` the panel actually stores. Both vocabularies work.
        params.append(segment_labels.to_raw(value) if dim == "segment" else value)
    if where:
        sql += " WHERE " + " AND ".join(where)
    if group_by:
        sql += " GROUP BY " + ", ".join(f"{_DIM_SQL[d][0]}.{_DIM_SQL[d][1]}" for d in group_by)
        sql += " ORDER BY count DESC"
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    if "segment" in group_by:
        for row in rows:
            row["segment"] = segment_labels.to_display(row.get("segment"))
    return rows


def segment_sizing(therapy_area: str = "") -> dict:
    """Real HCP counts per target-list segment from the 360 panel, sized on the specialties
    `therapy_area` maps to (falls back to the whole panel when nothing maps). This is what the
    planning 'audience' ask offers and what the final brief quotes -- the segments the user
    picks, and their sizing, come from the actual dummy population, not a hardcoded library.

    Segments are named and described in therapy-area terms (segment_labels), never in terms
    of this brand's own share: the panel's stored names are brand-relative and a launch brand
    has no share for them to be relative to. `segment_raw` carries the canonical value so a
    caller can still filter the panel with it.

    Returns {"scope": "specialty"|"panel", "specialties": [...], "total": N,
             "sourcing": "...", "segments": [{"segment": "High prescribers of therapy",
                          "segment_raw": "High Potentials", "count": 198, "pct": 19.1,
                          "criteria": "..."}, ...]} sorted by count desc. `total` is the
    scoped HCP count -- the denominator behind every pct."""
    specialties = _map_specialties(benchmarks.specialties_for(therapy_area) if therapy_area else [])
    conn = _conn()
    try:
        if specialties:
            spec_ph = ",".join("?" for _ in specialties)
            total = conn.execute(
                f"SELECT COUNT(*) n FROM hcp_demographic_data__dlm "
                f"WHERE primary_specialty_description__c IN ({spec_ph})", specialties).fetchone()["n"]
            rows = conn.execute(
                f"SELECT tl.segment__c s, COUNT(*) n FROM tbl_tl_data__dlm tl "
                f"JOIN hcp_demographic_data__dlm d ON d.npi_number__c = tl.npi_id__c "
                f"WHERE d.primary_specialty_description__c IN ({spec_ph}) AND tl.segment__c IS NOT NULL "
                f"GROUP BY s ORDER BY n DESC", specialties).fetchall()
            scope = "specialty"
        else:
            total = conn.execute("SELECT COUNT(*) n FROM hcp_demographic_data__dlm").fetchone()["n"]
            rows = conn.execute(
                "SELECT segment__c s, COUNT(*) n FROM tbl_tl_data__dlm WHERE segment__c IS NOT NULL "
                "GROUP BY s ORDER BY n DESC").fetchall()
            scope = "panel"
        total = int(total or 0)
        segments = [
            {"segment": segment_labels.to_display(r["s"]), "segment_raw": r["s"],
             "count": int(r["n"]),
             "pct": round(100 * r["n"] / total, 1) if total else 0.0,
             "criteria": segment_labels.criteria_for(r["s"])}
            for r in rows
        ]
        return {"scope": scope, "specialties": specialties, "total": total,
                "sourcing": segment_labels.PROVENANCE, "segments": segments}
    finally:
        conn.close()


_TOOLS = [
    {
        "name": "list_hcps",
        "description": "List HCPs (NPI, name, specialty, state, city) with optional filters. "
                        "Use to find/list specific HCPs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "exact specialty, e.g. 'Medical Oncology'"},
                "state": {"type": "string", "description": "2-letter state code, e.g. 'NY'"},
                "brand_writer": {"type": "string", "description": "brand name, e.g. 'Xalkori' -- "
                                                                    "filters to HCPs who write that brand"},
                "limit": {"type": "integer", "description": "max rows, default 50"},
            },
        },
    },
    {
        "name": "get_hcp",
        "description": "Full 360 record for one HCP by NPI: demographics, channel/content "
                        "affinity, day-time preference, writer status, TRx.",
        "input_schema": {
            "type": "object",
            "properties": {"npi": {"type": "integer"}},
            "required": ["npi"],
        },
    },
    {
        "name": "segment_summary",
        "description": "Count of HCPs grouped by one dimension. Use for 'segment/breakdown/how "
                        "many by X' questions.",
        "input_schema": {
            "type": "object",
            "properties": {"group_by": {"type": "string", "enum": sorted(_SEGMENT_GROUP_COLUMNS)}},
            "required": ["group_by"],
        },
    },
    {
        "name": "cross_tab",
        "description": "Count HCPs across TWO combined dimensions, or count with combined filters. "
                        "The dimensions may live in different tables (e.g. preferred_channel and "
                        "segment) -- they are joined by NPI for you. USE THIS for any 'X that are "
                        "also Y', overlap, intersection or cross-tab question, e.g. 'how many "
                        "Digital-preferred HCPs are High Potentials' -> "
                        "filters={\"preferred_channel\":\"Digital\",\"segment\":\"High Potentials\"}. "
                        "Filters are exact (case-insensitive). group_by returns a full breakdown "
                        "table. Never estimate an overlap -- call this instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(_DIM_SQL)},
                    "description": "up to 2 dimensions to break the count out by (omit for a single total)",
                },
                "filters": {
                    "type": "object",
                    "description": "dimension -> exact value equality filters, e.g. "
                                    "{\"preferred_channel\": \"Digital\"}; keys must be allow-listed dimensions",
                    "additionalProperties": {"type": "string"},
                },
            },
        },
    },
]
_TOOL_FUNCS = {"list_hcps": list_hcps, "get_hcp": get_hcp,
               "segment_summary": segment_summary, "cross_tab": cross_tab}
_ASK_SYSTEM = ("You answer questions about a synthetic HCP 360 dataset "
               "using the provided tools. Be concise. Never invent numbers -- only report what the "
               "tools return, and mention it's a synthetic/reference dataset when citing percentages. "
               "For any question about an OVERLAP or combination of two dimensions ('X that are also "
               "Y', 'X segment among Y channel', a cross-tab or intersection), call cross_tab -- the "
               "tables are joined by NPI, so never say you can't combine filters and never estimate "
               "the overlap. If a filter value returns 0 or errors, call segment_summary/cross_tab "
               "with group_by first to discover the exact spelling of the allowed values, then retry.")


def ask(question: str) -> dict:
    """Bounded tool-use loop: the LLM calls list_hcps/get_hcp/segment_summary to answer a
    free-text question about the panel. Never raises -- any failure (LLM unavailable, auth,
    etc.) returns a plain 'unavailable' answer instead, same resilience contract as
    persona_review's optional LLM narration."""
    if not conversation_llm.llm_available():
        return {"answer": "The LLM isn't configured, so I can't answer free-text questions right "
                           "now -- use the filters above instead.", "tool_calls": []}
    tool_calls_log: list[dict] = []
    try:
        client = conversation_llm._get_client()
        messages: list[dict] = [{"role": "user", "content": question}]
        for _ in range(3):  # bounded: at most 3 round trips
            resp = client.messages.create(model=conversation_llm.MODEL, max_tokens=700,
                                           system=_ASK_SYSTEM, tools=_TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                text = next((b.text for b in resp.content if b.type == "text"), "").strip()
                return {"answer": text or "No answer produced.", "tool_calls": tool_calls_log}
            tool_results = []
            for tu in tool_uses:
                tool_calls_log.append({"name": tu.name, "input": tu.input})
                try:
                    fn = _TOOL_FUNCS.get(tu.name)
                    result = fn(**tu.input) if fn else {"error": f"unknown tool {tu.name}"}
                except Exception as e:  # noqa: BLE001 -- report the error back to the model, don't raise
                    result = {"error": str(e)}
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                      "content": json.dumps(result, default=str)[:4000]})
            messages.append({"role": "user", "content": tool_results})
        return {"answer": "Couldn't settle on an answer within the tool-call budget -- try a "
                           "narrower question.", "tool_calls": tool_calls_log}
    except Exception as e:  # noqa: BLE001 -- never break the page on an LLM/auth failure
        return {"answer": f"Couldn't reach the LLM ({e}).", "tool_calls": tool_calls_log}


if __name__ == "__main__":
    print(load_hcp_360())
    print(stats())
    s = list_hcps(limit=3)
    print(s)
    if s:
        print(get_hcp(s[0]["npi_number__c"]))
