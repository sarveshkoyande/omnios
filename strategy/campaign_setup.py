"""Campaign delivery orchestration setup (Stage 2): the project manager's initial
setup of the campaign operation -- Jira space, stakeholder register, vendor
details, timeline/resource planning, and the RACI + BRD that fall out of it.

This is deliberately separate from the Stage-1 brand-plan/strategy result: it's
project-management scaffolding around delivering the plan, not more research
agent output. `result` (the Stage-1 PlanResult dict) is only read here, never
written.
"""
from __future__ import annotations

RACI_LETTERS = ("R", "A", "C", "I")

EMPTY_SETUP = {
    "jira": {"space_key": "", "project_id": "", "board_url": ""},
    "stakeholders": [],
    "vendors": [],
    "confirmations": [],
    "timeline": [],
    "resources": [],
    "raci": [],
    "brd": None,
}


def default_setup() -> dict:
    return {**EMPTY_SETUP, "stakeholders": [], "vendors": [], "confirmations": [], "timeline": [], "resources": [], "raci": []}


def build_raci(setup: dict) -> list[dict]:
    """Derive a RACI table: one row per timeline activity, one column per
    stakeholder, populated from each activity's `raci` assignment map
    (stakeholder_id -> R/A/C/I) that the PM fills in on the timeline row."""
    stakeholders = setup.get("stakeholders") or []
    timeline = setup.get("timeline") or []
    by_id = {s["id"]: s for s in stakeholders}
    rows = []
    for activity in timeline:
        assignments = activity.get("raci") or {}
        row = {
            "activity": activity.get("activity", ""),
            "assignments": [
                {
                    "stakeholder_id": sid,
                    "name": by_id.get(sid, {}).get("name", "?"),
                    "letter": letter,
                }
                for sid, letter in assignments.items()
                if letter in RACI_LETTERS
            ],
        }
        rows.append(row)
    return rows


def build_brd(result: dict | None, setup: dict, project_name: str) -> str:
    """Assemble a Business Requirements Document (markdown) for the campaign
    delivery, pulling brand-plan facts from the Stage-1 result and operational
    facts (stakeholders, vendors, timeline, RACI) from the setup the PM entered."""
    result = result or {}
    strategy = result.get("stage_2_4_strategy") or {}
    messaging = strategy.get("messaging_architecture") or {}
    message_flow = result.get("stage_2_4_message_flow") or {"key_messages": []}
    channels = (result.get("stage_5_channel_selection") or {}).get("channels") or []

    jira = setup.get("jira") or {}
    stakeholders = setup.get("stakeholders") or []
    vendors = setup.get("vendors") or []
    confirmations = setup.get("confirmations") or []
    timeline = setup.get("timeline") or []
    resources = setup.get("resources") or []
    raci = setup.get("raci") or build_raci(setup)

    lines: list[str] = []
    lines.append(f"# Business Requirements Document — {project_name}")
    lines.append("")
    lines.append("## 1. Background")
    lines.append("")
    if messaging.get("current_belief") or messaging.get("desired_belief"):
        lines.append(
            f"Belief shift objective: **{messaging.get('current_belief', '—')}** → "
            f"**{messaging.get('desired_belief', '—')}**."
        )
    lines.append("")
    lines.append("## 2. Key messages")
    lines.append("")
    if message_flow.get("key_messages"):
        for km in message_flow["key_messages"]:
            lines.append(f"- **{km.get('topic', '')}** — {', '.join(km.get('supporting_messages', [])[:2])}")
    else:
        lines.append("_No key messages captured in Stage 1 yet._")
    lines.append("")
    lines.append("## 3. Channels in scope")
    lines.append("")
    if channels:
        for c in channels:
            lines.append(f"- {c.get('channel', '')} (priority: {c.get('brand_priority', '—')})")
    else:
        lines.append("_No channel selection captured in Stage 1 yet._")
    lines.append("")
    lines.append("## 4. Delivery tracking")
    lines.append("")
    lines.append(f"- Jira space: `{jira.get('space_key', '—')}`")
    lines.append(f"- Jira project ID: `{jira.get('project_id', '—')}`")
    if jira.get("board_url"):
        lines.append(f"- Board: {jira['board_url']}")
    lines.append("")
    lines.append("## 5. Stakeholder register")
    lines.append("")
    if stakeholders:
        lines.append("| Name | Role | Team | Contact |")
        lines.append("|---|---|---|---|")
        for s in stakeholders:
            lines.append(f"| {s.get('name', '')} | {s.get('role', '')} | {s.get('team', '')} | {s.get('email', '')} |")
    else:
        lines.append("_No stakeholders registered yet._")
    lines.append("")
    lines.append("## 6. Vendor details")
    lines.append("")
    if vendors:
        lines.append("| Vendor | Type | Contact | Status |")
        lines.append("|---|---|---|---|")
        for v in vendors:
            lines.append(f"| {v.get('name', '')} | {v.get('type', '')} | {v.get('contact', '')} | {v.get('status', '')} |")
    else:
        lines.append("_No vendors registered yet._")
    lines.append("")
    lines.append("## 7. Stakeholder reconfirmation (marketing / medical asset availability)")
    lines.append("")
    if confirmations:
        lines.append("| Team | Item | Status | Notes |")
        lines.append("|---|---|---|---|")
        for c in confirmations:
            lines.append(f"| {c.get('team', '')} | {c.get('item', '')} | {c.get('status', '')} | {c.get('notes', '')} |")
    else:
        lines.append("_No reconfirmations logged yet._")
    lines.append("")
    lines.append("## 8. Timeline")
    lines.append("")
    if timeline:
        lines.append("| Activity | Start | End | Duration (days) | Status |")
        lines.append("|---|---|---|---|---|")
        for a in timeline:
            lines.append(f"| {a.get('activity', '')} | {a.get('start', '')} | {a.get('end', '')} | {a.get('duration_days', '')} | {a.get('status', '')} |")
    else:
        lines.append("_No timeline entered yet._")
    lines.append("")
    lines.append("## 9. Resource plan")
    lines.append("")
    if resources:
        lines.append("| Role | Assigned to | Allocation % | Notes |")
        lines.append("|---|---|---|---|")
        for r in resources:
            lines.append(f"| {r.get('role', '')} | {r.get('stakeholder_name', '')} | {r.get('allocation_pct', '')} | {r.get('notes', '')} |")
    else:
        lines.append("_No resource plan entered yet._")
    lines.append("")
    lines.append("## 10. RACI")
    lines.append("")
    if raci:
        lines.append("| Activity | Responsible | Accountable | Consulted | Informed |")
        lines.append("|---|---|---|---|---|")
        for row in raci:
            by_letter = {"R": [], "A": [], "C": [], "I": []}
            for a in row.get("assignments", []):
                if a["letter"] in by_letter:
                    by_letter[a["letter"]].append(a["name"])
            lines.append(
                f"| {row.get('activity', '')} | {', '.join(by_letter['R'])} | {', '.join(by_letter['A'])} | "
                f"{', '.join(by_letter['C'])} | {', '.join(by_letter['I'])} |"
            )
    else:
        lines.append("_No RACI generated yet — add timeline activities and stakeholder assignments first._")
    lines.append("")
    return "\n".join(lines)
