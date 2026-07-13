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
does honour a custom endpoint, so that's the provider this module configures --
confirmed working end-to-end against the Foundry deployment (add -> cognify -> search).

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

import os
import sys
from functools import lru_cache

from strategy.paths import DATA_DIR, ensure_data_dir


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
    data_root, system_root = _storage_roots()
    env_defaults = {
        **_foundry_llm_env(),
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "EMBEDDING_DIMENSIONS": "384",
        "DATA_ROOT_DIRECTORY": data_root,
        "SYSTEM_ROOT_DIRECTORY": system_root,
    }
    for key, value in env_defaults.items():
        os.environ.setdefault(key, value)


async def remember(text: str) -> None:
    """Ingest a piece of text into the memory graph."""
    configure()
    import cognee

    await cognee.add(text)
    await cognee.cognify()


async def recall(query: str) -> list[str]:
    """Answer a question against everything remembered so far.

    Returns the list of search_result strings (empty if nothing relevant was found).
    """
    configure()
    import cognee

    results = await cognee.search(query_text=query)
    out: list[str] = []
    for row in results:
        out.extend(row.get("search_result") or [])
    return out


async def forget_all() -> None:
    """Wipe the memory graph and databases. Mainly for tests/local resets."""
    configure()
    import cognee

    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
