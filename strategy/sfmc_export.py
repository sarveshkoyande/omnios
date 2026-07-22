from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib import error, parse, request
from typing import Any


TERMINAL_STEP_KINDS = {"exit", "closure"}
SEND_STEP_KINDS = {"send", "followup"}
SUPPORTED_WAIT_UNITS = "days"


@dataclass(frozen=True)
class SFMCConfig:
    auth_base_uri: str
    client_id: str
    client_secret: str
    account_id: str | None = None
    scope: str | None = None
    entry_data_extension_id: str | None = None
    entry_event_definition_key: str | None = None
    email_asset_id: str | None = None
    sender_profile_id: str | None = None
    delivery_profile_id: str | None = None
    schema_version_id: str | None = None
    fire_test_event: bool = False
    contact_key: str | None = None
    contact_key_value: str | None = None


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "journey"


def _as_str(value: Any, fallback: str = "") -> str:
    value = _unwrap(value)
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _as_int(value: Any, fallback: int | None = None) -> int | None:
    value = _unwrap(value)
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return int(value)
    try:
        if value is None or value == "":
            return fallback
        return int(float(str(value)))
    except (TypeError, ValueError):
        return fallback


def _node_data(node: dict) -> dict:
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def _node_field(node: dict, key: str) -> Any:
    return _unwrap(_node_data(node).get(key))


def _config_value(config: SFMCConfig | None, key: str) -> str | None:
    if config is None:
        return None
    return getattr(config, key)


def _normalise_document(project: dict) -> dict | None:
    doc = project.get("campaign_plan_layout")
    if isinstance(doc, dict) and doc.get("pages"):
        page = doc["pages"][0] or {}
        return {
            "source": "campaign_plan_layout",
            "name": doc.get("name") or project.get("name") or "Campaign Operations",
            "description": doc.get("description") or "",
            "nodes": page.get("nodes") or [],
            "edges": page.get("edges") or [],
        }

    result = project.get("result") or {}
    plan = result.get("stage_3_campaign_plan") or {}
    flow = plan.get("flow")
    if isinstance(flow, dict):
        return {
            "source": "stage_3_campaign_plan.flow",
            "name": project.get("name") or "Campaign Operations",
            "description": plan.get("summary") or "",
            "nodes": flow.get("nodes") or [],
            "edges": flow.get("edges") or [],
        }
    return None


def _step_kind(node: dict) -> str:
    kind = _as_str(_node_field(node, "campaignStepKind") or node.get("type"), "").lower()
    if kind in TERMINAL_STEP_KINDS:
        return kind
    if kind in SEND_STEP_KINDS | {"wait", "decision", "end", "terminal"}:
        return kind
    if kind.startswith("event.end"):
        return "exit"
    if kind in {"delay", "pause"}:
        return "wait"
    if kind.startswith("gateway.") or kind == "decision":
        return "decision"
    if kind == "process":
        return "send"
    return kind or "send"


def _activity_type(node: dict) -> str | None:
    kind = _step_kind(node)
    if kind in TERMINAL_STEP_KINDS or kind in {"end", "terminal"}:
        return None
    if kind == "wait":
        return "Wait"
    if kind == "decision":
        return "MultiCriteriaDecision"
    if kind in SEND_STEP_KINDS:
        return "EMAILV2"
    return "Rest"


def _activity_label(node: dict) -> str:
    return _as_str(node.get("label") or _node_field(node, "detail") or _node_field(node, "channel") or node.get("id"), "Journey step")


def _wait_duration(node: dict) -> int:
    day = _as_int(_node_field(node, "day"), None)
    if day is None:
        return 1
    return max(day, 1)


def _email_arguments(node: dict, config: SFMCConfig | None = None) -> dict:
    label = _activity_label(node)
    detail = _as_str(_node_field(node, "detail"), label)
    channel = _as_str(_node_field(node, "channel"), "email").lower()
    segment = _as_str(_node_field(node, "segment_key"))
    args = {
        "emailId": _config_value(config, "email_asset_id") or "{{REPLACE_WITH_EMAIL_ASSET_ID}}",
        "senderProfileId": _config_value(config, "sender_profile_id") or "{{REPLACE_WITH_SENDER_PROFILE_ID}}",
        "deliveryProfileId": _config_value(config, "delivery_profile_id") or "{{REPLACE_WITH_DELIVERY_PROFILE_ID}}",
        "emailSubject": detail,
        "preHeader": detail,
    }
    if channel:
        args["channel"] = channel
    if segment:
        args["segmentKey"] = segment
    return args


