"""Salesforce Flow metadata from the blueprint's flow spec.

A port of Camille's flowValidator.js (`validateFlowSpec`: auto-heals names, labels, types and
trigger settings in place) and index.js `generateFlowXml` (the spec -> Flow XML converter),
kept element-for-element, plus the deploy package (package.xml + flows/<name>.flow-meta.xml)
Camille zipped in /flows/deploy.

One correction: Camille listed "Notification" as a supported element type but never emitted
XML for it, so a connector pointed at a node that did not exist and the deploy failed. Only the
element types this converter can actually write are chained here.
"""
from __future__ import annotations

import copy
import io
import re
import zipfile

API_VERSION = "58.0"

# Element types generate_flow_xml writes. (Wait is not allowed in record-triggered flows --
# scheduled paths carry the timing -- so it is filtered out, as in Camille.)
SUPPORTED_TYPES = ("Email", "UpdateRecord", "CreateRecord", "Decision", "Loop", "Assignment", "GetRecords")


class FlowError(ValueError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def _js_str(v) -> str:
    """String conversion with JavaScript's formatting for the values a spec holds."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _escape(unsafe) -> str:
    if unsafe is None or unsafe is False or unsafe == "" or (isinstance(unsafe, (int, float)) and not isinstance(unsafe, bool) and unsafe == 0):
        return ""
    return (_js_str(unsafe).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def _int(v, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        m = re.match(r"\s*-?\d+", str(v or ""))
        return int(m.group(0)) if m else default


# ------------------------------------------------------------------ validation ----------

def api_name(name) -> str:
    """A Salesforce API name: letters, digits and single underscores, starting with a letter,
    not ending in an underscore, at most 80 characters (76 here, leaving room for a `_N`
    de-duplication suffix). Camille only replaced invalid characters and prefixed a leading
    digit with "_", which Salesforce still rejects."""
    n = re.sub(r"[^a-zA-Z0-9_]", "_", str(name or ""))
    n = re.sub(r"_+", "_", n).strip("_") or "Step"
    if not re.match(r"^[A-Za-z]", n):
        n = f"Step_{n}"
    return n[:76].rstrip("_")


def validate_flow_spec(spec: dict) -> dict:
    """Auto-heal the spec in place (Camille's validateFlowSpec) -> {valid, errors}."""
    if not spec or not isinstance(spec, dict):
        return {"valid": False, "errors": ["Flow spec is null or undefined"]}
    if not spec.get("triggerObject"):
        spec["triggerObject"] = "Contact"
    if not spec.get("triggerEvent"):
        spec["triggerEvent"] = "CreateAndUpdate"
    if spec.get("flowType") and spec["flowType"] != "RecordTriggered":
        spec["flowType"] = "RecordTriggered"
    if spec.get("triggerEvent") not in ("Create", "Update", "Delete", "CreateAndUpdate"):
        spec["triggerEvent"] = "CreateAndUpdate"

    clean_name = api_name

    def heal(el, index: int) -> None:
        if not isinstance(el, dict):
            return
        if not el.get("type"):
            el["type"] = "Assignment"
        if not el.get("name"):
            el["name"] = f"Step_{el['type']}_{index + 1}"
        el["name"] = clean_name(el["name"])
        if not el.get("label"):
            el["label"] = el["name"].replace("_", " ")
        if el["type"] == "Decision":
            for i, rule in enumerate(el.get("rules") or []):
                if not isinstance(rule, dict):
                    continue
                if not rule.get("name"):
                    rule["name"] = f"Outcome_{i + 1}"
                rule["name"] = clean_name(rule["name"])
                if not rule.get("label"):
                    rule["label"] = rule["name"].replace("_", " ")
                for j, nested in enumerate(rule.get("elements") or []):
                    heal(nested, j)
            for i, nested in enumerate(el.get("defaultElements") or []):
                heal(nested, i)
        if el["type"] == "Assignment" and isinstance(el.get("assignments"), list):
            for assign in el["assignments"]:
                if isinstance(assign, dict) and assign.get("operator"):
                    op = str(assign["operator"]).lower().strip()
                    if op in ("+=", "+", "add", "increment"):
                        assign["operator"] = "Add"
                    elif op in ("-=", "-", "subtract", "decrement"):
                        assign["operator"] = "Subtract"
                    elif op in ("=", "==", "assign", "set"):
                        assign["operator"] = "Assign"
        if el["type"] == "Loop":
            for i, nested in enumerate(el.get("loopElements") or []):
                heal(nested, i)

    for i, el in enumerate(spec.get("immediateElements") or []):
        heal(el, i)
    for path in spec.get("scheduledPaths") or []:
        if isinstance(path, dict):
            for j, el in enumerate(path.get("elements") or []):
                heal(el, j)
    return {"valid": True, "errors": []}


# ------------------------------------------------------------------ operators -----------

def _map_operator(op) -> str:
    if not op:
        return "EqualTo"
    return {
        "=": "EqualTo", "==": "EqualTo", "equal": "EqualTo", "equalto": "EqualTo",
        "!=": "NotEqualTo", "<>": "NotEqualTo", "notequal": "NotEqualTo", "notequalto": "NotEqualTo",
        "<": "LessThan", "lessthan": "LessThan",
        "<=": "LessThanOrEqualTo", "lessthanorequalto": "LessThanOrEqualTo",
        ">": "GreaterThan", "greaterthan": "GreaterThan",
        ">=": "GreaterThanOrEqualTo", "greaterthanorequalto": "GreaterThanOrEqualTo",
        "contains": "Contains", "startswith": "StartsWith", "endswith": "EndsWith",
    }.get(str(op).lower().strip(), "EqualTo")


_ASSIGN_OPS = ("Assign", "Add", "Subtract", "AddItem", "AddAtStart", "RemoveFirst", "RemoveBeforeFirst",
               "RemoveAfterBoth", "RemoveAll", "RemovePosition", "AssignCount")


def _map_assignment_operator(op) -> str:
    if not op:
        return "Assign"
    low = str(op).lower().strip()
    table = {
        "assign": "Assign", "=": "Assign", "==": "Assign", ":=": "Assign", "set": "Assign", "equals": "Assign", "equalto": "Assign",
        "add": "Add", "+=": "Add", "+": "Add", "increment": "Add", "plus": "Add", "append": "Add",
        "subtract": "Subtract", "-=": "Subtract", "-": "Subtract", "decrement": "Subtract", "minus": "Subtract",
        "additem": "AddItem", "add_item": "AddItem",
        "addatstart": "AddAtStart", "add_at_start": "AddAtStart",
        "removefirst": "RemoveFirst", "remove_first": "RemoveFirst",
        "removebeforefirst": "RemoveBeforeFirst", "remove_before_first": "RemoveBeforeFirst",
        "removeafterboth": "RemoveAfterBoth", "remove_after_both": "RemoveAfterBoth",
        "removeall": "RemoveAll", "remove_all": "RemoveAll",
        "removeposition": "RemovePosition", "remove_position": "RemovePosition",
        "assigncount": "AssignCount", "assign_count": "AssignCount", "count": "AssignCount",
    }
    if low in table:
        return table[low]
    return next((s for s in _ASSIGN_OPS if s.lower() == low), "Assign")


def _format_value(val) -> str:
    if val is None:
        return "<stringValue></stringValue>"
    if isinstance(val, bool):
        return f"<booleanValue>{'true' if val else 'false'}</booleanValue>"
    if isinstance(val, (int, float)):
        return f"<numberValue>{_js_str(val)}</numberValue>"
    s = _js_str(val).strip()
    if s in ("true", "false"):
        return f"<booleanValue>{s}</booleanValue>"
    if s.startswith(("$Record.", "$User.", "$Profile.")):
        return f"<elementReference>{_escape(s)}</elementReference>"
    return f"<stringValue>{_escape(s)}</stringValue>"


def _assignment_list(el: dict) -> list[dict]:
    src = el.get("assignments")
    if src is None:
        src = el.get("fieldAssignments")
    if isinstance(src, list):
        return [a for a in src if isinstance(a, dict)]
    if isinstance(src, dict):
        return [{"field": k, "value": v, "operator": "Assign"} for k, v in src.items()]
    return []


def _input_assignments(el: dict) -> str:
    out = ""
    for a in _assignment_list(el):
        field = a.get("field") or a.get("name") or ""
        value = a.get("value", "")
        out += f"""
        <inputAssignments>
            <field>{_escape(field)}</field>
            <value>
                {_format_value(value)}
            </value>
        </inputAssignments>"""
    return out


# ------------------------------------------------------------------ XML -----------------

def generate_flow_xml(spec: dict, flow_name: str, label: str | None = None) -> str:
    """Camille's generateFlowXml. Works on a copy: name de-duplication must not leak into the
    saved spec. `label` defaults to the flow's API name, as in Camille."""
    spec = copy.deepcopy(spec) if isinstance(spec, dict) else spec
    check = validate_flow_spec(spec)
    if not check["valid"]:
        raise FlowError("Invalid flow specification", {"errors": check["errors"]})
    label = label or flow_name

    all_elements: list[dict] = []
    y_pos = [200]
    used: set[str] = set()

    def unique_name(name) -> str:
        if not name:
            name = f"Element_{len(used) + 1}"
        candidate, counter = name, 2
        while candidate in used:
            candidate = f"{name}_{counter}"
            counter += 1
        used.add(candidate)
        return candidate

    def connector(target) -> str:
        return f"<connector><targetReference>{_escape(target)}</targetReference></connector>" if target else ""

    def chain(elements, after=None):
        if not elements:
            return after
        filtered = [e for e in elements if isinstance(e, dict) and e.get("type") in SUPPORTED_TYPES]
        if not filtered:
            return after
        for el in filtered:
            el["name"] = unique_name(el.get("name"))
        for i, el in enumerate(filtered):
            nxt = filtered[i + 1]["name"] if i + 1 < len(filtered) else after
            kind = el["type"]
            if kind == "Email":
                body = el.get("body") or el.get("text") or el.get("content") or ""
                xml = f"""
    <actionCalls>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        <actionName>emailSimple</actionName>
        <actionType>emailSimple</actionType>
        <flowTransactionModel>CurrentTransaction</flowTransactionModel>
        <inputParameters>
            <name>emailBody</name>
            <value><stringValue>{_escape(body)}</stringValue></value>
        </inputParameters>
        <inputParameters>
            <name>emailAddresses</name>
            <value><stringValue>{_escape(el.get('recipient') or '')}</stringValue></value>
        </inputParameters>
        <inputParameters>
            <name>emailSubject</name>
            <value><stringValue>{_escape(el.get('subject') or '')}</stringValue></value>
        </inputParameters>
        <inputParameters>
            <name>senderType</name>
            <value><stringValue>CurrentUser</stringValue></value>
        </inputParameters>
        {connector(nxt)}
    </actionCalls>"""
                all_elements.append({"tag": "actionCalls", "xml": xml})
            elif kind == "Assignment":
                items = ""
                for a in _assignment_list(el):
                    field = a.get("field") or a.get("name") or a.get("assignToReference") or ""
                    value = a.get("value", "")
                    items += f"""
        <assignmentItems>
            <assignToReference>{_escape(field)}</assignToReference>
            <operator>{_map_assignment_operator(a.get('operator'))}</operator>
            <value>
                {_format_value(value)}
            </value>
        </assignmentItems>"""
                xml = f"""
    <assignments>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        {items}
        {connector(nxt)}
    </assignments>"""
                all_elements.append({"tag": "assignments", "xml": xml})
            elif kind == "Loop":
                inside = chain(el.get("loopElements") or [], el["name"])
                # Camille wrote an empty <targetReference> when the loop ended the flow, which
                # Salesforce rejects; a loop with nothing after it simply has no such connector.
                no_more = (f"""<noMoreValuesConnector>
            <targetReference>{_escape(nxt)}</targetReference>
        </noMoreValuesConnector>""" if nxt else "")
                xml = f"""
    <loops>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        <collectionReference>{_escape(el.get('collectionReference'))}</collectionReference>
        <iterationOrder>Asc</iterationOrder>
        <nextValueConnector>
            <targetReference>{_escape(inside or el['name'])}</targetReference>
        </nextValueConnector>
        {no_more}
    </loops>"""
                all_elements.append({"tag": "loops", "xml": xml})
            elif kind == "Decision":
                rules_xml = ""
                for rule in el.get("rules") or []:
                    if not isinstance(rule, dict):
                        continue
                    rule["name"] = unique_name(rule.get("name"))
                    first = chain(rule.get("elements"), nxt)
                    target = first or nxt
                    cond = rule.get("condition") if isinstance(rule.get("condition"), dict) else {}
                    rules_xml += f"""
        <rules>
            <name>{_escape(rule['name'])}</name>
            <conditionLogic>and</conditionLogic>
            <conditions>
                <leftValueReference>{_escape(cond.get('field'))}</leftValueReference>
                <operator>{_map_operator(cond.get('operator'))}</operator>
                <rightValue>
                    {_format_value(cond.get('value'))}
                </rightValue>
            </conditions>
            {connector(target)}
            <label>{_escape(rule.get('label'))}</label>
        </rules>"""
                first_default = chain(el.get("defaultElements"), nxt)
                default_target = first_default or nxt
                default_conn = (f"<defaultConnector><targetReference>{_escape(default_target)}</targetReference></defaultConnector>"
                                if default_target else "")
                xml = f"""
    <decisions>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        {default_conn}
        <defaultConnectorLabel>Default Outcome</defaultConnectorLabel>
        {rules_xml}
    </decisions>"""
                all_elements.append({"tag": "decisions", "xml": xml})
            elif kind == "GetRecords":
                xml = f"""
    <recordLookups>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        <assignNullValuesIfNoRecordsFound>false</assignNullValuesIfNoRecordsFound>
        <filterLogic>and</filterLogic>
        <filters>
            <field>{_escape(el.get('field'))}</field>
            <operator>{_map_operator(el.get('operator'))}</operator>
            <value>
                {_format_value(el.get('value'))}
            </value>
        </filters>
        <getFirstRecordOnly>true</getFirstRecordOnly>
        <object>{_escape(el.get('object'))}</object>
        <storeOutputAutomatically>true</storeOutputAutomatically>
        {connector(nxt)}
    </recordLookups>"""
                all_elements.append({"tag": "recordLookups", "xml": xml})
            elif kind == "UpdateRecord":
                if el.get("object") == "$Record":
                    ref = "<inputReference>$Record</inputReference>"
                else:
                    ref = f"""
        <filters>
            <field>Id</field>
            <operator>EqualTo</operator>
            <value><elementReference>$Record.Id</elementReference></value>
        </filters>
        <object>{_escape(el.get('object'))}</object>"""
                xml = f"""
    <recordUpdates>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        {ref}
        {_input_assignments(el)}
        {connector(nxt)}
    </recordUpdates>"""
                all_elements.append({"tag": "recordUpdates", "xml": xml})
            elif kind == "CreateRecord":
                xml = f"""
    <recordCreates>
        <name>{_escape(el['name'])}</name>
        <label>{_escape(el.get('label'))}</label>
        <locationX>176</locationX>
        <locationY>{y_pos[0]}</locationY>
        <object>{_escape(el.get('object'))}</object>
        {_input_assignments(el)}
        <storeOutputAutomatically>true</storeOutputAutomatically>
        {connector(nxt)}
    </recordCreates>"""
                all_elements.append({"tag": "recordCreates", "xml": xml})
            y_pos[0] += 150
        return filtered[0]["name"]

    immediate = spec.get("immediateElements") if isinstance(spec.get("immediateElements"), list) else []
    scheduled = spec.get("scheduledPaths") if isinstance(spec.get("scheduledPaths"), list) else []
    # "Run Immediately" is never left empty: promote the first scheduled path, else a default
    # entry email (Camille's rules).
    if not immediate and scheduled:
        first_path = scheduled[0] if isinstance(scheduled[0], dict) else {}
        if first_path.get("elements"):
            immediate = first_path["elements"]
            scheduled = scheduled[1:]
    if not immediate and not scheduled:
        immediate = [{"type": "Email", "name": "Email_Day1_Entry", "label": "Send Campaign Initial Email",
                      "recipient": "Contact.Email", "subject": "Campaign Information",
                      "body": "Initial educational communication for the campaign."}]
    spec["immediateElements"], spec["scheduledPaths"] = immediate, scheduled

    chain(immediate)

    paths_xml = ""
    for idx, path in enumerate(scheduled):
        if not isinstance(path, dict):
            continue
        first = chain(path.get("elements") or [])
        name = f"Scheduled_Path_{idx + 1}"
        if first:
            paths_xml += f"""
    <scheduledPaths>
        <name>{_escape(name)}</name>
        <connector>
            <targetReference>{_escape(first)}</targetReference>
        </connector>
        <label>{_escape(name.replace('_', ' '))}</label>
        <offsetNumber>{_int(path.get('duration'))}</offsetNumber>
        <offsetUnit>{_escape(path.get('unit') or 'Hours')}</offsetUnit>
        <timeSource>RecordTriggerEvent</timeSource>
    </scheduledPaths>"""

    valid_immediate = [e for e in immediate if isinstance(e, dict) and e.get("type") in SUPPORTED_TYPES]
    start_connector = (f"<connector><targetReference>{_escape(valid_immediate[0]['name'])}</targetReference></connector>"
                       if valid_immediate else "")
    changed = "\n        <doesRequireRecordChangedToMeetCriteria>true</doesRequireRecordChangedToMeetCriteria>" if paths_xml else ""
    event = spec.get("triggerEvent")
    trigger_type = "Create" if event == "Create" else ("Update" if event == "Update" else "CreateAndUpdate")
    start = f"""
    <start>
        {start_connector}{changed}
        <locationX>50</locationX>
        <locationY>50</locationY>
        <object>{_escape(spec.get('triggerObject'))}</object>
        <recordTriggerType>{trigger_type}</recordTriggerType>
        {paths_xml}
        <triggerType>RecordAfterSave</triggerType>
    </start>"""

    parts = [
        {"tag": "apiVersion", "xml": f"<apiVersion>{API_VERSION}</apiVersion>"},
        {"tag": "interviewLabel", "xml": f"<interviewLabel>{_escape(label)}</interviewLabel>"},
        {"tag": "label", "xml": f"<label>{_escape(label)}</label>"},
        {"tag": "processMetadataValues1", "xml": """
    <processMetadataValues>
        <name>BuilderType</name>
        <value>
            <stringValue>LightningFlowBuilder</stringValue>
        </value>
    </processMetadataValues>"""},
        {"tag": "processMetadataValues2", "xml": """
    <processMetadataValues>
        <name>CanvasMode</name>
        <value>
            <stringValue>AUTO_LAYOUT_CANVAS</stringValue>
        </value>
    </processMetadataValues>"""},
        {"tag": "processType", "xml": "<processType>AutoLaunchedFlow</processType>"},
        {"tag": "start", "xml": start},
        {"tag": "status", "xml": "<status>Draft</status>"},
        *all_elements,
    ]
    # Salesforce expects the top-level elements in alphabetical order; the sort is stable, so
    # same-type elements keep their flow order (as in Camille).
    parts.sort(key=lambda p: re.sub(r"\d+$", "", p["tag"]))
    body = "\n".join(p["xml"].strip() for p in parts)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Flow xmlns="http://soap.sforce.com/2006/04/metadata">\n{body}\n</Flow>'


def package_xml(flow_name: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>{flow_name}</members>
        <name>Flow</name>
    </types>
    <version>{API_VERSION}</version>
</Package>"""


def build_package(flow_name: str, flow_xml: str) -> bytes:
    """The deployable zip: package.xml at the root plus flows/<name>.flow-meta.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("package.xml", package_xml(flow_name))
        zf.writestr(f"flows/{flow_name}.flow-meta.xml", flow_xml)
    return buf.getvalue()


def flow_api_name(stamp_ms: int) -> str:
    """Camille's naming: AI_Generated_Flow_<epoch ms> -- a valid Flow API name by construction."""
    return f"AI_Generated_Flow_{stamp_ms}"


def summarize(spec: dict) -> dict:
    """Counts for the blueprint view: elements by type across the immediate and scheduled paths."""
    counts: dict[str, int] = {}

    def walk(els):
        for el in els or []:
            if not isinstance(el, dict):
                continue
            counts[el.get("type") or "Unknown"] = counts.get(el.get("type") or "Unknown", 0) + 1
            if el.get("type") == "Decision":
                for rule in el.get("rules") or []:
                    if isinstance(rule, dict):
                        walk(rule.get("elements"))
                walk(el.get("defaultElements"))
            if el.get("type") == "Loop":
                walk(el.get("loopElements"))

    spec = spec or {}
    walk(spec.get("immediateElements"))
    for p in spec.get("scheduledPaths") or []:
        if isinstance(p, dict):
            walk(p.get("elements"))
    return {"elements": counts, "total": sum(counts.values()),
            "scheduled_paths": len([p for p in spec.get("scheduledPaths") or [] if isinstance(p, dict)])}
