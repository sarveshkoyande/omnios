"""Knowledge-graph connector implementations. Backend is chosen at config time via
`OMNI_KG_BACKEND` (env/`.env`): "vault_path" (default), "cognee", "obsidian_rest", or "mcp".

- `VaultPathConnector` — reads the curated SME brain pack in `SME Knowledge/` directly off
  disk and keyword-scores it (deliberately scoped to that allowlisted set, not the whole vault,
  so recommendations never draw on legacy notes, product/tool docs or unrelated files). No
  prior ingestion step, no extra service, works out of the box; this is the default because it
  is the only backend that is always available.
- `CogneeGraphConnector` â€” wraps the existing `strategy/memory_cognee.py` recall() against
  the graph `strategy/ingest_process_knowledge.py` already populates. Reused, not
  rebuilt, per the brief. Requires that ingestion to have been run first, and is
  currently gated off by default in this repo (`OMNI_PROCESS_GROUNDING=0` in `.env`,
  see memory_cognee.py's docstring on why) â€” the factory below does not check that flag
  itself, so selecting this backend explicitly always attempts the graph.
- `ObsidianRestApiConnector` â€” talks to the Obsidian Local REST API plugin
  (https://github.com/coddingtonbear/obsidian-local-rest-api) over HTTPS on the machine
  running Obsidian. Implemented against its documented `/search/simple/` endpoint. Not
  exercised in this environment (no Local REST API server was running here at build
  time) â€” wire `OBSIDIAN_REST_API_URL` / `OBSIDIAN_REST_API_KEY` and select this backend
  to use it for real.
- `McpObsidianConnector` â€” the seam for an MCP-server-backed vault connector. Left
  unimplemented (raises `NotImplementedError`): this app has no MCP client dependency
  today, and which MCP Obsidian server to target is a choice for whoever wires it, not
  something to guess. Selecting "mcp" fails loudly rather than silently no-op-ing.
"""
from __future__ import annotations

import os
import re
import threading

from strategy.paths import BASE_DIR
from strategy.planning_v2.connectors.base import KGResult, KnowledgeGraphConnector


