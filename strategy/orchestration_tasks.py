"""Stage 2 Orchestration task-checklist generator.

Turns what the plan already computed -- Stage 3's campaign-operations skeleton (touchpoints,
entry criteria, decision logic, segmentation), the message flow, and the Tactical Plan
(§26-33) -- into a flat, editable setup checklist. Pure derivation: no new agent call, no
new brief field, nothing here waits on user input that doesn't already exist in ctx by the
time Stage 1 finishes.

Each task is also routed to the team that owns picking it up (Web / Content & derivative
assets / Campaign operations / Data & data cloud / Reporting & insights), so the frontend
can render one board section per team instead of one per plan-derivation category.
"""
from __future__ import annotations

import json
import uuid

import campaign_ops
import conversation_llm
import orchestration_sla
import orchestration_taxonomy as tax
import plan_document

_NODE_VERB = {"send": "Build", "followup": "Build follow-up"}

# Fixed team roster + display order -- kept in sync with frontend/src/workspace/types.ts's
# ORCHESTRATION_TEAMS.
TEAM_WEB = "Web team"
TEAM_CONTENT = "Content & derivative assets team"
TEAM_CAMPAIGN_OPS = "Campaign operations team"
TEAM_DATA = "Data & data cloud team"
TEAM_REPORTING = "Reporting & insights team"

# Per-category default routing: which team picks it up, the SLA to clear it, the role
# typically assigned, and a one-line note on where the task was derived from (shown in the
# task-detail modal).
_CATEGORY_META = {
    "Touchpoint setup": (TEAM_CAMPAIGN_OPS, "10 business days", "Marketing Automation Lead",
                          "Derived from the Stage 3 campaign-operations flow -- one task per send/follow-up touchpoint instance."),
    "Journey logic": (TEAM_CAMPAIGN_OPS, "5 business days", "Campaign Operations Analyst",
                       "Derived from the campaign-operations entry criteria and decision-split logic."),
    "Segmentation": (TEAM_DATA, "5 business days", "Data & Audience Analyst",
                      "Derived from the campaign-operations audience segments."),
    "Content & tactics": (TEAM_CONTENT, "15 business days", "Content Strategist",
                           "Derived from the Stage 1 message flow's key messages."),
    "Tactical plan (CSFs)": (TEAM_CAMPAIGN_OPS, "10 business days", "Campaign Operations Lead",
                              "Derived from the Stage 1 Tactical Plan critical success factors (§26-33)."),
    "Scientific engagement": (TEAM_CONTENT, "15 business days", "Medical Content Lead",
                               "Derived from the plan's scientific evidence / proof points."),
    "Account & pathway": (TEAM_CAMPAIGN_OPS, "7 business days", "Field Operations Lead",
                           "Derived from the plan's account archetypes and pathway moves."),
    "Patient & support": (TEAM_CONTENT, "5 business days", "Regulatory/Legal Liaison",
                           "Manual compliance gate -- confirm with regulatory/legal before activation."),
    "Measurement": (TEAM_REPORTING, "7 business days", "Analytics Lead",
                     "Derived from the plan's KPI leading indicators."),
    "Custom": (TEAM_CAMPAIGN_OPS, "TBD", "Unassigned", "Manually added task."),
}

# Touchpoint-setup tasks are further re-routed to the Web team when the channel is a
# web/portal-surfaced one rather than a marketing-automation send.
_WEB_CHANNEL_KEYWORDS = ("web", "ehr", "point-of-care", "portal", "landing")


def _team_for_touchpoint(channel: str | None) -> str:
    c = (channel or "").lower()
    if any(k in c for k in _WEB_CHANNEL_KEYWORDS):
        return TEAM_WEB
    return TEAM_CAMPAIGN_OPS


