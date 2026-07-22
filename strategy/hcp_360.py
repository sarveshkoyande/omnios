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
import benchmarks  # noqa: E402  (specialties_for() maps a therapy area to real specialties)
import conversation_llm  # noqa: E402  (shared Anthropic Foundry client for ask())

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config" / "hcp_360"
SCHEMA_PATH = BASE_DIR / "db" / "hcp_360_schema.sql"
DB_PATH = data_path("hcp_360.db")

# Load order matters: demographic first -- every other table's npi column REFERENCES it.
_FILES = [
    ("pfizer_demographic_data__dlm", "pfizer_demographic_data__dlm.json"),
    ("global_channel_affinity_and_preference", "global_channel_affinity_and_preference.json"),
    ("pf_global_content_affinity_score_data", "pf_global_content_affinity_score_data.json"),
    ("tbl_trx_therapeutic_data__dlm", "tbl_trx_therapeutic_data__dlm.json"),
    ("global_day_time_preference_data", "global_day_time_preference_data.json"),
    ("tbl_pfizer_tl_data__dlm", "tbl_pfizer_tl_data__dlm.json"),
]


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if missing (idempotent)."""
    conn = _conn()
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


def load_hcp_360(force: bool = False) -> dict:
    """Bulk-load the six JSON files into hcp_360.db. Idempotent: no-ops if the
    demographic table already has rows, unless force=True (which deletes all six tables,
    children first, then reloads)."""
    init_db()
    conn = _conn()
    try:
        already = conn.execute(
            "SELECT COUNT(*) n FROM pfizer_demographic_data__dlm"
        ).fetchone()["n"]
        if already and not force:
            return {"loaded": False, "reason": "already loaded", "npi_count": already}
        if force:
            for table, _ in reversed(_FILES):
                conn.execute(f"DELETE FROM {table}")
        counts = {}
        for table, filename in _FILES:
            counts[table] = _load_table(conn, CONFIG_DIR / filename, table)
        conn.commit()
        return {"loaded": True, "counts": counts}
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
            "SELECT * FROM pfizer_demographic_data__dlm WHERE npi_number__c=?", (npi,)
        ).fetchone()
        if not d:
            return None
        out = dict(d)
        c = conn.execute(
            "SELECT * FROM global_channel_affinity_and_preference WHERE npi_number__c=?", (npi,)
        ).fetchone()
        out["channel_affinity"] = dict(c) if c else None
        k = conn.execute(
            "SELECT * FROM pf_global_content_affinity_score_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["content_affinity"] = dict(k) if k else None
        dt = conn.execute(
            "SELECT * FROM global_day_time_preference_data WHERE npi_num__c=?", (npi,)
        ).fetchone()
        out["day_time_preference"] = dict(dt) if dt else None
        tl = conn.execute(
            "SELECT * FROM tbl_pfizer_tl_data__dlm WHERE npi_id__c=?", (npi,)
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
               "FROM pfizer_demographic_data__dlm WHERE 1=1")
        params: list = []
        if specialty:
            sql += " AND primary_specialty_description__c = ?"
            params.append(specialty)
        if state:
            sql += " AND state_code__c = ?"
            params.append(state)
        if brand_writer:
            sql += (" AND npi_number__c IN "
                     "(SELECT npi_id__c FROM tbl_pfizer_tl_data__dlm WHERE brand__c = ?)")
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
# vocabulary (Title Case, see config/hcp_360/pfizer_demographic_data__dlm.json). Deliberately
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
            f"SELECT npi_number__c FROM pfizer_demographic_data__dlm "
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
            f"SELECT most_preferred_content_tag__c t, COUNT(*) n FROM pf_global_content_affinity_score_data "
            f"WHERE npi_num__c IN ({npi_ph}) AND most_preferred_content_tag__c IS NOT NULL "
            f"GROUP BY t ORDER BY n DESC LIMIT 3", npis).fetchall()
        top_content_tags = [r["t"] for r in tag_rows]

        seg_rows = conn.execute(
            f"SELECT segment__c s, COUNT(*) n FROM tbl_pfizer_tl_data__dlm "
            f"WHERE npi_id__c IN ({npi_ph}) GROUP BY s ORDER BY n DESC", npis).fetchall()
        segment_breakdown = {r["s"]: round(100 * r["n"] / n, 1) for r in seg_rows if r["s"]}

        onc_n = conn.execute(
            f"SELECT COUNT(*) n FROM tbl_pfizer_tl_data__dlm WHERE npi_id__c IN ({npi_ph}) AND "
            f"(xalkori_writer__c=1 OR besponsa_writer__c=1 OR bosulif_writers__c=1 OR mylotarg_writer__c=1)",
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
    "specialty": ("pfizer_demographic_data__dlm", "primary_specialty_description__c"),
    "state": ("pfizer_demographic_data__dlm", "state_code__c"),
    "preferred_channel": ("global_channel_affinity_and_preference", "preferred_channel__c"),
    "segment": ("tbl_pfizer_tl_data__dlm", "segment__c"),
    "writing_persona": ("tbl_pfizer_tl_data__dlm", "writing_persona__c"),
    "brand": ("tbl_pfizer_tl_data__dlm", "brand__c"),
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
        return [dict(r) for r in rows]
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
]
_TOOL_FUNCS = {"list_hcps": list_hcps, "get_hcp": get_hcp, "segment_summary": segment_summary}
_ASK_SYSTEM = ("You answer questions about a synthetic HCP 360 dataset (500 healthcare providers) "
               "using the provided tools. Be concise. Never invent numbers -- only report what the "
               "tools return, and mention it's a synthetic/reference dataset when citing percentages.")


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
