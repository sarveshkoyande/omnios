"""The Segmentation Planner's actions, called by the HTTP routes in app/server.py.

Camille's segState machine, kept on the server:
  ready    -- describe an audience                          (submit_query)
  consent  -- pick the email consent statuses, or skip       (answer_consent -> job "generate")
  naming   -- the SQL is ready; name the segment             (set_name       -> job "estimate")
  confirm  -- the size is known; create it or not            (create         -> job "create", or discard)
and back to ready. Writing the SQL, sizing and creating the segment run as background jobs
(campaign_creator/jobs.py) whose events stream to the browser. A job works on a copy of the
session state and commits it only when it finishes, so a failure or a cancel leaves the
conversation where it was and the step can be retried -- except that a segment Data Cloud has
created is always recorded.
"""
from __future__ import annotations

import copy
import threading
import time
import traceback
import uuid

from strategy.campaign_creator import jobs, llm

from . import datacloud, dataset, prompts, sqltools, store

MAX_HEAL = 2  # Camille's MAX_RETRIES: the Tester Agent's fixes per step
BUSY = "The Segmentation Planner is already working on a step."
UNTITLED = "Untitled — Segmentation plan"
CONSENT_TEXT = ("Before I generate the segment, could you specify the email consent status you want to include? "
                "You can select multiple options.")

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock(session_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(session_id, threading.Lock())


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iid() -> str:
    return uuid.uuid4().hex[:10]


def new_state(segments: list | None = None) -> dict:
    return {
        "schema": 1,
        "stage": "ready",          # ready | consent | naming | confirm
        "query": None,             # the audience as described
        "consent": None,           # the consent statuses picked ([] = skipped)
        "enriched_query": None,    # the request with the consent filter, as sent to the model
        "pending": None,           # the segment being defined (see _generate)
        "segments": list(segments or []),  # every segment created in this session, newest first
        "items": [],
        "token_usage": 0,
    }


# ------------------------------------------------------------------ sessions ------------

def _campaign_name(campaign_id: int | None) -> str | None:
    if not campaign_id:
        return None
    try:
        from strategy import hierarchy
        return hierarchy.get_campaign(campaign_id).get("name")
    except Exception:  # noqa: BLE001 -- the title just stays generic
        return None


def view(sess: dict) -> dict:
    job = jobs.active(sess["id"])
    return {
        "id": sess["id"], "brand": sess["brand"], "plan_id": sess["plan_id"], "campaign_id": sess["campaign_id"],
        "title": sess["title"], "created_at": sess["created_at"], "updated_at": sess["updated_at"],
        "state": sess["state"],
        "job": {"id": job.id, "kind": job.kind} if job else None,
        "llm": {"available": llm.available(), "engine": llm.engine_label()},
        "datacloud": {"configured": datacloud.configured(), "mode": datacloud.mode()},
    }


def _load(session_id: str) -> dict:
    sess = store.get(session_id)
    if not sess:
        raise KeyError(f"no segmentation planner session {session_id}")
    return sess


def open_session(brand: str | None, plan_id: int | None, campaign_id: int | None) -> dict:
    sess = store.find(brand, campaign_id)
    if not sess:
        name = _campaign_name(campaign_id)
        sess = store.create(brand, plan_id, campaign_id, f"{name} — Segmentation plan" if name else UNTITLED, new_state())
    elif plan_id and sess["plan_id"] != plan_id:
        store.set_fields(sess["id"], plan_id=plan_id)  # the campaign moved to another plan
        sess = _load(sess["id"])
    return view(sess)


def get_view(session_id: str) -> dict:
    return view(_load(session_id))


def rename(session_id: str, title: str) -> dict:
    _load(session_id)
    store.set_fields(session_id, title=(title or "").strip() or UNTITLED)
    return get_view(session_id)


def _ensure_idle(session_id: str) -> None:
    if jobs.active(session_id):
        raise jobs.Busy(BUSY)


def _stage_hint(stage: str) -> str:
    return {"consent": "Choose the email consent statuses above first, or skip the consent filter.",
            "naming": "Name the segment above first, or discard it.",
            "confirm": "Confirm or cancel the segment above first."}.get(stage, "Finish the current step first.")


def dataset_view(refresh: bool = False) -> dict:
    """The dataset for the Cockpit: the cached profile (or the snapshot); `refresh` re-reads it."""
    return dataset.public(dataset.profile(refresh=refresh, force=refresh))


# ------------------------------------------------------------------ job plumbing --------

class _Run:
    """One job's working copy of the session, its events, and its commit."""

    def __init__(self, job: jobs.Job, sess: dict):
        self.job = job
        self.sid = sess["id"]
        self.state = copy.deepcopy(sess["state"])

    def emit(self, ev: dict) -> None:
        self.job.emit(ev)

    def stop(self) -> bool:
        return self.job.cancelled

    def item(self, item: dict) -> dict:
        item = {"id": _iid(), "at": _now(), **item}
        self.state["items"].append(item)
        self.emit({"type": "item", "item": item})
        return item

    def update_item(self, item: dict) -> None:
        self.emit({"type": "item_update", "item": item})

    def find(self, item_id: str | None) -> dict | None:
        return next((it for it in self.state["items"] if it["id"] == item_id), None)

    def open_card(self, kind: str) -> dict | None:
        return next((it for it in reversed(self.state["items"])
                     if it["kind"] == kind and it.get("answered") is None and not it.get("closed")), None)

    def progress(self, item: dict, step: str, title: str, details: str) -> None:
        entry = {"step": step, "title": title, "details": details}
        item.setdefault("steps", []).append(entry)
        self.emit({"type": "progress", "item_id": item["id"], "step": entry})

    def finish_progress(self, item: dict) -> None:
        item["status"] = "done"
        self.update_item(item)

    def tokens(self, usage: dict | None) -> None:
        self.state["token_usage"] = int(self.state.get("token_usage") or 0) + int((usage or {}).get("totalTokenCount") or 0)

    def commit(self, force: bool = False) -> bool:
        """Save the working state. Skipped when the job was cancelled, unless `force` (a segment
        Data Cloud already created must be recorded)."""
        with _lock(self.sid):
            if self.job.cancelled and not force:
                return False
            store.save_state(self.sid, self.state)
        return True

    def done(self, status: str = "ok") -> None:
        sess = store.get(self.sid)
        self.emit({"type": "done", "status": status, "session": view(sess) if sess else None})

    def fail(self, message: str) -> None:
        self.emit({"type": "error", "message": message})
        self.done("error")


def _start(session_id: str, kind: str, body) -> dict:
    sess = _load(session_id)
    _ensure_idle(session_id)

    def work(job: jobs.Job) -> None:
        run = _Run(job, sess)
        try:
            body(run)
        except llm.Cancelled:
            run.emit({"type": "done", "status": "cancelled", "session": None})
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user; the session is untouched
            if not isinstance(exc, (ValueError, datacloud.DataCloudError)):
                traceback.print_exc()
            run.fail(str(exc) or exc.__class__.__name__)

    job = jobs.start(session_id, kind, work, busy_message=BUSY)
    return {"job_id": job.id, "kind": kind}


# ------------------------------------------------------------------ the Tester Agent ----

def _heal(run: _Run, error_detail: str, sql: str, prof: dict) -> tuple[str, str] | None:
    """Camille's Tester Agent: the model fixes the SQL from Data Cloud's error. None when it can't."""
    if not llm.available():
        return None
    try:
        data, usage = llm.complete_json(prompts.fix_prompt(error_detail, sql, prof), should_stop=run.stop)
        run.tokens(usage)
    except llm.Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001 -- the caller keeps the original error
        print(f"[segmentation] Tester Agent couldn't fix the SQL: {exc}")
        return None
    fixed = sqltools.sanitize(str((data or {}).get("sql") or "")).strip()
    if not fixed:
        return None
    return fixed, str((data or {}).get("explanation") or "Adjusted syntax based on error.").strip()


def _apply_fix(run: _Run, pending: dict, sql: str, why: str) -> None:
    pending["sql"] = sql
    pending["healed"] = [*pending.get("healed", []), why]
    pending["problems"] = sqltools.problems(sql)
    pending["warnings"] = sqltools.unknown_values(sql, dataset.profile(refresh=False))
    card = run.find(pending.get("sql_item"))
    if card:
        card.update(sql=sql, healed=pending["healed"], problems=pending["problems"], warnings=pending["warnings"])
        run.update_item(card)


# ------------------------------------------------------------------ actions -------------

def submit_query(session_id: str, text: str) -> dict:
    """Camille's handleSegSend in the idle state: the request, then the consent question."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Describe the audience segment you want to create.")
    _ensure_idle(session_id)
    with _lock(session_id):
        st = _load(session_id)["state"]
        if st["stage"] != "ready":
            raise ValueError(_stage_hint(st["stage"]))
        st["items"].append({"id": _iid(), "at": _now(), "kind": "user", "text": text})
        st["items"].append({"id": _iid(), "at": _now(), "kind": "consent", "text": CONSENT_TEXT,
                            "options": dataset.consent_options(), "answered": None})
        st.update(stage="consent", query=text, consent=None, enriched_query=None, pending=None)
        store.save_state(session_id, st)
    return get_view(session_id)


def answer_consent(session_id: str, values: list[str] | None) -> dict:
    """Camille's handleConsentConfirm / handleConsentSkip, then the SQL (an empty list skips)."""
    st = _load(session_id)["state"]
    if st["stage"] != "consent":
        raise ValueError("There's no consent question waiting for an answer.")
    card = next((it for it in reversed(st["items"]) if it["kind"] == "consent" and it.get("answered") is None), None)
    options = list((card or {}).get("options") or dataset.consent_options())
    picked: list[str] = []
    for v in values or []:
        v = str(v).strip()
        if v in options and v not in picked:
            picked.append(v)
    if values and not picked:
        raise ValueError("Pick one of the listed consent statuses, or skip the consent filter.")

    def body(run: _Run) -> None:
        state = run.state
        c = run.open_card("consent")
        if c:
            c["answered"] = picked
            run.update_item(c)
        run.item({"kind": "user", "text": f"Email Consent: {', '.join(picked)}" if picked else "Email Consent: Skip (no filter)"})
        enriched = prompts.enriched_query(state["query"] or "", picked)
        state.update(consent=picked, enriched_query=enriched)
        _generate(run, enriched)

    return _start(session_id, "generate", body)


def _generate(run: _Run, query: str) -> None:
    """Camille /segmentation/generate-sql (with the rules engine when the model can't answer)."""
    state = run.state
    prog = run.item({"kind": "progress", "title": "Segmentation Agent", "status": "running", "steps": []})
    run.progress(prog, "analyzing", "Segmentation Agent", "Analyzing your natural language query...")
    if datacloud.is_live() and dataset.is_stale():
        run.progress(prog, "profiling", "Data Cloud", "Reading the dataset's current values from Data Cloud...")
    prof = dataset.profile(refresh=True)

    # OmniOS rules R1/R2: the request is only ever read by the model. When it is unavailable or
    # returns nothing usable, stop with a plain message -- no SQL is built from keywords.
    result, source, note = None, "ai", None
    if not llm.available():
        run.finish_progress(prog)
        run.fail("No AI model is configured, so no SQL was written. Omni doesn't build segment SQL from "
                 "keywords - configure the model (or check its key) and try again.")
        return
    run.progress(prog, "generating", "Segmentation Agent", "Generating Data Cloud SQL query from your requirements...")
    try:
        data, usage = llm.complete_json(prompts.generation_user(query), system=prompts.generation_system(prof),
                                        should_stop=run.stop)
        run.tokens(usage)
        if isinstance(data, dict) and str(data.get("sql") or "").strip() and str(data.get("segmentName") or "").strip():
            result = data
    except llm.Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001 -- report honestly, never guess
        print(f"[segmentation] SQL generation failed: {exc}")
        run.finish_progress(prog)
        run.fail(f"The AI model couldn't be reached ({exc}), so no SQL was written. Try again in a moment.")
        return
    if result is None:
        run.finish_progress(prog)
        run.fail("The AI model didn't return a usable SQL query. Try rephrasing the audience, or try again.")
        return

    sql = sqltools.sanitize(str(result["sql"]))
    issues = sqltools.problems(sql)
    healed: list[str] = []
    if issues and source == "ai":
        run.progress(prog, "healing", "Tester Agent", "Checking the SQL: " + " ".join(issues))
        fixed = _heal(run, " ".join(issues), sql, prof)
        if fixed:
            sql, why = fixed
            healed.append(why)
            issues = sqltools.problems(sql)
            run.progress(prog, "healing_done", "Tester Agent", f"SQL fixed: {why}")
    if issues:
        note = ((note + " ") if note else "") + "Still to fix before it can be created: " + " ".join(issues)
    warnings = sqltools.unknown_values(sql, prof)
    run.progress(prog, "complete", "Segmentation Agent", "SQL query generated successfully!")
    run.finish_progress(prog)

    name = str(result.get("segmentName") or "").strip()[:80] or "New Segment"
    desc = str(result.get("segmentDescription") or "").strip()
    explanation = str(result.get("explanation") or "").strip()
    sql_card = run.item({"kind": "sql", "segmentName": name, "segmentDescription": desc, "sql": sql,
                         "explanation": explanation, "source": source, "note": note, "healed": healed, "problems": issues,
                         "warnings": warnings})
    run.item({"kind": "name", "suggested": name, "answered": None, "reason": None,
              "text": (f'I\'ve generated the SQL query for your segment. The suggested name is "{name}".\n\n'
                       "What would you like to name this segment? (Type a name or press Enter to use the suggested name)")})
    state.update(stage="naming", pending={
        "segmentName": name, "segmentDescription": desc, "sql": sql, "explanation": explanation, "source": source,
        "note": note, "healed": healed, "problems": issues, "warnings": warnings, "sql_item": sql_card["id"],
        "name": None, "count": None, "count_status": None, "count_note": None, "profile_source": prof["source"],
    })
    if run.commit():
        run.done()


def set_name(session_id: str, name: str | None) -> dict:
    """Camille's awaiting_name step: the name (an empty one takes the suggestion), then the size."""
    st = _load(session_id)["state"]
    if st["stage"] != "naming" or not st.get("pending"):
        raise ValueError("There's no segment waiting for a name.")
    final = ((name or "").strip() or st["pending"]["segmentName"])[:80]

    def body(run: _Run) -> None:
        pending = run.state["pending"]
        c = run.open_card("name")
        if c:
            c["answered"] = final
            run.update_item(c)
        run.item({"kind": "user", "text": final})
        pending["name"] = final
        _estimate(run)

    return _start(session_id, "estimate", body)


def _estimate(run: _Run) -> None:
    """Camille /segmentation/estimate-count, with the Tester Agent fixing SQL the count rejects."""
    state = run.state
    pending = state["pending"]
    prog = run.item({"kind": "progress", "title": "Data Cloud", "status": "running", "steps": []})
    run.progress(prog, "estimating", "Data Cloud", "Estimating segment size...")
    count, status, note = None, "unknown", None
    if not datacloud.configured():
        status, note = "unavailable", "Data Cloud isn't connected on this server."
    else:
        prof = dataset.profile(refresh=False)
        fixes = 0
        while True:
            try:
                count = datacloud.count(pending["sql"])
                status = "ok" if count > 0 else "zero"
                break
            except datacloud.DataCloudError as exc:
                if exc.is_sql_error and fixes < MAX_HEAL:
                    fixes += 1
                    run.progress(prog, "healing", "Tester Agent", "Data Cloud rejected the SQL. Analyzing error to fix SQL...")
                    fixed = _heal(run, exc.detail, pending["sql"], prof)
                    if fixed:
                        _apply_fix(run, pending, *fixed)
                        run.progress(prog, "healing_done", "Tester Agent", f"SQL fixed: {fixed[1]}")
                        continue
                status, note = "unknown", str(exc)
                break
            except Exception as exc:  # noqa: BLE001 -- an unreadable reply: the size is just unknown
                status, note = "unknown", str(exc) or exc.__class__.__name__
                break
    if status == "zero" and pending.get("warnings"):
        note = " ".join(pending["warnings"])  # why it's empty: a value the data doesn't have
    run.progress(prog, "estimated", "Data Cloud",
                 f"{count:,} records." if status in ("ok", "zero") else "The size couldn't be estimated.")
    run.finish_progress(prog)
    pending.update(count=count, count_status=status, count_note=note)
    run.item({"kind": "count", "count": count, "status": status, "note": note, "answered": None})
    state["stage"] = "confirm"
    if run.commit():
        run.done()


def discard(session_id: str) -> dict:
    """Camille's "No, cancel." (and a way out of the consent and naming steps)."""
    _ensure_idle(session_id)
    with _lock(session_id):
        st = _load(session_id)["state"]
        if st["stage"] == "ready":
            raise ValueError("There's no segment in progress.")
        for it in st["items"]:
            if it["kind"] == "count" and it.get("answered") is None:
                it["answered"] = {"proceed": False}
            elif it["kind"] in ("consent", "name") and it.get("answered") is None:
                it["closed"] = True
        st["items"].append({"id": _iid(), "at": _now(), "kind": "user",
                            "text": "No, cancel." if st["stage"] == "confirm" else "Discard this segment."})
        st.update(stage="ready", pending=None, query=None, consent=None, enriched_query=None)
        store.save_state(session_id, st)
    return get_view(session_id)


def create(session_id: str) -> dict:
    """Camille /segmentation/create-segment: duplicate check, creation with self-healing retries,
    publish."""
    st = _load(session_id)["state"]
    if st["stage"] != "confirm" or not st.get("pending"):
        raise ValueError("There's no segment waiting for confirmation.")
    if not datacloud.configured():
        raise ValueError("Data Cloud isn't configured on this server, so the segment can't be created here.")

    def body(run: _Run) -> None:
        state = run.state
        pending = state["pending"]
        c = run.open_card("count")
        if c:
            c["answered"] = {"proceed": True}
            run.update_item(c)
        run.item({"kind": "user", "text": "Yes, proceed."})
        name = pending.get("name") or pending["segmentName"]
        prog = run.item({"kind": "progress", "title": "Data Cloud", "status": "running", "steps": []})
        run.progress(prog, "authenticating", "Data Cloud", "Authenticating with Salesforce Data Cloud...")
        datacloud.authenticate()
        run.progress(prog, "checking_duplicates", "Data Cloud", "Checking for existing segments with the same name...")
        try:
            duplicate = any(n.strip().lower() == name.strip().lower() for n in datacloud.segment_names())
        except datacloud.DataCloudError as exc:  # Camille: continue even if the check fails
            print(f"[segmentation] couldn't check for duplicate names: {exc}")
            duplicate = False
        if duplicate:
            run.finish_progress(prog)
            msg = f'A segment named "{name}" already exists. Please choose a different name.'
            run.item({"kind": "name", "suggested": pending["segmentName"], "answered": None, "reason": msg,
                      "text": f"{msg}\n\nWhat would you like to name this segment instead?"})
            pending["name"] = None
            state["stage"] = "naming"
            if run.commit():
                run.done()
            return

        prof = dataset.profile(refresh=False)
        stamp = str(int(time.time() * 1000))[8:]
        attempt, sql = 0, pending["sql"]
        while True:
            if attempt == 0:
                run.progress(prog, "creating", "Data Cloud", f'Creating segment "{name}" in Data Cloud...')
            else:
                run.progress(prog, "retrying", "Tester Agent", f"Retry {attempt}/{MAX_HEAL}: Attempting creation with fixed SQL...")
            dev_name = datacloud.developer_name(name, stamp, attempt)
            payload = datacloud.build_payload(name, pending.get("segmentDescription") or f"Segment: {name}", sql, dev_name)
            try:
                segment_id = datacloud.create_segment(payload)
                break
            except datacloud.DataCloudError as exc:
                print(f"[segmentation] create error (attempt {attempt + 1}): {exc.detail[:500]}")
                if attempt < MAX_HEAL:
                    run.progress(prog, "healing", "Tester Agent", "Creation failed. Analyzing error to fix SQL...")
                    fixed = _heal(run, exc.detail, sql, prof)
                    if fixed:
                        sql = fixed[0]
                        _apply_fix(run, pending, *fixed)
                        run.progress(prog, "healing_done", "Tester Agent", f"SQL fixed: {fixed[1]}")
                        attempt += 1
                        continue
                raise datacloud.DataCloudError(f"Failed to create segment: {exc}", exc.status, exc.detail) from exc

        # Created: from here on the result is always recorded, even if the step was cancelled.
        run.progress(prog, "publishing", "Data Cloud", "Publishing segment for data population...")
        published, publish_error = False, None
        try:
            datacloud.publish(segment_id)
            published = True
        except Exception as exc:  # noqa: BLE001 -- Camille: the segment is still created
            publish_error = str(exc)
            print(f"[segmentation] publish failed (segment still created): {exc}")
        try:
            url = datacloud.segment_url(segment_id)
        except Exception:  # noqa: BLE001
            url = None
        run.progress(prog, "complete", "Data Cloud",
                     "Segment created and published." if published else "Segment created; publishing didn't go through.")
        run.finish_progress(prog)
        record = {"segmentId": segment_id, "segmentName": name, "segmentUrl": url, "published": published,
                  "publishError": publish_error, "developerName": dev_name,
                  "segmentDescription": pending.get("segmentDescription") or "", "sql": sql,
                  "count": pending.get("count"), "created_at": _now()}
        run.item({"kind": "success", **{k: record[k] for k in ("segmentId", "segmentName", "segmentUrl", "published",
                                                               "publishError", "developerName", "count")}})
        state["segments"] = [record, *state.get("segments", [])]
        state.update(stage="ready", pending=None, query=None, consent=None, enriched_query=None)
        run.commit(force=True)
        run.done()

    return _start(session_id, "create", body)


def reset(session_id: str) -> dict:
    """Start over: a fresh conversation. The segments already created stay listed."""
    job = jobs.active(session_id)
    if job and job.kind == "create":
        raise jobs.Busy("A segment is being created in Data Cloud; wait for it to finish.")
    _load(session_id)
    jobs.cancel_active(session_id)
    with _lock(session_id):
        st = _load(session_id)["state"]
        store.save_state(session_id, new_state(st.get("segments")))
    return get_view(session_id)


def cancel(session_id: str) -> dict:
    job = jobs.active(session_id)
    if job and job.kind == "create":
        raise ValueError("A segment is being created in Data Cloud and can't be stopped midway.")
    _load(session_id)
    jobs.cancel_active(session_id)
    return get_view(session_id)
