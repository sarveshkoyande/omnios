"""LLM-backed implementation of the conversation seam.

Three-tier fallback, cheapest/most-preferred first:
  1. Gemini, via `litellm` (GEMINI_API_KEY or GOOGLE_API_KEY env var) -- lets a dev use their
     own Gemini key instead of needing the team's Azure credential.
  2. Claude through **Microsoft Foundry (Azure AI)** -- the original path, auth via a plain
     API key (preferred) or Azure AD (`DefaultAzureCredential`) as a fallback.
  3. Neither configured -> conversation.py falls back to the deterministic rules engine.

Same return contract as the rules engine regardless of provider:
`interpret_message_llm(message, state) -> (state, reply, action)` with action 'ask' | 'run'.
Any failure here is caught by conversation.py, which falls back to the rules-based path and
records why in `get_llm_status()` -- so a missing/expired credential never breaks chat, it
just shows up as a fallback in the UI.

Credentials are read from a local `.env` file (gitignored) FIRST, falling back to real
process environment variables. This is deliberate: shell environment variables set via
`$env:` or `setx` in one terminal do not reach a server process started from a different
shell/process tree (e.g. a fresh automation-tool shell) -- a `.env` file is the one
mechanism that reliably reaches the app no matter which shell launches it.
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


def _load_dotenv() -> None:
    """Minimal, dependency-free .env loader. Only fills in vars not already set in the
    real environment, so a genuine env var always takes priority over the file."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


# --- Gemini config (tier 1) ---------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini/gemini-2.5-flash")


def _gemini_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


# --- Azure Foundry config (tier 2) ---------------------------------------------------------
# The AnthropicFoundry client builds the correctly-versioned endpoint itself from just the
# Azure resource name (`resource=`) -- it resolves to https://<resource>.services.ai.azure.com/anthropic/.
# Passing a hand-built `base_url` (e.g. an Azure AI Foundry *project* endpoint like
# ".../api/projects/<name>") skips that and 400s with "Missing required query parameter:
# api-version", because that URL shape is for the separate Azure AI Foundry Agents/Projects API,
# not the Anthropic-compatible passthrough this app talks to.
RESOURCE = os.environ.get("AZURE_AI_FOUNDRY_RESOURCE", "genai-demos-resource")
ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT")  # optional full override; usually unset
MODEL = os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "claude-sonnet-5")
API_KEY_ENV = "AZURE_AI_FOUNDRY_API_KEY"
SCOPE = "https://ai.azure.com/.default"
# Some Azure Foundry deployments require an explicit `?api-version=` query parameter on the
# Anthropic passthrough and otherwise 400 with "Missing required query parameter: api-version".
# The SDK's resource= path does NOT add one (anthropic/lib/foundry.py builds a bare
# .../anthropic/ base_url), so if a deployment needs it, set AZURE_AI_FOUNDRY_API_VERSION in
# .env and it is injected on every request via default_query. Unset = current working default
# (no api-version), so this is a no-op unless a deployment actually demands the parameter.
API_VERSION = os.environ.get("AZURE_AI_FOUNDRY_API_VERSION", "").strip()

_SYSTEM = f"""You are the intake agent for a pharmaceutical omnichannel campaign-planning tool.
Your job is to hold a short, warm, professional conversation that collects exactly four things,
then hand off to a team of research agents.

Collect:
1. brand: the brand / molecule the campaign is for (a real product; never invent one).
2. therapy_area: the therapy area / indication (a real clinical fact; never guess it).
3. lifecycle_key: where the brand is in its product lifecycle, mapped to ONE of:
   "launch" (just launching / pre-launch / newly approved),
   "growth" (gaining traction / scaling uptake),
   "mature" (established, in-line, defending share),
   "loe" (loss of exclusivity / patent cliff / generic erosion / decline).
4. budget: OPTIONAL total campaign budget in US dollars as a number (0 if none / skipped).

Rules of the conversation:
- Lead the conversation. Ask for whatever is still missing, ONE thing at a time, in the order
  brand -> therapy_area -> lifecycle -> budget.
- Extract multiple slots at once if the user front-loads them in a single message.
- If the user defers a required fact ("you decide", "not sure", "your call") for brand or therapy area,
  do NOT invent a value: gently explain it's their real product/indication and re-ask.
- Ask about budget only once. If they give a number use it; if they skip, set budget 0 and move on.
- Never ask about their current omnichannel/SFMC/tagging maturity directly -- but if the user volunteers
  something about it unprompted (e.g. "we don't have SFMC yet", "we already have a tagging system"), copy
  that sentence verbatim into maturity_notes. Leave maturity_notes empty otherwise.
- Set ready=true ONLY when brand, therapy_area and lifecycle_key are all known AND you have either a
  budget or the user has been asked about budget and skipped it.
- When ready=true, write a brief confirmation reply summarizing the locked-in brief (brand, therapy
  area, lifecycle, budget) and say your agent is starting its research now. Refer to a single agent
  ("I", "my agent") -- never "agents" or "the team", there is exactly one.
- Keep replies to 1-3 short sentences. You may use **bold** for the captured values.

Known example brands (for grounding only; the user may name any): {', '.join(KNOWN_BRANDS)}.
Known example therapy areas: {', '.join(KNOWN_THERAPIES)}.

You will receive a JSON object with what's known so far and the new user message. Respond with
ONLY a single raw JSON object matching this exact shape -- no markdown code fences, no prose
before or after it:
{{"brand": string, "therapy_area": string, "lifecycle_key": "launch"|"growth"|"mature"|"loe"|"",
"budget": number, "budget_asked": boolean, "maturity_notes": string, "ready": boolean, "reply": string}}"""

