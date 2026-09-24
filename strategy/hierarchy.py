"""Brand > Engagement Plan > Campaign > Flow (plan docs/plans/2026-09-24-1400-feat-brand-hierarchy-ia-plan.md).

Every level lives in campaigns.db (KTD1): `engagement_plan`, the existing `campaign` table
(linked by `campaign.engagement_plan_id`), and `flow`. A brand is its brand-kit key
(`brand.kit_key`, KTD4). Each record is created inside an existing parent (R8), campaign
status is derived from facts (KTD5), and `backfill()` places existing work into one
"Earlier work" engagement plan per brand (R20).
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import db  # noqa: E402
# Package imports so this shares the server's module instances (brand_kit's cache in
# particular -- see brand_journey.py).
from strategy import brand_kit, campaign_store  # noqa: E402

EARLIER_WORK = "Earlier work"
PLAN_STATUSES = ("active", "closed")
CAMPAIGN_STATUSES = ("draft", "in_progress", "confirmed", "closed")
FLOW_ORIGINS = ("journey", "campaign_plan", "manual", "legacy_layout")


class NotFound(KeyError):
    """An unknown brand, engagement plan, campaign or flow."""


def _now() -> str:
    return campaign_store._now()


_ready: set[str] = set()


def _conn():
    # init_db runs the whole schema script plus the column checks; once per data file is enough.
    path = str(campaign_store.DB_PATH)
    if path not in _ready:
        campaign_store.init_db()
        _ready.add(path)
    return db.connect("campaigns")


def _row(r) -> dict:
    return dict(r) if r is not None else {}


# --------------------------------------------------------------------------- brands ----

def brand_key(brand: str) -> str:
    """The brand-kit key for `brand` (case-insensitive), or NotFound."""
    key = brand_kit.canonical_key(brand or "")
    if key is None:
        raise NotFound(f"no brand '{brand}'")
    return key


def _brand_id(conn, brand: str) -> tuple[int, str]:
    key = brand_key(brand)
    return campaign_store.brand_row_for_kit(conn, key), key


# ------------------------------------------------------------------ engagement plans ----

def _check_period(start, end) -> tuple[str | None, str | None]:
    out = []
    for v in (start, end):
        if v in (None, ""):
            out.append(None)
            continue
        try:
            out.append(_dt.date.fromisoformat(str(v)).isoformat())
        except ValueError:
            raise ValueError(f"'{v}' is not a date (YYYY-MM-DD)") from None
    if out[0] and out[1] and out[1] < out[0]:
        raise ValueError("the period ends before it starts")
    return out[0], out[1]


def _plan_dict(conn, r) -> dict:
    d = _row(r)
    b = conn.execute("SELECT kit_key FROM brand WHERE id=?", (d["brand_id"],)).fetchone()
    d["brand"] = b["kit_key"] if b else None
    return d


def create_plan(brand: str, name: str, period_start=None, period_end=None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("an engagement plan needs a name")
    start, end = _check_period(period_start, period_end)
    conn = _conn()
    try:
        bid, _ = _brand_id(conn, brand)
        cur = conn.execute(
            "INSERT INTO engagement_plan (brand_id, name, period_start, period_end, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)", (bid, name, start, end, "active", _now(), _now()))
        conn.commit()
        return get_plan(cur.lastrowid)
    finally:
        conn.close()


def get_plan(plan_id: int) -> dict:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM engagement_plan WHERE id=?", (plan_id,)).fetchone()
        if r is None:
            raise NotFound(f"no engagement plan {plan_id}")
        return _plan_dict(conn, r)
    finally:
        conn.close()


def list_plans(brand: str) -> list[dict]:
    conn = _conn()
    try:
        bid, _ = _brand_id(conn, brand)
        conn.commit()
        rows = conn.execute("SELECT * FROM engagement_plan WHERE brand_id=? "
                            "ORDER BY COALESCE(period_start, created_at) DESC, id DESC", (bid,)).fetchall()
        return [_plan_dict(conn, r) for r in rows]
    finally:
        conn.close()


def update_plan(plan_id: int, **fields) -> dict:
    cur = get_plan(plan_id)
    name = fields.get("name", cur["name"])
    if not (name or "").strip():
        raise ValueError("an engagement plan needs a name")
    start, end = _check_period(fields.get("period_start", cur["period_start"]),
                               fields.get("period_end", cur["period_end"]))
    status = fields.get("status", cur["status"])
    if status not in PLAN_STATUSES:
        raise ValueError(f"status must be one of {', '.join(PLAN_STATUSES)}")
    conn = _conn()
    try:
        conn.execute("UPDATE engagement_plan SET name=?, period_start=?, period_end=?, status=?, updated_at=? "
                     "WHERE id=?", (name.strip(), start, end, status, _now(), plan_id))
        conn.commit()
    finally:
        conn.close()
    return get_plan(plan_id)


def _earlier_work_plan(conn, brand_id: int) -> int:
    r = conn.execute("SELECT id FROM engagement_plan WHERE brand_id=? AND name=? ORDER BY id LIMIT 1",
                     (brand_id, EARLIER_WORK)).fetchone()
    if r:
        return r["id"]
    cur = conn.execute(
        "INSERT INTO engagement_plan (brand_id, name, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (brand_id, EARLIER_WORK, "active", _now(), _now()))
    return cur.lastrowid


# ------------------------------------------------------------------------- campaigns ----

def _derive_status(conn, c: dict) -> str:
    """KTD5: closed stays closed; a Campaign Plan is confirmed once a version exists (Deploy
    done); flows-only campaigns are confirmed when every flow is; anything underway is
    in_progress; otherwise draft."""
    if c["status"] == "closed":
        return "closed"
    flows = [r["status"] for r in conn.execute("SELECT status FROM flow WHERE campaign_id=?", (c["id"],))]
    if c.get("project_id"):
        versions = conn.execute("SELECT COUNT(*) AS n FROM campaign_version WHERE campaign_id=?",
                                (c["id"],)).fetchone()["n"]
        if versions:
            return "confirmed"
        return "in_progress" if (c.get("status_detail") or flows) else "draft"
    if flows:
        return "confirmed" if all(s == "confirmed" for s in flows) else "in_progress"
    return "draft"


def _refresh_status(conn, campaign_id: int) -> None:
    r = conn.execute("SELECT * FROM campaign WHERE id=?", (campaign_id,)).fetchone()
    if r is None:
        return
    status = _derive_status(conn, dict(r))
    if status != r["status"]:
        conn.execute("UPDATE campaign SET status=?, updated_at=? WHERE id=?", (status, _now(), campaign_id))


def _campaign_dict(conn, r) -> dict:
    c = _row(r)
    snapshot = c.pop("snapshot_json", None)
    c["has_campaign_plan"] = bool(c.get("project_id"))
    c["versions"] = conn.execute("SELECT COUNT(*) AS n FROM campaign_version WHERE campaign_id=?",
                                 (c["id"],)).fetchone()["n"]
    c["flow_count"] = conn.execute("SELECT COUNT(*) AS n FROM flow WHERE campaign_id=?",
                                   (c["id"],)).fetchone()["n"]
    b = conn.execute("SELECT kit_key FROM brand WHERE id=?", (c["brand_id"],)).fetchone() if c.get("brand_id") else None
    c["brand"] = b["kit_key"] if b else None
    d = _drift(_json(snapshot), c["brand"]) if c["brand"] else {"tracked": False, "changed": {}}
    c["content"] = {"tracked": d["tracked"], "changed_steps": list(d["changed"]),
                    "snapshot_at": c.get("snapshot_at")}
    return c


def create_campaign(plan_id: int, name: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("a campaign needs a name")
    plan = get_plan(plan_id)
    if plan["status"] == "closed":
        raise ValueError("this engagement plan is closed")
    conn = _conn()
    try:
        snap = take_snapshot(plan["brand"])
        cur = conn.execute(
            "INSERT INTO campaign (brand_id, engagement_plan_id, name, status, snapshot_json, snapshot_at, "
            "start_date, end_date, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (plan["brand_id"], plan_id, name, "draft", json.dumps(snap), snap["taken_at"],
             start_date or None, end_date or None, _now(), _now()))
        conn.commit()
        return get_campaign(cur.lastrowid)
    finally:
        conn.close()


def schedule_campaign(campaign_id: int, start_date: str | None, end_date: str | None) -> dict:
    """When a campaign is meant to run, for the engagement plan's timeline (R21). Either
    date may be cleared by passing an empty string."""
    get_campaign(campaign_id)
    conn = _conn()
    try:
        conn.execute("UPDATE campaign SET start_date=?, end_date=?, updated_at=? WHERE id=?",
                     (start_date or None, end_date or None, _now(), campaign_id))
        conn.commit()
    finally:
        conn.close()
    return get_campaign(campaign_id)


def get_campaign(campaign_id: int) -> dict:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        if r is None:
            raise NotFound(f"no campaign {campaign_id}")
        return _campaign_dict(conn, r)
    finally:
        conn.close()


def list_campaigns(plan_id: int) -> list[dict]:
    get_plan(plan_id)
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM campaign WHERE engagement_plan_id=? ORDER BY updated_at DESC, id DESC",
                            (plan_id,)).fetchall()
        return [_campaign_dict(conn, r) for r in rows]
    finally:
        conn.close()


def rename_campaign(campaign_id: int, name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("a campaign needs a name")
    get_campaign(campaign_id)
    conn = _conn()
    try:
        conn.execute("UPDATE campaign SET name=?, updated_at=? WHERE id=?", (name, _now(), campaign_id))
        conn.commit()
    finally:
        conn.close()
    return get_campaign(campaign_id)


def move_campaign(campaign_id: int, target_plan_id: int) -> dict:
    """Same brand: the campaign moves (R17). Another brand: it is closed and a new campaign
    opens in the target plan, taking over the Campaign Plan's project so later versions attach
    there (R16). Flows stay with the closed campaign -- they were built from the old brand."""
    c = get_campaign(campaign_id)
    if c["status"] == "closed":
        raise ValueError("a closed campaign can't be moved")
    target = get_plan(target_plan_id)
    if target["status"] == "closed":
        raise ValueError("the target engagement plan is closed")
    conn = _conn()
    try:
        if target["brand_id"] == c["brand_id"]:
            conn.execute("UPDATE campaign SET engagement_plan_id=?, updated_at=? WHERE id=?",
                         (target_plan_id, _now(), campaign_id))
            conn.commit()
            return get_campaign(campaign_id)
        conn.execute("UPDATE campaign SET status='closed', closed_at=?, updated_at=? WHERE id=?",
                     (_now(), _now(), campaign_id))
        snap = take_snapshot(target["brand"])
        cur = conn.execute(
            "INSERT INTO campaign (project_id, brand_id, engagement_plan_id, name, status, status_detail, "
            "snapshot_json, snapshot_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (c.get("project_id"), target["brand_id"], target_plan_id, c["name"], "draft",
             c.get("status_detail"), json.dumps(snap), snap["taken_at"], _now(), _now()))
        new_id = cur.lastrowid
        plan_flow = conn.execute("SELECT id FROM flow WHERE campaign_id=? AND origin='campaign_plan'",
                                 (campaign_id,)).fetchone()
        if plan_flow and c.get("project_id"):
            from strategy import projects as pstore
            layout = (pstore.get_project(c["project_id"]) or {}).get("campaign_plan_layout")
            conn.execute("UPDATE flow SET layout_json=? WHERE id=?",
                         (json.dumps(layout) if layout else None, plan_flow["id"]))
            _ensure_plan_flow(conn, new_id)
        _refresh_status(conn, new_id)
        conn.commit()
    finally:
        conn.close()
    if c.get("project_id"):
        _set_project_brand(c["project_id"], target["brand"])
    return get_campaign(new_id)


def _set_project_brand(project_id: str, brand: str) -> None:
    from strategy import projects as pstore
    proj = pstore.get_project(project_id)
    if proj:
        state = proj["state"]
        state.setdefault("slots", {})["brand"] = brand
        pstore.save_project(project_id, state=state)


# ---------------------------------------------------------------------- provenance ----
# Idea 5 (P-R1..P-R6): a campaign keeps the brand content it was built from.

SNAPSHOT_STEPS = ("brief", "audience", "message", "kit")


def take_snapshot(brand: str) -> dict:
    """The brand's current Brief/Audience/Message/Kit answers plus the kit itself (flows
    build from it), as of now."""
    from strategy import brand_journey
    key = brand_key(brand)
    return {"taken_at": _now(), "kit": brand_kit.kit_for(key) or {}, "answers": brand_journey.answers_for(key)}


def _norm(v):
    from strategy import journey_fields as jf
    return json.dumps(v, sort_keys=True) if jf.has_value(v) else None


def _drift(snapshot: dict | None, brand: str, detail: bool = False) -> dict:
    """What changed in the brand's content since `snapshot`, per step (P-R3)."""
    if not snapshot:
        return {"tracked": False, "changed": {}}
    from strategy import brand_journey, journey_fields as jf
    current = brand_journey.answers_for(brand)
    changed: dict[str, list] = {}
    for step in SNAPSHOT_STEPS:
        for f in jf.fields_for(step):
            key = f["key"]
            if key == "brand_name":
                continue
            then, now = snapshot["answers"].get(key), current.get(key)
            if _norm(then) != _norm(now):
                entry = {"key": key, "label": key.replace("_", " ").capitalize()}
                if detail:
                    entry.update({"then": then, "now": now})
                changed.setdefault(step, []).append(entry)
    return {"tracked": True, "changed": changed}


