"""Salesforce Data Cloud for the Segmentation Planner (Camille's segmentationAgent.js).

Configured in the environment (or <repo>/.env), under Camille's names:
    DC_SALESFORCE_LOGIN_URL   the OAuth token endpoint (…/services/oauth2/token)
    DC_CLIENT_ID, DC_CLIENT_SECRET, DC_USERNAME, DC_PASSWORD
    DC_API_VERSION            optional, v64.0 by default (Camille's default)

  * Sign-in: the OAuth 2.0 username-password flow, as Camille's dcAuthenticate. The token is
    reused for a few minutes and a 401 signs in again once.
  * Query API (ssot/queryv2): record counts and the dataset profile. Its rows come back as
    arrays, with each column's position in `metadata[col].placeInOrder`.
  * Segments API (ssot/segments): every page of existing segments for the duplicate check,
    creation of a DBT segment, and publish.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from decimal import Decimal

import requests

from strategy import conversation_llm  # noqa: F401  (importing it loads <repo>/.env into os.environ)

from .dataset import DMO

_TOKEN_TTL_S = 15 * 60
_LOCK = threading.Lock()
_AUTH: dict = {"at": 0.0, "token": None, "instance_url": None}


class DataCloudError(RuntimeError):
    """A Data Cloud call failed. `detail` is the raw response body text (what the Tester Agent
    reads to fix the SQL); str(error) is a readable message."""

    def __init__(self, message: str, status: int | None = None, detail: str | None = None):
        super().__init__(message)
        self.status = status
        self.detail = detail or message

    @property
    def is_sql_error(self) -> bool:
        return self.status == 400


def _cfg() -> dict:
    e = os.environ
    return {"login_url": e.get("DC_SALESFORCE_LOGIN_URL", "").strip(), "client_id": e.get("DC_CLIENT_ID", "").strip(),
            "client_secret": e.get("DC_CLIENT_SECRET", "").strip(), "username": e.get("DC_USERNAME", "").strip(),
            "password": e.get("DC_PASSWORD", ""), "version": (e.get("DC_API_VERSION", "").strip() or "v64.0")}


def is_live() -> bool:
    """True when the DC_* settings point at a real Data Cloud org."""
    c = _cfg()
    return all(c[k] for k in ("login_url", "client_id", "client_secret", "username", "password"))


def configured() -> bool:
    """Segments can be sized and created: against the real org when it's configured, otherwise
    against the generated local stand-in (segmentation/local_store.py)."""
    return True


def mode() -> str:
    return "live" if is_live() else "local"


def api_version() -> str:
    return _cfg()["version"]


def _readable(body) -> str:
    """The human part of a Data Cloud error body. Query errors nest a JSON string in `message`."""
    items = body if isinstance(body, list) else [body]
    msgs = []
    for it in items:
        if not isinstance(it, dict):
            msgs.append(str(it))
            continue
        msg = it.get("message") or it.get("error_description") or it.get("error") or it.get("errorCode") or ""
        if isinstance(msg, str) and msg.lstrip().startswith("{"):
            try:
                inner = json.loads(msg)
                msg = inner.get("message") or msg
            except ValueError:
                pass
        msg = re.sub(r"\s*\[TraceId:[^\]]*\]", "", str(msg)).strip()
        if msg:
            msgs.append(msg)
    return "; ".join(msgs)[:500] or "Unknown error"


def _raise_for(resp: requests.Response, what: str) -> None:
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        detail = json.dumps(body, ensure_ascii=False)
    except ValueError:
        body, detail = resp.text, resp.text
    raise DataCloudError(f"{what} failed ({resp.status_code}): {_readable(body)}", resp.status_code, detail[:4000])


def authenticate(force: bool = False) -> dict:
    """{access_token, instance_url} (instance URL without a trailing slash)."""
    if not is_live():
        return {"access_token": "local", "instance_url": "local", "mode": "local"}
    with _LOCK:
        if not force and _AUTH["token"] and time.time() - _AUTH["at"] < _TOKEN_TTL_S:
            return {"access_token": _AUTH["token"], "instance_url": _AUTH["instance_url"]}
        c = _cfg()
        try:
            resp = requests.post(c["login_url"], data={
                "grant_type": "password", "client_id": c["client_id"], "client_secret": c["client_secret"],
                "username": c["username"], "password": c["password"]}, timeout=30)
        except requests.RequestException as exc:
            raise DataCloudError(f"Authentication failed: {exc}") from exc
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
            raise DataCloudError(f"Authentication failed: {_readable(body)}", resp.status_code)
        data = resp.json()
        _AUTH.update(at=time.time(), token=data["access_token"], instance_url=str(data["instance_url"]).rstrip("/"))
        return {"access_token": _AUTH["token"], "instance_url": _AUTH["instance_url"]}


def _call(method: str, path: str, what: str, *, timeout: float, headers: dict | None = None, **kwargs):
    for attempt in (1, 2):
        auth = authenticate(force=attempt == 2)
        headers_now = {"Authorization": f"Bearer {auth['access_token']}", "Accept": "application/json", **(headers or {})}
        try:
            resp = requests.request(method, f"{auth['instance_url']}{path}", headers=headers_now, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise DataCloudError(f"{what} failed: {exc}") from exc
        if resp.status_code == 401 and attempt == 1:
            continue  # the session expired: sign in again once
        _raise_for(resp, what)
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}
    return {}


def query(sql: str, timeout: float = 30) -> list[dict]:
    """Rows as {column: value} dicts, whatever shape the Query API returned them in."""
    if not is_live():
        from . import local_store
        return local_store.query(sql)
    body = _call("POST", f"/services/data/{api_version()}/ssot/queryv2", "Data Cloud query", timeout=timeout,
                 json={"sql": sql}, headers={"Content-Type": "application/json"})
    meta = body.get("metadata") or {}
    order = sorted(meta, key=lambda k: (meta[k] or {}).get("placeInOrder", 0)) if isinstance(meta, dict) else []
    rows = []
    for row in body.get("data") or []:
        if isinstance(row, dict):
            rows.append(row)
        elif isinstance(row, list):
            rows.append({(order[i] if i < len(order) else str(i)): v for i, v in enumerate(row)})
    return rows


def count(sql: str) -> int:
    """How many records a segment's SQL selects (Camille's estimate-count)."""
    rows = query(f"SELECT count(*) AS cnt FROM ({sql}) seg")
    value = (rows[0] if rows else {}).get("cnt")
    return int(Decimal(str(value))) if value is not None else 0


def segment_names() -> list[str]:
    """The display names of every segment in the org, all pages."""
    if not is_live():
        from . import local_store
        return local_store.segment_names()
    names: list[str] = []
    offset = 0
    for _ in range(50):
        body = _call("GET", f"/services/data/{api_version()}/ssot/segments", "Listing segments", timeout=30,
                     params={"batchSize": 200, "offset": offset})
        page = body.get("segments") or []
        names += [str(s.get("displayName") or "") for s in page]
        offset += len(page)
        if not page or offset >= int(body.get("totalSize") or 0):
            break
    return names


def developer_name(display: str, stamp: str, attempt: int = 0) -> str:
    """Camille's generateDeveloperName (upper-case, spaces to underscores, up to 27 characters,
    then a timestamp suffix; `_r<n>` on a retry), made a valid API name: letters, digits and
    single underscores, starting with a letter, never ending in an underscore."""
    s = re.sub(r"[^A-Za-z0-9\s]", "", (display or "").strip() or "UnnamedSegment")
    s = re.sub(r"\s+", "_", s.strip()).upper()
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not s[0].isalpha():
        s = ("SEG_" + s).rstrip("_")
    s = s[:27].rstrip("_")
    return f"{s}_{stamp}" + (f"_r{attempt}" if attempt else "")


def build_payload(name: str, description: str, sql: str, dev_name: str) -> dict:
    """Camille's buildSegmentPayload: a DBT segment on the data model object."""
    return {
        "developerName": dev_name,
        "displayName": name,
        "description": description or f"Segment: {name}",
        "segmentType": "Dbt",
        "segmentOnApiName": DMO,
        "includeDbt": {"models": {"models": [{"name": dev_name, "sql": sql}]}},
    }


def create_segment(payload: dict) -> str:
    if not is_live():
        from . import local_store
        return local_store.create_segment(payload)
    body = _call("POST", f"/services/data/{api_version()}/ssot/segments", "Segment creation", timeout=60,
                 json=payload, headers={"Content-Type": "application/json"})
    seg_id = body.get("marketSegmentId") if isinstance(body, dict) else None
    if not seg_id:
        raise DataCloudError("Segment creation returned no ID. Response: " + json.dumps(body, ensure_ascii=False)[:1000],
                             None, json.dumps(body, ensure_ascii=False)[:4000])
    return str(seg_id)


def publish(segment_id: str) -> None:
    if not is_live():
        from . import local_store
        return local_store.publish(segment_id)
    _call("POST", f"/services/data/{api_version()}/ssot/segments/{segment_id}/actions/publish", "Publishing",
          timeout=60, headers={"Content-Length": "0"})


def segment_url(segment_id: str) -> str:
    if not is_live():
        from . import local_store
        return local_store.segment_url(segment_id)
    return f"{authenticate()['instance_url']}/lightning/r/MarketSegment/{segment_id}/view"
