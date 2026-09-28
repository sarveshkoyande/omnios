"""Builds an agent's input cards from its framework config (redesign M1/M3/M4/M6).

The framework lives in config/frameworks/<id>.json: stages -> data points, each marked
derive / confirm / ask with where its value comes from. This module resolves those sources
against the real brand kit, plan and campaign and returns cards ready to render. It reads
structured fields by path; it never interprets free text.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import channel_selection  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_FRAMEWORKS = _ROOT / "config" / "frameworks"


def load_framework(framework_id: str) -> dict:
    return json.loads((_FRAMEWORKS / f"{framework_id}.json").read_text(encoding="utf-8"))


def framework_for_agent(agent_id: str) -> tuple[dict, list[str]] | None:
    """The framework and the stage ids an agent works with (what it consumes or owns)."""
    for path in sorted(_FRAMEWORKS.glob("*.json")):
        fw = json.loads(path.read_text(encoding="utf-8"))
        spec = (fw.get("agents") or {}).get(agent_id)
        if spec:
            return fw, list(spec.get("consumes") or spec.get("owns") or [])
    return None


_STEP = re.compile(r"^(\w+)(\[(\d*)\])?$")  # path syntax only: "name", "name[]", "name[0]"


def _get(obj, path: str):
    """Reads a dotted path; `list[]` plucks a field from every item, `list[0]` indexes."""
    cur = [obj]
    plucking = False
    for part in path.split("."):
        m = _STEP.match(part)
        if not m:
            return None
        key, bracket, idx = m.group(1), m.group(2), m.group(3)
        nxt = []
        for c in cur:
            v = c.get(key) if isinstance(c, dict) else None
            if v is None:
                continue
            if bracket is None:
                nxt.append(v)
            elif idx:
                if isinstance(v, list) and int(idx) < len(v):
                    nxt.append(v[int(idx)])
            else:
                plucking = True
                nxt.extend(v if isinstance(v, list) else [])
        cur = nxt
    if plucking:
        return [c for c in cur if c not in (None, "")]
    return cur[0] if cur else None


def _resolve(src, ctx: dict):
    if isinstance(src, dict) and "value" in src:
        return src["value"]
    if isinstance(src, dict) and src.get("from") == "toolkit_channels":
        return list(channel_selection._CHANNEL_TO_BUCKET.keys())
    if isinstance(src, dict) and src.get("from") in ctx:
        return _get(ctx[src["from"]], src["path"])
    return src  # a literal list or string in the config


def _display(value, spec: dict, brand: str) -> str | None:
    if value in (None, "", [], {}):
        return spec.get("empty")
    if isinstance(value, list):
        if spec.get("count"):
            return f"{len(value)} {spec['count']}"
        value = ", ".join(str(v) for v in value)
    tpl = spec.get("template")
    if tpl:
        fields = value if isinstance(value, dict) else {}
        return tpl.format(value=value, brand=brand, **fields)
    return str(value)


def build_cards(agent_id: str, brand: str, plan: dict | None, campaign: dict | None,
                territory: str | None = None) -> dict:
    found = framework_for_agent(agent_id)
    if not found:
        return {"framework": None, "stages": []}
    fw, stage_ids = found
    kit = brand_kit.kit_for(brand) if brand else {}
    ctx = {"kit": kit or {}, "plan": plan or {}, "campaign": campaign or {}}

    stages = []
    for st in fw["stages"]:
        if st["id"] not in stage_ids:
            continue
        points = []
        for dp in st["data_points"]:
            spec = dp.get("prefill") or {}
            value = _display(_resolve({k: spec[k] for k in ("from", "path") if k in spec}, ctx), spec, brand) \
                if spec.get("from") else None
            options = _resolve(spec["options"], ctx) if "options" in spec else []
            recommendation = _resolve(spec["recommend"], ctx) if "recommend" in spec else None
            points.append({
                "key": dp["key"], "label": dp["label"], "source": dp["source"],
                "derivation": dp["derivation"], "value": value,
                "options": [str(o) for o in (options or [])],
                "recommendation": str(recommendation) if recommendation else None,
            })
        stages.append({k: st[k] for k in ("id", "name", "decision", "framework", "how", "feeds")} | {"data_points": points})
    return {
        "framework": {"id": fw["id"], "name": fw["name"], "derivation_meaning": fw["derivation_meaning"]},
        "stages": stages,
    }
