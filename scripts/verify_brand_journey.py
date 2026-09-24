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
