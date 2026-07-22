"""Persistent feedback overlay for process-knowledge/Cognee grounding.

The live Cognee graph is optional and can be disabled locally. Feedback captured from the
diagnostics UI is therefore stored in the app data directory and injected into future
process-grounding responses regardless of Cognee availability. When Cognee is enabled, this
same text is also suitable for ingestion, but the overlay is the reliable path.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from strategy.paths import data_path, ensure_data_dir

FEEDBACK_FILE = "cognee_feedback.jsonl"


def _path() -> Path:
    ensure_data_dir()
    return data_path(FEEDBACK_FILE)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def add_feedback(payload: dict) -> dict:
    topic = str(payload.get("topic") or "").strip()
    if not topic:
        raise ValueError("topic is required")
    note = str(payload.get("feedback") or "").strip()
    if not note:
        raise ValueError("feedback is required")
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topic": topic,
        "brand": str(payload.get("brand") or "").strip(),
        "therapy_area": str(payload.get("therapy_area") or "").strip(),
        "request": str(payload.get("request") or "").strip(),
        "observed": str(payload.get("observed") or "").strip(),
        "feedback": note,
        "expected": str(payload.get("expected") or "").strip(),
        "rating": str(payload.get("rating") or "").strip(),
    }
    with _path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_feedback(limit: int = 50) -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.sort(key=lambda row: row.get("ts") or "", reverse=True)
    return rows[: max(1, min(limit, 200))]


def matching_feedback(topic: str, brand: str = "", therapy_area: str = "", limit: int = 5) -> list[dict]:
    topic_n = _norm(topic)
    brand_n = _norm(brand)
    ta_n = _norm(therapy_area)
    matches: list[dict] = []
    for row in list_feedback(limit=200):
        if _norm(row.get("topic")) != topic_n:
            continue
        row_brand = _norm(row.get("brand"))
        row_ta = _norm(row.get("therapy_area"))
        if row_brand and brand_n and row_brand != brand_n:
            continue
        if row_ta and ta_n and row_ta != ta_n:
            continue
        matches.append(row)
        if len(matches) >= limit:
            break
    return matches


def feedback_guidance(topic: str, brand: str = "", therapy_area: str = "", limit: int = 5) -> str:
    rows = matching_feedback(topic, brand=brand, therapy_area=therapy_area, limit=limit)
    if not rows:
        return ""
    bullets = []
    for row in rows:
        expected = row.get("expected")
        detail = row.get("feedback") or ""
        if expected:
            detail = f"{detail} Expected correction: {expected}"
        bullets.append(f"- {detail}")
    return "Human extraction feedback to apply on future requests:\n" + "\n".join(bullets)
