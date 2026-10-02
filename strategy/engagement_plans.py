"""Engagement plans (docs/redesign/engagement-plan.md): the next N months for ONE brand --
objectives, the audience x objective shift map, the campaign portfolio, timeline, relative
budget, KPIs and risks.

A new store (`engagement_plans.db`), deliberately separate from the existing engagement-plan
records in strategy/hierarchy.py, which stay as they are (decision 3). Every save is a new
version, like v3 artifacts, so history, compare and restore come for free.

Brand IQ is the single input (decision: the brand plan reaches the engagement plan only through
Brand IQ's plan layer). Each plan records which Brand IQ plan it was built on, so it can be
flagged stale when the brand's active plan changes.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from paths import data_path  # noqa: E402

_FRAMEWORKS = Path(__file__).resolve().parent.parent / "config" / "frameworks"
# Pharma only (engagement-plan-v2.md). Brands differ by situation: lifecycle x archetype x access.
ARCHETYPES_FILE = "engagement_archetypes"
DEFAULT_MONTHS = 6

# The plan body's shape. Empty lists/None mean "not decided yet" and render as "Needs input".
EMPTY_BODY = {
    "situation": {"narrative": None, "baselines": [], "changes": [], "lessons": []},
    # v2 diagnosis chain: classify -> bucket -> root causes -> options -> chosen option
    "classification": None,  # {lifecycle, archetype, access, evidence: [{point, source}], status}
    "bucket": None,          # {indication, stages: [{stage, value, unit, conversion, source, year}], leaks: [...], gaps: [...]}
    "root_causes": [],       # {leak, audience, ladder_rung, belief, behaviour, evidence: [source]}
    "options": [],           # {id, name, thesis, leaks_addressed, impact, relative_cost, risk, time_to_effect, trade_off}
    "chosen_option": None,   # {ids: [...], note}
    "checks": None,          # {feasibility: [...], red_team: [...]}
    "objectives": [],      # {id, objective, kpi, baseline, target, by, serves, priority, source}
    "audiences": [],       # {id, name, size, lifecycle, why_now, funnel: {stage: {today, target}}, source}
    "shifts": [],          # {audience_id, objective_id, from, to, barrier, message, proof, moment, source}
    "campaigns": [],       # {id, name, type, audience_ids, shift_refs, message, channels, start, end, weight, kpi, status}
    "channels": [],        # {audience_id, mix: [{channel, role}], frequency_cap}
    "fixed_moments": [],   # {date, label, type, source}
    "budget": {"by_objective": {}, "by_audience": {}, "by_channel": {}},   # relative weights (%)
    "measurement": {"kpi_tree": [], "review_cadence": None},
    "risks": [],           # {risk, likelihood, impact, owner, mitigation}
    "assumptions": [],     # {text, status: proposed|accepted|changed, note}
    "sources": [],         # {label, page, detail} -- which Brand IQ pages fed the draft
}

_DB = None


def _conn() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        path = data_path("engagement_plans.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        _DB = sqlite3.connect(str(path), check_same_thread=False)
        _DB.row_factory = sqlite3.Row
        _DB.execute("""CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY, brand TEXT NOT NULL, industry TEXT NOT NULL, title TEXT,
            period_start TEXT, period_end TEXT, months INTEGER, status TEXT,
            brand_iq_plan TEXT, created_at TEXT, updated_at TEXT)""")
        _DB.execute("""CREATE TABLE IF NOT EXISTS versions (
            plan_id TEXT, version INTEGER, created_at TEXT, reason TEXT, body TEXT,
            PRIMARY KEY (plan_id, version))""")
        _DB.commit()
    return _DB


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def framework(archetype: str | None = None) -> dict:
    """The pharma archetype framework; with `archetype`, that archetype is also returned under
    "archetype" (its patient flow, typical leaks, audiences, modules)."""
    fw = json.loads((_FRAMEWORKS / f"{ARCHETYPES_FILE}.json").read_text(encoding="utf-8"))
    if archetype:
        arch = next((a for a in fw["archetypes"] if a["id"] == archetype), None)
        if not arch:
            raise KeyError(f"no archetype '{archetype}' (have: {', '.join(a['id'] for a in fw['archetypes'])})")
        fw = {**fw, "archetype": arch}
    return fw


def _add_months(d: _dt.date, months: int) -> _dt.date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    # last day of the period: the day before the same date `months` later
    start_next = _dt.date(y, m, min(d.day, 28))
    return start_next - _dt.timedelta(days=1)


def _active_brand_iq_plan(brand: str) -> str | None:
    import brand_kit
    kit = brand_kit.kit_for(brand) or {}
    return kit.get("active_plan") or ((kit.get("plans") or [{}])[0].get("id"))


def _view(meta: sqlite3.Row, ver: sqlite3.Row) -> dict:
    out = dict(meta)
    out.update(version=ver["version"], version_reason=ver["reason"], version_at=ver["created_at"],
               body=json.loads(ver["body"]))
    current = _active_brand_iq_plan(meta["brand"])
    out["stale"] = bool(meta["brand_iq_plan"] and current and current != meta["brand_iq_plan"])
    return out


def _latest(plan_id: str) -> sqlite3.Row | None:
    return _conn().execute("SELECT * FROM versions WHERE plan_id=? ORDER BY version DESC LIMIT 1", (plan_id,)).fetchone()


def create(brand: str, months: int | None = None, start: str | None = None, title: str | None = None) -> dict:
    """A new, empty engagement plan for one brand (decision 2). Period defaults to 6 months from
    the first of next month; the user can pick another length (decision 1)."""
    import brand_kit
    if not brand_kit.kit_for(brand):
        raise KeyError(f"no brand kit for '{brand}'")
    months = int(months or DEFAULT_MONTHS)
    if months < 1 or months > 24:
        raise ValueError("months must be between 1 and 24")
    today = _dt.date.today()
    s = _dt.date.fromisoformat(start) if start else (_dt.date(today.year + (today.month == 12), today.month % 12 + 1, 1))
    e = _add_months(s, months)
    pid = uuid.uuid4().hex[:12]
    now = _now()
    db = _conn()
    db.execute("INSERT INTO plans VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (pid, brand_kit.canonical_key(brand), "pharma",
                title or f"{brand_kit.canonical_key(brand)} engagement plan {s:%b %Y} - {e:%b %Y}",
                s.isoformat(), e.isoformat(), months, "draft", _active_brand_iq_plan(brand), now, now))
    db.execute("INSERT INTO versions VALUES (?,?,?,?,?)", (pid, 1, now, "Created", json.dumps(EMPTY_BODY)))
    db.commit()
    return get(pid)


def get(plan_id: str, version: int | None = None) -> dict | None:
    db = _conn()
    meta = db.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not meta:
        return None
    ver = (db.execute("SELECT * FROM versions WHERE plan_id=? AND version=?", (plan_id, version)).fetchone()
           if version else _latest(plan_id))
    return _view(meta, ver) if ver else None


def list_plans(brand: str | None = None) -> list[dict]:
    db = _conn()
    rows = (db.execute("SELECT * FROM plans WHERE lower(brand)=lower(?) ORDER BY updated_at DESC", (brand,)).fetchall()
            if brand else db.execute("SELECT * FROM plans ORDER BY updated_at DESC").fetchall())
    out = []
    for r in rows:
        v = _latest(r["id"])
        out.append({**dict(r), "version": v["version"] if v else None})
    return out


def save(plan_id: str, body: dict, reason: str, meta: dict | None = None) -> dict:
    """Store `body` as a new version. `meta` may update title/status/period fields."""
    db = _conn()
    if not db.execute("SELECT 1 FROM plans WHERE id=?", (plan_id,)).fetchone():
        raise KeyError(plan_id)
    merged = {**EMPTY_BODY, **(body or {})}
    v = (_latest(plan_id)["version"] or 0) + 1
    now = _now()
    db.execute("INSERT INTO versions VALUES (?,?,?,?,?)", (plan_id, v, now, reason or "Edited", json.dumps(merged)))
    allowed = {k: v2 for k, v2 in (meta or {}).items() if k in ("title", "status", "period_start", "period_end", "months")}
    sets = ", ".join(f"{k}=?" for k in allowed)
    db.execute(f"UPDATE plans SET {sets + ', ' if sets else ''}updated_at=? WHERE id=?", (*allowed.values(), now, plan_id))
    db.commit()
    return get(plan_id)


def versions(plan_id: str) -> list[dict]:
    rows = _conn().execute("SELECT version, created_at, reason FROM versions WHERE plan_id=? ORDER BY version DESC",
                           (plan_id,)).fetchall()
    return [dict(r) for r in rows]


def restore(plan_id: str, version: int) -> dict:
    old = get(plan_id, version)
    if not old:
        raise KeyError(f"{plan_id} v{version}")
    return save(plan_id, old["body"], f"Restored v{version}")