def _task(category: str, title: str, channel: str | None = None, team: str | None = None,
          complexity: str = orchestration_sla.DEFAULT_COMPLEXITY) -> dict:
    default_team, sla_str, role, source = _CATEGORY_META.get(category, _CATEGORY_META["Custom"])
    task = {
        "id": uuid.uuid4().hex[:10],
        "category": category,
        "title": title,
        "channel": channel,
        "done": False,
        "team": team or default_team,
        "sla": sla_str,          # display string -- overwritten below when an SLA record exists
        "assigned_to": role,
        "source": source,
    }
    return _enrich(task, complexity)


def _enrich(task: dict, complexity: str = orchestration_sla.DEFAULT_COMPLEXITY) -> dict:
    """Attach the Engagement Orchestration activity model to a base task: activity-type, the
    governed multi-dimensional tags, the structured SLA (baseline vs target days + definition-of-
    done + input gate), the compliance tier / hard-gate kind, automation class, and risk. Pure
    lookup off orchestration_taxonomy + orchestration_sla -- deterministic, no LLM. The flat `sla`
    string is kept for frontend back-compat; the structured record lives under `sla_meta`."""
    reg = tax.registry_for(task.get("category", "Custom"))
    activity_type = reg["activity_type"]
    resolved = orchestration_sla.resolve(activity_type, complexity)
    task["activity_type"] = activity_type
    task["phase"] = reg["phase"]
    task["automation_class"] = reg["automation"]
    task["compliance_tier"] = reg["tier"]
    task["gate"] = reg["gate"]  # hard-gate kind or None -- never agent-closable (PRD F9)
    task["risk"] = reg["risk"]
    task["definition_of_done"] = resolved["definition_of_done"]
    task["gating_input"] = resolved["gating_input"]
    task["sla_meta"] = resolved
    task["sla"] = resolved["sla_label"]
    task["tags"] = {
        "team": task.get("team"),
        "channel": (task.get("channel") or "").lower() if task.get("channel") else None,
        "asset_type": reg["asset_type"],
        "phase": reg["phase"],
        "compliance_tier": reg["tier"],
        "automation_class": reg["automation"],
        "risk": reg["risk"],
    }
    return task


CATEGORIES = list(_CATEGORY_META)

TEAMS = [TEAM_WEB, TEAM_CONTENT, TEAM_CAMPAIGN_OPS, TEAM_DATA, TEAM_REPORTING]


def manual_task(title: str, category: str = "Custom", channel: str | None = None,
                team: str | None = None, assigned_to: str | None = None) -> dict:
    """A user-authored activity (e.g. added through the orchestration agent's chat):
    same enriched shape as a derived task, category defaults to Custom."""
    if category not in _CATEGORY_META:
        category = "Custom"
    if team not in TEAMS:
        team = None
    task = _task(category, title, channel=channel, team=team)
    if assigned_to:
        task["assigned_to"] = assigned_to
    task["source"] = "Added manually via the orchestration agent."
    return task


def reenrich(task: dict) -> dict:
    """Recompute the derived activity-model fields after a category/complexity edit."""
    return _enrich(task)


def ensure_enriched(tasks: list[dict]) -> list[dict]:
    """Back-compat: activities saved before the Engagement Orchestration model existed are flat
    ({id,category,title,team,sla-string,...}). Re-run the pure-lookup enrichment on any task
    missing `sla_meta` so the scheduler / view / connectors always see the full model, without
    disturbing user edits to the fields that already exist."""
    out = []
    for t in tasks or []:
        out.append(t if t.get("sla_meta") else _enrich(dict(t)))
    return out


