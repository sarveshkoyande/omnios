"""Ingest the Obsidian "SME Knowledge" process/methodology docs into the cognee knowledge layer.

This is the loader that populates the graph memory `memory_cognee.recall()` reads from, so
every agent stage in the planning pipeline can ground its section in the firm's own documented
process (the value chain, the four-phase toolkit, the BAM/CX methodology, the engagement
benchmarks, client brand intelligence, real client uploads, ...) instead of only the
deterministic defaults baked into code.

Source of truth is the vault's curated SME Knowledge set (ONE level above this repo, then into
that subfolder) -- deliberately separated from the rest of the Obsidian vault (product/tool docs,
app-version notes, navigation scaffolding like index.md/log.md/kb_full.md) so agent grounding
never mixes in non-SME content. This loader only ingests the curated allowlist in that set;
legacy notes in the folder are ignored.

The current curated pack is the `brainV2` set: `OMNICHANNEL-PRIMER.md`, `00-index-and-governance.md`,
`04-planning-method-S0-S11.md`, `05-segmentation-and-targeting.md`, `06-message-and-behavior-science.md`,
`07-channel-playbook.md`, `08-content-supply-chain-and-MLR-ops.md`, `09-measurement-and-attribution.md`,
and `13-campaign-brief-and-journey-BRD-anatomy.md`. `--exclude-master` is retained for compatibility
and simply skips the primer in this curated pack.

Usage (from omni-data-hub/):
    python -m strategy.ingest_process_knowledge --dry-run        # estimate chunks/cost, ingest nothing
    python -m strategy.ingest_process_knowledge                  # fresh ingest of every process doc
    python -m strategy.ingest_process_knowledge --exclude-master # skip the 730KB master doc
    python -m strategy.ingest_process_knowledge --append         # add to the existing graph (no prune)
    python -m strategy.ingest_process_knowledge --verify-only    # just run the recall probes
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import memory_cognee  # noqa: E402

VAULT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "SME Knowledge"  # <vault>/SME Knowledge
CURATED_DOCS = [
    "OMNICHANNEL-PRIMER.md",
    "00-index-and-governance.md",
    "04-planning-method-S0-S11.md",
    "05-segmentation-and-targeting.md",
    "06-message-and-behavior-science.md",
    "07-channel-playbook.md",
    "08-content-supply-chain-and-MLR-ops.md",
    "09-measurement-and-attribution.md",
    "13-campaign-brief-and-journey-BRD-anatomy.md",
]

# Probes run after ingestion to prove the graph answers real process questions (not just that
# text went in). Each should be answerable ONLY from the ingested docs.
VERIFY_QUERIES = [
    "What are the four phases of the omnichannel campaign toolkit and their order?",
    "What is a BAM chart and how is it used in campaign planning?",
    "How should channels be selected for a target customer group?",
    "What engagement benchmarks does the process use for HCP digital channels?",
]


def discover_docs(exclude_master: bool = False) -> list[pathlib.Path]:
    """Curated allowlist in the vault's `SME Knowledge/` folder, sorted largest-last.

    Legacy notes in the folder are intentionally ignored so grounding stays on the new
    SME brain pack. `--exclude-master` is kept for compatibility and skips the primer
    when requested."""
    allow = [VAULT_DIR / name for name in CURATED_DOCS if (VAULT_DIR / name).exists()]
    if exclude_master:
        allow = [p for p in allow if p.name != "OMNICHANNEL-PRIMER.md"]
    return sorted(allow, key=lambda p: p.stat().st_size)


def _doc_payload(path: pathlib.Path) -> str:
    """The note's text, prefixed with a stable provenance header so recalled snippets can be
    attributed back to a source doc and so the graph links content to its originating note."""
    text = path.read_text(encoding="utf-8")
    return f"# Omni OS process knowledge — source: {path.name}\n\n{text}"


def _estimate(path: pathlib.Path) -> tuple[int, int]:
    """(approx tokens, approx chunks) for a doc. ~4 chars/token, cognee's default ~1024-token
    chunk. Rough by design -- just to size a run before paying for it."""
    chars = path.stat().st_size
    tokens = chars // 4
    return tokens, max(1, tokens // 1024)


def dry_run(exclude_master: bool) -> None:
    docs = discover_docs(exclude_master)
    print(f"Vault: {VAULT_DIR}")
    print(f"Docs to ingest: {len(docs)} (exclude_master={exclude_master})\n")
    tot_tok = tot_chunk = 0
    for p in docs:
        tok, chunk = _estimate(p)
        tot_tok += tok
        tot_chunk += chunk
        print(f"  {p.stat().st_size/1024:8.1f} KB  ~{tok:>7,} tok  ~{chunk:>4} chunks   {p.name}")
    print(f"\n  TOTAL ~{tot_tok:,} tokens, ~{tot_chunk} chunks "
          f"(≈{tot_chunk} Foundry extraction calls at cognify time).")


async def ingest(exclude_master: bool = False, fresh: bool = True, throttle: float = 2.0) -> None:
    """Ingest each doc as its own add+cognify pass rather than one big cognify at the end.

    Why per-doc: the Foundry deployment enforces a tokens-per-minute limit, and cognify fans
    every ~1K-token chunk out to the LLM concurrently for entity/graph extraction. One cognify
    over the ~730KB master doc (183 chunks) bursts straight through the limit and drops chunks.
    Cognifying doc-by-doc (cognify is incremental — it only processes newly-added data) keeps
    each burst small, throttles between docs, and — crucially — isolates failures so a single
    doc that still trips the limit doesn't take the other nine down with it. Each doc's success/
    failure is reported at the end.
    """
    docs = discover_docs(exclude_master)
    if not docs:
        print("No 'Omni OS *.md' docs found in", VAULT_DIR)
        return
    memory_cognee.configure()
    # Ask cognee to self-limit LLM request bursts (belt-and-suspenders alongside per-doc pacing).
    os.environ.setdefault("LLM_RATE_LIMIT_ENABLED", "true")
    os.environ.setdefault("LLM_RATE_LIMIT_REQUESTS", "30")
    os.environ.setdefault("LLM_RATE_LIMIT_INTERVAL_SECONDS", "60")
    if fresh:
        print("Pruning existing knowledge graph (fresh ingest)...", flush=True)
        await memory_cognee.forget_all()

    import cognee  # configured by memory_cognee.configure()

    t0 = time.time()
    ok: list[str] = []
    failed: list[tuple[str, str]] = []
    for i, path in enumerate(docs, 1):
        payload = _doc_payload(path)
        print(f"[{i}/{len(docs)}] {path.name} ({len(payload)/1024:.1f} KB) — add + cognify...", flush=True)
        try:
            await cognee.add(payload)
            await cognee.cognify()
            ok.append(path.name)
            print(f"    [ok] done ({time.time()-t0:.0f}s elapsed)", flush=True)
        except Exception as exc:  # noqa: BLE001 - isolate one doc's failure from the rest
            failed.append((path.name, str(exc)[:200]))
            print(f"    [FAIL] (continuing): {str(exc)[:200]}", flush=True)
        if i < len(docs) and throttle:
            await asyncio.sleep(throttle)  # let the per-minute token budget refill between docs

    print(f"\nIngestion finished in {time.time()-t0:.0f}s -- {len(ok)} ok, {len(failed)} failed.", flush=True)
    for name, err in failed:
        print(f"  [FAIL] {name}: {err}", flush=True)


async def verify() -> None:
    print("\n--- recall probes ---", flush=True)
    for q in VERIFY_QUERIES:
        hits = await memory_cognee.recall(q)
        head = hits[0][:400] if hits else "(no result)"
        print(f"\nQ: {q}\n   hits={len(hits)}  ->  {head}", flush=True)


def main() -> None:
    # Force UTF-8 stdout so progress markers (arrows, check marks) don't crash with a
    # UnicodeEncodeError when this script's output is redirected to a file on Windows (the
    # console's default cp1252 codec can't encode them).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - older stream types; ASCII-safe fallbacks below cover it
            pass

    ap = argparse.ArgumentParser(description="Ingest Omni OS process docs into cognee.")
    ap.add_argument("--dry-run", action="store_true", help="estimate size only; ingest nothing")
    ap.add_argument("--exclude-master", action="store_true", help="skip the ~730KB master doc")
    ap.add_argument("--append", action="store_true", help="add to the existing graph (no prune)")
    ap.add_argument("--verify-only", action="store_true", help="run recall probes without ingesting")
    args = ap.parse_args()

    if args.dry_run:
        dry_run(args.exclude_master)
        return
    if args.verify_only:
        asyncio.run(verify())
        return
    asyncio.run(ingest(exclude_master=args.exclude_master, fresh=not args.append))
    asyncio.run(verify())


if __name__ == "__main__":
    main()
