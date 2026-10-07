"""Shared intake for the step-by-step agents: the documents a person drops (brand plan, briefs, research)
and the notes they type, kept per agent + key under DATA_DIR/agent_intake/ (local only: brand plans are
confidential), plus the shared "Here's what I've got" acknowledgement.

The acknowledgement is model-only (rule R1): the agent reads what was given -- or notices nothing was --
and says plainly what's available, what's missing and how it will proceed. No model -> LLMUnavailable.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from document_intake import extract_text  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402
from paths import data_path  # noqa: E402

MAX_TEXT = 60000

ACK_SHAPE = ('{"mode":"documents|notes|secondary","understood":"","have":[{"what":"","detail":""}],'
             '"missing":[{"what":"","impact":""}],"approach":[""],"question":""}')


def _path(agent: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{key}")
    return data_path("agent_intake", agent, f"{safe}.json")


def read_uploads(files: list[tuple[str, bytes]]) -> tuple[list[dict], str]:
    """Extract every file's text (PDF/DOCX/PPTX/TXT/MD), each under its own filename header."""
    meta, parts = [], []
    for name, content in files:
        text = extract_text(name, content, max_chars=MAX_TEXT)
        meta.append({"name": name, "chars": len(text)})
        parts.append(f"=== {name} ===\n{text}")
    return meta, "\n\n".join(parts)[:MAX_TEXT]


def save(agent: str, key: str, files: list[dict], text: str, notes: str) -> dict:
    p = _path(agent, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"files": files, "text": text, "notes": notes, "saved_at": datetime.now().isoformat(timespec="seconds")}
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return {"files": files, "has_notes": bool(notes.strip())}


def load(agent: str, key: str) -> dict:
    p = _path(agent, key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"files": [], "text": "", "notes": ""}


def acknowledge(role: str, context: dict, intake: dict, extra_instructions: str = "", extra_shape: str = "",
                max_tokens: int = 1800) -> dict:
    """The agent's first reply: what it understood from the input, what it has, what it lacks, how it'll proceed."""
    shape = ACK_SHAPE if not extra_shape else ACK_SHAPE[:-1] + "," + extra_shape + "}"
    return complete_json(
        role + " Before doing any work, read what the person provided -- uploaded documents and/or typed notes; "
        "either may be empty -- together with the context you already have. Reply to the person in plain words: "
        "what you understood; what is available -- BOTH what the person gave (name each document) AND what the "
        "context already provides (e.g. each Brand Compass section or campaign input that is present), one item each; "
        "what is missing and what that means for the result; and how you'll proceed. If nothing was provided, say you'll work from secondary "
        "sources and Brand Compass only, and that drafts will be marked to confirm. Never invent facts. "
        + extra_instructions + " Reply with one JSON object.\nShape: " + shape,
        {"documents": [f["name"] for f in intake.get("files") or []], "document_text": (intake.get("text") or "")[:20000],
         "notes": intake.get("notes") or "", "context": context}, max_tokens=max_tokens)


__all__ = ["read_uploads", "save", "load", "acknowledge", "LLMUnavailable"]
