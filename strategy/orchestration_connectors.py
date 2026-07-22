"""Engagement Orchestration -- downstream connector abstraction + idempotent push (PRD 6.5/6.6).

The provider interface is the load-bearing design decision (the vault's real downstream systems
are Smartsheet/Jira/Veeva/SFMC; Monday was only the example). Everything here is written against
the `Connector` ABC so a new system is added by dropping in one subclass + a routing entry, never
by touching the push logic.

Shipped now:
  - StubConnector -- a fully-working in-memory/SQLite connector (writes to orchestration_store.
    stub_item). Lets push + bindings + (M3) two-way sync run end-to-end with no credentials.
  - MondayConnector / SmartsheetConnector / JiraConnector -- real wiring points. They declare
    themselves unavailable() until their credentials are set in the environment, so push reports a
    clear "not configured yet" per route instead of failing. Fill in the marked create/update/read
    bodies when tokens + board/sheet/project ids are supplied.

Push is idempotent: each activity carries a hash of its synced-field snapshot; a binding whose
last_synced_hash matches is skipped, a changed one is updated, an unbound one is created -- so
re-pushing never duplicates items (loop prevention + external-ID map).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import orchestration_store as store  # noqa: E402

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ROUTING_JSON = BASE_DIR / "config" / "orchestration_routing.json"


# --- routing ----------------------------------------------------------------------------------

def load_routing() -> dict:
    try:
        return json.loads(ROUTING_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"default_system": "stub", "routes": {}}


def route_for(team: str, routing: dict | None = None) -> dict:
    routing = routing or load_routing()
    r = (routing.get("routes") or {}).get(team)
    if r:
        return r
    return {"system": routing.get("default_system", "stub"), "board": f"{team} board"}


# --- field snapshot + idempotency -------------------------------------------------------------

def _snapshot(activity: dict) -> dict:
    """The subset of an activity's fields that are pushed downstream. Hashing this drives
    skip-if-unchanged; it is also the field-map source each connector maps into native columns."""
    return {
        "title": activity.get("title"),
        "team": activity.get("team"),
        "status": "Done" if activity.get("done") else "To do",
        "assignee": activity.get("assigned_to"),
        "due": activity.get("planned_due"),
        "gate": activity.get("gate"),
        "compliance_tier": activity.get("compliance_tier"),
        "sla": activity.get("sla"),
    }


def _hash(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16]


# --- connector interface ----------------------------------------------------------------------

class Connector:
    system = "base"

    def available(self) -> bool:
        """True when this connector can actually talk to its system (credentials present)."""
        return False

    def create_item(self, project_id: str, activity: dict, board: str, snapshot: dict) -> dict:
        """Create the downstream record. Return {external_id, external_url}."""
        raise NotImplementedError

    def update_item(self, project_id: str, activity: dict, binding: dict, board: str, snapshot: dict) -> dict:
        """Update the existing downstream record. Return {external_id, external_url}."""
        raise NotImplementedError

    def read_item(self, binding: dict) -> dict | None:
        """Read the current downstream state (for two-way sync, M3). Return a snapshot-shaped dict."""
        return None


class StubConnector(Connector):
    """In-memory/SQLite mock. Persists items to orchestration_store.stub_item so M3 sync has a real
    other side. Always available -- no credentials."""
    system = "stub"

    def available(self) -> bool:
        return True

    def create_item(self, project_id, activity, board, snapshot):
        item_id = f"stub_{uuid.uuid4().hex[:10]}"
        store.upsert_stub_item(
            item_id, system=self.system, project_id=project_id, activity_id=activity["id"],
            title=snapshot["title"], status=snapshot["status"], assignee=snapshot["assignee"],
            due=snapshot["due"], origin="orchestrator")
        return {"external_id": item_id, "external_url": f"stub://{board}/{item_id}"}

    def update_item(self, project_id, activity, binding, board, snapshot):
        item_id = binding["external_id"]
        store.upsert_stub_item(
            item_id, system=self.system, project_id=project_id, activity_id=activity["id"],
            title=snapshot["title"], status=snapshot["status"], assignee=snapshot["assignee"],
            due=snapshot["due"], origin="orchestrator")
        return {"external_id": item_id, "external_url": binding.get("external_url") or f"stub://{board}/{item_id}"}

    def read_item(self, binding):
        it = store.get_stub_item(binding.get("external_id") or "")
        if not it:
            return None
        return {"title": it["title"], "status": it["status"], "assignee": it["assignee"],
                "due": it["due"], "origin": it["origin"]}


class _CredentialConnector(Connector):
    """Base for real vendor connectors -- unavailable until its env credentials are set. Create/
    update/read raise until implemented, but push never reaches them while unavailable()."""
    system = "vendor"
    _env_keys: tuple[str, ...] = ()

    def available(self) -> bool:
        return all(os.getenv(k) for k in self._env_keys)

    def create_item(self, project_id, activity, board, snapshot):  # pragma: no cover - wiring point
        raise NotImplementedError(f"{self.system} create_item not implemented -- supply credentials + board id, then map snapshot->native fields here.")

    def update_item(self, project_id, activity, binding, board, snapshot):  # pragma: no cover
        raise NotImplementedError(f"{self.system} update_item not implemented.")


class MondayConnector(_CredentialConnector):
    """monday.com GraphQL items API. Wiring point: POST to https://api.monday.com/v2 with a
    `create_item`/`change_multiple_column_values` mutation; map snapshot -> column ids of `board`."""
    system = "monday"
    _env_keys = ("MONDAY_API_TOKEN",)


class SmartsheetConnector(_CredentialConnector):
    """Smartsheet rows API (the vault's incumbent tagging/tracking tool). Wiring point: POST rows
    to sheet `board`; map snapshot -> column ids."""
    system = "smartsheet"
    _env_keys = ("SMARTSHEET_API_TOKEN",)


class JiraConnector(_CredentialConnector):
    """Jira issues API. Wiring point: POST /rest/api/3/issue into project `board`; map snapshot ->
    fields; status via transitions."""
    system = "jira"
    _env_keys = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


_REGISTRY: dict[str, Connector] = {
    "stub": StubConnector(),
    "monday": MondayConnector(),
    "smartsheet": SmartsheetConnector(),
    "jira": JiraConnector(),
}


def connector_for(system: str) -> Connector:
    return _REGISTRY.get(system, _REGISTRY["stub"])


# --- push -------------------------------------------------------------------------------------

def push_activities(project_id: str, activities: list[dict], teams: list[str] | None = None) -> dict:
    """Idempotently push activities to their routed downstream systems. `teams` optionally limits
    the push to specific teams (selective push, PRD F5.6). Returns a per-activity result list +
    a summary. Nothing here can satisfy a compliance gate -- it only mirrors activity state."""
    routing = load_routing()
    results = []
    counts = {"created": 0, "updated": 0, "skipped": 0, "unconfigured": 0, "error": 0}
    for a in activities:
        team = a.get("team", "")
        if teams and team not in teams:
            continue
        route = route_for(team, routing)
        system = route.get("system", "stub")
        board = route.get("board", f"{team} board")
        conn = connector_for(system)
        snapshot = _snapshot(a)
        h = _hash(snapshot)
        binding = store.get_binding(project_id, a["id"], system)

        if not conn.available():
            store.upsert_binding(project_id, a["id"], system, external_id=None, external_url=None,
                                 last_synced_hash=None, sync_state="unconfigured", snapshot=snapshot)
            counts["unconfigured"] += 1
            results.append({"activity_id": a["id"], "title": a.get("title"), "system": system,
                            "action": "unconfigured",
                            "detail": f"{system} connector needs credentials -- routed but not pushed."})
            continue
        try:
            if binding and binding.get("external_id"):
                if binding.get("last_synced_hash") == h:
                    counts["skipped"] += 1
                    results.append({"activity_id": a["id"], "title": a.get("title"), "system": system,
                                    "action": "skipped", "external_url": binding.get("external_url")})
                    continue
                res = conn.update_item(project_id, a, binding, board, snapshot)
                action = "updated"
                counts["updated"] += 1
            else:
                res = conn.create_item(project_id, a, board, snapshot)
                action = "created"
                counts["created"] += 1
            store.upsert_binding(project_id, a["id"], system, external_id=res["external_id"],
                                 external_url=res["external_url"], last_synced_hash=h,
                                 sync_state="synced", snapshot=snapshot)
            results.append({"activity_id": a["id"], "title": a.get("title"), "system": system,
                            "action": action, "external_id": res["external_id"],
                            "external_url": res["external_url"], "board": board})
        except Exception as e:  # noqa: BLE001 -- one bad route must not abort the whole push
            counts["error"] += 1
            results.append({"activity_id": a["id"], "title": a.get("title"), "system": system,
                            "action": "error", "detail": str(e)})
    return {"results": results, "counts": counts, "bindings": store.list_bindings(project_id)}