def campaign_snapshot(campaign_id: int) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT snapshot_json FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        if r is None:
            raise NotFound(f"no campaign {campaign_id}")
        return _json(r["snapshot_json"])
    finally:
        conn.close()


def drift(campaign_id: int) -> dict:
    """P-R3/P-R4: per step, each field whose current value differs from the campaign's
    snapshot, with both values. Untracked (legacy) campaigns say so (P-R6)."""
    c = get_campaign(campaign_id)
    snap = campaign_snapshot(campaign_id)
    d = _drift(snap, c["brand"], detail=True)
    return {"campaign_id": campaign_id, "tracked": d["tracked"], "snapshot_at": c.get("snapshot_at"),
            "has_drift": bool(d["changed"]), "changed": d["changed"]}


def refresh_snapshot(campaign_id: int) -> dict:
    """P-KD3: take a new snapshot, then rebuild the campaign's rules flows from it with their
    kept edits reapplied; reports edits a rebuild had to drop."""
    c = get_campaign(campaign_id)
    if c["status"] == "closed":
        raise ValueError("this campaign is closed")
    snap = take_snapshot(c["brand"])
    conn = _conn()
    try:
        conn.execute("UPDATE campaign SET snapshot_json=?, snapshot_at=?, updated_at=? WHERE id=?",
                     (json.dumps(snap), snap["taken_at"], _now(), campaign_id))
        conn.commit()
        rebuild = [r["id"] for r in conn.execute(
            "SELECT id FROM flow WHERE campaign_id=? AND kind='rules' AND base_json IS NOT NULL", (campaign_id,))]
    finally:
        conn.close()
    from strategy import brand_journey
    flows = []
    for fid in rebuild:
        doc = brand_journey.build_flow_by_id(fid)
        flows.append({"flow_id": fid, "status": doc["status"], "dropped": doc.get("dropped", [])})
    return {**drift(campaign_id), "flows": flows}


