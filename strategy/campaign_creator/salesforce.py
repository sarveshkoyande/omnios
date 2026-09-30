"""Salesforce connection for the Campaign Planner: OAuth, org metadata, Flow deploy.

Camille did this with jsforce inside an Express session (index.js /auth/salesforce/*,
getSalesforceMetadata, /flows/deploy). The same three things over plain HTTPS here:

  * OAuth 2.0 web-server flow. Configure a Salesforce Connected App whose callback URL is
    <omni-host>/api/salesforce/callback, then set in the environment (or <repo>/.env):
        SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET,
        SALESFORCE_REDIRECT_URI  (e.g. http://localhost:8731/api/salesforce/callback -- Salesforce
                                  takes plain http only for localhost; a Connect clicked on
                                  another host name for this server hops to this one first)
        SALESFORCE_LOGIN_URL     (optional; https://login.salesforce.com by default, or a
                                  My Domain / test.salesforce.com URL)
    Tokens are held in server memory only, keyed by an HttpOnly browser cookie -- never
    written to disk, gone on restart, like Camille's in-memory session store.
  * Org metadata: the objects a brief mentions (plus the common CRM objects) with their field
    names, labels and types, which the Architect and QA agents map the journey onto. When no
    org is connected, a standard-object schema stands in so the agents can still work.
  * Deploy: the Flow package zip through the Metadata API's SOAP `deploy`, then
    `checkDeployStatus` polled every 2 seconds until Salesforce finishes.
"""
from __future__ import annotations

import base64
import os
import secrets
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlsplit

import requests

from strategy import conversation_llm  # noqa: F401  (importing it loads <repo>/.env into os.environ)

API_VERSION = "58.0"
_HTTP_TIMEOUT = 30
_MD_NS = "http://soap.sforce.com/2006/04/metadata"
_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

COMMON_OBJECTS = ("Account", "Contact", "Lead", "Opportunity", "Case", "Task", "User", "Campaign")

_LOCK = threading.Lock()
_CONNECTIONS: dict[str, dict] = {}   # browser sid -> {access_token, instance_url, refresh_token, id_url, user}
_PENDING: dict[str, dict] = {}       # oauth state -> {sid, return_to, created}


class SalesforceError(RuntimeError):
    pass


# ------------------------------------------------------------------ config --------------

