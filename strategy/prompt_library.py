"""Read-only catalog of this app's LLM system prompts / agent "skills", for the in-app
Prompt Library viewer (temporary nav tab). Every entry pulls its ACTUAL current text
straight from the running code via introspection -- never a copy-pasted snapshot, so it
can't drift out of sync with what the app really sends the model.

Two kinds of entry:
  - "prompt": a clean module-level string constant (the literal system prompt).
  - "function": no single top-level constant exists (the prompt is built inline, often with
    f-string interpolation) -- shows the whole function's source instead, which is just as
    revealing and equally guaranteed to be current.
"""
from __future__ import annotations

import importlib
import inspect
import pathlib
import sys

# Several strategy/ modules do a bare `import sibling_module` (relying on their own
# `sys.path.insert(0, <this dir>)`), which only works once something has put strategy/ on
# sys.path directly. app/server.py's import order normally does that; standing this module
# up on its own (e.g. a script) needs the same insert so those bare imports resolve too.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

REGISTRY: list[dict] = [
    {
        "id": "conversation-intake",
        "name": "Brief Intake Agent",
        "stage": "Planning & Strategy",
        "file": "strategy/conversation_llm.py",
        "blurb": "Extracts brand / therapy area / lifecycle / budget from free-text chat during Stage 1 intake.",
        "kind": "prompt", "module": "conversation_llm", "target": "_SYSTEM",
    },
    {
        "id": "orchestration-extra-tasks",
        "name": "Extra Tasks From Document",
        "stage": "Engagement Orchestration",
        "file": "strategy/orchestration_tasks.py",
        "blurb": "Turns a user's free-text note or uploaded document into additional setup/orchestration tasks.",
        "kind": "prompt", "module": "orchestration_tasks", "target": "_EXTRA_TASKS_SYSTEM",
    },
    {
        "id": "hcp360-ask",
        "name": "HCP 360 Panel Q&A Agent",
        "stage": "Planning & Strategy",
        "file": "strategy/hcp_360.py",
        "blurb": "Answers free-text questions about the HCP 360 dataset shown in the audience panel.",
        "kind": "prompt", "module": "hcp_360", "target": "_ASK_SYSTEM",
    },
    {
        "id": "tab-chat-operations",
        "name": "Campaign Operations Chat Agent",
        "stage": "Campaign Operations",
        "file": "strategy/tab_chat.py",
        "blurb": "Per-tab chat agent for Stage 3 -- can read and rewrite the live campaign flow document.",
        "kind": "prompt", "module": "tab_chat", "target": "_OPS_SYSTEM",
    },
    {
        "id": "tab-chat-orchestration",
        "name": "Engagement Orchestration Chat Agent",
        "stage": "Engagement Orchestration",
        "file": "strategy/tab_chat.py",
        "blurb": "Per-tab chat agent for Stage 2 -- grounded read-only Q&A over the orchestration plan.",
        "kind": "prompt", "module": "tab_chat", "target": "_ORCH_SYSTEM",
    },
    {
        "id": "tab-chat-generic",
        "name": "Generic Stage Chat Agent (template)",
        "stage": "Any",
        "file": "strategy/tab_chat.py",
        "blurb": "Fallback template used for any stage tab without a dedicated system prompt above.",
        "kind": "prompt", "module": "tab_chat", "target": "_GENERIC_SYSTEM",
    },
    {
        "id": "tab-chat-reporting",
        "name": "Reporting & Insights Chat Agent",
        "stage": "Reporting & Insights",
        "file": "strategy/tab_chat.py",
        "blurb": "Per-tab chat agent for Stage 4 -- grounded Q&A over the KPI scorecard and insights.",
        "kind": "prompt", "module": "tab_chat", "target": "_REPORTING_SYSTEM",
    },
    {
        "id": "campaign-ops-fill-detail",
        "name": "Campaign Ops: Fill Operational Detail",
        "stage": "Campaign Operations",
        "file": "strategy/campaign_ops.py",
        "blurb": "Builds the send/wait/decision copy for a campaign-flow node from segment + channel context.",
        "kind": "function", "module": "campaign_ops", "target": "_llm_fill_operational_detail",
    },
    {
        "id": "persona-review-narrative",
        "name": "Persona Review: HCP Narrative Voice",
        "stage": "Planning & Strategy",
        "file": "strategy/persona_review.py",
        "blurb": "Writes a synthetic HCP persona's first-person reaction to the plan, in their own voice.",
        "kind": "function", "module": "persona_review", "target": "_llm_narrative",
    },
    {
        "id": "tactical-source-sharpen",
        "name": "Strategic Source Extraction",
        "stage": "Planning & Strategy",
        "file": "strategy/tactical_source.py",
        "blurb": "Pulls CSFs, guardrails, evidence and positioning out of an uploaded strategic-plan document.",
        "kind": "function", "module": "tactical_source", "target": "_llm_sharpen",
    },
    {
        "id": "llm-decisioning-core",
        "name": "Sequential Studio: Section Decisioning Core",
        "stage": "Planning & Strategy",
        "file": "strategy/llm_decisioning.py",
        "blurb": "Shared JSON-mode call used by the Sequential Plan Studio's per-section \"ask\" rewrites; each caller supplies its own system text.",
        "kind": "function", "module": "llm_decisioning", "target": "_call_json",
    },
    {
        "id": "planning-v2-extract",
        "name": "Planning V2: Strategic Context Extraction",
        "stage": "Planning & Strategy",
        "file": "strategy/planning_v2/extract.py",
        "blurb": "Extracts structured strategic context from an ingested brand-plan document.",
        "kind": "function", "module": "planning_v2.extract", "target": "_call_llm",
    },
    {
        "id": "planning-v2-gap-analysis",
        "name": "Planning V2: Gap Analysis",
        "stage": "Planning & Strategy",
        "file": "strategy/planning_v2/gap_analysis.py",
        "blurb": "Identifies gaps between the strategic context and the enrichment bundle.",
        "kind": "function", "module": "planning_v2.gap_analysis", "target": "_call_llm",
    },
    {
        "id": "planning-v2-synthesize",
        "name": "Planning V2: Tactical Plan Synthesis",
        "stage": "Planning & Strategy",
        "file": "strategy/planning_v2/synthesize.py",
        "blurb": "Synthesizes the tactical plan and business-requirements brief from context + gaps.",
        "kind": "function", "module": "planning_v2.synthesize", "target": "_call_llm",
    },
]


def _load_entry(entry: dict) -> dict:
    mod = importlib.import_module(f"strategy.{entry['module']}")
    target = getattr(mod, entry["target"])
    text = target if entry["kind"] == "prompt" else inspect.getsource(target)
    return {**{k: v for k, v in entry.items() if k not in ("module", "target")}, "text": text}


def list_prompts() -> list[dict]:
    out = []
    for entry in REGISTRY:
        try:
            out.append(_load_entry(entry))
        except Exception as exc:  # noqa: BLE001 -- one bad entry shouldn't break the whole catalog
            out.append({**{k: v for k, v in entry.items() if k not in ("module", "target")},
                        "text": f"(could not load: {exc})"})
    return out