# ----------------------------------------------------------------------------- flows ----

def create_flow(campaign_id: int, name: str, origin: str = "manual") -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("a flow needs a name")
    if origin not in FLOW_ORIGINS:
        raise ValueError(f"origin must be one of {', '.join(FLOW_ORIGINS)}")
    c = get_campaign(campaign_id)
    if c["status"] == "closed":
        raise ValueError("this campaign is closed")
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO flow (campaign_id, name, origin, status, created_at, updated_at) "
                           "VALUES (?,?,?,?,?,?)", (campaign_id, name, origin, "draft", _now(), _now()))
        _refresh_status(conn, campaign_id)
        conn.commit()
        return get_flow(cur.lastrowid)
    finally:
        conn.close()


def get_flow(flow_id: int) -> dict:
    conn = _conn()
    try:
        r = conn.execute("SELECT id, campaign_id, name, origin, status, created_at, updated_at FROM flow WHERE id=?",
                         (flow_id,)).fetchone()
        if r is None:
            raise NotFound(f"no flow {flow_id}")
        return _row(r)
    finally:
        conn.close()


def list_flows(campaign_id: int) -> list[dict]:
    get_campaign(campaign_id)
    conn = _conn()
    try:
        rows = conn.execute("SELECT id, campaign_id, name, origin, status, created_at, updated_at FROM flow "
                            "WHERE campaign_id=? ORDER BY updated_at DESC, id DESC", (campaign_id,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


PLAN_FLOW = "Campaign Plan flow"
FIRST_PLAN = "First engagement plan"
FIRST_CAMPAIGN = "Launch campaign"
JOURNEY_FLOW = "Journey flow"


def _json(v):
    return json.loads(v) if v else None


def flow_storage(flow_id: int) -> dict:
    """A flow's stored document (U-R1): base (rules-built plan + codes), kept ops, pending
    draft ops, dropped ops, plus its campaign and brand."""
    conn = _conn()
    try:
        r = conn.execute(
            "SELECT f.*, c.status AS campaign_status, c.project_id, c.snapshot_json AS campaign_snapshot, "
            "b.kit_key AS brand FROM flow f "
            "JOIN campaign c ON c.id=f.campaign_id LEFT JOIN brand b ON b.id=c.brand_id WHERE f.id=?",
            (flow_id,)).fetchone()
        if r is None:
            raise NotFound(f"no flow {flow_id}")
        return {"id": r["id"], "campaign_id": r["campaign_id"], "name": r["name"], "origin": r["origin"],
                "kind": r["kind"], "status": r["status"], "brand": r["brand"],
                "campaign_status": r["campaign_status"], "project_id": r["project_id"],
                "frozen_layout": _json(r["layout_json"]), "campaign_snapshot": _json(r["campaign_snapshot"]),
                "base": _json(r["base_json"]), "ops": _json(r["ops_json"]) or [],
                "draft_ops": _json(r["draft_ops_json"]), "dropped": _json(r["dropped_json"]) or []}
    finally:
        conn.close()


_UNSET = object()


def save_flow_storage(flow_id: int, base=_UNSET, ops=_UNSET, dropped=_UNSET, draft_ops=_UNSET,
                      status=_UNSET) -> None:
    sets, vals = [], []
    for col, v in (("base_json", base), ("ops_json", ops), ("dropped_json", dropped),
                   ("draft_ops_json", draft_ops)):
        if v is not _UNSET:
            sets.append(f"{col}=?")
            vals.append(json.dumps(v) if v not in (None, []) or col == "ops_json" else None)
    if status is not _UNSET:
        sets.append("status=?")
        vals.append(status)
    if not sets:
        return
    conn = _conn()
    try:
        r = conn.execute("SELECT campaign_id FROM flow WHERE id=?", (flow_id,)).fetchone()
        if r is None:
            raise NotFound(f"no flow {flow_id}")
        conn.execute(f"UPDATE flow SET {', '.join(sets)}, updated_at=? WHERE id=?", (*vals, _now(), flow_id))
        _refresh_status(conn, r["campaign_id"])
        conn.commit()
    finally:
        conn.close()


def _ensure_plan_flow(conn, campaign_id: int) -> int:
    r = conn.execute("SELECT id FROM flow WHERE campaign_id=? AND origin='campaign_plan' ORDER BY id LIMIT 1",
                     (campaign_id,)).fetchone()
    if r:
        return r["id"]
    cur = conn.execute(
        "INSERT INTO flow (campaign_id, name, origin, kind, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)", (campaign_id, PLAN_FLOW, "campaign_plan", "document", "built", _now(), _now()))
    _refresh_status(conn, campaign_id)
    return cur.lastrowid


def ensure_plan_flow(project_id: str) -> int | None:
    """The Campaign Plan's Operations diagram as a flow of its campaign (U6): a "document"
    flow whose content is the project's campaign_plan_layout. Called when that layout is
    saved; a project with no open campaign has none."""
    conn = _conn()
    try:
        r = conn.execute("SELECT id FROM campaign WHERE project_id=? AND status<>'closed' ORDER BY id DESC LIMIT 1",
                         (project_id,)).fetchone()
        if r is None:
            return None
        fid = _ensure_plan_flow(conn, r["id"])
        conn.commit()
        return fid
    finally:
        conn.close()


def journey_flow_id(brand: str) -> int | None:
    """The brand's Journey-built flow (the Journey's Flow step shows this one), if any."""
    key = brand_key(brand)
    conn = _conn()
    try:
        r = conn.execute(
            "SELECT f.id FROM flow f JOIN campaign c ON c.id=f.campaign_id JOIN brand b ON b.id=c.brand_id "
            "WHERE b.kit_key=? AND f.origin='journey' AND c.status<>'closed' ORDER BY f.id DESC LIMIT 1",
            (key,)).fetchone()
        return r["id"] if r else None
    finally:
        conn.close()


def open_campaigns(brand: str) -> list[dict]:
    """The brand's campaigns a new flow can go into, with their engagement plan's name."""
    out = []
    for p in list_plans(brand):
        if p["status"] == "closed":
            continue
        for c in list_campaigns(p["id"]):
            if c["status"] != "closed":
                out.append({"id": c["id"], "name": c["name"], "engagement_plan_id": p["id"],
                            "engagement_plan": p["name"]})
    return out


class NeedsCampaign(ValueError):
    """The brand already has engagement plans: the caller must say which campaign."""


def ensure_journey_flow(brand: str, campaign_id: int | None = None) -> int:
    """R22: the Journey's flow lives in a campaign. With no engagement plans yet, create
    "First engagement plan" > "Launch campaign" for it; otherwise the flow goes into the
    campaign the user picked (NeedsCampaign when none was given)."""
    existing = journey_flow_id(brand)
    if existing is not None:
        return existing
    key = brand_key(brand)
    if campaign_id is None:
        if list_plans(key):
            raise NeedsCampaign("choose the campaign this flow belongs to")
        plan = create_plan(key, FIRST_PLAN)
        campaign_id = create_campaign(plan["id"], FIRST_CAMPAIGN)["id"]
    else:
        c = get_campaign(campaign_id)
        if c["brand"] != key:
            raise ValueError("that campaign belongs to another brand")
    return create_flow(campaign_id, JOURNEY_FLOW, origin="journey")["id"]


def delete_journey_flows(brand: str) -> int:
    """R19: wiping a brand's Journey deletes the flows it created, nothing else."""
    key = brand_kit.canonical_key(brand or "")
    if key is None:
        return 0
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT f.id, f.campaign_id FROM flow f JOIN campaign c ON c.id=f.campaign_id "
            "JOIN brand b ON b.id=c.brand_id WHERE b.kit_key=? AND f.origin='journey'", (key,)).fetchall()
        for r in rows:
            conn.execute("DELETE FROM flow WHERE id=?", (r["id"],))
            _refresh_status(conn, r["campaign_id"])
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def set_flow_status(flow_id: int, status: str) -> dict:
    if status not in ("built", "confirmed"):
        raise ValueError("status must be built or confirmed")
    rec = flow_storage(flow_id)
    if rec["kind"] != "rules" or not rec["base"]:
        raise ValueError("build the flow before confirming it")
    save_flow_storage(flow_id, status=status)
    return get_flow(flow_id)


def summary_counts() -> dict:
    """Per kit brand: active engagement plans and open campaigns (the Cockpit rail badges, R-R4)."""
    conn = _conn()
    try:
        out: dict[str, dict] = {}
        for r in conn.execute(
                "SELECT b.kit_key AS brand, "
                "(SELECT COUNT(*) FROM engagement_plan e WHERE e.brand_id=b.id AND e.status='active') AS plans, "
                "(SELECT COUNT(*) FROM campaign c JOIN engagement_plan e ON e.id=c.engagement_plan_id "
                " WHERE e.brand_id=b.id AND c.status<>'closed') AS campaigns "
                "FROM brand b WHERE b.kit_key IS NOT NULL"):
            out[r["brand"]] = {"active_plans": r["plans"], "open_campaigns": r["campaigns"]}
        return out
    finally:
        conn.close()


# ------------------------------------------------------------------------------ tree ----

def tree(brand: str) -> dict:
    key = brand_key(brand)
    plans = list_plans(key)
    for p in plans:
        p["campaigns"] = list_campaigns(p["id"])
        for c in p["campaigns"]:
            c["flows"] = list_flows(c["id"])
    return {"brand": key, "engagement_plans": plans}


# -------------------------------------------------------------------- Campaign Plans ----

def open_campaign_for_project(project_id: str) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM campaign WHERE project_id=? AND status<>'closed' ORDER BY id DESC LIMIT 1",
                         (project_id,)).fetchone()
        return _campaign_dict(conn, r) if r else None
    finally:
        conn.close()