def _wait_arguments(node: dict) -> dict:
    return {
        "waitDuration": _wait_duration(node),
        "waitUnit": SUPPORTED_WAIT_UNITS,
    }


def _decision_arguments(node: dict, config: SFMCConfig | None = None) -> dict:
    return {
        "schemaVersionId": _config_value(config, "schema_version_id") or "{{REPLACE_WITH_SCHEMA_VERSION_ID}}",
        "expressionBuilderPrefix": _activity_label(node),
    }


def _rest_arguments(node: dict) -> dict:
    return {
        "label": _activity_label(node),
    }


def _node_sort(nodes: list[dict], edges: list[dict]) -> list[dict]:
    by_id = {n.get("id"): n for n in nodes if n.get("id")}
    indegree = {node_id: 0 for node_id in by_id}
    outgoing: dict[str, list[str]] = defaultdict(list)
    original_index = {n.get("id"): i for i, n in enumerate(nodes) if n.get("id")}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in by_id and target in by_id:
            outgoing[source].append(target)
            indegree[target] = indegree.get(target, 0) + 1

    queue = sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=lambda node_id: original_index.get(node_id, 10**9))
    ordered: list[dict] = []
    seen: set[str] = set()
    while queue:
        node_id = queue.pop(0)
        if node_id in seen or node_id not in by_id:
            continue
        seen.add(node_id)
        ordered.append(by_id[node_id])
        for child in outgoing.get(node_id, []):
            indegree[child] = indegree.get(child, 0) - 1
            if indegree[child] <= 0:
                queue.append(child)

    for node in nodes:
        node_id = node.get("id")
        if node_id and node_id not in seen:
            ordered.append(node)
    return ordered


def _apply_config(bundle: dict, config: SFMCConfig | None) -> dict:
    if config is None:
        return bundle
    journey = bundle.get("journeySpec") or {}
    for activity in journey.get("activities") or []:
        if activity.get("type") == "EMAILV2":
            args = activity.get("arguments") or {}
            if config.email_asset_id:
                args["emailId"] = config.email_asset_id
            if config.sender_profile_id:
                args["senderProfileId"] = config.sender_profile_id
            if config.delivery_profile_id:
                args["deliveryProfileId"] = config.delivery_profile_id
            activity["arguments"] = args
        if activity.get("type") == "MultiCriteriaDecision":
            args = activity.get("arguments") or {}
            if config.schema_version_id:
                args["schemaVersionId"] = config.schema_version_id
            activity["arguments"] = args
            cfg = activity.get("configurationArguments") or {}
            if config.schema_version_id:
                cfg["schemaVersionId"] = config.schema_version_id
            activity["configurationArguments"] = cfg
    return bundle


