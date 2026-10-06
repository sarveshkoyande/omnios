"""What Brand IQ already holds for a brand, so every agent can open with "Ready from Brand IQ" instead of
asking for the brand plan again. The brand plan is uploaded once, in the Brand IQ Agent; the other agents
read it from here.

Each item is ok / partial / missing / synthetic with a one-line detail and, when something is missing,
where to fix it. Nothing here calls a model.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
from paths import data_path  # noqa: E402

_FIX = "#/v3/agent/brand-iq"


def _has(v) -> bool:
    if isinstance(v, dict):
        return any(_has(x) for x in v.values())
    if isinstance(v, str):
        return bool(v.strip()) and not v.startswith("Needs input")
    return v not in (None, [], {})


def readiness(brand: str) -> dict:
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    key = brand_kit.canonical_key(brand)
    plans = kit.get("plans") or []
    active = next((p for p in plans if p.get("id") == kit.get("active_plan")), plans[0] if plans else None)
    view = {**kit, **(active or {})}
    items = []

    # Brand plan: a structured plan in the kit, or one uploaded through the Brand IQ Agent.
    uploaded = None
    up = data_path("brand_plans", f"{key}.json")
    if up.exists():
        try:
            uploaded = json.loads(up.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            uploaded = None
    from_plan = [k for k, v in (kit.get("proposals") or {}).items() if (v or {}).get("engine") == "kit_proposer.brand_plan"]
    imperatives, kpis = len(view.get("strategic_imperatives") or []), len(view.get("kpis") or [])
    if active:
        items.append({"id": "brand_plan", "label": "Brand plan", "status": "ok",
                      "detail": f"{active.get('name') or 'Brand plan'} · {imperatives} imperatives · {kpis} KPIs"})
    elif uploaded and (uploaded.get("filename") or from_plan):
        items.append({"id": "brand_plan", "label": "Brand plan", "status": "ok",
                      "detail": f"{uploaded.get('filename') or 'Your notes'} · read into {len(from_plan)} kit sections"})
    else:
        items.append({"id": "brand_plan", "label": "Brand plan", "status": "missing",
                      "detail": "No brand plan in Brand IQ yet: agents work from the kit and public sources, drafts marked to confirm",
                      "fix": _FIX})

    core = {"Positioning": view.get("positioning_statement"), "Core claim": view.get("core_claim"),
            "Messages": view.get("message_hierarchy"), "Guardrails": view.get("guardrails"),
            "Big Idea": view.get("tagline") or view.get("big_idea")}
    have = [k for k, v in core.items() if _has(v)]
    items.append({"id": "kit", "label": "Brand kit", "status": "ok" if len(have) >= 4 else "partial" if have else "missing",
                  "detail": ", ".join(have) if have else "Positioning, messages and guardrails not built yet",
                  **({} if len(have) >= 4 else {"fix": _FIX})})

    hcp = len(((view.get("personas") or {}).get("hcp")) or [])
    segs = len(view.get("audience_segments") or [])
    items.append({"id": "audiences", "label": "Audiences", "status": "ok" if hcp or segs else "missing",
                  "detail": f"{hcp} HCP persona(s), {segs} segment(s)" if hcp or segs else "No personas or segments yet",
                  **({} if hcp or segs else {"fix": _FIX})})

    flow = view.get("patient_flow") or []
    items.append({"id": "patient_flow", "label": "Patient flow", "status": "ok" if flow else "missing",
                  "detail": f"{len(flow)} indication(s) mapped" if flow else "Where patients are lost is not mapped yet",
                  **({} if flow else {"fix": _FIX})})

    try:
        import compliance
        cp = compliance.for_brand(key)
    except Exception:  # noqa: BLE001
        cp = None
    items.append({"id": "compliance", "label": "Compliance", "status": "ok" if cp else "missing",
                  "detail": (f"{len(((cp or {}).get('approval_workflow') or {}).get('steps') or [])}-step approval workflow, "
                             f"{len((cp or {}).get('channel_rules') or [])} channel rules") if cp else "No company SOPs assigned",
                  **({} if cp else {"fix": "#/v3/iq/guardrails"})})

    try:
        import client_data
        cd = client_data.summary(key)
        items.append({"id": "client_data", "label": "Client data", "status": "synthetic" if cd.get("synthetic") else "ok",
                      "detail": "Synthetic stand-in (no live HCP / access / field feed yet)" if cd.get("synthetic") else "Connected"})
    except Exception:  # noqa: BLE001
        items.append({"id": "client_data", "label": "Client data", "status": "missing", "detail": "Not generated yet", "fix": _FIX})

    stamps = [m for m in brand_kit._mtimes() if m]
    updated = dt.datetime.fromtimestamp(max(stamps) / 1e9).isoformat(timespec="minutes") if stamps else None
    return {"brand": key, "items": items, "updated": updated,
            "has_brand_plan": items[0]["status"] == "ok",
            "ready": any(i["status"] == "ok" for i in items)}


__all__ = ["readiness"]
