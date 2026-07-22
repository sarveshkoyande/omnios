"""Standalone cognee-backed memory layer.

Separate from the app's existing stores (campaigns.db, brand_market_intel.json,
synthetic_personas.json, conversation.py slot state) -- this does not replace any of
them. It gives agents/back-end code an optional knowledge-graph memory: `remember()`
ingests free text, `recall()` answers a question against everything remembered so far.

LLM routing: this app has no plain Anthropic API key -- Claude is only reachable via an
Azure AI Foundry passthrough (see conversation_llm.py), authenticated with
AZURE_AI_FOUNDRY_API_KEY against a custom base_url. cognee's built-in "anthropic"
provider calls the raw `anthropic.AsyncAnthropic` SDK with no way to override its base
URL, so it always targets api.anthropic.com and cannot use a Foundry key. Its "custom"
provider (LLMProvider.CUSTOM -> GenericAPIAdapter) goes through litellm + instructor and
does honour a custom endpoint, so that's the provider this module configures.

Known issue (2026-07-15/16): the Foundry endpoint sometimes hangs on connect from this
network, and litellm/openai's client has no override for the hardcoded 600s HTTP
fallback timeout -- one grounding topic stalling for 10 minutes blocked a plan run (see
server_8733.log, 2026-07-15T10:29:20). A local-Ollama alternative was tried and reverted
same day: CPU-only inference on this machine was too slow/heavy for structured-output
calls (100% CPU, 300s+ per call even on a 1B model) and risked crashing the box, so it's
off the table until this machine has a GPU. Process-knowledge grounding is therefore
disabled by default (OMNI_PROCESS_GROUNDING=0 in .env) until one of these is fixed --
see process_knowledge.py's enabled() gate, which short-circuits before this module is
ever touched.

Embeddings: Claude/Foundry has no embedding endpoint, and there's no OpenAI key in this
app, so embeddings run locally via fastembed (all-MiniLM-L6-v2, 384-dim, no API key, no
network call).

Storage: local-only by default -- LanceDB (vector), NetworkX (graph), SQLite
(relational), all under a directory this module resolves itself. Vector/graph rows
cognee generates internally nest several UUID-named path segments deep; combined with a
long Windows dev path this can exceed MAX_PATH (260 chars) and fail with a LanceDB
"failed to persist temp file" / "os error 3" write error (verified while testing this
module). Production (Render) is Linux with no such limit, so only local Windows dev
needs the short-root workaround below.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import threading
from functools import lru_cache

from strategy.paths import DATA_DIR, ensure_data_dir

_REPO_DIR = pathlib.Path(__file__).resolve().parent.parent

# cognee's graph store (Ladybug) takes an EXCLUSIVE per-connection file lock, so two overlapping
# recalls in the same process collide with "Could not set lock" (OS error 33). This process-wide
# lock serialises graph access so concurrent plan runs queue instead of failing.
_GRAPH_LOCK = threading.Lock()


def _load_dotenv() -> None:
    """Load omni-data-hub/.env into os.environ (real env vars win).

    memory_cognee is used standalone (ingestion scripts, back-end recall) where
    conversation_llm's loader hasn't run, so the Foundry API key would otherwise be
    absent and cognee's LLM connection check fails with LLMAPIKeyNotSetError."""
    env_path = _REPO_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _foundry_llm_env() -> dict[str, str]:
    resource = os.environ.get("AZURE_AI_FOUNDRY_RESOURCE", "genai-demos-resource")
    deployment = os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "claude-sonnet-5")
    api_key = os.environ.get("AZURE_AI_FOUNDRY_API_KEY", "")
    return {
        "LLM_PROVIDER": "custom",
        "LLM_MODEL": f"anthropic/{deployment}",
        "LLM_ENDPOINT": f"https://{resource}.services.ai.azure.com/anthropic",
        "LLM_API_KEY": api_key,
    }


def _storage_roots() -> tuple[str, str]:
    """Where cognee keeps its local databases.

    Short root on Windows (drive root of DATA_DIR, e.g. "D:\\.omni_cognee") to stay
    under MAX_PATH; the normal data_path("cognee") location everywhere else.
    """
    if sys.platform == "win32":
        drive = DATA_DIR.drive or "C:"
        root = f"{drive}\\.omni_cognee"
    else:
        root = str(ensure_data_dir() / "cognee")
    return f"{root}/data", f"{root}/system"


@lru_cache(maxsize=1)
def configure() -> None:
    """Point cognee at this app's Foundry Claude deployment + local fastembed/LanceDB.

    Idempotent (lru_cache) -- safe to call before every remember()/recall(). Only sets
    variables that are not already set, so an operator's own cognee env config (e.g. in
    production) always wins.
    """
    _load_dotenv()
    data_root, system_root = _storage_roots()
    env_defaults = {
        **_foundry_llm_env(),
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "EMBEDDING_DIMENSIONS": "384",
        "DATA_ROOT_DIRECTORY": data_root,
        "SYSTEM_ROOT_DIRECTORY": system_root,
        # cognee 1.3 turns these on by default; the app uses a single local, single-user
        # graph, so disable multi-tenant access control (else search needs a user context)
        # and session caching (keeps recall() deterministic across processes).
        "ENABLE_BACKEND_ACCESS_CONTROL": "false",
        "CACHING": "false",
    }
    for key, value in env_defaults.items():
        os.environ.setdefault(key, value)


async def _graph_op_with_retry(op):
    """Run a graph coroutine factory under the process-wide lock, retrying briefly on the
    transient exclusive-lock error (OS error 33) so an ingest or recall that overlaps another
    (or a just-released connection) waits and succeeds instead of failing outright. Returns the
    op's result."""
    with _GRAPH_LOCK:
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                return await op()
            except Exception as exc:  # noqa: BLE001
                if "lock" not in str(exc).lower() and "error: 33" not in str(exc).lower():
                    raise
                last_exc = exc
                await asyncio.sleep(0.75 * (attempt + 1))
        raise last_exc  # type: ignore[misc]


async def remember(text: str) -> None:
    """Ingest a piece of text into the memory graph (add + cognify), serialised + lock-retried."""
    configure()
    import cognee

    async def _op():
        await cognee.add(text)
        await cognee.cognify()

    await _graph_op_with_retry(_op)


async def recall(query: str) -> list[str]:
    """Answer a question against everything remembered so far.

    Returns the list of search_result strings (empty if nothing relevant was found).
    """
    configure()
    import cognee

    # Serialise graph access and retry briefly on the transient exclusive-lock error, so a plan
    # run whose recall overlaps another (or a just-released ingestion) waits and succeeds rather
    # than losing its grounding. A persistent holder (e.g. a crashed process that never released
    # the lock) still surfaces after the retries, and the caller degrades to "no grounding".
    results = await _graph_op_with_retry(lambda: cognee.search(query_text=query))
    # cognee's search return shape has changed across versions: 1.3.0 yields a list of plain
    # strings; older builds yielded dicts carrying a "search_result" list. Handle both so a
    # cognee upgrade/downgrade doesn't silently return nothing.
    out: list[str] = []
    for row in results or []:
        if isinstance(row, str):
            if row.strip():
                out.append(row)
        elif isinstance(row, dict):
            sr = row.get("search_result")
            if isinstance(sr, list):
                out.extend(s for s in sr if isinstance(s, str) and s.strip())
            elif isinstance(sr, str) and sr.strip():
                out.append(sr)
        elif row is not None:
            out.append(str(row))
    return out


async def forget_all() -> None:
    """Wipe the memory graph and databases. Mainly for tests/local resets."""
    configure()
    import cognee

    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
