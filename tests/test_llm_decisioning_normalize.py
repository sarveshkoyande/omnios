import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategy"))

import llm_decisioning  # noqa: E402


def test_normalize_ask_payload_removes_blank_recommendations_and_options():
    draft = {
        "ask_id": "ask-1",
        "section": 1,
        "question_focus": "Confirm the program placement.",
        "text": "",
        "evidence_basis": "Draft basis",
        "why": "Draft why",
        "recommendation": {"label": "Net-new journey", "source": "grounded default"},
        "options": [{"label": "Extension of an existing program", "source": "grounded alternative"}],
        "free_text": True,
    }
    malformed = {
        "text": "Is this a new journey?",
        "recommendation": {"label": "", "source": ""},
        "options": [{"label": "", "source": ""}, {"label": "  ", "source": "blank"}],
        "free_text": True,
    }

    ask = llm_decisioning._normalize_ask_payload(malformed, draft, {"ask": "program"})

    assert ask["recommendation"]["label"] == "Net-new journey"
    assert ask["recommendation"]["source"] == "grounded default"
    assert ask["options"] == []
    assert ask["text"] == "Is this a new journey?"