def bind_project(campaign_id: int, project_id: str) -> dict:
    """Link a newly created Campaign Plan project to its campaign (R13)."""
    c = get_campaign(campaign_id)
    if c["status"] == "closed":
        raise ValueError("this campaign is closed")
    if c.get("project_id"):
        raise ValueError("this campaign already has a campaign plan")
    conn = _conn()
    try:
        conn.execute("UPDATE campaign SET project_id=?, updated_at=? WHERE id=?", (project_id, _now(), campaign_id))
        _refresh_status(conn, campaign_id)
        conn.commit()
    finally:
        conn.close()
    return get_campaign(campaign_id)


def mark_plan_phase(project_id: str, phase: str) -> None:
    """A Campaign Plan phase ran: record it so the campaign reads in_progress (KTD5)."""
    conn = _conn()
    try:
        r = conn.execute("SELECT id FROM campaign WHERE project_id=? AND status<>'closed' ORDER BY id DESC LIMIT 1",
                         (project_id,)).fetchone()
        if r is None:
            return
        conn.execute("UPDATE campaign SET status_detail=?, updated_at=? WHERE id=?", (phase, _now(), r["id"]))
        _refresh_status(conn, r["id"])
        conn.commit()
    finally:
        conn.close()


def after_plan_saved(campaign_id: int) -> None:
    """A Campaign Plan version was stored: place an unlinked campaign (a plan started outside
    the hierarchy, which only the legacy frontend/ home can still do) under its kit brand's
    "Earlier work" plan, and refresh its status."""
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        if r is None:
            return
        if r["engagement_plan_id"] is None and r["brand_id"] is not None:
            b = conn.execute("SELECT kit_key FROM brand WHERE id=?", (r["brand_id"],)).fetchone()
            if b and b["kit_key"]:
                conn.execute("UPDATE campaign SET engagement_plan_id=? WHERE id=?",
                             (_earlier_work_plan(conn, r["brand_id"]), campaign_id))
        _refresh_status(conn, campaign_id)
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------------------------------- backfill ----

