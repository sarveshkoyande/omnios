"""Engagement Orchestration -- Nudge agent (PRD 6.8, M4).

Evaluates the scheduled activities and emits notifications to the owning teams, so work is
surfaced proactively instead of chased. Autonomy = **notify + auto-escalate**: the agent notifies
owners and, on repeated overdue, escalates to the lead/conductor automatically -- but it never
closes a compliance gate (PRD F9); AE/MIR is detection + routing only, never auto-response.

Triggers (per not-done activity, from the schedule):
  assigned  -- once, when the activity exists: tells the team it's theirs, with the brief + due.
  upcoming  -- start is within the policy lead time.
  overdue   -- past its planned due date. Escalatable: repeated fires -> escalate to lead/conductor.
  at-risk   -- on the critical path (zero slack) and not yet done.
  gate      -- a hard compliance gate is pending; routed to the gate owner. AE/MIR is urgent +
               escalatable and goes to Pharmacovigilance/Medical Information.
  expiry    -- an AFU asset is within 30/60/90 days of expiry (fires only once Veeva expiry data
               is present, M5); the hook is here now.

De-duplication + cooldown: one notification row per (activity, trigger); re-running increments a
fire_count rather than spamming, and an acknowledged notification is not re-raised. Every nudge is
recorded (channel + recipient + fire history) as an audit by-product.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import orchestration_store as store  # noqa: E402

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
POLICY_JSON = BASE_DIR / "config" / "orchestration_nudge.json"

_SEVERITY_RANK = {"urgent": 0, "high": 1, "warning": 2, "info": 3}


def load_policy() -> dict:
    try:
        return json.loads(POLICY_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"lead_time_days": 3, "escalate_after_fires": 2,
                "escalation_recipient": "Campaign conductor", "default_channel": "email",
                "teams": {}, "gate_recipients": {}}


def _parse(d) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(d)[:10])
    except (ValueError, TypeError):
        return None


def _channel(team: str, policy: dict) -> str:
    return ((policy.get("teams") or {}).get(team) or {}).get("channel") or policy.get("default_channel", "email")


def _gate_recipient(gate: str, policy: dict) -> str:
    return (policy.get("gate_recipients") or {}).get(gate, "MLR / Regulatory / Medical")


def _triggers_for(a: dict, now: _dt.date, lead_days: int) -> list[dict]:
    """The nudge conditions an activity currently meets. Each: trigger/severity/title/body/
    escalatable (+ optional recipient/channel override for gate routing)."""
    out: list[dict] = []
    title = a.get("title", "activity")
    due = _parse(a.get("planned_due"))
    start = _parse(a.get("planned_start"))
    team = a.get("team", "")
    sla = a.get("sla") or ""
    dod = a.get("definition_of_done") or ""

    # assigned -- one-time acknowledgement that this is the team's work, with everything to start.
    brief = f"Owner: {team}. Due {a.get('planned_due','TBD')}. SLA {sla}. Done when: {dod}"
    out.append({"trigger": "assigned", "severity": "info", "escalatable": False,
                "title": f"New activity assigned: {title}", "body": brief})

    if due and due < now:
        out.append({"trigger": "overdue", "severity": "high", "escalatable": True,
                    "title": f"Overdue: {title}",
                    "body": f"Was due {a.get('planned_due')} and isn't done. {team} to complete or request an extension."})
    elif start and 0 <= (start - now).days <= lead_days:
        out.append({"trigger": "upcoming", "severity": "info", "escalatable": False,
                    "title": f"Starting soon: {title}",
                    "body": f"Planned to start {a.get('planned_start')} ({(start - now).days}d). {brief}"})

    if a.get("is_critical") and not (due and due < now):
        out.append({"trigger": "at-risk", "severity": "warning", "escalatable": False,
                    "title": f"On the critical path: {title}",
                    "body": f"Zero slack — a slip here moves go-live. Waiting on: {a.get('gating_input') or 'nothing'}."})

    gate = a.get("gate")
    if gate == "AE_MIR":
        out.append({"trigger": "gate", "severity": "urgent", "escalatable": True,
                    "title": f"AE/MIR routing: {title}",
                    "body": "Potential adverse-event / medical-information signal — route to PV/Medical Info within SLA. Detection + routing only; never auto-respond.",
                    "recipient_gate": gate})
    elif gate:
        out.append({"trigger": "gate", "severity": "warning", "escalatable": False,
                    "title": f"{gate} gate pending: {title}",
                    "body": f"Hard {gate} gate must be cleared by a human before this can complete — routed, tracked, never auto-closed.",
                    "recipient_gate": gate})

    # asset-expiry hook (fires once AFU expiry data is present, M5).
    exp = _parse(a.get("afu_expiry"))
    if exp:
        days = (exp - now).days
        for th in (30, 60, 90):
            if 0 <= days <= th:
                out.append({"trigger": f"expiry-{th}", "severity": "warning", "escalatable": False,
                            "title": f"AFU expiring in ≤{th}d: {title}",
                            "body": f"Approved asset expires {a.get('afu_expiry')} — refresh/renew via Veeva."})
                break
    return out


def run_nudges(project_id: str, scheduled_activities: list[dict], today: str | None = None) -> dict:
    """Evaluate all activities and raise/refresh notifications. Returns the created/refreshed set,
    the subset that escalated, and the current open (unacked) notifications."""
    now = _parse(today) or _dt.date.today()
    policy = load_policy()
    lead = int(policy.get("lead_time_days", 3))
    esc_after = int(policy.get("escalate_after_fires", 2))
    esc_to = policy.get("escalation_recipient", "Campaign conductor")

    created: list[dict] = []
    escalated: list[dict] = []
    for a in scheduled_activities:
        if a.get("done"):
            continue
        for trig in _triggers_for(a, now, lead):
            dedupe = f"{a['id']}:{trig['trigger']}"
            existing = store.get_notification(project_id, dedupe)
            if existing and existing.get("acked"):
                continue  # already handled -- don't re-raise
            fire_count = (existing["fire_count"] if existing else 0) + 1
            escalate = bool(trig.get("escalatable")) and fire_count >= esc_after
            if trig["trigger"] == "gate" and trig.get("recipient_gate"):
                recipient = _gate_recipient(trig["recipient_gate"], policy)
                channel = _channel(recipient, policy)
            else:
                recipient = a.get("team", "")
                channel = _channel(recipient, policy)
            if escalate:
                recipient = f"{recipient} → {esc_to}"
            store.upsert_notification(project_id, dedupe, activity_id=a["id"], trigger=trig["trigger"],
                                      severity=trig["severity"], channel=channel, recipient=recipient,
                                      title=trig["title"], body=trig["body"], gate=a.get("gate"),
                                      fire_count=fire_count, escalated=escalate)
            row = {"dedupe_key": dedupe, "activity_id": a["id"], "trigger": trig["trigger"],
                   "severity": trig["severity"], "channel": channel, "recipient": recipient,
                   "title": trig["title"], "fire_count": fire_count, "escalated": escalate}
            created.append(row)
            if escalate:
                escalated.append(row)

    created.sort(key=lambda r: _SEVERITY_RANK.get(r["severity"], 9))
    return {"created": created, "escalated": escalated,
            "open": store.list_notifications(project_id, include_acked=False)}
