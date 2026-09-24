"""Proof script for Brand > Engagement Plan > Campaign > Flow, Phase A
(docs/plans/2026-09-24-1400-feat-brand-hierarchy-ia-plan.md, U1-U4).

No test suite exists in this repo, so this is plain python with asserts:
`python scripts/verify_brand_hierarchy.py`, non-zero exit on failure.

Isolation: a temporary DATA_DIR (OMNI_DATA_DIR, set before any strategy import) and a
temporary copy of config/brand_kits.json, so real data and the real kit file are never touched.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="verify_brand_hierarchy_"))
os.environ["OMNI_DATA_DIR"] = str(_TMP / "data")
os.environ.pop("DATABASE_URL", None)
(_TMP / "data").mkdir()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "strategy"))

from strategy import brand_kit  # noqa: E402

_REAL_KITS = brand_kit.KITS_JSON
_REAL_KITS_BYTES = _REAL_KITS.read_bytes()
_KITS_COPY = _TMP / "brand_kits.json"
shutil.copyfile(_REAL_KITS, _KITS_COPY)
_doc = json.loads(_KITS_COPY.read_text(encoding="utf-8"))
if not any(k.lower() == "cardiovex" for k in _doc["kits"]):
    _doc["kits"]["Cardiovex"] = {**_doc["kits"]["Oncomyra"], "therapy_area": "cardiology"}
    _KITS_COPY.write_text(json.dumps(_doc, indent=2), encoding="utf-8")
brand_kit.KITS_JSON = _KITS_COPY
brand_kit._load.cache_clear()

from strategy import campaign_store, hierarchy as h  # noqa: E402
from strategy import projects as pstore  # noqa: E402

_client_cache: list = []


def _client():
    if not _client_cache:
        from fastapi.testclient import TestClient
        from app import server
        for name in ("conversation_llm", "strategy.conversation_llm"):
            mod = sys.modules.get(name)
            if mod is not None:
                mod.llm_available = lambda: False
        _client_cache.append(TestClient(server.app))
    return _client_cache[0]


def _server():
    _client()
    from app import server
    return server


def _raw():
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _versions(campaign_id: int) -> list[int]:
    conn = _raw()
    try:
        return [r["version_no"] for r in conn.execute(
            "SELECT version_no FROM campaign_version WHERE campaign_id=? ORDER BY version_no", (campaign_id,))]
    finally:
        conn.close()


def _new_project(brand: str, name: str = "Legacy plan", phase: str = "collecting") -> str:
    from strategy.conversation import new_state
    state = new_state()
    state["slots"]["brand"] = brand
    state["phase"] = phase
    return pstore.create_project(name, state, [])["id"]


_counter = [0]


def _plan(brand: str = "Oncomyra", **kw) -> dict:
    _counter[0] += 1
    return h.create_plan(brand, kw.pop("name", f"Plan {_counter[0]}"), **kw)


# ---- backfill against a pre-hierarchy database (runs first, on an empty store) --------

def check_backfill_from_old_database_is_idempotent():  # R9, R20, AE7; KTD2 migration
    # A campaigns.db as it existed before this work: the schema script only (no ALTERed
    # columns), a lowercase roster brand row, a non-kit brand, and duplicate campaigns for
    # one project from two Deploys.
    conn = _raw()
    conn.executescript(campaign_store.SCHEMA_PATH.read_text(encoding="utf-8"))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(campaign)")}
    assert "engagement_plan_id" not in cols, "fixture should predate the added columns"
    conn.execute("INSERT INTO brand (id, name) VALUES (1, 'oncomyra')")
    conn.execute("INSERT INTO brand (id, name) VALUES (2, 'Zentrax')")
    p1 = _new_project("Oncomyra", "Q1 push", phase="done")
    p2 = _new_project("Oncomira")           # typo: no kit
    p3 = _new_project("oncomyra", "Never deployed", phase="running")
    p5 = _new_project("Zentrax")
    for cid, pid, bid, ts in ((1, p1, 1, "2026-01-01T00:00:00Z"), (2, p1, 1, "2026-02-01T00:00:00Z"),
                              (3, p5, 2, "2026-01-05T00:00:00Z")):
        conn.execute("INSERT INTO campaign (id, project_id, brand_id, name, status, created_at, updated_at) "
                     "VALUES (?,?,?,?,?,?,?)", (cid, pid, bid, f"c{cid}", "draft", ts, ts))
        conn.execute("INSERT INTO campaign_version (campaign_id, version_no, created_at) VALUES (?,?,?)",
                     (cid, 1, ts))
        conn.execute("INSERT INTO campaign_kpi (campaign_id, kpi_type, metric) VALUES (?,?,?)", (cid, "leading", "x"))
    conn.commit()
    conn.close()

    first = h.backfill()
    assert first["folded"] == 1 and first["created"] == 1, first
    assert sorted(u["brand"] for u in first["unplaced"]) == ["Oncomira", "Zentrax"], first["unplaced"]
    assert {u["project_id"] for u in first["unplaced"]} == {p2, p5}, first["unplaced"]

    t = h.tree("oncomyra")
    assert [p["name"] for p in t["engagement_plans"]] == [h.EARLIER_WORK], t
    camps = {c["project_id"]: c for c in t["engagement_plans"][0]["campaigns"]}
    assert set(camps) == {p1, p3}, camps
    assert _versions(camps[p1]["id"]) == [1, 2], _versions(camps[p1]["id"])
    assert camps[p1]["status"] == "confirmed", camps[p1]
    assert camps[p3]["status"] == "in_progress", camps[p3]
    conn = _raw()
    try:
        assert conn.execute("SELECT kit_key FROM brand WHERE id=1").fetchone()["kit_key"] == "Oncomyra"
        assert conn.execute("SELECT COUNT(*) FROM brand WHERE lower(name)='oncomira'").fetchone()[0] == 0
    finally:
        conn.close()

    second = h.backfill()
    assert (second["folded"], second["placed"], second["created"], second["linked_brands"]) == (0, 0, 0, 0), second
    assert h.tree("Oncomyra") == t, "a second backfill must change nothing"


def check_init_db_twice_is_a_noop():  # KTD2
    campaign_store.init_db()
    campaign_store.init_db()
    conn = _raw()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(campaign)")}
        assert {"engagement_plan_id", "closed_at", "snapshot_json", "status_detail"} <= cols, cols
    finally:
        conn.close()


# ---- U1: hierarchy store -------------------------------------------------------------

def check_create_each_level_inside_its_parent():  # R1, R8
    p = _plan()
    c = h.create_campaign(p["id"], "HCP launch")
    f = h.create_flow(c["id"], "Email nurture")
    assert c["engagement_plan_id"] == p["id"] and f["campaign_id"] == c["id"]
    assert h.get_campaign(c["id"])["status"] == "in_progress", "a flow puts a campaign in progress"
    for fn, args in ((h.create_campaign, (999999, "x")), (h.create_flow, (999999, "x"))):
        try:
            fn(*args)
            raise AssertionError(f"{fn.__name__} accepted a missing parent")
        except h.NotFound:
            pass
    for fn, args in ((h.create_plan, ("Oncomyra", " ")), (h.create_campaign, (p["id"], ""))):
        try:
            fn(*args)
            raise AssertionError("an empty name was accepted")
        except ValueError:
            pass


def check_brand_is_the_kit_case_insensitive():  # R10, KTD4
    p = _plan("ONCOMYRA")
    assert p["brand"] == "Oncomyra", p
    try:
        h.create_plan("Oncomira", "x")
        raise AssertionError("an unknown brand was accepted")
    except h.NotFound:
        pass
    conn = _raw()
    try:
        assert conn.execute("SELECT COUNT(*) FROM brand WHERE kit_key='Oncomyra'").fetchone()[0] == 1
    finally:
        conn.close()


def check_period_is_optional_and_validated():  # R3, KTD12 (requirements)
    assert _plan()["period_start"] is None
    p = _plan(period_start="2026-07-01", period_end="2026-09-30")
    assert (p["period_start"], p["period_end"]) == ("2026-07-01", "2026-09-30")
    for bad in (("2026-09-30", "2026-07-01"), ("Q3", None)):
        try:
            _plan(period_start=bad[0], period_end=bad[1])
            raise AssertionError(f"bad period {bad} accepted")
        except ValueError:
            pass
    closed = h.update_plan(p["id"], status="closed")
    assert closed["status"] == "closed"
    try:
        h.create_campaign(p["id"], "late")
        raise AssertionError("a campaign was created in a closed plan")
    except ValueError:
        pass


def check_tree_shape():  # AE1
    brand_kit.create_brand("TreeBrand")
    q2 = h.create_plan("TreeBrand", "Q2 2026", "2026-04-01", "2026-06-30")
    q3 = h.create_plan("TreeBrand", "Q3 2026", "2026-07-01", "2026-09-30")
    h.create_campaign(q2["id"], "Old")
    a = h.create_campaign(q3["id"], "A")
    h.create_campaign(q3["id"], "B")
    for n in ("f1", "f2", "f3"):
        h.create_flow(a["id"], n)
    t = h.tree("treebrand")
    assert [p["name"] for p in t["engagement_plans"]] == ["Q3 2026", "Q2 2026"], t
    q3t = t["engagement_plans"][0]
    assert sorted(c["name"] for c in q3t["campaigns"]) == ["A", "B"]
    assert len(next(c for c in q3t["campaigns"] if c["name"] == "A")["flows"]) == 3


def check_move_within_and_across_brands():  # R16, R17, AE4
    p1, p2 = _plan(), _plan()
    c = h.create_campaign(p1["id"], "Movable")
    moved = h.move_campaign(c["id"], p2["id"])
    assert moved["id"] == c["id"] and moved["engagement_plan_id"] == p2["id"]

    other = h.create_plan("Cardiovex", "Q3 2026")
    pid = _new_project("Oncomyra")
    h.bind_project(c["id"], pid)
    new = h.move_campaign(c["id"], other["id"])
    old = h.get_campaign(c["id"])
    assert old["status"] == "closed" and old["closed_at"], old
    assert new["id"] != c["id"] and new["brand"] == "Cardiovex" and new["project_id"] == pid, new
    assert pstore.get_project(pid)["state"]["slots"]["brand"] == "Cardiovex"
    assert h.open_campaign_for_project(pid)["id"] == new["id"]
    try:
        h.move_campaign(c["id"], p1["id"])
        raise AssertionError("a closed campaign moved")
    except ValueError:
        pass


# ---- U2: Campaign Plans bound to campaigns --------------------------------------------

def check_campaign_plan_starts_with_the_brand_filled():  # R13, AE3, F-AE3
    c = h.create_campaign(_plan()["id"], "Bound launch")
    r = _client().post(f"/api/campaigns/{c['id']}/campaign-plan")
    assert r.status_code == 200, r.text
    body = r.json()
    pid = body["project"]["id"]
    assert body["campaign"]["project_id"] == pid
    slots = pstore.get_project(pid)["state"]["slots"]
    assert slots["brand"] == "Oncomyra" and slots["campaign_name"] == "Bound launch", slots
    assert "Oncomyra" in body["project"]["messages"][0]["text"]
    chat = _client().post("/api/chat", json={"project_id": pid, "message": "hello"})
    assert chat.status_code == 200, chat.text
    assert "which **brand" not in json.dumps(chat.json()).lower(), chat.json()
    again = _client().post(f"/api/campaigns/{c['id']}/campaign-plan")
    assert again.status_code == 409, again.text


def _result() -> dict:
    return {"stage_7_kpi": {"leading_indicators": ["reach", "engagement"]},
            "inferred_inputs": {"persona": "HCP"}}


def check_rerun_adds_a_version_not_a_campaign():  # R15, AE2
    server = _server()
    c = h.create_campaign(_plan()["id"], "Versioned")
    pid = _new_project("Oncomyra")
    h.bind_project(c["id"], pid)
    slots = {"brand": "Oncomyra"}
    server._record_campaign_plan(pid, slots, _result(), "# plan v1")
    server._record_campaign_plan(pid, slots, _result(), "# plan v2")
    assert _versions(c["id"]) == [1, 2], _versions(c["id"])
    conn = _raw()
    try:
        assert conn.execute("SELECT COUNT(*) FROM campaign WHERE project_id=?", (pid,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM campaign_kpi WHERE campaign_id=?", (c["id"],)).fetchone()[0] == 2
    finally:
        conn.close()
    assert h.get_campaign(c["id"])["status"] == "confirmed"


def check_phase_marks_campaign_in_progress():  # KTD5
    server = _server()
    c = h.create_campaign(_plan()["id"], "Phased")
    pid = _new_project("Oncomyra")
    h.bind_project(c["id"], pid)
    assert h.get_campaign(c["id"])["status"] == "draft"
    server._record_plan_phase(pid, "align")
    assert h.get_campaign(c["id"])["status"] == "in_progress"


def check_unlinked_plan_lands_in_earlier_work():  # transitional legacy path
    server = _server()
    pid = _new_project("CARDIOVEX")
    server._record_campaign_plan(pid, {"brand": "CARDIOVEX"}, _result(), "")
    c = h.open_campaign_for_project(pid)
    assert c and c["brand"] == "Cardiovex", c
    plan = h.get_plan(c["engagement_plan_id"])
    assert plan["name"] == h.EARLIER_WORK and plan["brand"] == "Cardiovex", plan


def check_record_failures_never_raise():  # R18, AE6
    server = _server()
    real_persist, real_mark = campaign_store.persist_campaign_from_result, h.mark_plan_phase

    def boom(*a, **k):
        raise RuntimeError("campaigns.db unavailable")
    try:
        server.campaign_store.persist_campaign_from_result = boom
        server.hierarchy.mark_plan_phase = boom
        server._record_campaign_plan("nope", {}, _result(), "")
        server._record_plan_phase("nope", "align")
    finally:
        server.campaign_store.persist_campaign_from_result = real_persist
        server.hierarchy.mark_plan_phase = real_mark


# ---- U4: API ---------------------------------------------------------------------------

def check_api_routes():  # R21
    c = _client()
    assert c.get("/api/brands/Oncomira/engagement-plans").status_code == 404
    assert c.get("/api/engagement-plans/999999").status_code == 404
    assert c.get("/api/campaigns/999999").status_code == 404
    assert c.post("/api/brands/Oncomyra/engagement-plans", json={"name": " "}).status_code == 400
    p = c.post("/api/brands/oncomyra/engagement-plans",
               json={"name": "API plan", "period_start": "2026-10-01", "period_end": "2026-12-31"})
    assert p.status_code == 200 and p.json()["brand"] == "Oncomyra", p.text
    pid = p.json()["id"]
    camp = c.post(f"/api/engagement-plans/{pid}/campaigns", json={"name": "API campaign"}).json()
    assert c.patch(f"/api/campaigns/{camp['id']}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    detail = c.get(f"/api/campaigns/{camp['id']}").json()
    assert detail["flows"] == [] and detail["has_campaign_plan"] is False, detail
    other = c.post("/api/brands/Cardiovex/engagement-plans", json={"name": "Elsewhere"}).json()
    c.post(f"/api/campaigns/{camp['id']}/move", json={"engagement_plan_id": other["id"]})
    listed = c.get(f"/api/engagement-plans/{pid}/campaigns").json()["campaigns"]
    assert [x["status"] for x in listed] == ["closed"], "closed campaigns stay listed, marked closed"
    assert c.patch(f"/api/engagement-plans/{pid}", json={"status": "closed"}).json()["status"] == "closed"
    tree = c.get("/api/brands/Oncomyra/tree").json()
    assert any(x["id"] == pid for x in tree["engagement_plans"]), tree


# ---- U5: flows keyed by flow id; the Journey writes into the hierarchy ---------------------

def _bj():
    from strategy import brand_journey
    return brand_journey


def _flow_ready_brand(prefix: str = "FlowBrand") -> str:
    bj = _bj()
    _counter[0] += 1
    b = f"{prefix}{_counter[0]}"
    brand_kit.create_brand(b)
    vals = {
        "brief": [("indication", "Heart failure"), ("territories", ["US"]),
                  ("key_objective", "Grow new patient starts"), ("branded", "branded")],
        "audience": [("primary_audience", "HCPs"),
                     ("personas", {"hcp": [{"name": "The Busy Cardiologist", "who": "Treats HF",
                                            "tier": "Primary"}]})],
        "message": [("core_claim", "Fewer HF hospitalizations"),
                    ("positioning_statement", "The HF therapy that keeps patients home"),
                    ("message_hierarchy", [{"pillar": "Efficacy", "claim": "c", "evidence": "e"}]),
                    ("tone_pillars", ["Confident"])],
    }
    for step, pairs in vals.items():
        for k, v in pairs:
            bj.keep(b, bj.propose(b, step, k, v)["id"])
        bj.confirm(b, step)
    return b


def check_journey_first_flow_creates_first_plan_and_campaign():  # R22
    bj = _bj()
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    assert doc["status"] == "built" and doc["flow_id"], doc
    t = h.tree(b)
    assert [p["name"] for p in t["engagement_plans"]] == [h.FIRST_PLAN], t
    camp = t["engagement_plans"][0]["campaigns"][0]
    assert camp["name"] == h.FIRST_CAMPAIGN and [f["origin"] for f in camp["flows"]] == ["journey"], camp
    assert camp["status"] == "in_progress", camp
    assert bj.build_flow(b)["flow_id"] == doc["flow_id"], "a rebuild reuses the same flow"
    bj.confirm(b, "flow")
    assert h.get_flow(doc["flow_id"])["status"] == "confirmed"
    assert h.get_campaign(camp["id"])["status"] == "confirmed"
    bj.reopen(b, "flow")
    assert h.get_flow(doc["flow_id"])["status"] == "built"


def check_journey_flow_asks_for_a_campaign_when_plans_exist():  # R22
    bj = _bj()
    b = _flow_ready_brand()
    plan = h.create_plan(b, "Q3 2026")
    camp = h.create_campaign(plan["id"], "HCP launch")
    doc = bj.get_flow(b)
    assert doc.get("needs_campaign") and [c["id"] for c in doc["campaigns"]] == [camp["id"]], doc
    r = _client().post(f"/api/brands/{b}/journey/flow/build")
    assert r.status_code == 409, r.text
    r = _client().post(f"/api/brands/{b}/journey/flow/build", json={"campaign_id": camp["id"]})
    assert r.status_code == 200 and r.json()["campaign_id"] == camp["id"], r.text
    assert [p["name"] for p in h.tree(b)["engagement_plans"]] == ["Q3 2026"], "no extra plan was created"
    other = h.create_campaign(h.create_plan("Oncomyra", "Elsewhere")["id"], "Not yours")
    try:
        h.ensure_journey_flow(_flow_ready_brand(), other["id"])
        raise AssertionError("a flow went into another brand's campaign")
    except (ValueError, h.NeedsCampaign):
        pass


def check_flow_routes_by_id():  # U-R1, U-R2
    bj = _bj()
    c = _client()
    b = _flow_ready_brand()
    fid = bj.build_flow(b)["flow_id"]
    doc = c.get(f"/api/flows/{fid}").json()
    first = doc["flow"]["nodes"][1]["data"]["block_code"]
    r = c.post(f"/api/flows/{fid}/turn", json={"ops": [{"op": "change", "code": first, "set": {"label": "Renamed"}}]})
    assert r.status_code == 200 and r.json()["flow"]["draft"], r.text
    kept = c.post(f"/api/flows/{fid}/keep").json()
    assert kept["draft"] is None and any(n["data"]["label"] == "Renamed" for n in kept["flow"]["nodes"]), kept
    rebuilt = c.post(f"/api/flows/{fid}/build").json()
    assert any(n["data"]["label"] == "Renamed" for n in rebuilt["flow"]["nodes"]), "kept edit survives a rebuild"
    c.post(f"/api/flows/{fid}/turn", json={"ops": [{"op": "remove", "code": first}]})
    assert c.post(f"/api/flows/{fid}/undo").json()["draft"] is None
    assert c.get("/api/flows/999999").status_code == 404


def check_existing_journey_flow_is_backfilled():  # U-R6, R20
    bj = _bj()
    b = _flow_ready_brand()
    fid = bj.build_flow(b)["flow_id"]
    first = bj.get_flow(b)["flow"]["nodes"][1]["data"]["block_code"]
    bj.flow_turn(b, "", [{"op": "change", "code": first, "set": {"label": "Kept edit"}}])
    bj.keep_flow_draft(b)
    bj.flow_turn(b, "", [{"op": "change", "code": first, "set": {"label": "Pending edit"}}])
    rec = h.flow_storage(fid)
    before = bj.get_flow(b)
    # Recreate the pre-hierarchy state: the flow only in brand_journey.db, no flow row, no plans.
    jconn = bj._conn()
    jconn.execute("CREATE TABLE IF NOT EXISTS journey_flow_draft (brand TEXT PRIMARY KEY, ops_json TEXT NOT NULL, "
                  "updated_at TEXT NOT NULL)")
    jconn.execute("INSERT INTO journey_flow (brand, doc_json, updated_at) VALUES (?,?,?)",
                  (b, json.dumps({"base": rec["base"]["base"], "codes": rec["base"]["codes"], "ops": rec["ops"],
                                  "dropped": rec["dropped"]}), "2026-01-01T00:00:00Z"))
    jconn.execute("INSERT INTO journey_flow_draft (brand, ops_json, updated_at) VALUES (?,?,?)",
                  (b, json.dumps(rec["draft_ops"]), "2026-01-01T00:00:00Z"))
    jconn.commit()
    jconn.close()
    conn = _raw()
    conn.execute("DELETE FROM flow WHERE id=?", (fid,))
    conn.execute("DELETE FROM campaign WHERE engagement_plan_id IN (SELECT e.id FROM engagement_plan e "
                 "JOIN brand br ON br.id=e.brand_id WHERE br.kit_key=?)", (b,))
    conn.execute("DELETE FROM engagement_plan WHERE brand_id=(SELECT id FROM brand WHERE kit_key=?)", (b,))
    conn.commit()
    conn.close()
    assert h.journey_flow_id(b) is None
    res = h.backfill()
    assert res["journey_flows"] >= 1, res
    t = h.tree(b)
    plan = t["engagement_plans"][0]
    assert plan["name"] == h.EARLIER_WORK and plan["campaigns"][0]["name"] == h.FIRST_CAMPAIGN, t
    after = bj.get_flow(b)
    assert after["flow"] == before["flow"] and after["ops"] == before["ops"], "codes and kept edits survive"
    assert after["draft"]["ops"] == before["draft"]["ops"], "the pending draft survives"
    again = h.backfill()
    assert h.tree(b) == t and again["journey_flows"] == 0, "a second backfill changes nothing"


def check_reset_deletes_only_journey_flows():  # R19, AE5
    import importlib.util
    spec = importlib.util.spec_from_file_location("reset_test_data", ROOT / "scripts" / "reset_test_data.py")
    rtd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rtd)
    bj = _bj()
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    manual = h.create_flow(doc["campaign_id"], "Hand-added")
    counts = rtd.clear_brand_journey(b.lower())
    assert counts["campaigns.flow (journey)"] == 1, counts
    assert [f["id"] for f in h.list_flows(doc["campaign_id"])] == [manual["id"]]
    assert h.journey_flow_id(b) is None


# ---- U6: the Campaign Plan's Operations diagram is a flow of its campaign --------------------

_DOC = {"version": 1, "pages": [{"id": "p1", "name": "Flow", "nodes": [{"id": "n1", "label": "Email 1"}], "edges": []}]}


def _bound_campaign(plan_brand: str = "Oncomyra") -> tuple[dict, str]:
    c = h.create_campaign(_plan(plan_brand)["id"], "Diagrammed")
    pid = _new_project(plan_brand)
    h.bind_project(c["id"], pid)
    return c, pid


def check_saving_the_operations_diagram_creates_one_plan_flow():  # U6
    cl = _client()
    c, pid = _bound_campaign()
    assert h.list_flows(c["id"]) == []
    assert cl.patch(f"/api/projects/{pid}/campaign-plan-layout", json=_DOC).status_code == 200
    doc2 = {**_DOC, "pages": [{**_DOC["pages"][0], "name": "Edited"}]}
    cl.patch(f"/api/projects/{pid}/campaign-plan-layout", json=doc2)
    flows = h.list_flows(c["id"])
    assert [(f["origin"], f["name"]) for f in flows] == [("campaign_plan", h.PLAN_FLOW)], flows
    got = cl.get(f"/api/flows/{flows[0]['id']}").json()
    assert got["kind"] == "document" and got["document"] == doc2 and got["project_id"] == pid, got
    assert h.get_campaign(c["id"])["status"] == "in_progress"
    r = cl.post(f"/api/flows/{flows[0]['id']}/turn", json={"ops": [{"op": "remove", "code": "B1"}]})
    assert r.status_code == 400 and "Operations" in r.text, r.text
    assert cl.post(f"/api/flows/{flows[0]['id']}/build").status_code == 400


def check_unlinked_project_diagram_save_still_works():  # U6, no regression
    pid = _new_project("Oncomira")
    assert _client().patch(f"/api/projects/{pid}/campaign-plan-layout", json=_DOC).status_code == 200
    assert pstore.get_project(pid)["campaign_plan_layout"] == _DOC


def check_moving_a_campaign_freezes_its_old_diagram():  # U6 + R16
    cl = _client()
    c, pid = _bound_campaign()
    cl.patch(f"/api/projects/{pid}/campaign-plan-layout", json=_DOC)
    old_flow = h.list_flows(c["id"])[0]["id"]
    new = h.move_campaign(c["id"], h.create_plan("Cardiovex", "Moved here")["id"])
    new_flows = h.list_flows(new["id"])
    assert [f["origin"] for f in new_flows] == ["campaign_plan"], new_flows
    later = {**_DOC, "pages": [{**_DOC["pages"][0], "name": "After the move"}]}
    cl.patch(f"/api/projects/{pid}/campaign-plan-layout", json=later)
    old = cl.get(f"/api/flows/{old_flow}").json()
    assert old["frozen"] and old["document"] == _DOC, "the closed campaign keeps the diagram as it was"
    assert cl.get(f"/api/flows/{new_flows[0]['id']}").json()["document"] == later


def check_backfill_adds_plan_flows_for_existing_diagrams():  # U6 backfill
    c, pid = _bound_campaign()
    pconn = pstore._conn()
    pconn.execute("UPDATE projects SET campaign_plan_layout=? WHERE id=?", (json.dumps(_DOC), pid))
    pconn.commit()
    pconn.close()
    assert h.list_flows(c["id"]) == []
    h.backfill()
    assert [f["origin"] for f in h.list_flows(c["id"])] == ["campaign_plan"]
    h.backfill()
    assert len(h.list_flows(c["id"])) == 1, "a second backfill adds nothing"


# ---- U8: each campaign keeps the brand content it was built from -------------------------

def _labels(doc: dict) -> str:
    return json.dumps([n["data"].get("label") for n in doc["flow"]["nodes"]])


def check_flow_keeps_its_snapshot_until_updated():  # P-R1, P-R3, P-R5, P-AE1, P-AE2
    bj = _bj()
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    fid, cid = doc["flow_id"], doc["campaign_id"]
    assert "Efficacy" in _labels(doc)
    assert h.get_campaign(cid)["content"] == {"tracked": True, "changed_steps": [],
                                              "snapshot_at": h.get_campaign(cid)["snapshot_at"]}
    wait = next(n for n in doc["flow"]["nodes"] if n["type"] == "wait")["data"]["block_code"]
    bj.flow_turn(b, "", [{"op": "change", "code": wait, "set": {"label": "Wait a fortnight"}}])
    bj.keep_flow_draft(b)
    # The brand's message changes after the campaign was built.
    bj.keep(b, bj.propose(b, "message", "message_hierarchy",
                          [{"pillar": "Outcomes", "claim": "c", "evidence": "e"}])["id"])
    assert h.get_campaign(cid)["content"]["changed_steps"] == ["message"]
    d = _client().get(f"/api/campaigns/{cid}/drift").json()
    change = d["changed"]["message"][0]
    assert d["has_drift"] and change["key"] == "message_hierarchy", d
    assert change["then"][0]["pillar"] == "Efficacy" and change["now"][0]["pillar"] == "Outcomes", change
    rebuilt = bj.build_flow_by_id(fid)
    assert "Efficacy" in _labels(rebuilt) and "Outcomes" not in _labels(rebuilt), "a rebuild still uses the snapshot"
    r = _client().post(f"/api/campaigns/{cid}/refresh-snapshot").json()
    assert r["has_drift"] is False and r["flows"][0]["flow_id"] == fid, r
    updated = bj.get_flow_by_id(fid)
    assert "Outcomes" in _labels(updated) and "Wait a fortnight" in _labels(updated), "new content, kept edit reapplied"


def check_campaign_plan_prefills_from_the_snapshot():  # P-R5
    c = h.create_campaign(_plan()["id"], "Snapshot plan")
    real = brand_kit.kit_for("Oncomyra")["therapy_area"]
    brand_kit.apply_diff("Oncomyra", {"therapy_area": "changed after the snapshot"})
    try:
        pid = _client().post(f"/api/campaigns/{c['id']}/campaign-plan").json()["project"]["id"]
        assert pstore.get_project(pid)["state"]["slots"]["therapy_area"] == real
        assert h.drift(c["id"])["tracked"] is True
    finally:
        brand_kit.apply_diff("Oncomyra", {"therapy_area": real})


def check_legacy_campaigns_are_not_called_up_to_date():  # P-R6
    pid = _new_project("Cardiovex")
    _server()._record_campaign_plan(pid, {"brand": "Cardiovex"}, _result(), "")
    c = h.open_campaign_for_project(pid)
    assert c["content"]["tracked"] is False, c["content"]
    assert _client().get(f"/api/campaigns/{c['id']}/drift").json()["tracked"] is False


# ---- U9-U12: the Cockpit's hierarchy screens (backend side) --------------------------------

def check_new_flow_needs_confirmed_steps():  # F-R4, F-R5, F-AE1, F-AE2
    cl = _client()
    brand_kit.create_brand("NotReady")
    c = h.create_campaign(h.create_plan("NotReady", "Q3")["id"], "Early")
    r = cl.post(f"/api/campaigns/{c['id']}/flows", json={"name": "Too soon"})
    assert r.status_code == 400 and "Needs:" in r.text and "Message" in r.text, r.text
    assert h.list_flows(c["id"]) == [], "nothing is created while steps are unconfirmed"
    b = _flow_ready_brand()
    camp = h.create_campaign(h.create_plan(b, "Q4")["id"], "HCP launch")
    for name in ("Email nurture", "Rep follow-up"):
        r = cl.post(f"/api/campaigns/{camp['id']}/flows", json={"name": name})
        assert r.status_code == 200 and r.json()["status"] == "built", r.text
    assert sorted(f["name"] for f in h.list_flows(camp["id"])) == ["Email nurture", "Rep follow-up"]


def check_flow_confirm_and_reopen():  # KTD5 roll-up for flows-only campaigns
    cl = _client()
    b = _flow_ready_brand()
    camp = h.create_campaign(h.create_plan(b, "Q1")["id"], "Solo")
    fid = cl.post(f"/api/campaigns/{camp['id']}/flows", json={"name": "Only flow"}).json()["flow_id"]
    assert h.get_campaign(camp["id"])["status"] == "in_progress"
    cl.post(f"/api/flows/{fid}/confirm")
    assert h.get_flow(fid)["status"] == "confirmed" and h.get_campaign(camp["id"])["status"] == "confirmed"
    cl.post(f"/api/flows/{fid}/reopen")
    assert h.get_flow(fid)["status"] == "built" and h.get_campaign(camp["id"])["status"] == "in_progress"


def check_summary_counts_and_dashboard_agree():  # R-R4, R-R6, R-AE2
    brand_kit.create_brand("Countable")
    q2 = h.create_plan("Countable", "Q2")
    q3 = h.create_plan("Countable", "Q3")
    h.update_plan(q2["id"], status="closed")
    a = h.create_campaign(q3["id"], "A")
    h.create_campaign(q3["id"], "B")
    h.move_campaign(a["id"], h.create_plan("Oncomyra", "Elsewhere")["id"])  # closes A under Countable
    s = _client().get("/api/hierarchy/summary").json()["Countable"]
    assert s == {"active_plans": 1, "open_campaigns": 1}, s
    counts = campaign_store.campaign_counts_by_brand()
    assert counts.get("Countable") == 1 and counts.get("countable") == 1, counts


def check_page_routes():  # S-KD3, S-R5, S-R6, KTD10, KTD11
    cl = _client()
    root = cl.get("/")
    assert root.status_code == 200 and "/static/cockpit/" in root.text, "/ serves the Cockpit"
    embed = cl.get("/campaign-plan-view?project=x&embed=1")
    assert embed.status_code == 200 and "/static/v2/" in embed.text
    assert "/static/v2/" in cl.get("/v2").text, "the earlier app stays reachable"
    assert cl.get("/legacy").status_code == 200 and cl.get("/hcp360").status_code == 200


# ---- U7: one vocabulary ------------------------------------------------------------------

def check_glossaries_match():  # N-R6
    import re
    from strategy import glossary
    ts = (ROOT / "frontend" / "src" / "glossary.ts").read_text(encoding="utf-8")
    front = {m[0]: (m[1], m[2]) for m in re.findall(
        r'(\w+): \{ label: "([^"]*)", definition: "([^"]*)" \}', ts)}
    assert front == glossary.TERMS, (front, glossary.TERMS)


def check_engagement_plan_only_means_the_period_container():  # N-R2, N-R4, N-AE2
    import re
    # User-facing strings and prompt text only: string literals and JSX text, not comments or
    # identifiers. "Engagement Planning Toolkit" is an external workbook's name and stays.
    allowed = re.compile(r"engagement[ -]planning toolkit|brand > engagement plan > campaign", re.I)
    offenders = []
    files = [p for d in ("strategy", "frontend/src", "cockpit/src") for p in (ROOT / d).rglob("*")
             if p.suffix in (".py", ".ts", ".tsx") and "node_modules" not in p.parts]
    files.append(ROOT / "app" / "server.py")
    for path in files:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0] if path.suffix == ".py" else re.sub(r"//.*|/\*.*|^\s*\*.*", "", line)
            for lit in re.findall(r'"[^"]*"|`[^`]*`|>[^<>{}]+<', code):
                if re.search(r"brand engagement plan|engagement plan composer", lit, re.I) and not allowed.search(lit):
                    offenders.append(f"{path.relative_to(ROOT)}:{i}: {lit.strip()}")
    assert not offenders, offenders


def check_export_title_reads_campaign_plan():  # N-AE1
    import plan_document
    md, html = plan_document.compose_plan_partial({"brand": "Oncomyra", "therapy_area": "oncology"}, set())[:2]
    assert md.splitlines()[0].startswith("# Campaign Plan"), md.splitlines()[0]
    assert "<h1>Campaign Plan</h1>" in html and "Engagement Plan" not in html.split("</h1>")[0]


CHECKS = [v for k, v in list(globals().items()) if k.startswith("check_") and callable(v)]


def main() -> int:
    failed = 0
    try:
        for fn in CHECKS:
            try:
                fn()
                print(f"PASS {fn.__name__}")
            except Exception:  # noqa: BLE001
                failed += 1
                print(f"FAIL {fn.__name__}")
                traceback.print_exc()
    finally:
        assert _REAL_KITS.read_bytes() == _REAL_KITS_BYTES, "the real brand kit file was modified"
        shutil.rmtree(_TMP, ignore_errors=True)
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