def _cfg() -> dict:
    return {
        "client_id": os.environ.get("SALESFORCE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("SALESFORCE_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.environ.get("SALESFORCE_REDIRECT_URI", "").strip(),
        "login_url": (os.environ.get("SALESFORCE_LOGIN_URL", "").strip() or "https://login.salesforce.com").rstrip("/"),
    }


def configured() -> bool:
    c = _cfg()
    return bool(c["client_id"] and c["client_secret"] and c["redirect_uri"])


def new_sid() -> str:
    return secrets.token_urlsafe(24)


def callback_origin() -> tuple[str, str] | None:
    """(scheme, host[:port]) of SALESFORCE_REDIRECT_URI. The sign-in cookie has to be set on
    this host: it's where Salesforce sends the browser back to."""
    u = urlsplit(_cfg()["redirect_uri"])
    return (u.scheme, u.netloc) if u.scheme and u.netloc else None


# ------------------------------------------------------------------ OAuth ---------------

def authorize_url(sid: str, return_to: str) -> str:
    """The Salesforce login URL for this browser session; `state` ties the callback to it."""
    c = _cfg()
    if not configured():
        raise SalesforceError("Salesforce isn't configured on this server.")
    state = secrets.token_urlsafe(24)
    with _LOCK:
        now = time.time()
        for k in [k for k, v in _PENDING.items() if now - v["created"] > 900]:
            _PENDING.pop(k, None)
        _PENDING[state] = {"sid": sid, "return_to": return_to, "created": now}
    query = urlencode({"response_type": "code", "client_id": c["client_id"], "redirect_uri": c["redirect_uri"],
                       "scope": "api id web refresh_token", "state": state})
    return f"{c['login_url']}/services/oauth2/authorize?{query}"


def complete_login(sid: str, code: str, state: str) -> str:
    """Exchange the callback's code for tokens; returns where to send the browser next."""
    with _LOCK:
        pending = _PENDING.pop(state, None)
    if not pending or pending["sid"] != sid:
        raise SalesforceError("This sign-in link has expired or belongs to another browser. Start the connection again.")
    c = _cfg()
    resp = requests.post(f"{c['login_url']}/services/oauth2/token", data={
        "grant_type": "authorization_code", "code": code, "client_id": c["client_id"],
        "client_secret": c["client_secret"], "redirect_uri": c["redirect_uri"],
    }, timeout=_HTTP_TIMEOUT)
    data = _json_or_error(resp, "Salesforce sign-in failed")
    conn = {"access_token": data["access_token"], "instance_url": data["instance_url"].rstrip("/"),
            "refresh_token": data.get("refresh_token"), "id_url": data.get("id"), "user": None}
    conn["user"] = _identity(conn)
    with _LOCK:
        _CONNECTIONS[sid] = conn
    return pending["return_to"]


def _json_or_error(resp, what: str) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or not isinstance(data, dict):
        detail = (data.get("error_description") or data.get("error") or (data.get("message") if isinstance(data, dict) else None)
                  or resp.text[:300])
        raise SalesforceError(f"{what}: {detail}")
    return data


def _refresh(conn: dict) -> None:
    c = _cfg()
    if not conn.get("refresh_token"):
        raise SalesforceError("The Salesforce session expired. Connect the org again.")
    resp = requests.post(f"{c['login_url']}/services/oauth2/token", data={
        "grant_type": "refresh_token", "refresh_token": conn["refresh_token"],
        "client_id": c["client_id"], "client_secret": c["client_secret"],
    }, timeout=_HTTP_TIMEOUT)
    data = _json_or_error(resp, "Refreshing the Salesforce session failed")
    conn["access_token"] = data["access_token"]
    if data.get("instance_url"):
        conn["instance_url"] = data["instance_url"].rstrip("/")


def _identity(conn: dict) -> dict | None:
    if not conn.get("id_url"):
        return None
    try:
        r = requests.get(conn["id_url"], headers={"Authorization": f"Bearer {conn['access_token']}"}, timeout=_HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        d = r.json()
        return {"display_name": d.get("display_name"), "username": d.get("username"),
                "organization_id": d.get("organization_id"), "email": d.get("email")}
    except (requests.RequestException, ValueError):
        return None


def connection(sid: str | None) -> dict | None:
    if not sid:
        return None
    with _LOCK:
        return _CONNECTIONS.get(sid)


def disconnect(sid: str | None) -> None:
    with _LOCK:
        conn = _CONNECTIONS.pop(sid, None) if sid else None
    if conn:
        try:  # best effort: revoke the token so it can't be reused
            requests.post(f"{_cfg()['login_url']}/services/oauth2/revoke", data={"token": conn["access_token"]},
                          timeout=10)
        except requests.RequestException:
            pass


def status(sid: str | None) -> dict:
    conn = connection(sid)
    return {"configured": configured(), "connected": bool(conn),
            "instance_url": conn["instance_url"] if conn else None,
            "user": conn.get("user") if conn else None}


# ------------------------------------------------------------------ REST ----------------

def _rest(conn: dict, path: str) -> dict:
    url = f"{conn['instance_url']}/services/data/v{API_VERSION}{path}"
    for attempt in range(2):
        r = requests.get(url, headers={"Authorization": f"Bearer {conn['access_token']}"}, timeout=_HTTP_TIMEOUT)
        if r.status_code == 401 and attempt == 0:
            _refresh(conn)
            continue
        if r.status_code >= 400:
            raise SalesforceError(f"Salesforce API {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()
    raise SalesforceError("Salesforce rejected the session.")


def org_metadata(conn: dict, prompt: str) -> dict:
    """Camille's getSalesforceMetadata: the common objects plus every object the prompt names
    (custom objects matched without their __c suffix), up to 10 described, as
    {ObjectName: [{name, label, type}]}."""
    names = [o.get("name") for o in _rest(conn, "/sobjects/").get("sobjects", []) if o.get("name")]
    text = (prompt or "").lower()
    found: list[str] = [n for n in COMMON_OBJECTS if n in names]
    for n in names:
        if n not in found and n.lower().replace("__c", "") in text:
            found.append(n)

    def describe(name: str):
        try:
            fields = _rest(conn, f"/sobjects/{name}/describe/").get("fields", [])
            return name, [{"name": f.get("name"), "label": f.get("label"), "type": f.get("type")} for f in fields]
        except SalesforceError as exc:
            print(f"[campaign-creator] describe {name} failed: {exc}")
            return name, None

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(describe, found[:10]))
    return {name: fields for name, fields in results if fields is not None}


def _f(name: str, label: str, typ: str) -> dict:
    return {"name": name, "label": label, "type": typ}


def standard_metadata() -> dict:
    """Standard Salesforce objects and fields, for when no org is connected."""
    common = [_f("Id", "Record ID", "id"), _f("Name", "Name", "string"), _f("OwnerId", "Owner ID", "reference"),
              _f("CreatedDate", "Created Date", "datetime"), _f("LastModifiedDate", "Last Modified Date", "datetime")]
    return {
        "Contact": [_f("Id", "Contact ID", "id"), _f("FirstName", "First Name", "string"), _f("LastName", "Last Name", "string"),
                    _f("Email", "Email", "email"), _f("HasOptedOutOfEmail", "Email Opt Out", "boolean"),
                    _f("Title", "Title", "string"), _f("Department", "Department", "string"),
                    _f("AccountId", "Account ID", "reference"), _f("MailingState", "Mailing State/Province", "string"),
                    _f("MailingCountry", "Mailing Country", "string"), _f("Phone", "Business Phone", "phone"),
                    _f("MobilePhone", "Mobile Phone", "phone"), _f("DoNotCall", "Do Not Call", "boolean"),
                    _f("LeadSource", "Lead Source", "picklist"), _f("CreatedDate", "Created Date", "datetime"),
                    _f("LastModifiedDate", "Last Modified Date", "datetime")],
        "Account": common + [_f("Industry", "Industry", "picklist"), _f("Type", "Account Type", "picklist"),
                             _f("BillingState", "Billing State/Province", "string")],
        "Lead": [_f("Id", "Lead ID", "id"), _f("FirstName", "First Name", "string"), _f("LastName", "Last Name", "string"),
                 _f("Email", "Email", "email"), _f("HasOptedOutOfEmail", "Email Opt Out", "boolean"),
                 _f("Status", "Lead Status", "picklist"), _f("Company", "Company", "string"),
                 _f("LeadSource", "Lead Source", "picklist"), _f("CreatedDate", "Created Date", "datetime")],
        "Campaign": common + [_f("Status", "Status", "picklist"), _f("Type", "Type", "picklist"),
                              _f("IsActive", "Active", "boolean"), _f("StartDate", "Start Date", "date"),
                              _f("EndDate", "End Date", "date")],
        "CampaignMember": [_f("Id", "Campaign Member ID", "id"), _f("CampaignId", "Campaign ID", "reference"),
                           _f("ContactId", "Contact ID", "reference"), _f("LeadId", "Lead ID", "reference"),
                           _f("Status", "Status", "picklist"), _f("HasResponded", "Responded", "boolean")],
        "Task": [_f("Id", "Activity ID", "id"), _f("Subject", "Subject", "combobox"), _f("Status", "Status", "picklist"),
                 _f("Priority", "Priority", "picklist"), _f("WhoId", "Name ID", "reference"),
                 _f("WhatId", "Related To ID", "reference"), _f("ActivityDate", "Due Date Only", "date"),
                 _f("OwnerId", "Assigned To ID", "reference")],
        "User": [_f("Id", "User ID", "id"), _f("Name", "Full Name", "string"), _f("Email", "Email", "email"),
                 _f("IsActive", "Active", "boolean")],
    }


# ------------------------------------------------------------------ Metadata API --------

def _soap(conn: dict, body: str) -> ET.Element:
    envelope = (f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<soapenv:Envelope xmlns:soapenv="{_SOAP_NS}"><soapenv:Header>'
                f'<SessionHeader xmlns="{_MD_NS}"><sessionId>{{token}}</sessionId></SessionHeader>'
                f'</soapenv:Header><soapenv:Body>{body}</soapenv:Body></soapenv:Envelope>')
    for attempt in range(2):
        payload = envelope.replace("{token}", _xml_escape(conn["access_token"]))
        r = requests.post(f"{conn['instance_url']}/services/Soap/m/{API_VERSION}", data=payload.encode("utf-8"),
                          headers={"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": '""'}, timeout=120)
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            raise SalesforceError(f"Salesforce Metadata API -> {r.status_code}: {r.text[:300]}")
        fault = root.find(f".//{{{_SOAP_NS}}}Fault")
        if fault is not None:
            # faultcode/faultstring are unqualified in SOAP 1.1, but match by local name so a
            # default namespace on the envelope can't hide them.
            parts = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in fault}
            code, msg = parts.get("faultcode", ""), parts.get("faultstring", "")
            if "INVALID_SESSION_ID" in code and attempt == 0:
                _refresh(conn)
                continue
            raise SalesforceError(msg or code or "Salesforce Metadata API error")
        return root
    raise SalesforceError("Salesforce rejected the session.")


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _text(root: ET.Element, tag: str) -> str:
    """A direct child of the response's <result> (not a same-named element nested in details)."""
    result = root.find(f".//{{{_MD_NS}}}result")
    found = result.find(f"{{{_MD_NS}}}{tag}") if result is not None else None
    return (found.text or "").strip() if found is not None and found.text else ""


def deploy(conn: dict, zip_bytes: bytes, on_status=None, timeout_s: int = 600) -> dict:
    """Deploy the package; poll until done. -> {success, id, status, errors, details}."""
    zipped = base64.b64encode(zip_bytes).decode("ascii")
    root = _soap(conn, f'<deploy xmlns="{_MD_NS}"><ZipFile>{zipped}</ZipFile><DeployOptions>'
                       '<rollbackOnError>true</rollbackOnError><singlePackage>true</singlePackage>'
                       '</DeployOptions></deploy>')
    deploy_id = _text(root, "id")
    if not deploy_id:
        raise SalesforceError("Salesforce did not return a deployment id.")
    if on_status:
        on_status("Queued", deploy_id)
    started = time.time()
    while True:
        time.sleep(2)
        res = _soap(conn, f'<checkDeployStatus xmlns="{_MD_NS}"><asyncProcessId>{deploy_id}</asyncProcessId>'
                          '<includeDetails>true</includeDetails></checkDeployStatus>')
        state = _text(res, "status")
        done = _text(res, "done").lower() == "true"
        if on_status:
            on_status(state or "InProgress", deploy_id)
        if done or state not in ("", "Pending", "InProgress", "Canceling"):
            break
        if time.time() - started > timeout_s:
            raise SalesforceError(f"Salesforce was still processing deployment {deploy_id} after {timeout_s // 60} minutes.")
    errors = []
    for failure in res.iter(f"{{{_MD_NS}}}componentFailures"):
        problem = (failure.findtext(f"{{{_MD_NS}}}problem") or "").strip()
        name = (failure.findtext(f"{{{_MD_NS}}}fullName") or "").strip()
        if problem:
            errors.append(f"{name}: {problem}" if name else problem)
    if not errors and _text(res, "errorMessage"):
        errors.append(_text(res, "errorMessage"))
    return {"success": state == "Succeeded", "id": deploy_id, "status": state, "errors": errors}


def flows_url(conn: dict) -> str:
    return f"{conn['instance_url']}/lightning/setup/Flows/home"
