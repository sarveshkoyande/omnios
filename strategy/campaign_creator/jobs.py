"""Background jobs whose events stream to the browser.

Camille ran each LLM step inside the HTTP request and streamed SSE from it, so closing the tab
lost the work. Here a POST starts a job on a worker thread and returns at once; the browser
then reads the job's events from GET /events (server-sent events), and can re-attach after a
reload from any point (`after` = events already seen). A job keeps going if the page is
closed, and its result is saved to the session when it finishes. Jobs live in process memory:
a server restart drops a running job, and the session is left as it was before the job began
(results are committed only when a job completes).
"""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from typing import Callable, Iterator

HEARTBEAT_S = 15.0
_KEEP_FINISHED = 40


class Busy(RuntimeError):
    """The session already has a job running."""


class Job:
    def __init__(self, session_id: str, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.kind = kind
        self.events: list[dict] = []
        self.done = False
        self.cancelled = False
        self.started_at = time.time()
        self.finished_at: float | None = None
        self._cond = threading.Condition()

    def emit(self, event: dict) -> None:
        # Snapshot now: the worker keeps mutating the objects it emits (an item gains steps
        # after its `item` event), and a replay must see each event as it was sent.
        snapshot = copy.deepcopy(event)
        with self._cond:
            self.events.append({**snapshot, "seq": len(self.events) + 1})
            self._cond.notify_all()

    def finish(self) -> None:
        with self._cond:
            self.done = True
            self.finished_at = time.time()
            self._cond.notify_all()

    def cancel(self) -> None:
        self.cancelled = True

    def should_stop(self) -> bool:
        return self.cancelled

    def wait(self, after: int, timeout: float) -> tuple[list[dict], bool]:
        """Events after `after`, waiting up to `timeout` for new ones. -> (events, done)."""
        with self._cond:
            if len(self.events) <= after and not self.done:
                self._cond.wait(timeout)
            return self.events[after:], self.done


_LOCK = threading.Lock()
_JOBS: dict[str, Job] = {}
_ACTIVE: dict[str, str] = {}  # session_id -> running job id


def get(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)


def active(session_id: str) -> Job | None:
    with _LOCK:
        jid = _ACTIVE.get(session_id)
        job = _JOBS.get(jid) if jid else None
    return job if job and not job.done else None


def start(session_id: str, kind: str, work: Callable[[Job], None],
          busy_message: str = "This campaign planner is already working on a step.") -> Job:
    """Run `work(job)` on a daemon thread. Raises Busy when this session already has a job.
    `work` emits its own events; an uncaught exception becomes an `error` event, and the job
    always ends with a `done` event (emitted by `work` itself on success). Session ids are
    random, so the Campaign and Segmentation Planners share this registry safely."""
    with _LOCK:
        running = _ACTIVE.get(session_id)
        if running and running in _JOBS and not _JOBS[running].done:
            raise Busy(busy_message)
        job = Job(session_id, kind)
        _JOBS[job.id] = job
        _ACTIVE[session_id] = job.id
        finished = sorted((j for j in _JOBS.values() if j.done), key=lambda j: j.finished_at or 0)
        for old in finished[:-_KEEP_FINISHED]:
            _JOBS.pop(old.id, None)

    def runner() -> None:
        try:
            work(job)
        except Exception as exc:  # noqa: BLE001 -- a job must always end with an event, never hang the stream
            import traceback
            traceback.print_exc()
            job.emit({"type": "error", "message": str(exc) or exc.__class__.__name__})
            job.emit({"type": "done", "status": "error", "session": None})
        finally:
            job.finish()
            with _LOCK:
                if _ACTIVE.get(session_id) == job.id:
                    _ACTIVE.pop(session_id, None)

    threading.Thread(target=runner, name=f"campaign-creator-{kind}-{job.id}", daemon=True).start()
    return job


def cancel_active(session_id: str) -> Job | None:
    job = active(session_id)
    if job:
        job.cancel()
    return job


def sse(job: Job, after: int = 0) -> Iterator[str]:
    """Server-sent events for a job, from event number `after`. Comment lines keep idle
    connections open through proxies (Camille's 15-second heartbeat)."""
    sent = max(0, after)
    while True:
        events, _ = job.wait(sent, HEARTBEAT_S)
        if events:
            for ev in events:
                yield f"id: {ev['seq']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
            sent += len(events)
        elif not job.done:
            yield ": heartbeat\n\n"
        if job.done and sent >= len(job.events):
            return