def backfill() -> dict:
    """Idempotent (R20). Links brand rows to kits, folds duplicate campaigns of one project
    into one campaign with numbered versions, places unplaced campaigns and kit-brand projects
    without a campaign into the brand's "Earlier work" plan, and logs what it can't place."""
    from strategy import projects as pstore
    out = {"linked_brands": 0, "folded": 0, "placed": 0, "created": 0, "unplaced": []}
    conn = _conn()
    try:
        # 1. Brand rows whose name matches a kit.
        for r in conn.execute("SELECT id, name FROM brand WHERE kit_key IS NULL").fetchall():
            key = brand_kit.canonical_key(r["name"])
            if key and not conn.execute("SELECT 1 FROM brand WHERE kit_key=?", (key,)).fetchone():
                conn.execute("UPDATE brand SET kit_key=? WHERE id=?", (key, r["id"]))
                out["linked_brands"] += 1
        # Campaigns pointing at a duplicate-name brand row move to the kit's row.
        for r in conn.execute("SELECT c.id, b.name FROM campaign c JOIN brand b ON b.id=c.brand_id "
                              "WHERE b.kit_key IS NULL").fetchall():
            key = brand_kit.canonical_key(r["name"])
            if key:
                conn.execute("UPDATE campaign SET brand_id=? WHERE id=?",
                             (campaign_store.brand_row_for_kit(conn, key), r["id"]))

        # 2. Fold duplicates: several open campaigns for one project -> the oldest keeps them
        # all as versions, in creation order. The duplicates' derived rows are dropped (their
        # plan and result live on in the moved versions' blobs).
        dup_projects = conn.execute(
            "SELECT project_id FROM campaign WHERE project_id IS NOT NULL AND status<>'closed' "
            "GROUP BY project_id HAVING COUNT(*) > 1").fetchall()
        for d in dup_projects:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM campaign WHERE project_id=? AND status<>'closed' ORDER BY id", (d["project_id"],))]
            keeper, extra = ids[0], ids[1:]
            versions = conn.execute(
                "SELECT id FROM campaign_version WHERE campaign_id IN (%s) ORDER BY created_at, id"
                % ",".join("?" * len(ids)), ids).fetchall()
            # Park numbers out of the way first so the UNIQUE(campaign_id, version_no) holds.
            for i, v in enumerate(versions, start=1):
                conn.execute("UPDATE campaign_version SET campaign_id=?, version_no=? WHERE id=?",
                             (keeper, -i, v["id"]))
            for i, v in enumerate(versions, start=1):
                conn.execute("UPDATE campaign_version SET version_no=? WHERE id=?", (i, v["id"]))
            for cid in extra:
                conn.execute("UPDATE flow SET campaign_id=? WHERE campaign_id=?", (keeper, cid))
                for table in ("campaign_segment", "campaign_message", "campaign_channel", "campaign_kpi"):
                    conn.execute(f"DELETE FROM {table} WHERE campaign_id=?", (cid,))
                conn.execute("DELETE FROM campaign WHERE id=?", (cid,))
                out["folded"] += 1

        # 3. Unplaced campaigns of a kit brand -> "Earlier work".
        for r in conn.execute("SELECT c.id, c.brand_id, c.project_id, b.kit_key, b.name FROM campaign c "
                              "LEFT JOIN brand b ON b.id=c.brand_id WHERE c.engagement_plan_id IS NULL").fetchall():
            if r["kit_key"]:
                conn.execute("UPDATE campaign SET engagement_plan_id=? WHERE id=?",
                             (_earlier_work_plan(conn, r["brand_id"]), r["id"]))
                out["placed"] += 1
            else:
                out["unplaced"].append({"campaign_id": r["id"], "project_id": r["project_id"],
                                        "brand": r["name"]})

        # 4. Projects with a kit brand and no campaign -> a campaign in "Earlier work".
        linked = {r["project_id"] for r in conn.execute(
            "SELECT project_id FROM campaign WHERE project_id IS NOT NULL")}
        seen_unplaced = {u["project_id"] for u in out["unplaced"]}
        pconn = pstore._conn()
        try:
            prows = pconn.execute("SELECT id, name, state_json, created_at FROM projects").fetchall()
        finally:
            pconn.close()
        for p in prows:
            if p["id"] in linked:
                continue
            try:
                pstate = json.loads(p["state_json"] or "{}") or {}
            except ValueError:
                pstate = {}
            slots = pstate.get("slots") or {}
            started = pstate.get("phase") not in (None, "", "collecting")
            name = (slots.get("brand") or "").strip()
            key = brand_kit.canonical_key(name) if name else None
            if key is None:
                if p["id"] not in seen_unplaced:
                    out["unplaced"].append({"campaign_id": None, "project_id": p["id"], "brand": name or None})
                continue
            bid = campaign_store.brand_row_for_kit(conn, key)
            cur = conn.execute(
                "INSERT INTO campaign (project_id, brand_id, engagement_plan_id, name, status, status_detail, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (p["id"], bid, _earlier_work_plan(conn, bid), p["name"] or f"{key} plan", "draft",
                 pstate.get("phase") if started else None, p["created_at"] or _now(), _now()))
            out["created"] += 1
            _refresh_status(conn, cur.lastrowid)

        # 5a. Campaign Plans that already have an Operations diagram get their plan flow (U6).
        with_layout = _projects_with_layout()
        for r in conn.execute("SELECT id, project_id FROM campaign WHERE project_id IS NOT NULL "
                              "AND status<>'closed' AND engagement_plan_id IS NOT NULL").fetchall():
            if r["project_id"] in with_layout:
                if not conn.execute("SELECT 1 FROM flow WHERE campaign_id=? AND origin='campaign_plan'",
                                    (r["id"],)).fetchone():
                    _ensure_plan_flow(conn, r["id"])
                    out["plan_flows"] = out.get("plan_flows", 0) + 1

        # 5. Each brand's Journey flow (brand_journey.db, one per brand before this work)
        # -> a flow row in "Earlier work" > "Launch campaign", keeping codes, kept and pending
        # edits (U-R6). Brands that already have a Journey flow row are skipped.
        out["journey_flows"] = _backfill_journey_flows(conn)

        for r in conn.execute("SELECT id FROM campaign WHERE engagement_plan_id IS NOT NULL").fetchall():
            _refresh_status(conn, r["id"])
        conn.commit()
    finally:
        conn.close()
    return out


