"""Renders a brand kit as a "Brand Plan" PDF -- served at /api/brand-kits/{brand}/sample-pdf as a
sample brand-plan document, and also usable as a straight
"export this kit as PDF" feature later.

General renderer, not a fixed demo fixture: works off whatever fields the given kit
actually has, using the same "Not captured" honesty this session established elsewhere
in the cockpit UI -- a kit missing key_objective/market_share (e.g. Oncomyra) renders
those sections as not captured rather than inventing figures.

Builds a markdown document, then reuses strategy/plan_export.markdown_to_pdf() (the
same reportlab renderer the live plan's PDF export already falls back to) rather than
introducing a second PDF toolchain.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plan_export  # noqa: E402

_MISSING = "*Not captured in this kit yet.*"


def _fact_line(label: str, value) -> str:
    return f"- **{label}:** {value if value else _MISSING}"


def kit_to_markdown(kit: dict, brand: str) -> str:
    lines = [f"# {brand} -- Brand Plan", ""]
    lines.append(f"*Source: {kit.get('source_label', 'n/a')}*")
    lines.append("")

    lines.append("## Brand details")
    lines.append(_fact_line("Indication", kit.get("indication")))
    lines.append(_fact_line("Lifecycle stage", kit.get("fiscal_frame")))
    market_share = kit.get("market_share")
    lines.append(_fact_line(
        "Market share (current -> target)",
        f"{market_share['current']} -> {market_share['target']}" if market_share else None))
    lines.append(_fact_line("Key objective", kit.get("key_objective")))
    lines.append(_fact_line("Tagline", kit.get("tagline")))
    lines.append(_fact_line("Core claim", kit.get("core_claim")))
    lines.append(_fact_line("Positioning statement", kit.get("positioning_statement")))
    lines.append("")

    lines.append("## Brand persona")
    lines.append(_fact_line("Tone pillars", ", ".join(kit.get("tone_pillars") or []) or None))
    lines.append(_fact_line("Voice -- do", ", ".join(kit.get("voice_do") or []) or None))
    lines.append(_fact_line("Voice -- don't", ", ".join(kit.get("voice_dont") or []) or None))
    lines.append("")
    for m in kit.get("message_hierarchy", []):
        lines.append(f"- **{m.get('pillar')}:** {m.get('claim')} ({m.get('evidence')})")
    lines.append("")

    lines.append("## Guardrails")
    guardrails = kit.get("guardrails") or {}
    lines.append("**Do:**")
    for d in guardrails.get("dos", []):
        lines.append(f"- {d.get('category')}: {d.get('text')}")
    lines.append("")
    lines.append("**Don't:**")
    for d in guardrails.get("donts", []):
        lines.append(f"- {d.get('category')}: {d.get('text')}")
    lines.append("")

    lines.append("## HCP persona")
    for p in (kit.get("personas") or {}).get("hcp", []):
        lines.append(f"- **{p.get('name')}** ({p.get('tier')}): {p.get('who')} -- \"{p.get('voice')}\"")
    lines.append("")

    lines.append("## HCP segmentation")
    personas = kit.get("personas") or {}
    for group_label, key in (("Patient", "patient"), ("Payer", "payer")):
        for p in personas.get(key, []):
            lines.append(f"- **{group_label} -- {p.get('name')}:** {p.get('who')}")
    for c in kit.get("competitors", []):
        lines.append(f"- **Competitor -- {c.get('name')}:** {c.get('threat')} -- {c.get('detail')}")
    lines.append("")

    return "\n".join(lines)


def render_kit_pdf(kit: dict, brand: str) -> bytes:
    markdown = kit_to_markdown(kit, brand)
    return plan_export.markdown_to_pdf(markdown, title=f"{brand} -- Brand Plan")
