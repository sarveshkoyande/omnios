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