def _load_dotenv() -> None:
    """Same minimal loader as conversation_llm.py/memory_cognee.py: shell env vars set in
    one terminal don't reach a server process started from a different shell, so `.env` is
    the one mechanism that reliably reaches this module however it's imported/used. Real
    env vars always win (only fills in what's not already set)."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

VAULT_DIR = BASE_DIR.parent / "SME Knowledge"  # curated SME-only folder, one level above the repo checkout
CURATED_DOCS = {
    "OMNICHANNEL-PRIMER.md",
    "00-index-and-governance.md",
    "04-planning-method-S0-S11.md",
    "05-segmentation-and-targeting.md",
    "06-message-and-behavior-science.md",
    "07-channel-playbook.md",
    "08-content-supply-chain-and-MLR-ops.md",
    "09-measurement-and-attribution.md",
    "13-campaign-brief-and-journey-BRD-anatomy.md",
}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")


class VaultPathConnector(KnowledgeGraphConnector):
    """Direct keyword search over the curated SME brain pack only â€” deliberately excludes
    legacy notes in `SME Knowledge/` plus the rest of the Obsidian vault (product/tool docs,
    app-version notes, navigation scaffolding) so grounding never mixes in non-SME content.
    No index is built or cached â€” the allowlisted pack is small enough that a fresh scan per
    query is fast and always reflects the latest edits."""

    def __init__(self, vault_dir=None):
        self.vault_dir = vault_dir or VAULT_DIR

    def query(self, text: str, top_k: int = 5) -> list[KGResult]:
        terms = {w.lower() for w in _WORD_RE.findall(text)}
        if not terms:
            return []
        scored: list[tuple[float, KGResult]] = []
        for path in self.vault_dir.glob("*.md"):
            if path.name not in CURATED_DOCS:
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lower = body.lower()
            score = sum(lower.count(t) for t in terms)
            if score <= 0:
                continue
            snippet = _snippet(body, lower, terms)
            scored.append((float(score), KGResult(
                note_title=path.stem, link=str(path), snippet=snippet, score=float(score),
            )))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [r for _, r in scored[:top_k]]


def _snippet(body: str, lower: str, terms: set[str], width: int = 280) -> str:
    pos = min((lower.find(t) for t in terms if lower.find(t) >= 0), default=-1)
    if pos < 0:
        return body[:width].strip()
    start = max(0, pos - width // 3)
    return body[start:start + width].strip()


class CogneeGraphConnector(KnowledgeGraphConnector):
    """Wraps `strategy/memory_cognee.recall()`. Note-level attribution is best-effort:
    each ingested doc is prefixed with a `# ... source: <file>.md` header
    (`ingest_process_knowledge.py`'s `_doc_payload`), which survives into a hit's text
    only when the returned chunk happens to include it â€” cognee's raw search results
    carry no structured note metadata, so a hit missing that header is labeled
    "(cognee graph, source note not identified in chunk)" rather than guessed."""

    _SOURCE_RE = re.compile(r"source:\s*([^\n]+\.md)", re.IGNORECASE)

    def query(self, text: str, top_k: int = 5) -> list[KGResult]:
        from strategy import memory_cognee

        hits = _run_async(memory_cognee.recall(text))
        results: list[KGResult] = []
        for hit in hits[:top_k]:
            m = self._SOURCE_RE.search(hit)
            title = m.group(1).strip() if m else "(cognee graph, source note not identified in chunk)"
            results.append(KGResult(note_title=title, link="", snippet=hit[:400], score=None))
        return results


class ObsidianRestApiConnector(KnowledgeGraphConnector):
    """Obsidian Local REST API plugin backend. Docs:
    https://github.com/coddingtonbear/obsidian-local-rest-api â€” the plugin serves a
    self-signed HTTPS endpoint (default https://127.0.0.1:27124) and requires a bearer
    API key generated in Obsidian's plugin settings."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.environ.get("OBSIDIAN_REST_API_URL", "https://127.0.0.1:27124")).rstrip("/")
        self.api_key = api_key or os.environ.get("OBSIDIAN_REST_API_KEY", "")

    def query(self, text: str, top_k: int = 5) -> list[KGResult]:
        import requests

        if not self.api_key:
            raise RuntimeError(
                "ObsidianRestApiConnector selected but OBSIDIAN_REST_API_KEY is not set â€” "
                "generate one in Obsidian's Local REST API plugin settings and set it in .env."
            )
        resp = requests.post(
            f"{self.base_url}/search/simple/",
            params={"query": text, "contextLength": 200},
            headers={"Authorization": f"Bearer {self.api_key}"},
            verify=False,  # the plugin's cert is self-signed by design; see its docs
            timeout=8,
        )
        resp.raise_for_status()
        rows = resp.json() if resp.content else []
        results: list[KGResult] = []
        for row in rows[:top_k]:
            matches = row.get("matches") or []
            snippet = matches[0].get("context", "") if matches else ""
            results.append(KGResult(
                note_title=(row.get("filename") or "").rsplit("/", 1)[-1].removesuffix(".md"),
                link=row.get("filename", ""),
                snippet=snippet,
                score=row.get("score"),
            ))
        return results


class McpObsidianConnector(KnowledgeGraphConnector):
    """Seam for an MCP-server-backed vault connector. Not wired: this backend requires
    choosing a specific MCP Obsidian server and adding an MCP client dependency, both of
    which are deployment decisions for whoever enables this mode, not something to
    default silently. Selecting "mcp" without wiring one fails loudly here rather than
    returning an empty result set that would look like "no notes found"."""

    def query(self, text: str, top_k: int = 5) -> list[KGResult]:
        raise NotImplementedError(
            "OMNI_KG_BACKEND=mcp selected but no MCP client is wired yet. "
            "Implement this connector against your chosen MCP Obsidian server, or "
            "switch OMNI_KG_BACKEND to 'vault_path', 'cognee', or 'obsidian_rest'."
        )


def _run_async(coro):
    """Run an async coroutine from sync code whether or not this thread already has a
    running event loop (same pattern as `strategy/process_knowledge.py`'s `_run_async`)."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict = {}

    def _worker():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001 - re-raised on the calling thread below
            result["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


_BACKENDS = {
    "vault_path": VaultPathConnector,
    "cognee": CogneeGraphConnector,
    "obsidian_rest": ObsidianRestApiConnector,
    "mcp": McpObsidianConnector,
}


def get_kg_connector(backend: str | None = None) -> KnowledgeGraphConnector:
    """Factory: `backend` explicit arg > `OMNI_KG_BACKEND` env/.env > "vault_path"."""
    name = (backend or os.environ.get("OMNI_KG_BACKEND") or "vault_path").strip().lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"Unknown OMNI_KG_BACKEND '{name}' â€” choose one of {sorted(_BACKENDS)}")
    return cls()