class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _AnthropicShapedResponse:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _GeminiClient:
    """Drop-in stand-in for the AnthropicFoundry client, shaped so every one of this app's
    ~11 call sites (all written as `client.messages.create(model=..., system=..., messages=[...])`
    then `resp.content[i].text`) works completely unchanged when Gemini is the active provider
    -- `model=` is ignored in favor of GEMINI_MODEL, everything else is translated 1:1."""

    class _Messages:
        def create(self, model=None, max_tokens: int = 700, system: str | None = None,
                    messages: list[dict] | None = None, **_ignored):
            import litellm
            msgs = ([{"role": "system", "content": system}] if system else []) + list(messages or [])
            resp = litellm.completion(model=GEMINI_MODEL, api_key=_gemini_key(), max_tokens=max_tokens, messages=msgs)
            return _AnthropicShapedResponse(resp.choices[0].message.content)

    messages = _Messages()


_client = None  # lazily built + cached Foundry client; cleared on construction failure so a later retry can succeed


def _get_client():
    """Build (and cache) the LLM client every call site in this app uses.

    Returns a Gemini-backed shim if GEMINI_API_KEY/GOOGLE_API_KEY is set (same priority as
    active_provider()/interpret_message_llm()) -- so setting a personal Gemini key covers
    every AI-assisted feature in the app, not just the conversational intake seam.

    Otherwise builds (and caches) the AnthropicFoundry client. Prefers a plain API key
    (AZURE_AI_FOUNDRY_API_KEY) -- no azure-identity or Azure AD round-trip needed, which is
    what a platform like Render can set as a single secret. Falls back to Azure AD
    (DefaultAzureCredential) only if no key is configured, for environments that use a
    service principal / managed identity instead.
    """
    if _gemini_key():
        return _GeminiClient()

    global _client
    if _client is not None:
        return _client
    from anthropic import AnthropicFoundry

    api_key = os.environ.get(API_KEY_ENV)
    # Prefer `resource=` -- the SDK derives the URL from it. Only pass `base_url=` when the
    # user explicitly set a full override via AZURE_AI_FOUNDRY_ENDPOINT.
    location_kwargs = {"base_url": ENDPOINT} if ENDPOINT else {"resource": RESOURCE}
    # Inject api-version only if configured (see API_VERSION note above); harmless when unset.
    if API_VERSION:
        location_kwargs["default_query"] = {"api-version": API_VERSION}
    try:
        if api_key:
            _client = AnthropicFoundry(api_key=api_key, **location_kwargs)
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), SCOPE)
            _client = AnthropicFoundry(azure_ad_token_provider=token_provider, **location_kwargs)
        return _client
    except Exception:
        _client = None
        raise


def _foundry_configured() -> bool:
    if not (ENDPOINT or RESOURCE):
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


def active_provider() -> str | None:
    """Which provider a call to interpret_message_llm() would use right now, in priority
    order, or None if nothing is configured (conversation.py then uses the rules engine)."""
    if _gemini_key():
        return "gemini"
    if _foundry_configured():
        return "azure-foundry"
    return None


def llm_available() -> bool:
    """True when *some* provider (Gemini key, or Azure Foundry key/identity) is configured
    to attempt with. This does NOT guarantee the credential actually authenticates -- that's
    only known at call time (bad key, expired token, no `az login`). Real success/failure of
    the last attempt is reported by conversation.get_llm_status()."""
    return active_provider() is not None


def _parse_json_reply(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return json.loads(text.strip())


def _call_gemini(payload: dict) -> str:
    import litellm
    resp = litellm.completion(
        model=GEMINI_MODEL,
        api_key=_gemini_key(),
        max_tokens=700,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    return resp.choices[0].message.content


def _call_foundry(payload: dict) -> str:
    client = _get_client()
    # NOTE: output_config.format (native structured outputs) is not enabled on every Azure AI
    # Foundry workspace -- it 400s there with "structured_outputs not supported in your
    # workspace." Falling back to plain-JSON-in-the-system-prompt works everywhere, at the
    # cost of needing to defensively strip markdown fences the model may still wrap it in.
    resp = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    return next(b.text for b in resp.content if b.type == "text")


def interpret_message_llm(message: str, state: dict) -> tuple[dict, str, str]:
    slots = state["slots"]
    payload = {
        "known_so_far": {
            "brand": slots["brand"],
            "therapy_area": slots["therapy_area"],
            "lifecycle_key": slots["lifecycle_key"],
            "budget": slots["budget"],
            "maturity_notes": slots.get("maturity_notes", ""),
        },
        "budget_already_asked": bool(state.get("budget_asked", False)),
        "user_message": message,
    }

    provider = active_provider()
    if provider == "gemini":
        raw_text = _call_gemini(payload)
    elif provider == "azure-foundry":
        raw_text = _call_foundry(payload)
    else:
        raise RuntimeError("no LLM provider configured")
    data = _parse_json_reply(raw_text)

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
    if data.get("maturity_notes"):
        slots["maturity_notes"] = data["maturity_notes"].strip()[-500:]

    reply = data.get("reply") or "Could you tell me the brand and therapy area you're planning for?"
    ready = bool(data.get("ready")) and slots["brand"] and slots["therapy_area"] and slots["lifecycle_key"]

    if ready:
        state["awaiting"] = None
        state["phase"] = "running"
        return state, reply, "run"

    state["awaiting"] = None
    return state, reply, "ask"
