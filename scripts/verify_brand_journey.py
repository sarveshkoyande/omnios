"""Proof script for the Agentic Brand Journey backend (plan
docs/plans/2026-09-24-0629-feat-agentic-brand-journey-plan.md).

The repo has no test suite (and its instructions forbid inventing one), so this is plain
python with asserts: `python scripts/verify_brand_journey.py`, non-zero exit on failure.

Isolation: a temporary DATA_DIR (OMNI_DATA_DIR, set BEFORE any strategy import) and a
temporary copy of config/brand_kits.json (brand_kit.KITS_JSON is repointed at it), so the
real kit file and the real data/ directory are never touched.

Later units append checks: write a `check_<name>()` function and add it to CHECKS.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="verify_brand_journey_"))
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
# The Cardiovex checks need a pre-existing, fully populated legacy kit. A fresh checkout
# commits only Oncomyra, so seed Cardiovex into the temporary copy (never the real file)
# from Oncomyra's kit plus the two required Brief fields it lacks.
_kits_doc = json.loads(_KITS_COPY.read_text(encoding="utf-8"))
if not any(k.lower() == "cardiovex" for k in _kits_doc["kits"]):
    _kits_doc["kits"]["Cardiovex"] = {**_kits_doc["kits"]["Oncomyra"], "territories": ["US"],
                                      "key_objective": "Grow new patient starts"}
    _KITS_COPY.write_text(json.dumps(_kits_doc, indent=2), encoding="utf-8")
brand_kit.KITS_JSON = _KITS_COPY
brand_kit._load.cache_clear()

import journey_fields as jf  # noqa: E402
import brand_journey as bj  # noqa: E402

KTD4_FIELDS = {"lifecycle_stage", "success_measure", "branded", "primary_audience"}
_counter = [0]


def _fresh_brand(prefix: str = "VerifyBrand") -> str:
    _counter[0] += 1
    name = f"{prefix}{_counter[0]}"
    brand_kit.create_brand(name)
    return name


def _step(state: dict, step: str) -> dict:
    return next(s for s in state["steps"] if s["step"] == step)


def _answer_all(step: str, answers: dict, branded: str = "branded") -> dict:
    """Answer next questions until none is open; returns answers."""
    for _ in range(100):
        nxt = jf.next_questions(step, answers, 1)
        if not nxt:
            return answers
        f = nxt[0]
        if f["key"] == "branded":
            answers[f["key"]] = branded
        elif f["chips"]:
            answers[f["key"]] = f["chips"][0]
        else:
            answers[f["key"]] = "x"
    raise AssertionError(f"{step}: questions never closed")


# ---- U1: registry + next-question engine -------------------------------------------------

def check_u1_empty_brief_asks_brand_name():
    q = jf.next_questions("brief", {}, 1)
    assert q and q[0]["key"] == "brand_name", q


def check_u1_territory_after_name_and_indication():
    q = jf.next_questions("brief", {"brand_name": "X", "indication": "Y"}, 1)
    assert q[0]["key"] == "territories", q
    assert "Other" in q[0]["chips"], q[0]["chips"]


def check_u1_unbranded_hides_claims():  # AE1
    keys = {f["key"] for f in jf.open_fields("message", {"branded": "unbranded"})}
    assert "core_claim" not in keys, keys
    keys_b = {f["key"] for f in jf.open_fields("message", {"branded": "branded"})}
    assert "core_claim" in keys_b, keys_b
    # unanswered gate: the gated field waits rather than opening
    assert "core_claim" not in {f["key"] for f in jf.open_fields("message", {})}


def check_u1_kit_targets_are_real_fields():
    ts = (ROOT / "cockpit" / "src" / "types.ts").read_text(encoding="utf-8")
    body = ts.split("export interface BrandKit {", 1)[1].split("\n}", 1)[0]
    declared = {line.strip().split(":")[0].rstrip("?") for line in body.splitlines()
                if ":" in line and not line.strip().startswith(("/", "*"))}
    for f in jf.FIELDS:
        if f["target"] == "kit":
            assert f["key"] in declared or f["key"] in KTD4_FIELDS, f["key"]
    assert KTD4_FIELDS <= declared, KTD4_FIELDS - declared


def check_u1_flow_prerequisites():
    assert list(jf.step_prerequisites("flow")) == ["brief", "audience", "message"]


def check_u1_all_fields_reachable():
    for branded in ("branded", "unbranded"):
        seen: set[str] = set()
        answers: dict = {}
        for step in jf.STEPS:
            _answer_all(step, answers, branded)
        seen = set(answers)
        expected = {f["key"] for f in jf.FIELDS
                    if branded == "branded" or f["key"] not in jf.CLAIM_FIELDS}
        assert expected <= seen, expected - seen


def check_u1_unknown_step_raises():
    try:
        jf.open_fields("nope", {})
    except ValueError:
        return
    raise AssertionError("unknown step accepted")


# ---- U2: journey store --------------------------------------------------------------------

def check_u2_keep_one_of_three_personas():  # AE2
    b = _fresh_brand()
    ids = [bj.propose(b, "audience", "personas", {"name": f"P{i}", "who": "w", "tier": "Primary",
                                                  "voice": "v"}, mode="append", path="hcp")["id"]
           for i in range(3)]
    bj.keep(b, ids[0])
    bj.undo(b, ids[1])
    bj.undo(b, ids[2])
    st = _step(bj.journey_state(b), "audience")
    assert st["drafts"] == [], st["drafts"]
    hcp = brand_kit.kit_for(b)["personas"]["hcp"]
    assert [p["name"] for p in hcp] == ["P0"], hcp


def check_u2_keep_tagline_updates_kit():
    b = _fresh_brand()
    d = bj.propose(b, "message", "tagline", "Clarity, daily.")
    bj.keep(b, d["id"])
    assert json.loads(_KITS_COPY.read_text(encoding="utf-8"))["kits"][b]["tagline"] == "Clarity, daily."
    assert brand_kit.kit_for(b)["tagline"] == "Clarity, daily."


def check_u2_undo_leaves_kit_identical():
    b = _fresh_brand()
    before = _KITS_COPY.read_bytes()
    d = bj.propose(b, "message", "tagline", "Nope")
    bj.undo(b, d["id"])
    assert _KITS_COPY.read_bytes() == before
    bj.undo(b, d["id"])  # idempotent
    assert _KITS_COPY.read_bytes() == before


def check_u2_flow_waits_on_prereqs():  # AE5
    b = _fresh_brand()
    st = _step(bj.journey_state(b), "flow")
    assert st["waiting"] == ["brief", "audience", "message"], st["waiting"]


def check_u2_earlier_count_and_fresh_prompt():  # AE3
    b = _fresh_brand()
    for i in range(5):
        bj.add_turn(b, "audience", "user" if i % 2 == 0 else "agent", f"turn {i}")
    st = _step(bj.journey_state(b), "audience")
    assert st["earlier_count"] == 5, st["earlier_count"]
    assert "history" not in st
    assert st["question"] and st["question"]["key"] == "primary_audience", st["question"]
    full = _step(bj.journey_state(b, history_step="audience"), "audience")
    assert len(full["history"]) == 5


def check_u2_cardiovex_brief_confirmed():
    st = bj.journey_state("Cardiovex")
    assert _step(st, "brief")["status"] == "confirmed", _step(st, "brief")
    # branded is not on the kit yet: still an open Brief question
    assert _step(st, "brief")["question"]["key"] in ("lifecycle_stage", "success_measure", "branded")


def check_u2_confirmed_step_missing_kit_field_reads_drafted():
    b = _fresh_brand()
    for key, val in (("indication", "HF"), ("territories", ["US"]), ("key_objective", "Grow")):
        bj.keep(b, bj.propose(b, "brief", key, val)["id"])
    bj.confirm(b, "brief")
    assert _step(bj.journey_state(b), "brief")["status"] == "confirmed"
    brand_kit.apply_diff(b, {"indication": ""})
    assert _step(bj.journey_state(b), "brief")["status"] == "drafted"


def check_u2_open_question_skips_pending_draft():
    # The dock's question must match what a turn asks next, or a chip answers the wrong field.
    b = _fresh_brand()
    first = _step(bj.journey_state(b), "brief")["question"]["key"]
    d = bj.propose(b, "brief", first, "Pending value")
    st = _step(bj.journey_state(b), "brief")
    assert st["question"]["key"] != first, st["question"]
    assert st["question"]["key"] == jf.next_questions("brief", bj._effective_answers(b), 1)[0]["key"]
    assert first in st["missing"], st["missing"]
    bj.undo(b, d["id"])
    assert _step(bj.journey_state(b), "brief")["question"]["key"] == first


def check_u2_new_brand_not_started():
    b = _fresh_brand()
    st = bj.journey_state(b)
    assert _step(st, "message")["status"] == "not_started"
    assert set(bj.STATUSES) == {"not_started", "drafted", "confirmed"}


def check_u2_keep_missing_draft_raises():
    b = _fresh_brand()
    try:
        bj.keep(b, "does-not-exist")
    except KeyError:
        return
    raise AssertionError("keep of unknown draft accepted")


def check_u2_propose_validates():
    b = _fresh_brand()
    for args in (("nope", "tagline", "x"), ("brief", "tagline", "x")):
        try:
            bj.propose(b, *args)
        except ValueError:
            continue
        raise AssertionError(f"propose accepted {args}")


def check_u2_create_brand_has_ktd4_fields():
    b = _fresh_brand()
    kit = brand_kit.kit_for(b)
    assert KTD4_FIELDS <= set(kit), KTD4_FIELDS - set(kit)


# ---- U3: agent turn + document pre-fill endpoints (TestClient, LLM forced off) ----------

_client_cache: list = []


def _client():
    """TestClient over app.server.app with every conversation_llm instance forced off."""
    if not _client_cache:
        from fastapi.testclient import TestClient
        from app import server
        _client_cache.append(TestClient(server.app))
    for name in ("conversation_llm", "strategy.conversation_llm"):
        mod = sys.modules.get(name)
        if mod is not None:
            mod.llm_available = lambda: False
    return _client_cache[0]


def _sbj():
    """The strategy.brand_journey instance app/server.py uses (the one to monkeypatch)."""
    from strategy import brand_journey
    return brand_journey


class _patched:
    def __init__(self, mod, **attrs):
        self.mod, self.attrs = mod, attrs

    def __enter__(self):
        self.old = {k: getattr(self.mod, k) for k in self.attrs}
        for k, v in self.attrs.items():
            setattr(self.mod, k, v)

    def __exit__(self, *exc):
        for k, v in self.old.items():
            setattr(self.mod, k, v)


def check_u3_get_journey_and_unknowns():
    c = _client()
    b = _fresh_brand()
    r = c.get(f"/api/brands/{b}/journey")
    assert r.status_code == 200, r.text
    assert [s["step"] for s in r.json()["steps"]] == list(jf.STEPS)
    assert c.get("/api/brands/NoSuchBrandXYZ/journey").status_code == 404
    assert c.post(f"/api/brands/{b}/journey/nope/turn", json={"message": "hi"}).status_code == 404
    assert c.post("/api/brands/NoSuchBrandXYZ/journey/brief/turn",
                  json={"message": "hi"}).status_code == 404


def check_u3_llm_turn_drops_out_of_step_proposals():
    c = _client()
    b = _fresh_brand()

    def fake(system, payload):
        return {"reply": "Got it.", "proposals": {"indication": "Heart failure",
                                                  "tagline": "Out of step"}}
    with _patched(_sbj(), _llm_on=lambda: True, _call_turn_llm=fake):
        r = c.post(f"/api/brands/{b}/journey/brief/turn",
                   json={"message": "It's a heart failure drug called Cardiozen"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "llm", body
    assert {d["field"] for d in body["drafts"]} == {"indication"}, body["drafts"]
    assert "tagline" in body["dropped"], body
    assert all(d["step"] == "brief" for d in bj.list_drafts(b))
    assert bj.list_drafts(b, "message") == []


def check_u3_llm_turn_failure_falls_back():
    c = _client()
    b = _fresh_brand()

    def boom(system, payload):
        raise RuntimeError("provider down")
    with _patched(_sbj(), _llm_on=lambda: True, _call_turn_llm=boom):
        r = c.post(f"/api/brands/{b}/journey/brief/turn", json={"message": "Heart failure"})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "fallback"


def check_u3_fallback_turn_chip_becomes_draft():
    c = _client()
    b = _fresh_brand()
    st = c.get(f"/api/brands/{b}/journey").json()
    q = _step(st, "brief")["question"]
    assert q["key"] == "indication", q
    r = c.post(f"/api/brands/{b}/journey/brief/turn", json={"message": "Heart failure"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "fallback", body
    assert [(d["field"], d["value"]) for d in body["drafts"]] == [("indication", "Heart failure")]
    # territories defaults to ["US"] on create_brand, so lifecycle_stage (a chip question) is next
    assert body["question"]["key"] == "lifecycle_stage", body["question"]
    assert body["question"]["chips"] == jf.FIELDS_BY_KEY["lifecycle_stage"]["chips"]
    c.post(f"/api/brands/{b}/journey/brief/turn", json={"message": "Launch"})  # a chip
    r = c.post(f"/api/brands/{b}/journey/brief/turn", json={"message": "Grow share"})
    assert r.json()["question"]["key"] == "success_measure", r.json()["question"]
    fields = [d["field"] for d in bj.list_drafts(b, "brief")]
    assert fields == ["indication", "lifecycle_stage", "key_objective"], fields
    st = _step(bj.journey_state(b), "brief")
    assert st["status"] == "drafted" and st["earlier_count"] == 6, st


def check_u3_keep_undo_confirm_routes():
    c = _client()
    b = _fresh_brand()
    ids = [bj.propose(b, "brief", k, v)["id"] for k, v in
           (("indication", "HF"), ("key_objective", "Grow"))]
    extra = bj.propose(b, "brief", "success_measure", "NPS")["id"]
    r = c.post(f"/api/brands/{b}/journey/brief/undo", json={"draft_ids": [extra]})
    assert r.status_code == 200, r.text
    assert c.post(f"/api/brands/{b}/journey/brief/confirm").status_code == 400  # missing fields
    r = c.post(f"/api/brands/{b}/journey/brief/keep", json={"draft_ids": ids})
    assert r.status_code == 200, r.text
    assert brand_kit.kit_for(b)["indication"] == "HF"
    assert c.post(f"/api/brands/{b}/journey/brief/keep",
                  json={"draft_ids": ["missing"]}).status_code == 404
    r = c.post(f"/api/brands/{b}/journey/brief/confirm")
    assert r.status_code == 200, r.text
    assert _step(r.json(), "brief")["status"] == "confirmed"


def check_u3_keep_all_route():
    c = _client()
    b = _fresh_brand()
    bj.propose(b, "message", "tagline", "T1")
    r = c.post(f"/api/brands/{b}/journey/message/keep", json={"all": True})
    assert r.status_code == 200, r.text
    assert brand_kit.kit_for(b)["tagline"] == "T1"


def check_u3_start_with_document_prefills():  # F1
    c = _client()
    canned = {"brief": {"indication": "Heart failure", "tagline": "dropped: not brief"},
              "message": {"tagline": "Beat by beat"}}
    with _patched(_sbj(), extract_step=lambda step, text: canned.get(step, {})):
        r = c.post("/api/brands/journey/start", data={"name": "VerifyF1Brand"},
                   files={"file": ("plan.txt", b"Cardiozen brand plan", "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["brand"] == "VerifyF1Brand"
    assert sorted(body["changed_steps"]) == ["brief", "message"], body
    st = bj.journey_state("VerifyF1Brand")
    for step, field in (("brief", "indication"), ("message", "tagline")):
        s = _step(st, step)
        assert s["status"] == "drafted", s
        assert [d["field"] for d in s["drafts"]] == [field], s["drafts"]


def check_u3_start_with_sentence_only():  # F2
    c = _client()
    r = c.post("/api/brands/journey/start",
               data={"description": "A heart failure drug called Verifyzen"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["brand"] == "Verifyzen", body
    assert body["question"]["key"] == "indication", body["question"]
    assert brand_kit.kit_for("Verifyzen") is not None


def check_u3_start_duplicate_409_and_no_name_400():
    c = _client()
    assert c.post("/api/brands/journey/start", data={"name": "Cardiovex"}).status_code == 409
    assert c.post("/api/brands/journey/start", data={}).status_code == 400


def check_u3_revised_document_changes_only_message():  # F4
    c = _client()
    b = _fresh_brand()
    for step, vals in (("brief", {"indication": "HF", "key_objective": "Grow",
                                  "branded": "unbranded"}),
                       ("message", {"tagline": "Old", "positioning_statement": "P",
                                    "tone_pillars": ["Calm"]})):
        for k, v in vals.items():
            bj.keep(b, bj.propose(b, step, k, v)["id"])
    bj.confirm(b, "brief")
    bj.confirm(b, "message")
    canned = {"brief": {"indication": "HF", "key_objective": "Grow"},
              "message": {"tagline": "New", "positioning_statement": "P"}}
    with _patched(_sbj(), extract_step=lambda step, text: canned.get(step, {})):
        r = c.post(f"/api/brands/{b}/journey/document",
                   files={"file": ("rev.txt", b"revised plan", "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["changed_steps"] == ["message"], r.json()
    st = bj.journey_state(b)
    assert [d["field"] for d in _step(st, "message")["drafts"]] == ["tagline"]
    assert _step(st, "brief")["drafts"] == [] and _step(st, "brief")["status"] == "confirmed"
    assert _step(st, "message")["status"] == "drafted"
    r = c.post("/api/brands/NoSuchBrandXYZ/journey/document",
               files={"file": ("rev.txt", b"x", "text/plain")})
    assert r.status_code == 404, r.text


def check_u3_reuploaded_document_does_not_stack_drafts():
    b = _fresh_brand()
    canned = {"message": {"tagline": "Beat by beat"}}
    with _patched(bj, extract_step=lambda step, text: canned.get(step, {})):
        assert bj.apply_document(b, "plan") == ["message"]
        assert bj.apply_document(b, "plan") == [], "same document drafted again"
        canned["message"]["tagline"] = "Newer line"
        assert bj.apply_document(b, "plan v2") == ["message"]
    drafts = bj.list_drafts(b, "message")
    assert [(d["field"], d["value"]) for d in drafts] == [("tagline", "Newer line")], drafts


# ---- U6: brand-derived flow, stable block codes, structured edits -------------------------

def _flow_ready_brand() -> str:
    b = _fresh_brand("FlowBrand")
    vals = {
        "brief": [("indication", "Heart failure"), ("territories", ["US"]),
                  ("key_objective", "Grow new patient starts"), ("branded", "branded")],
        "audience": [("primary_audience", "HCPs"),
                     ("personas", {"hcp": [{"name": "The Busy Cardiologist", "who": "Treats HF",
                                            "tier": "Primary"}]})],
        "message": [("core_claim", "Fewer HF hospitalizations"),
                    ("positioning_statement", "The HF therapy that keeps patients home"),
                    ("message_hierarchy", [{"pillar": "Efficacy", "claim": "c", "evidence": "e"},
                                           {"pillar": "Safety", "claim": "c", "evidence": "e"}]),
                    ("tone_pillars", ["Confident"])],
    }
    for step, pairs in vals.items():
        for k, v in pairs:
            bj.keep(b, bj.propose(b, step, k, v)["id"])
        bj.confirm(b, step)
    return b


def _codes(doc: dict) -> dict:
    return {n["id"]: n["data"]["block_code"] for n in doc["flow"]["nodes"]}


def check_u6_build_has_send_wait_exit():
    doc = bj.build_flow(_flow_ready_brand())
    assert doc["status"] == "built", doc
    types = {n["type"] for n in doc["flow"]["nodes"]}
    assert {"send", "wait", "exit"} <= types, types
    codes = sorted(int(c[1:]) for c in _codes(doc).values())
    assert codes == list(range(1, len(codes) + 1)), codes


def check_u6_ctx_from_brand():
    b = _flow_ready_brand()
    ctx = bj.brand_ctx(b)
    assert ctx["brand"] == b and ctx["therapy_area"], ctx
    assert ctx["brief"]["objective"] == "Grow new patient starts", ctx["brief"]
    assert "HCPs" in ctx["brief"]["audience"], ctx["brief"]
    assert ctx["inferred"]["persona"] == "The Busy Cardiologist", ctx["inferred"]
    assert "content_library" in ctx


def check_u6_codes_stable_after_add_and_rebuild():  # AE4
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    before = _codes(doc)
    first = doc["flow"]["nodes"][1]["data"]["block_code"]
    r = bj.flow_turn(b, "", [{"op": "add", "type": "send", "label": "Rep visit", "after": first}])
    assert r["flow"]["draft"] and r["flow"]["draft"]["ops"], r
    bj.keep_flow_draft(b)
    rebuilt = bj.build_flow(b)
    after = _codes(rebuilt)
    for nid, code in before.items():
        assert after[nid] == code, (nid, code, after.get(nid))
    added = [c for nid, c in after.items() if nid not in before]
    assert added == [f"B{len(before) + 1}"], added
    assert rebuilt["dropped"] == [], rebuilt["dropped"]


def check_u6_change_unknown_code_rejected():
    c = _client()
    b = _flow_ready_brand()
    bj.build_flow(b)
    r = c.post(f"/api/brands/{b}/journey/flow/turn",
               json={"ops": [{"op": "change", "code": "B999", "set": {"label": "x"}}]})
    assert r.status_code == 400 and "B999" in r.text, r.text
    assert bj.get_flow(b)["draft"] is None


def check_u6_build_waits_when_brief_unconfirmed():  # AE5
    c = _client()
    b = _fresh_brand()
    r = c.post(f"/api/brands/{b}/journey/flow/build")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "waiting" and body["flow"] is None, body
    assert body["waiting"] == ["brief", "audience", "message"], body


def check_u6_llm_off_build_route_and_identical():
    c = _client()
    b = _flow_ready_brand()
    r1 = c.post(f"/api/brands/{b}/journey/flow/build")
    r2 = c.post(f"/api/brands/{b}/journey/flow/build")
    assert r1.status_code == 200 and r1.json()["status"] == "built", r1.text
    assert r1.json() == r2.json()
    assert c.get(f"/api/brands/{b}/journey/flow").json() == r2.json()


def check_u6_flow_draft_keep_undo_and_free_text_fallback():
    c = _client()
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    code = doc["flow"]["nodes"][1]["data"]["block_code"]
    r = c.post(f"/api/brands/{b}/journey/flow/turn",
               json={"ops": [{"op": "change", "code": code, "set": {"label": "Renamed"}}]})
    assert r.status_code == 200, r.text
    assert r.json()["flow"]["draft"]["flow"]["nodes"][1]["data"]["label"] == "Renamed"
    c.post(f"/api/brands/{b}/journey/flow/undo", json={"all": True})
    got = bj.get_flow(b)
    assert got["draft"] is None and got["flow"]["nodes"][1]["data"]["label"] != "Renamed"
    r = c.post(f"/api/brands/{b}/journey/flow/turn", json={"message": "add an SMS reminder"})
    assert r.status_code == 200 and r.json()["mode"] == "fallback" and r.json()["reply"], r.text
    assert bj.get_flow(b)["draft"] is None
    c.post(f"/api/brands/{b}/journey/flow/turn",
           json={"ops": [{"op": "remove", "code": code}]})
    c.post(f"/api/brands/{b}/journey/flow/keep", json={"all": True})
    got = bj.get_flow(b)
    assert code not in {n["data"]["block_code"] for n in got["flow"]["nodes"]}
    assert got["ops"] and got["draft"] is None


def check_u6_chained_adds_resolve_refs_and_survive_keep():
    b = _flow_ready_brand()
    doc = bj.build_flow(b)
    anchor = doc["flow"]["nodes"][1]["data"]["block_code"]
    ops = [{"op": "add", "type": "wait", "label": "Wait 3 days", "after": anchor, "ref": "N1"},
           {"op": "add", "type": "send", "label": "Reminder", "after": "N1", "channel": "email"}]
    r = bj.flow_turn(b, "", ops)
    added = [n for n in r["flow"]["draft"]["flow"]["nodes"] if n["id"].startswith("added_")]
    assert [n["data"]["label"] for n in added] == ["Wait 3 days", "Reminder"], added
    wait_id = added[0]["id"]
    assert any(e["source"] == wait_id and e["target"] == added[1]["id"]
               for e in r["flow"]["draft"]["flow"]["edges"]), "reminder not chained after wait"
    bj.keep_flow_draft(b)
    got = bj.build_flow(b)
    assert got["dropped"] == [], got["dropped"]
    assert {"Wait 3 days", "Reminder"} <= {n["data"]["label"] for n in got["flow"]["nodes"]}


def check_u6_flow_turn_llm_success_drafts_ops():
    b = _flow_ready_brand()
    code = bj.build_flow(b)["flow"]["nodes"][1]["data"]["block_code"]

    def fake(system, payload):
        assert code in payload, payload
        return {"reply": "Renamed it.", "ops": [{"op": "change", "code": code,
                                                 "set": {"label": "LLM renamed"}}]}
    with _patched(bj, _llm_on=lambda: True, _call_flow_llm=fake):
        r = bj.flow_turn(b, "rename the first send")
    assert r["mode"] == "llm" and r["reply"] == "Renamed it.", r
    draft = bj.get_flow(b)["draft"]
    assert draft and draft["flow"]["nodes"][1]["data"]["label"] == "LLM renamed", draft
    assert bj.get_flow(b)["flow"]["nodes"][1]["data"]["label"] != "LLM renamed"


def check_u6_flow_turn_llm_invalid_op_falls_back():
    b = _flow_ready_brand()
    bj.build_flow(b)

    def fake(system, payload):
        return {"reply": "Done.", "ops": [{"op": "change", "code": "B999", "set": {"label": "x"}}]}
    with _patched(bj, _llm_on=lambda: True, _call_flow_llm=fake):
        r = bj.flow_turn(b, "rename something that isn't there")
    assert r["mode"] == "fallback" and r["reply"] == bj._FLOW_HELP, r
    assert bj.get_flow(b)["draft"] is None


# ---- U8: retirement of the guided update screen + reset script ---------------------------

def check_u8_kit_update_route_gone():
    r = _client().get("/api/projects/Cardiovex/kit-update/Cardiovex")
    assert r.status_code == 404, r.status_code


def check_u8_reset_brand_clears_journey_rows_only():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reset_test_data", ROOT / "scripts" / "reset_test_data.py")
    rtd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rtd)
    b, other = _fresh_brand("ResetMe"), _fresh_brand("KeepMe")
    for x in (b, other):
        bj.propose(x, "message", "tagline", "T")
        bj.add_turn(x, "message", "user", "hi")
    kit_before = _KITS_COPY.read_bytes()
    counts = rtd.clear_brand_journey(b.upper())
    assert sum(counts.values()) >= 1, counts
    assert _KITS_COPY.read_bytes() == kit_before, "kit file changed"
    assert _REAL_KITS.read_bytes() == _REAL_KITS_BYTES
    conn = bj._conn()
    left = conn.execute("SELECT COUNT(*) FROM journey_drafts WHERE lower(brand) = lower(?)", (b,)).fetchone()[0]
    kept = conn.execute("SELECT COUNT(*) FROM journey_drafts WHERE lower(brand) = lower(?)", (other,)).fetchone()[0]
    conn.close()
    assert left == 0 and kept >= 1, (left, kept)


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
        brand_kit.KITS_JSON = _REAL_KITS
        brand_kit._load.cache_clear()
        assert _REAL_KITS.read_bytes() == _REAL_KITS_BYTES, "real brand_kits.json changed!"
        shutil.rmtree(_TMP, ignore_errors=True)
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