def build_sfmc_bundle(project: dict, config: SFMCConfig | None = None) -> dict:
    normalized = _normalise_document(project)
    if not normalized:
        raise ValueError("project does not contain a campaign plan layout to export")

    project_id = project.get("id") or "project"
    project_name = normalized["name"] or project.get("name") or "Campaign Operations"
    project_slug = _slug(project_name)
    journey_key = f"omni-{project_slug}-{project_id}"
    trigger_key = f"entry-{project_id}"

    nodes = [n for n in normalized["nodes"] if isinstance(n, dict) and n.get("id")]
    edges = [e for e in normalized["edges"] if isinstance(e, dict) and e.get("source") and e.get("target")]
    node_by_id = {n["id"]: n for n in nodes}
    ordered_nodes = _node_sort(nodes, edges)

    outgoing_edges: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in node_by_id and target in node_by_id:
            outgoing_edges[source].append(edge)

    activity_by_node_id: dict[str, str] = {}
    activities: list[dict] = []
    notes: list[str] = []

    for node in ordered_nodes:
        activity_type = _activity_type(node)
        if activity_type is None:
            continue
        node_id = node["id"]
        activity_key = f"act-{node_id}"
        activity_by_node_id[node_id] = activity_key

        if activity_type == "EMAILV2":
            arguments = _email_arguments(node, config)
            configuration_arguments = {"isConfigured": False}
        elif activity_type == "Wait":
            arguments = {}
            configuration_arguments = _wait_arguments(node)
        elif activity_type == "MultiCriteriaDecision":
            arguments = _decision_arguments(node, config)
            configuration_arguments = {
                "isConfigured": False,
                "schemaVersionId": _config_value(config, "schema_version_id") or "{{REPLACE_WITH_SCHEMA_VERSION_ID}}",
            }
        else:
            arguments = _rest_arguments(node)
            configuration_arguments = {"isConfigured": False}

        activities.append({
            "key": activity_key,
            "name": _activity_label(node),
            "type": activity_type,
            "arguments": arguments,
            "configurationArguments": configuration_arguments,
            "outcomes": [],
        })

    for node in ordered_nodes:
        node_id = node["id"]
        activity_key = activity_by_node_id.get(node_id)
        if not activity_key:
            if _step_kind(node) in TERMINAL_STEP_KINDS or _step_kind(node) in {"end", "terminal"}:
                notes.append(f"Terminal node '{_activity_label(node)}' is represented as an exit outcome (next: null).")
            continue

        outcomes: list[dict] = []
        node_edges = outgoing_edges.get(node_id, [])
        if not node_edges:
            outcomes.append({"key": "next", "next": None})
        else:
            for edge in node_edges:
                target_id = edge.get("target")
                target_node = node_by_id.get(target_id)
                next_key = activity_by_node_id.get(target_id)
                if target_node is not None and next_key is None and (_step_kind(target_node) in TERMINAL_STEP_KINDS or _step_kind(target_node) in {"end", "terminal"}):
                    next_key = None
                label = _as_str(edge.get("label"), "") or _as_str(edge.get("sourcePortId"), "") or _as_str(edge.get("targetPortId"), "")
                if not label:
                    label = target_node["label"] if target_node else target_id
                outcome_key = _slug(label)
                outcomes.append({"key": outcome_key, "next": next_key})
                if next_key is None:
                    notes.append(f"Outcome '{label}' from '{_activity_label(node)}' exits the journey.")
        for activity in activities:
            if activity["key"] == activity_key:
                activity["outcomes"] = outcomes
                break

    result_summary = ((project.get("result") or {}).get("stage_3_campaign_plan") or {}).get("summary") or ""
    summary = normalized.get("description") or result_summary

    journey_spec = {
        "key": journey_key,
        "name": f"{project_name} Journey Builder",
        "description": summary or f"Generated from the {project_name} campaign plan.",
        "workflowApiVersion": "1.1",
        "triggers": [{
            "key": trigger_key,
            "name": f"{project_name} entry event",
            "type": "event",
            "eventDefinitionKey": trigger_key,
            "arguments": {},
            "configurationArguments": {},
        }],
        "activities": activities,
    }

    deployment_steps = [
        {
            "step": 1,
            "method": "POST",
            "path": "/interaction/v1/eventDefinitions",
            "purpose": "Create the journey entry event definition and capture its key.",
            "note": "Replace the event scaffold with your tenant's entry data-extension / contact criteria.",
        },
        {
            "step": 2,
            "method": "POST",
            "path": "/interaction/v1/interactions",
            "purpose": "Create the journey draft from the Journey Specification JSON.",
            "note": "Use the returned journey id/key when you later publish or revise the journey.",
        },
        {
            "step": 3,
            "method": "POST",
            "path": "/interaction/v1/interactions/publishAsync/{id}?versionNumber={versionNumber}",
            "purpose": "Publish the journey after you have completed asset wiring.",
            "note": "The email activities still need real email asset, sender profile, and delivery profile ids.",
        },
        {
            "step": 4,
            "method": "POST",
            "path": "/interaction/v1/events",
            "purpose": "Fire the entry event to test the journey.",
            "note": "Use the eventDefinitionKey created in step 1.",
        },
    ]

    return {
        "bundleVersion": 1,
        "source": normalized["source"],
        "project": {
            "id": project_id,
            "name": project_name,
            "journeyKey": journey_key,
        },
        "journeySpec": journey_spec,
        "entryEvent": {
            "key": trigger_key,
            "name": f"{project_name} entry event",
            "type": "event",
            "eventDefinitionKey": trigger_key,
        },
        "deploymentSteps": deployment_steps,
        "mappingNotes": notes + [
            "Email activities ship with placeholders for email asset, sender profile, delivery profile, and schema version ids.",
            "Journey Builder has no explicit start activity; the first activity in the list is the journey entry point.",
            "Journey endings are represented by outcomes whose next value is null.",
        ],
    }