def generate_tasks(ctx: dict, extra_context: str | None = None) -> list[dict]:
    """extra_context: free text the user typed or a document they uploaded when kicking off
    Stage 2 from the frontend chat, instead of just using the Stage 1 plan as-is. Folded in
    as additional tasks on top of the deterministic derivation below, never replacing it."""
    tasks: list[dict] = []
    campaign_plan = campaign_ops.build_campaign_plan(ctx)

    # Touchpoint setup -- one task per real send/followup node in the campaign-ops flow
    # (already-derived touchpoint instances, one per primary channel + one per segment).
    for node in campaign_plan.get("flow", {}).get("nodes", []):
        if node.get("type") not in _NODE_VERB:
            continue
        data = node.get("data", {})
        channel = data.get("channel", "Channel")
        title = f"{_NODE_VERB[node['type']]} {channel}" + (f" — {data['label']}" if data.get("label") else "")
        tasks.append(_task("Touchpoint setup", title, channel, team=_team_for_touchpoint(channel)))

    # Journey logic setup -- entry criteria + decision splits.
    for c in campaign_plan.get("entry_criteria", []):
        tasks.append(_task("Journey logic", f"Implement entry criterion: {c}"))
    for d in campaign_plan.get("decision_logic_summary", []):
        tasks.append(_task("Journey logic",
                           f"Configure decision split: {d.get('condition', '')} → {d.get('outcome', '')}"))

    # Segmentation.
    for seg in campaign_plan.get("segments", []):
        vol = f" (~{seg['volume']:,} contacts)" if seg.get("volume") else ""
        tasks.append(_task("Segmentation", f"Confirm targeting for segment: {seg.get('name', '')}{vol}"))

    # Content & tactics.
    for km in (ctx.get("message_flow") or {}).get("key_messages", []):
        if km.get("topic"):
            tasks.append(_task("Content & tactics", f"Prepare content for message: {km['topic']}"))

    # Tactical plan activities (§26-33) -- reuse the exact same derivations the plan
    # document's own sections use, so Stage 1 and Stage 2 never disagree.
    for c in plan_document._tactical_csfs(ctx):
        tasks.append(_task("Tactical plan (CSFs)", f"Activate CSF: {c['title']}"))

    src = ctx.get("strategic_source")
    sci_items = (src.get("evidence") if src and src.get("evidence") else None) or \
        ((ctx.get("strategy") or {}).get("messaging_architecture") or {}).get("proof_points", [])
    for e in sci_items[:5]:
        tasks.append(_task("Scientific engagement", f"Prep scientific-exchange anchor: {e}"))

    for name, move in plan_document._account_archetypes(ctx):
        tasks.append(_task("Account & pathway", f"{name}: {move}"))

    tasks.append(_task("Patient & support", "Confirm patient-gate status with regulatory/legal"))

    for ind in (ctx.get("kpi") or {}).get("leading_indicators", []):
        tasks.append(_task("Measurement", f"Stand up tracking for: {ind}"))

    if extra_context and extra_context.strip():
        tasks.extend(_extra_tasks_from_context(extra_context.strip()))

    return tasks


_EXTRA_TASKS_SYSTEM = f"""You turn a user's free-text note or uploaded document into extra
Stage 2 setup tasks for a pharma omnichannel campaign, on top of a checklist already derived
from the plan. Read the text and propose only concrete, actionable setup tasks it implies --
skip anything already generic/obvious. Return ONLY a raw JSON array (no markdown fence, no
prose), each item: {{"category": one of {list(_CATEGORY_META.keys())!r}, "title": str,
"channel": str or null}}. Return [] if the text implies no additional setup work. Max 8 items."""


def _extra_tasks_from_context(text: str) -> list[dict]:
    """Best-effort LLM pass over user-supplied extra context -> additional tasks. Falls back
    to a single Custom task carrying the raw note so the user's input is never silently
    dropped when the LLM is unavailable or misbehaves."""
    fallback = [_task("Custom", f"Review additional context: {text[:140]}{'…' if len(text) > 140 else ''}")]
    if not conversation_llm.llm_available():
        return fallback
    try:
        client = conversation_llm._get_client()
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=1500, system=_EXTRA_TASKS_SYSTEM,
            messages=[{"role": "user", "content": text[:12000]}])
        raw = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[:-3]
        items = json.loads(raw.strip())
        if not isinstance(items, list):
            return fallback
        out = []
        for it in items[:8]:
            if not isinstance(it, dict) or not it.get("title"):
                continue
            category = it.get("category") if it.get("category") in _CATEGORY_META else "Custom"
            out.append(_task(category, str(it["title"]), it.get("channel")))
        return out or fallback
    except Exception:  # noqa: BLE001 -- never break checklist generation on an LLM/parse failure
        return fallback
