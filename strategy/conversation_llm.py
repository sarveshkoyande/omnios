"""LLM-backed implementation of the conversation seam.

Talks to Claude through **Microsoft Foundry (Azure AI)**, not the plain Anthropic API --
auth is Azure AD (`DefaultAzureCredential`), not an API key. Same return contract as the
rules engine: `interpret_message_llm(message, state) -> (state, reply, action)` with
action 'ask' | 'run'. Any failure here is caught by conversation.py, which falls back to
the rules-based path and records why in `get_llm_status()` -- so a missing/expired Azure
credential never breaks chat, it just shows up as a fallback in the UI.
"""
from __future__ import annotations

import json
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
_seeds = json.loads((BASE_DIR / "config" / "seed_terms.json").read_text())
KNOWN_BRANDS = _seeds.get("drugs", [])
KNOWN_THERAPIES = _seeds.get("therapy_areas", [])
LIFECYCLE_KEYS = ["launch", "growth", "mature", "loe"]

ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT", "https://genai-demos-resource.services.ai.azure.com/anthropic")
MODEL = os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "claude-sonnet-5")
API_KEY_ENV = "AZURE_AI_FOUNDRY_API_KEY"
SCOPE = "https://ai.azure.com/.default"

_SYSTEM = f"""You are the intake agent for a pharmaceutical omnichannel campaign-planning tool.
Your job is to hold a short, warm, professional conversation that collects exactly four things,
then hand off to a team of research agents.

Collect:
1. brand — the brand / molecule the campaign is for (a real product; never invent one).
2. therapy_area — the therapy area / indication (a real clinical fact; never guess it).
3. lifecycle_key — where the brand is in its product lifecycle, mapped to ONE of:
   "launch" (just launching / pre-launch / newly approved),
   "growth" (gaining traction / scaling uptake),
   "mature" (established, in-line, defending share),
   "loe" (loss of exclusivity / patent cliff / generic erosion / decline).
4. budget — OPTIONAL total campaign budget in US dollars as a number (0 if none / skipped).

Rules of the conversation:
- Lead the conversation. Ask for whatever is still missing, ONE thing at a time, in the order
  brand -> therapy_area -> lifecycle -> budget.
- Extract multiple slots at once if the user front-loads them in a single message.
- If the user defers a required fact ("you decide", "not sure", "your call") for brand or therapy area,
  do NOT invent a value: gently explain it's their real product/indication and re-ask.
- Ask about budget only once. If they give a number use it; if they skip, set budget 0 and move on.
- Set ready=true ONLY when brand, therapy_area and lifecycle_key are all known AND you have either a
  budget or the user has been asked about budget and skipped it.
- When ready=true, write a brief confirmation reply summarizing the locked-in brief (brand, therapy
  area, lifecycle, budget) and say the research agents are starting now.
- Keep replies to 1-3 short sentences. You may use **bold** for the captured values.

Known example brands (for grounding only; the user may name any): {', '.join(KNOWN_BRANDS)}.
Known example therapy areas: {', '.join(KNOWN_THERAPIES)}.

You will receive a JSON object with what's known so far and the new user message. Respond with the
structured object only."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string"},
        "therapy_area": {"type": "string"},
        "lifecycle_key": {"type": "string", "enum": ["launch", "growth", "mature", "loe", ""]},
        "budget": {"type": "number"},
        "budget_asked": {"type": "boolean"},
        "ready": {"type": "boolean"},
        "reply": {"type": "string"},
    },
    "required": ["brand", "therapy_area", "lifecycle_key", "budget", "budget_asked", "ready", "reply"],
    "additionalProperties": False,
}

_client = None  # lazily built + cached; cleared on construction failure so a later retry can succeed


def _get_client():
    """Build (and cache) the AnthropicFoundry client.

    Prefers a plain API key (AZURE_AI_FOUNDRY_API_KEY) -- no azure-identity or Azure AD
    round-trip needed, which is what a platform like Render can set as a single secret.
    Falls back to Azure AD (DefaultAzureCredential) only if no key is configured, for
    environments that use a service principal / managed identity instead.
    """
    global _client
    if _client is not None:
        return _client
    from anthropic import AnthropicFoundry

    api_key = os.environ.get(API_KEY_ENV)
    try:
        if api_key:
            _client = AnthropicFoundry(api_key=api_key, base_url=ENDPOINT)
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), SCOPE)
            _client = AnthropicFoundry(azure_ad_token_provider=token_provider, base_url=ENDPOINT)
        return _client
    except Exception:
        _client = None
        raise


def llm_available() -> bool:
    """True when the SDK is importable, an endpoint is configured, and *some* credential
    (API key or Azure Identity) is present to attempt with.

    This does NOT guarantee the credential actually authenticates -- that's only known at
    call time (bad key, expired token, no `az login`). Real success/failure of the last
    attempt is reported by conversation.get_llm_status().
    """
    if not ENDPOINT:
        return False
    try:
        from anthropic import AnthropicFoundry  # noqa: F401
    except ImportError:
        return False
    if os.environ.get(API_KEY_ENV):
        return True
    try:
        from azure.identity import DefaultAzureCredential  # noqa: F401
        return True
    except ImportError:
        return False


def interpret_message_llm(message: str, state: dict) -> tuple[dict, str, str]:
    client = _get_client()
    slots = state["slots"]
    payload = {
        "known_so_far": {
            "brand": slots["brand"],
            "therapy_area": slots["therapy_area"],
            "lifecycle_key": slots["lifecycle_key"],
            "budget": slots["budget"],
        },
        "budget_already_asked": bool(state.get("budget_asked", False)),
        "user_message": message,
    }

    resp = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)

    # Merge results into state (never blank out an already-captured slot).
    if data.get("brand"):
        slots["brand"] = data["brand"].strip()
    if data.get("therapy_area"):
        slots["therapy_area"] = data["therapy_area"].strip()
    lc = (data.get("lifecycle_key") or "").lower().strip()
    if lc in LIFECYCLE_KEYS:
        slots["lifecycle_key"] = lc
    if data.get("budget"):
        try:
            slots["budget"] = float(data["budget"])
        except (TypeError, ValueError):
            pass
    if data.get("budget_asked"):
        state["budget_asked"] = True

    reply = data.get("reply") or "Could you tell me the brand and therapy area you're planning for?"
    ready = bool(data.get("ready")) and slots["brand"] and slots["therapy_area"] and slots["lifecycle_key"]

    if ready:
        state["awaiting"] = None
        state["phase"] = "running"
        return state, reply, "run"

    state["awaiting"] = None
    return state, reply, "ask"
