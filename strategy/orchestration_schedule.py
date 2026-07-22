"""Engagement Orchestration -- timeline / schedule engine.

Places enriched activities on a calendar by campaign phase and computes the elapsed timeline,
the critical path, per-activity slack, and the elapsed time saved vs the manual baseline.

Model (M1 -- phase-band critical path, the same banding execution_plan.py uses, but per-activity
and SLA-driven):
  - Activities are grouped by campaign phase (planning -> production -> review -> execution ->
    wrap). Phases run in sequence (finish-to-start); activities WITHIN a phase run in parallel.
  - A phase's duration = the longest activity in it (its critical activity). Total pre-launch
    elapsed time = sum of pre-launch phase durations. This is the elapsed/critical-path figure,
    distinct from the effort-day sum in orchestration_sla.summarize_time_saved().
  - Two scheduling modes (PRD F4.1/F4.3):
      * backward  -- anchor the execution phase's end on a given go-live date, walk starts back.
        Flags infeasibility if a required start lands before `today` (PRD F4.6).
      * forward   -- anchor planning's start on a start date (default today); go-live falls out.
  - The wrap phase (measurement) runs AFTER go-live.
  - Dates are business days (Mon-Fri). No holiday calendar yet -- the vault flags a real holiday /
    working-day calendar as an open item; wire it here when available.

See PRD-Orchestration-Phase.md section 6.4.
"""
from __future__ import annotations

import datetime as _dt

import orchestration_sla as sla
import orchestration_taxonomy as tax

_PRE_LAUNCH = [tax.PHASE_PLANNING, tax.PHASE_PRODUCTION, tax.PHASE_REVIEW, tax.PHASE_EXECUTION]
_POST_LAUNCH = [tax.PHASE_WRAP]


# --- business-day date math -------------------------------------------------------------------

def _parse(d: str | None) -> _dt.date | None:
    if not d:
        return None
    try:
        return _dt.date.fromisoformat(d[:10])
    except (ValueError, TypeError):
        return None


def add_business_days(start: _dt.date, n: int) -> _dt.date:
    """Advance `start` by `n` business days (n may be negative). n=0 returns the next business day
    on or after start when start is a weekend, else start itself."""
    d = start
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    # normalise a weekend start onto a weekday first
    while d.weekday() >= 5:
        d += _dt.timedelta(days=step)
    while remaining > 0:
        d += _dt.timedelta(days=step)
        if d.weekday() < 5:
            remaining -= 1
    return d


def _phase_of(a: dict) -> str:
    return a.get("phase") or (a.get("tags") or {}).get("phase") or tax.PHASE_PRODUCTION


def _duration(a: dict) -> int:
    s = a.get("sla_meta") or {}
    return max(1, int(s.get("target_days") or 1))


def _baseline_duration(a: dict) -> int:
    s = a.get("sla_meta") or {}
    return max(1, int(s.get("baseline_days") or _duration(a)))


# --- core --------------------------------------------------------------------------------------

def _phase_durations(activities: list[dict], key) -> dict[str, int]:
    """Longest activity per phase (the phase's critical activity), using duration fn `key`."""
    out: dict[str, int] = {}
    for a in activities:
        p = _phase_of(a)
        out[p] = max(out.get(p, 0), key(a))
    return out


def build_schedule(activities: list[dict], go_live: str | None = None,
                   start_date: str | None = None, today: str | None = None) -> dict:
    """Compute the full schedule. Returns per-activity planned_start/planned_due (+ is_critical /
    slack_days), phase bands, the critical path, go-live date, elapsed figures, and the elapsed
    time-saved-vs-baseline number for the ROI lens."""
    now = _parse(today) or _dt.date.today()
    present = [p for p in tax.PHASE_ORDER if any(_phase_of(a) == p for a in activities)]
    pre = [p for p in _PRE_LAUNCH if p in present]
    post = [p for p in _POST_LAUNCH if p in present]

    dur = _phase_durations(activities, _duration)
    base_dur = _phase_durations(activities, _baseline_duration)
    pre_elapsed = sum(dur.get(p, 0) for p in pre)
    pre_elapsed_baseline = sum(base_dur.get(p, 0) for p in pre)

    # Resolve the anchor + per-phase start dates (business-day arithmetic).
    infeasible = False
    mode = "forward"
    gl = _parse(go_live)
    if gl:
        mode = "backward"
        # execution (last pre-launch phase) ends at go-live; walk phase starts backward.
        phase_end = {}
        cursor = gl
        for p in reversed(pre):
            phase_end[p] = cursor
            cursor = add_business_days(cursor, -dur.get(p, 0))
        earliest_start = cursor  # start of the first pre-launch phase
        if earliest_start < now:
            infeasible = True
        phase_start = {p: add_business_days(phase_end[p], -dur.get(p, 0)) for p in pre}
    else:
        start = _parse(start_date) or now
        phase_start = {}
        cursor = start
        for p in pre:
            phase_start[p] = cursor
            cursor = add_business_days(cursor, dur.get(p, 0))
        gl = cursor  # go-live falls out of the forward pass
        phase_end = {p: add_business_days(phase_start[p], dur.get(p, 0)) for p in pre}

    # Post-launch (wrap) always runs forward from go-live.
    cursor = gl
    for p in post:
        phase_start[p] = cursor
        cursor = add_business_days(cursor, dur.get(p, 0))
        phase_end[p] = cursor

    # Per-activity placement + slack + critical flag.
    scheduled = []
    critical_ids = []
    for a in activities:
        p = _phase_of(a)
        d = _duration(a)
        p_start = phase_start.get(p, now)
        a_start = p_start
        a_due = add_business_days(p_start, d)
        slack = dur.get(p, d) - d
        is_critical = slack == 0 and d > 0
        b = dict(a)
        b["planned_start"] = a_start.isoformat()
        b["planned_due"] = a_due.isoformat()
        b["slack_days"] = slack
        b["is_critical"] = is_critical
        scheduled.append(b)
        if is_critical:
            critical_ids.append(a.get("id"))

    bands = [{
        "phase": p, "start": phase_start[p].isoformat(), "end": phase_end[p].isoformat(),
        "duration_days": dur.get(p, 0), "baseline_duration_days": base_dur.get(p, 0),
        "is_post_launch": p in post,
    } for p in present]

    reduction_pct = (round(100 * (pre_elapsed_baseline - pre_elapsed) / pre_elapsed_baseline)
                     if pre_elapsed_baseline else 0)

    return {
        "mode": mode,
        "go_live": gl.isoformat(),
        "infeasible": infeasible,
        "infeasible_note": (
            "The earliest possible start is before today -- this go-live date can't be met without "
            "compressing the critical path or moving the date." if infeasible else None),
        "activities": scheduled,
        "bands": bands,
        "critical_path_ids": critical_ids,
        "elapsed": {
            "pre_launch_days": pre_elapsed,
            "pre_launch_days_baseline": pre_elapsed_baseline,
            "days_saved": pre_elapsed_baseline - pre_elapsed,
            "reduction_pct": reduction_pct,
            # vault reference points for the stakeholder story.
            "reference_baseline_simple_campaign_days": 18,
            "reference_target_days": 5,
        },
        "effort": sla.summarize_time_saved(activities),
    }
