"""Engagement Orchestration -- two-way sync engine (PRD 6.6, M3).

Inbound reconciliation: for every external binding, read the current downstream state and fold
real changes back into the internal activity, honouring:

  - Loop prevention (origin tagging). Each downstream write is tagged with who made it. If WE
    (the orchestrator) wrote it last, there is no genuine inbound change -- skip, so a push never
    echoes back as a fake inbound update.
  - Conflict policy (source-of-truth per field). The downstream tool is authoritative for live
    execution *status / completion / assignee*; the internal schedule stays authoritative for
    *dates / structure / gates*. A downstream change to an internal-authoritative field is logged
    as a conflict and NOT applied (kept for a manual-review surface), never silently overwriting
    the plan.
  - Idempotent apply. After folding a change in, the binding's snapshot + hash are updated so the
    next push sees internal and external as equal (no redundant write, no ping-pong).

Every applied change and conflict is written to the sync_event log (audit-by-product, PRD 9).

Real connectors get inbound changes from webhooks (event-driven); the StubConnector is polled via
`reconcile_inbound`. `simulate_external_change` flips a stub item as if a teammate updated it in
the downstream tool, so the whole loop is demonstrable without a real vendor system.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import orchestration_connectors as oc  # noqa: E402
import orchestration_store as store  # noqa: E402

# Source-of-truth per field. "external" = downstream tool wins; "internal" = plan wins.
CONFLICT_POLICY = {
    "status": "external",
    "done": "external",
    "assignee": "external",
    "due": "internal",
    "title": "internal",
    "gate": "internal",
}


def reconcile_inbound(project_id: str, tasks: list[dict]) -> dict:
    """Fold genuine downstream changes back into `tasks` (mutated in place). Returns the applied
    changes, the conflicts held back, whether anything changed (so the caller can persist), and a
    tail of the sync-event log."""
    applied: list[dict] = []
    conflicts: list[dict] = []
    changed = False
    by_id = {t.get("id"): t for t in tasks}

    for b in store.list_bindings(project_id):
        ext_id = b.get("external_id")
        if not ext_id:
            continue
        task = by_id.get(b["activity_id"])
        if not task:
            continue
        conn = oc.connector_for(b["system"])
        ext = conn.read_item(b)
        if not ext:
            continue
        if ext.get("origin") == "orchestrator":
            continue  # loop prevention: we wrote last -- nothing genuinely inbound

        # external-authoritative: completion/status
        ext_done = ext.get("status") == "Done"
        if ext_done != bool(task.get("done")):
            store.record_sync_event(project_id, activity_id=task["id"], system=b["system"],
                                    direction="inbound", field="done",
                                    old_value=task.get("done"), new_value=ext_done, result="applied")
            task["done"] = ext_done
            applied.append({"activity_id": task["id"], "title": task.get("title"),
                            "field": "done", "value": ext_done, "system": b["system"]})
            changed = True

        # external-authoritative: assignee
        ext_assignee = ext.get("assignee")
        if ext_assignee and ext_assignee != task.get("assigned_to"):
            store.record_sync_event(project_id, activity_id=task["id"], system=b["system"],
                                    direction="inbound", field="assigned_to",
                                    old_value=task.get("assigned_to"), new_value=ext_assignee, result="applied")
            task["assigned_to"] = ext_assignee
            applied.append({"activity_id": task["id"], "title": task.get("title"),
                            "field": "assigned_to", "value": ext_assignee, "system": b["system"]})
            changed = True

        # internal-authoritative: a downstream date change is a conflict, held for review
        snap = b.get("snapshot") or {}
        if ext.get("due") and snap.get("due") and ext["due"] != snap["due"]:
            store.record_sync_event(project_id, activity_id=task["id"], system=b["system"],
                                    direction="inbound", field="due",
                                    old_value=snap.get("due"), new_value=ext["due"], result="conflict-held")
            conflicts.append({"activity_id": task["id"], "title": task.get("title"),
                              "field": "due", "internal": snap.get("due"), "external": ext["due"],
                              "resolution": "kept internal (schedule is authoritative)"})

        # idempotent apply: re-sync the binding snapshot/hash to the new internal state, and mark
        # the stub item back to orchestrator-origin so the same change isn't reapplied next poll.
        new_snap = oc._snapshot(task)
        store.upsert_binding(project_id, task["id"], b["system"], external_id=ext_id,
                             external_url=b.get("external_url"), last_synced_hash=oc._hash(new_snap),
                             sync_state="synced", snapshot=new_snap)
        it = store.get_stub_item(ext_id)
        if it:
            store.upsert_stub_item(ext_id, system=it["system"], project_id=project_id,
                                   activity_id=task["id"], title=it["title"], status=it["status"],
                                   assignee=it["assignee"], due=it["due"], origin="orchestrator")

    return {"applied": applied, "conflicts": conflicts, "changed": changed,
            "events": store.list_sync_events(project_id, 20)}


def simulate_external_change(project_id: str, activity_id: str, status: str = "Done",
                            system: str = "stub") -> dict | None:
    """Demo/verify helper: flip a stub downstream item as if a teammate changed it in the tool
    (origin='external'), so a following reconcile_inbound picks it up. No-op for real systems."""
    b = store.get_binding(project_id, activity_id, system)
    if not b or not b.get("external_id"):
        return None
    it = store.get_stub_item(b["external_id"])
    if not it:
        return None
    store.upsert_stub_item(b["external_id"], system=system, project_id=project_id,
                           activity_id=activity_id, title=it["title"], status=status,
                           assignee=it["assignee"], due=it["due"], origin="external")
    return store.get_stub_item(b["external_id"])