def _json_request(url: str, data: dict, headers: dict[str, str] | None = None, method: str = "POST") -> dict:
    body = json.dumps(data).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with request.urlopen(req, timeout=45) as resp:
            payload = resp.read().decode("utf-8") or "{}"
            return json.loads(payload)
    except error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode('utf-8', errors='replace')}") from e


def _form_request(url: str, data: dict[str, str]) -> dict:
    body = parse.urlencode(data).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with request.urlopen(req, timeout=45) as resp:
            payload = resp.read().decode("utf-8") or "{}"
            return json.loads(payload)
    except error.HTTPError as e:
        raise RuntimeError(f"POST {url} -> {e.code}: {e.read().decode('utf-8', errors='replace')}") from e


def get_access_token(config: SFMCConfig) -> dict:
    auth_base = config.auth_base_uri.rstrip("/")
    payload = {
        "grant_type": "client_credentials",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    if config.scope:
        payload["scope"] = config.scope
    if config.account_id:
        payload["account_id"] = str(config.account_id)
    return _form_request(f"{auth_base}/v2/token", payload)


def _build_event_definition(project: dict, config: SFMCConfig, journey_key: str) -> dict:
    entry_key = config.entry_event_definition_key or f"{journey_key}-entry"
    entry_name = f"{project.get('name') or 'Campaign Operations'} entry event"
    event_def: dict[str, Any] = {
        "name": entry_name,
        "description": f"Entry event for {project.get('name') or 'Campaign Operations'}",
        "eventDefinitionKey": entry_key,
        "category": "Event",
        "mode": "Production",
        "isVisibleInPicker": True,
    }
    if config.entry_data_extension_id:
        event_def["dataExtensionId"] = config.entry_data_extension_id
    return event_def


def _journey_runtime_config(token: dict, config: SFMCConfig) -> tuple[str, str, str]:
    rest_instance_url = token.get("rest_instance_url")
    access_token = token.get("access_token")
    if not rest_instance_url or not access_token:
        raise RuntimeError("OAuth token response missing rest_instance_url or access_token")
    return rest_instance_url.rstrip("/"), access_token, token.get("token_type") or "Bearer"


def _sfmc_api_post(rest_base: str, path: str, access_token: str, payload: dict) -> dict:
    return _json_request(
        f"{rest_base}{path}",
        payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def push_sfmc_journey(project: dict, config: SFMCConfig) -> dict:
    bundle = build_sfmc_bundle(project, config=config)
    token = get_access_token(config)
    rest_base, access_token, token_type = _journey_runtime_config(token, config)

    journey_spec = bundle["journeySpec"]
    event_definition = _build_event_definition(project, config, journey_spec["key"])
    event_response = _sfmc_api_post(rest_base, "/interaction/v1/eventDefinitions", access_token, event_definition)

    journey_spec = dict(journey_spec)
    if journey_spec.get("triggers"):
        journey_spec["triggers"] = [dict(journey_spec["triggers"][0], eventDefinitionKey=event_definition["eventDefinitionKey"])]

    journey_response = _sfmc_api_post(rest_base, "/interaction/v1/interactions", access_token, journey_spec)
    journey_id = journey_response.get("id") or journey_response.get("journeyId") or journey_response.get("definitionId")
    version_number = journey_response.get("version") or journey_response.get("versionNumber") or 1

    publish_response = {}
    if journey_id:
        publish_response = _sfmc_api_post(
            rest_base,
            f"/interaction/v1/interactions/publishAsync/{journey_id}?versionNumber={version_number}",
            access_token,
            {},
        )

    fire_response = {}
    if config.fire_test_event:
        contact_key = config.contact_key or "ContactKey"
        contact_value = config.contact_key_value or "sfmc-test-contact"
        fire_response = _sfmc_api_post(
            rest_base,
            "/interaction/v1/events",
            access_token,
            {
                "ContactKey": contact_value,
                "EventDefinitionKey": event_definition["eventDefinitionKey"],
                contact_key: contact_value,
            },
        )

    return {
        "bundle": bundle,
        "token": {k: token.get(k) for k in ("rest_instance_url", "soap_instance_url", "expires_in", "scope")},
        "journey": journey_response,
        "publish": publish_response,
        "eventDefinition": event_response,
        "fireEvent": fire_response,
        "tokenType": token_type,
        "journeyId": journey_id,
        "versionNumber": version_number,
    }
