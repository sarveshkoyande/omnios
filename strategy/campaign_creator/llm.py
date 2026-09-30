"""Model access for the Campaign Planner, on OmniOS's own LLM client.

Camille made two kinds of calls through a LiteLLM gateway (gpt-5):
  * JSON calls (index.js `azureChatJSON`, OpenAI json_object mode) for the Campaign
    Consultant's analysis / questions / assumptions / briefing / update.
  * Streamed calls (reasoningEngine.js `_streamHelper`) for the blueprint agents: a free-text
    thinking block, then a `---JSON_START---` line, then one JSON object, streamed to the UI
    as it arrives.

Providers, in order:
  1. Camille's own gateway -- any OpenAI-compatible /chat/completions endpoint, set with
     LITELLM_BASE_URL + LITELLM_API_KEY (the names in Camille's backend/.env) and
     LITELLM_MODEL (else AZURE_OPENAI_MODEL, else "gpt-5"). Called exactly as Camille called
     it: streamed, max_completion_tokens, json_object mode on the JSON calls. Only this
     planner uses it; the rest of OmniOS keeps its own provider.
  2. `strategy.conversation_llm`: Claude on Azure AI Foundry, else Gemini.
Gateway and Foundry calls stream, so long outputs never hit a non-streaming size guard and the
agents' reasoning reaches the browser as it is written. The Gemini path has no streaming, so its
whole reply arrives as one chunk. Camille's JSON recovery is ported for every provider: fence
stripping, balanced-bracket extraction, and repair of a reply truncated by the token limit --
plus one model round-trip to fix a reply that still won't parse.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import time
from typing import Callable

from strategy import conversation_llm  # importing it loads the repo's .env

# Camille used max_completion_tokens 16384. gpt-5 spends hidden reasoning tokens out of that
# same budget, so a large diagram or spec was cut off mid-JSON and lost (a 75-node journey
# diagram, in testing). 32768 is within every provider's output limit (gpt-5, Claude, Gemini 2.5).
MAX_TOKENS = 32768


def truncated(usage: dict | None) -> bool:
    """True when a reply stopped at the output limit (each provider's name for it)."""
    return str((usage or {}).get("stopReason") or "").lower() in ("length", "max_tokens", "max_output_tokens")

JSON_ONLY_SYSTEM = ("Respond with exactly one valid JSON object and nothing else: no markdown, no code "
                    "fences, no commentary before or after it.")

_REPAIR_SYSTEM = ("You are a JSON repair tool. The user message is text that was meant to be one JSON "
                  "object but does not parse. Return only the corrected JSON object: keep every key and "
                  "value you can, close anything left open, and add nothing new.")

_SEPARATOR = re.compile(r"-{2,}\s*JSON_START\s*-{2,}")


class LLMUnavailable(RuntimeError):
    """No LLM provider is configured."""


class Cancelled(RuntimeError):
    """The job this call belongs to was cancelled mid-stream."""


def _gateway() -> tuple[str, str, str] | None:
    """(base_url, api_key, model) of Camille's gateway, when configured."""
    base = os.environ.get("LITELLM_BASE_URL", "").strip()
    key = os.environ.get("LITELLM_API_KEY", "").strip()
    if not (base and key):
        return None
    model = (os.environ.get("LITELLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or "gpt-5").strip()
    return base.rstrip("/"), key, model


def provider() -> str | None:
    if _gateway():
        return "gateway"
    p = conversation_llm.active_provider()
    if p == "gemini" and importlib.util.find_spec("litellm") is None:
        return None  # a Gemini key without litellm installed can't be called
    return p


def available() -> bool:
    return provider() is not None


def engine_label() -> str:
    p = provider()
    if p == "gateway":
        return f"{_gateway()[2]} via the LLM gateway"
    if p == "azure-foundry":
        return f"Claude via Azure AI Foundry ({conversation_llm.MODEL})"
    if p == "gemini":
        return f"Gemini ({conversation_llm.GEMINI_MODEL})"
    return "Rules only (no AI model configured)"


def _usage(inp: int, out: int, stop: str | None = None) -> dict:
    return {"inputTokens": inp, "outputTokens": out, "totalTokenCount": inp + out, "stopReason": stop}


def _gateway_complete(prompt: str, system: str | None, max_tokens: int, json_mode: bool,
                      on_chunk: Callable[[str], None] | None,
                      should_stop: Callable[[], bool] | None) -> tuple[str, dict]:
    """Camille's calls: an agent's (with `on_chunk`) streams over SSE like
    reasoningEngine._streamHelper; a JSON call is one request like azureChatJSON."""
    import httpx
    base, key, model = _gateway()
    body: dict = {"model": model, "max_completion_tokens": max_tokens,
                  "messages": ([{"role": "system", "content": system}] if system else [])
                  + [{"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}"}
    # A reasoning model can think for minutes before its first token.
    timeout = httpx.Timeout(connect=30, read=600, write=60, pool=30)
    if on_chunk is None:
        resp = httpx.post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM gateway returned HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if should_stop and should_stop():
            raise Cancelled("cancelled")
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return ((choice.get("message") or {}).get("content") or "",
                _usage(int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0),
                       choice.get("finish_reason")))
    body.update(stream=True, stream_options={"include_usage": True})
    parts: list[str] = []
    usage = {}
    finish = None
    with httpx.stream("POST", f"{base}/chat/completions", json=body, timeout=timeout, headers=headers) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise RuntimeError(f"LLM gateway returned HTTP {resp.status_code}: {resp.text[:300]}")
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if isinstance(ev.get("error"), dict):
                raise RuntimeError(f"LLM gateway error: {str(ev['error'].get('message'))[:300]}")
            if ev.get("usage"):
                usage = ev["usage"]
            for choice in ev.get("choices") or []:
                finish = choice.get("finish_reason") or finish
                text = (choice.get("delta") or {}).get("content") or ""
                if text:
                    parts.append(text)
                    if on_chunk:
                        on_chunk(text)
            if should_stop and should_stop():
                raise Cancelled("cancelled")
    return "".join(parts), _usage(int(usage.get("prompt_tokens") or 0),
                                  int(usage.get("completion_tokens") or 0), finish)


def complete(prompt: str, *, system: str | None = None, max_tokens: int = MAX_TOKENS,
             on_chunk: Callable[[str], None] | None = None,
             should_stop: Callable[[], bool] | None = None,
             json_mode: bool = False) -> tuple[str, dict]:
    """One model call. Returns (text, usage). `on_chunk` receives text as it streams;
    `should_stop` is polled between chunks and raises Cancelled when it returns True.
    `json_mode` asks the gateway for a JSON object, as Camille did (other providers rely on
    the prompt and JSON recovery)."""
    p = provider()
    if p == "gateway":
        return _gateway_complete(prompt, system, max_tokens, json_mode, on_chunk, should_stop)
    if p == "azure-foundry":
        client = conversation_llm._get_client()
        kwargs: dict = {"model": conversation_llm.MODEL, "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        parts: list[str] = []
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if not text:
                    continue
                parts.append(text)
                if on_chunk:
                    on_chunk(text)
                if should_stop and should_stop():
                    raise Cancelled("cancelled")
            final = stream.get_final_message()
        usage = getattr(final, "usage", None)
        return "".join(parts), _usage(int(getattr(usage, "input_tokens", 0) or 0),
                                      int(getattr(usage, "output_tokens", 0) or 0),
                                      getattr(final, "stop_reason", None))
    if p == "gemini":
        import litellm
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        # Gemini 2.5 counts hidden "thinking" against max_tokens, which truncates long JSON
        # replies; these are structured-output calls, so thinking is off (as in llm_json.py).
        resp = litellm.completion(model=conversation_llm.GEMINI_MODEL, api_key=conversation_llm._gemini_key(),
                                  max_tokens=max_tokens, reasoning_effort="disable", messages=msgs)
        text = resp.choices[0].message.content or ""
        if on_chunk and text:
            on_chunk(text)
        usage = getattr(resp, "usage", None)
        return text, _usage(int(getattr(usage, "prompt_tokens", 0) or 0),
                            int(getattr(usage, "completion_tokens", 0) or 0),
                            getattr(resp.choices[0], "finish_reason", None))
    raise LLMUnavailable("No LLM is configured.")


# ------------------------------------------------------------------ JSON recovery -------

def _strip_fences(raw: str) -> str:
    """Camille: drop ```json markers and a closing fence; a leading bare fence too."""
    text = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    text = re.sub(r"^\s*```[A-Za-z]*\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()


def _repair_truncated(s: str) -> str:
    """Camille's auto-repair of a reply cut off by the token limit: drop a partial string,
    dangling separators and a key left without a value, then close every open bracket."""
    in_str = esc = False
    last_quote = -1
    for i, c in enumerate(s):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            if in_str:
                last_quote = i
    if in_str and last_quote >= 0:
        s = s[:last_quote]
    for _ in range(6):
        s = s.rstrip()
        if s.endswith(","):
            s = s[:-1]
            continue
        if s.endswith(":"):
            s = s[:-1].rstrip()
            if s.endswith('"'):
                j = s.rfind('"', 0, len(s) - 1)
                if j >= 0:
                    s = s[:j]
            continue
        break
    stack: list[str] = []
    in_str = esc = False
    for c in s:
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            stack.append("}")
        elif c == "[":
            stack.append("]")
        elif c in "}]" and stack and stack[-1] == c:
            stack.pop()
    return s + "".join(reversed(stack))


def _fix_brackets(s: str) -> str:
    """Swap a closing bracket that doesn't match what it closes (a list opened with "[" and
    closed with "}"): a one-character model slip that otherwise loses the whole reply (a Technical
    Writer reply, in testing). Not in Camille."""
    out = list(s)
    stack: list[str] = []
    in_str = esc = False
    for i, c in enumerate(s):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c in "{[":
            stack.append("}" if c == "{" else "]")
        elif c in "}]" and stack:
            want = stack.pop()
            if c != want:
                out[i] = want
    return "".join(out)


def extract_json(raw: str):
    """The first balanced JSON object/array in `raw` (Camille's extractBracketJson), then with
    mismatched brackets fixed, then the truncated-JSON repair as a last resort. None when
    nothing usable is found."""
    if not raw:
        return None
    clean = _strip_fences(raw)
    start = -1
    for i, c in enumerate(clean):
        if c in "{[":
            start = i
            break
    if start < 0:
        return None
    clean = clean[start:]
    depth = 0
    in_str = esc = False
    end = -1
    for i, c in enumerate(clean):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                end = i
                break
    candidate = clean[:end + 1] if end > 0 else clean
    fixed = _fix_brackets(candidate)
    for attempt in (candidate, fixed, _repair_truncated(fixed)):
        try:
            return json.loads(attempt, strict=False)
        except (ValueError, TypeError):
            continue
    return None


def parse_json_text(text: str):
    """A reply that should be pure JSON: direct parse first, then recovery."""
    try:
        return json.loads(_strip_fences(text), strict=False)
    except (ValueError, TypeError):
        return extract_json(text)


def split_reasoning(full_text: str) -> tuple[str, object]:
    """An agent reply: (thinking text, parsed JSON or None). Camille's _streamHelper: the part
    after the JSON_START separator first, then the whole reply as a fallback."""
    parts = _SEPARATOR.split(full_text, maxsplit=1)
    parsed = extract_json(parts[1]) if len(parts) > 1 else None
    if parsed is None:
        parsed = extract_json(full_text)
    return parts[0].strip(), parsed


def _with_retry(prompt: str, **kwargs) -> tuple[str, dict]:
    """complete(), retried once after a failed call (e.g. the gateway dropping its upstream
    connection), so one network hiccup doesn't send a step to its fallback. Not in Camille."""
    try:
        return complete(prompt, **kwargs)
    except (Cancelled, LLMUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 -- the second failure propagates to the caller's fallback
        print(f"[campaign-creator] model call failed, retrying once: {exc}")
        time.sleep(2)
        return complete(prompt, **kwargs)


def complete_json(prompt: str, *, max_tokens: int = MAX_TOKENS,
                  should_stop: Callable[[], bool] | None = None,
                  system: str | None = None) -> tuple[dict, dict]:
    """A JSON-returning call: (object, usage). `system` replaces the default JSON-only system
    prompt (the Segmentation Planner sends Camille's own). One model round-trip repairs a reply
    that still won't parse; ValueError when it can't be made into a JSON object."""
    text, usage = _with_retry(prompt, system=system or JSON_ONLY_SYSTEM, max_tokens=max_tokens,
                              should_stop=should_stop, json_mode=True)
    parsed = parse_json_text(text)
    if isinstance(parsed, dict):
        return parsed, usage
    fixed_text, fix_usage = complete(text[:60000], system=_REPAIR_SYSTEM, max_tokens=max_tokens,
                                     should_stop=should_stop, json_mode=True)
    fixed = parse_json_text(fixed_text)
    total = dict(usage)
    for k in ("inputTokens", "outputTokens", "totalTokenCount"):
        total[k] = int(usage.get(k) or 0) + int(fix_usage.get(k) or 0)
    if isinstance(fixed, dict):
        return fixed, total
    raise ValueError("The model's reply was not valid JSON.")