def _projects_with_layout() -> set[str]:
    from strategy import projects as pstore
    pconn = pstore._conn()
    try:
        return {r["id"] for r in pconn.execute(
            "SELECT id FROM projects WHERE campaign_plan_layout IS NOT NULL AND campaign_plan_layout <> 'null'")}
    finally:
        pconn.close()


def _backfill_journey_flows(conn) -> int:
    try:
        jconn = db.connect("brand_journey")
    except Exception:  # noqa: BLE001
        return 0
    try:
        try:
            rows = jconn.execute("SELECT brand, doc_json FROM journey_flow").fetchall()
        except Exception:  # noqa: BLE001 -- no Journey flows were ever built here
            return 0
        drafts, confirmed = {}, set()
        try:
            drafts = {r["brand"]: r["ops_json"] for r in jconn.execute("SELECT brand, ops_json FROM journey_flow_draft")}
        except Exception:  # noqa: BLE001
            pass
        try:
            confirmed = {r["brand"] for r in jconn.execute(
                "SELECT brand FROM journey_steps WHERE step='flow' AND status='confirmed'")}
        except Exception:  # noqa: BLE001
            pass
    finally:
        jconn.close()
    moved = 0
    for r in rows:
        key = brand_kit.canonical_key(r["brand"])
        if key is None:
            continue
        bid = campaign_store.brand_row_for_kit(conn, key)
        if conn.execute("SELECT 1 FROM flow f JOIN campaign c ON c.id=f.campaign_id "
                        "WHERE c.brand_id=? AND f.origin='journey'", (bid,)).fetchone():
            continue
        stored = json.loads(r["doc_json"])
        plan_id = _earlier_work_plan(conn, bid)
        c = conn.execute("SELECT id FROM campaign WHERE engagement_plan_id=? AND name=? AND status<>'closed' "
                         "ORDER BY id LIMIT 1", (plan_id, FIRST_CAMPAIGN)).fetchone()
        cid = c["id"] if c else conn.execute(
            "INSERT INTO campaign (brand_id, engagement_plan_id, name, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)", (bid, plan_id, FIRST_CAMPAIGN, "draft", _now(), _now())).lastrowid
        conn.execute(
            "INSERT INTO flow (campaign_id, name, origin, status, base_json, ops_json, draft_ops_json, "
            "dropped_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, JOURNEY_FLOW, "journey", "confirmed" if r["brand"] in confirmed else "built",
             json.dumps({"base": stored["base"], "codes": stored["codes"]}), json.dumps(stored.get("ops") or []),
             drafts.get(r["brand"]), json.dumps(stored["dropped"]) if stored.get("dropped") else None,
             _now(), _now()))
        _refresh_status(conn, cid)
        moved += 1
    return moved
