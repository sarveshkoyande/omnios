"""Live simulation: the watched view of every brand's engagement plans -> campaigns -> journeys, and the
nightly check (12:00 am server time, or on demand) that keeps it current.

What the check does, per brand:
  * Changes by itself only safe, derived things -- each campaign's phase from its dates
    (unscheduled / planned / running / ended) -- and logs every such change.
  * Raises "updates waiting" for everything else, each with what changed, why, and an action:
      drift       the brand content changed since the campaign was created  -> Apply = refresh the
                  campaign's snapshot and rebuild its rules journeys (hierarchy.refresh_snapshot)
      no_journey  a campaign that isn't over has no journey yet              -> open the Flow Agent
      brand_iq    the brand kit changed since the last check                 -> review the campaigns
      plan_stale  an engagement plan was built on an older Brand IQ plan     -> open the planner
      signals     Signal Scout has a newer readout                           -> open Signal Scout
  * Asks the model (when available) to propose what to change for drift and signal updates, citing the
    evidence; without a model the update still appears, saying no proposal was written (R2).
Updates you dismiss or apply stay that way; a waiting update whose cause has gone away is resolved.
State: DATA_DIR/live_sim/state.json.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
from paths import data_path  # noqa: E402

_LOCK = threading.Lock()
CHECK_HOUR = 0  # 12:00 am, server local time


def _path() -> Path:
    return data_path("live_sim", "state.json")


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"last_check": None, "brands": {}}


def _save(state: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def next_check() -> str:
    now = dt.datetime.now()
    nxt = now.replace(hour=CHECK_HOUR, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += dt.timedelta(days=1)
    return nxt.isoformat(timespec="seconds")


def phase(c: dict, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    if c.get("status") == "closed":
        return "closed"
    s, e = c.get("start_date"), c.get("end_date")
    if not s and not e:
        return "unscheduled"
    try:
        if s and today < dt.date.fromisoformat(s[:10]):
            return "planned"
        if e and today > dt.date.fromisoformat(e[:10]):
            return "ended"
    except ValueError:
        return "unscheduled"
    return "running"


def _uid(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def _brands_with_work() -> list[str]:
    import hierarchy
    out = []
    for b in brand_kit.list_brands():
        name = b.get("brand") if isinstance(b, dict) else b
        try:
            if hierarchy.list_plans(name):
                out.append(name)
        except Exception:  # noqa: BLE001
            continue
    return out


def _propose(brand: str, items: list[dict]) -> list[dict | None]:
    """One model call per brand: a concrete proposal for each drift / signals update, in the same order."""
    from llm_json import complete_json
    out = complete_json(
        "You are the Live simulation reviewer for a US pharma brand's campaigns. For EACH update, in order, write "
        "a short, concrete proposal of what the brand team should change in that campaign or its journey "
        "(message, audience, channel, timing), citing the evidence given. Never invent facts; if the change is "
        "cosmetic say no action is needed. Copy each update's `id` into `update_id` exactly. Reply with one JSON "
        'object: {"proposals":[{"update_id":"","proposal":"","evidence":""}]}',
        {"brand": brand, "updates": items}, max_tokens=2500)
    got = [p for p in out.get("proposals") or [] if isinstance(p, dict)]
    by_id = {p.get("update_id") or p.get("id"): p for p in got}
    if all(i["id"] in by_id for i in items):
        return [by_id[i["id"]] for i in items]
    return [got[n] if n < len(got) else None for n in range(len(items))]  # fall back to order


def check(brands: list[str] | None = None, use_ai: bool = True) -> dict:
    """Run the check now. Returns a summary per brand."""
    import engagement_plans as ep
    import hierarchy
    with _LOCK:
        state = _load()
        last = state.get("last_check")
        stamps = [m for m in brand_kit._mtimes() if m]
        kit_mtime = dt.datetime.fromtimestamp(max(stamps) / 1e9).isoformat(timespec="seconds") if stamps else None
        summary = {}
        for brand in brands or _brands_with_work():
            key = hierarchy.brand_key(brand)
            bs = state["brands"].setdefault(key, {"updates": [], "log": [], "phases": {}})
            tree = hierarchy.tree(key)
            found: dict[str, dict] = {}
            log_new = []
            for plan in tree["engagement_plans"]:
                for c in plan["campaigns"]:
                    cid = str(c["id"])
                    ph = phase(c)
                    prev = bs["phases"].get(cid)
                    if prev and prev != ph:
                        log_new.append({"at": _now(), "what": f"{c['name']}: {prev} → {ph}", "why": "Its dates"})
                    bs["phases"][cid] = ph
                    steps = (c.get("content") or {}).get("changed_steps") or []
                    if steps:
                        d = hierarchy.drift(c["id"])
                        uid = _uid("drift", cid, json.dumps(d["changed"], sort_keys=True, default=str))
                        found[uid] = {"id": uid, "kind": "drift", "campaign_id": c["id"], "plan_id": plan["id"],
                                      "title": f"Brand content changed since “{c['name']}” was created",
                                      "detail": "Changed: " + ", ".join(
                                          f"{s}: {', '.join(x['label'] for x in fields)}" for s, fields in d["changed"].items()),
                                      "evidence_raw": d["changed"], "action": "refresh"}
                    if not c.get("flow_count") and ph not in ("ended", "closed"):
                        uid = _uid("no_journey", cid)
                        found[uid] = {"id": uid, "kind": "no_journey", "campaign_id": c["id"], "plan_id": plan["id"],
                                      "title": f"“{c['name']}” has no journey yet",
                                      "detail": f"It is {ph}. Build its journey in the Flow Agent.",
                                      "action": "open", "href": f"#/v3/agent/flow-planner/for/{key}/{plan['id']}/{c['id']}"}
            # engagement plans built on an older Brand IQ plan
            for p in ep.list_plans(key):
                full = ep.get(p["id"]) or {}
                if full.get("stale"):
                    uid = _uid("plan_stale", p["id"], full.get("brand_iq_plan"))
                    found[uid] = {"id": uid, "kind": "plan_stale", "title": f"“{p['title']}” was built on an older brand plan",
                                  "detail": "The brand's active Brand IQ plan changed. Revisit the strategy.",
                                  "action": "open", "href": f"#/v3/agent/engagement-planner/{p['id']}"}
            # Brand IQ changed since the last check
            if last and kit_mtime and kit_mtime > last:
                uid = _uid("brand_iq", key, kit_mtime)
                found[uid] = {"id": uid, "kind": "brand_iq", "title": "Brand IQ was updated",
                              "detail": "The brand kit changed since the last check; campaigns built before it may need a refresh.",
                              "action": "open", "href": "#/v3/iq/kits"}
            # Signal Scout readout newer than the last check
            try:
                import signal_scout
                cur = signal_scout.load(key).get("current") or {}
                syn = (cur.get("sections") or {}).get("synthesis") or {}
                stamp = cur.get("updated") or cur.get("started")
                if syn.get("signals") and (not last or (stamp and stamp >= last[:10])):
                    uid = _uid("signals", key, stamp, syn.get("headline"))
                    found[uid] = {"id": uid, "kind": "signals", "title": f"Signal Scout: {syn.get('headline') or 'new signals'}",
                                  "detail": "; ".join(s.get("title", "") for s in syn["signals"][:4]),
                                  "evidence_raw": syn["signals"][:4], "action": "open", "href": "#/v3/agent/signal-agent"}
            except Exception:  # noqa: BLE001 -- signals are additive
                pass

            # merge with what's already there: keep applied/dismissed, resolve vanished waiting ones
            old = {u["id"]: u for u in bs["updates"]}
            merged = []
            for uid, u in found.items():
                if uid in old:
                    merged.append({**u, **{k: old[uid][k] for k in ("status", "proposal", "evidence", "raised_at", "resolved_at") if k in old[uid]}})
                else:
                    merged.append({**u, "status": "waiting", "raised_at": _now()})
            for uid, u in old.items():
                if uid not in found:
                    if u.get("kind") == "demo":
                        merged.append(u)
                        continue
                    if u["status"] == "waiting":
                        log_new.append({"at": _now(), "what": f"Resolved: {u['title']}", "why": "The cause has gone away"})
                        u = {**u, "status": "resolved", "resolved_at": _now()}
                    merged.append(u)
            # model proposals for new drift / signals updates
            need = [u for u in merged if u["status"] == "waiting" and u["kind"] in ("drift", "signals") and not u.get("proposal")]
            if need and use_ai:
                try:
                    # short ids: the model copies "u1" reliably, a random hash less so
                    props = _propose(key, [{"id": f"u{i + 1}", "title": u["title"], "detail": u["detail"],
                                            "evidence": u.get("evidence_raw")} for i, u in enumerate(need)])
                    for u, p in zip(need, props):
                        if p:
                            u["proposal"], u["evidence"] = p.get("proposal"), p.get("evidence")
                except Exception as e:  # noqa: BLE001 -- R2: say so, never guess
                    for u in need:
                        u["proposal_note"] = f"The AI model couldn't be reached ({e}); no proposal was written."
            for u in merged:
                u.pop("evidence_raw", None)
            bs["updates"] = sorted(merged, key=lambda u: (u["status"] != "waiting", u.get("raised_at") or ""), reverse=False)[:200]
            bs["log"] = (log_new + bs["log"])[:200]
            bs["last_check"] = _now()
            summary[key] = {"waiting": sum(u["status"] == "waiting" for u in merged), "changes": len(log_new)}
        state["last_check"] = _now()
        _save(state)
        return summary


def view(brand: str) -> dict:
    import hierarchy
    key = hierarchy.brand_key(brand)
    state = _load()
    bs = state["brands"].get(key, {"updates": [], "log": [], "phases": {}})
    tree = hierarchy.tree(key)
    for plan in tree["engagement_plans"]:
        for c in plan["campaigns"]:
            c["phase"] = phase(c)
    demo = (state.get("demo") or {}).get(key) or {}
    return {"brand": key, "tree": tree, "updates": bs["updates"], "log": bs["log"],
            "last_check": bs.get("last_check") or state.get("last_check"), "next_check": next_check(),
            "demo": bool(demo), "demo_plan_ids": demo.get("plan_ids") or [], "journey_meta": demo.get("journey_meta") or {}}


def resolve(brand: str, update_id: str, action: str) -> dict:
    """Apply or dismiss one update. Applying a drift update refreshes the campaign's snapshot and rebuilds
    its rules journeys; the other kinds are links, so applying marks them done."""
    import hierarchy
    key = hierarchy.brand_key(brand)
    with _LOCK:
        state = _load()
        bs = state["brands"].get(key) or {}
        u = next((x for x in bs.get("updates") or [] if x["id"] == update_id), None)
        if not u:
            raise KeyError(update_id)
        if action == "apply":
            if u["kind"] == "drift" and u.get("campaign_id"):
                res = hierarchy.refresh_snapshot(u["campaign_id"])
                dropped = sum(len(f.get("dropped") or []) for f in res.get("flows") or [])
                bs["log"].insert(0, {"at": _now(), "what": f"Refreshed {u['title'].split('“')[-1].rstrip('” was created')}",
                                     "why": f"Applied update; {len(res.get('flows') or [])} journey(s) rebuilt"
                                            + (f", {dropped} edit(s) couldn't be kept" if dropped else "")})
            u["status"] = "applied"
        elif action == "dismiss":
            u["status"] = "dismissed"
        else:
            raise ValueError("action must be apply or dismiss")
        u["resolved_at"] = _now()
        _save(state)
        return u


# ---------------------------------------------------------------------- demo data (Jardiance)
# A ready-made plan -> campaign -> journey tree so Live simulation can be shown before every item is
# built by hand. Everything here is labelled DEMO in the UI; journey numbers are illustrative.

_DEMO = {
    "Jardiance": [
        {"name": "Jardiance HF & T2D engagement plan — H1 2026", "start": "2026-01-01", "end": "2026-06-30", "campaigns": [
            {"name": "EMPEROR evidence refresh for cardiologists", "start": "2026-01-01", "end": "2026-03-31", "journeys": [
                ("Cardiologist email series", "confirmed", {"sends": 6, "hcps": 4820, "channels": ["Email", "Rep"]}),
                ("Rep-triggered follow-up", "confirmed", {"sends": 3, "hcps": 1310, "channels": ["Rep", "Email"]})]},
            {"name": "PCP screening nudge: T2D patients with HF risk", "start": "2026-02-01", "end": "2026-06-30", "journeys": [
                ("PCP digital journey", "confirmed", {"sends": 5, "hcps": 11250, "channels": ["Email", "HCP portal", "Paid social"]})]},
        ]},
        {"name": "Jardiance HF growth plan — Sep 2026 to Feb 2027", "start": "2026-09-01", "end": "2027-02-28", "campaigns": [
            {"name": "HF Clinical Evidence Exchange", "start": "2026-09-01", "end": "2026-12-31", "journeys": [
                ("Cardiologist evidence journey", "confirmed", {"sends": 7, "hcps": 5140, "channels": ["Email", "Webinar", "Rep"]}),
                ("KOL webinar invitations", "draft", {"sends": 3, "hcps": 860, "channels": ["Email", "Webinar"]})]},
            {"name": "Post-discharge GDMT acceleration", "start": "2026-10-01", "end": "2027-01-31", "journeys": [
                ("Hospitalist & HF clinic journey", "draft", {"sends": 4, "hcps": 2390, "channels": ["Email", "Rep", "EHR alert"]})]},
            {"name": "Patient Connect: adherence & home-time", "start": "2026-11-01", "end": "2027-02-28", "journeys": []},
            {"name": "CKD cross-referral to nephrology", "start": "2027-01-01", "end": "2027-02-28", "journeys": [
                ("Nephrology email journey", "draft", {"sends": 4, "hcps": 1780, "channels": ["Email", "Rep"]})]},
        ]},
        {"name": "Jardiance plan — H2 2027 (draft)", "start": "2027-05-01", "end": "2027-10-31", "campaigns": [
            {"name": "New HFpEF data readiness", "start": "2027-05-01", "end": "2027-07-31", "journeys": []},
        ]},
    ],
}

_DEMO_UPDATES = {
    "Jardiance": [
        {"title": "Open rate on the Cardiologist evidence journey fell 18% after send 3",
         "detail": "DEMO metric. Sends 1-2 averaged 31% opens; send 3 dropped to 25%.",
         "proposal": "Test a shorter subject line that leads with the HF hospitalisation result, and move send 4 two days earlier.",
         "evidence": "Journey metrics (demo)"},
        {"title": "Formulary win in Texas (synthetic client data)",
         "detail": "DEMO. Jardiance moved to preferred tier on a major Texas commercial plan.",
         "proposal": "Add a Texas access message to the PCP and cardiologist journeys and raise rep frequency for high-decile Texas HCPs for 6 weeks.",
         "evidence": "Client data · formulary by state (synthetic)"},
    ],
}


def seed_demo(brand: str = "Jardiance") -> dict:
    """Create the demo tree for `brand` once (idempotent). Returns what was created or already there."""
    import hierarchy
    key = hierarchy.brand_key(brand)
    spec = _DEMO.get(key)
    if not spec or not brand_kit.kit_for(key):
        raise KeyError(brand)
    with _LOCK:
        state = _load()
        demo = state.setdefault("demo", {}).get(key)
        if demo:
            try:
                for pid in demo["plan_ids"]:
                    hierarchy.get_plan(pid)
                return {"brand": key, "created": False, **demo}
            except hierarchy.NotFound:
                pass
        plan_ids, meta = [], {}
        for p in spec:
            hp = hierarchy.create_plan(key, p["name"], p["start"], p["end"])
            plan_ids.append(hp["id"])
            for c in p["campaigns"]:
                hc = hierarchy.create_campaign(hp["id"], c["name"], c["start"], c["end"])
                for name, status, m in c["journeys"]:
                    f = hierarchy.create_flow(hc["id"], name, "manual")
                    conn = hierarchy._conn()
                    try:
                        conn.execute("UPDATE flow SET status=? WHERE id=?", (status, f["id"]))
                        hierarchy._refresh_status(conn, hc["id"])
                        conn.commit()
                    finally:
                        conn.close()
                    meta[str(f["id"])] = m
        state["demo"][key] = {"plan_ids": plan_ids, "journey_meta": meta, "seeded_at": _now()}
        bs = state["brands"].setdefault(key, {"updates": [], "log": [], "phases": {}})
        for u in _DEMO_UPDATES.get(key, []):
            bs["updates"].append({**u, "id": _uid("demo", key, u["title"]), "kind": "demo", "status": "waiting",
                                  "raised_at": _now(), "action": "acknowledge"})
        bs["log"] = [{"at": _now(), "what": "EMPEROR evidence refresh for cardiologists: running → ended", "why": "Its dates (demo)"},
                     {"at": _now(), "what": "Post-discharge GDMT acceleration: planned → running", "why": "Its dates (demo)"}] + bs["log"]
        _save(state)
        return {"brand": key, "created": True, **state["demo"][key]}


# ---------------------------------------------------------------------- the nightly scheduler

_started = False


def start_scheduler() -> None:
    """Background thread: run the check every night at CHECK_HOUR (server local time)."""
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            wait = (dt.datetime.fromisoformat(next_check()) - dt.datetime.now()).total_seconds()
            time.sleep(max(30, wait))
            try:
                check()
            except Exception:  # noqa: BLE001 -- never kill the loop
                traceback.print_exc()

    threading.Thread(target=loop, name="live-sim-nightly", daemon=True).start()


__all__ = ["check", "view", "resolve", "seed_demo", "start_scheduler", "next_check", "phase"]
