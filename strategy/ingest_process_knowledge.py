"""Ingest the Obsidian "Omni OS" process/methodology docs into the cognee knowledge layer.

This is the loader that populates the graph memory `memory_cognee.recall()` reads from, so
every agent stage in the planning pipeline can ground its section in the firm's own documented
process (the value chain, the four-phase toolkit, the BAM/CX methodology, the engagement
benchmarks, the data model, client brand intelligence, ...) instead of only the deterministic
defaults baked into code.

Source of truth is the Obsidian vault that sits ONE level above this repo -- the "Omni OS — *.md"
notes in `<vault>/`. Those are the curated process write-ups. Deliberately excluded:
  * kb_full.md          -- an image-carrying *duplicate* of the master doc (its own header says
                           "don't edit it directly"); ingesting it would double-weight that content.
  * index.md / log.md   -- navigation/scaffolding, not process knowledge.
The glob ("Omni OS *.md") already excludes those three by name; this is just why.

The master doc ("Omni OS — Omnichannel Activation & Campaign Transformation.md", ~730KB) is the
long-form founding-session write-up. It is a large share of total ingest cost (each ~1K-token
chunk is one Foundry entity-extraction call), so `--exclude-master` is offered for a fast, cheap
pass over just the methodology/playbook/benchmark notes.

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
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import memory_cognee  # noqa: E402

VAULT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent  # <vault>/Omnichannel Activation
MASTER_DOC = "Omni OS — Omnichannel Activation & Campaign Transformation.md"

# Probes run after ingestion to prove the graph answers real process questions (not just that
# text went in). Each should be answerable ONLY from the ingested docs.
VERIFY_QUERIES = [
    "What are the four phases of the omnichannel campaign toolkit and their order?",
    "What is a BAM chart and how is it used in campaign planning?",
    "How should channels be selected for a target customer group?",
    "What engagement benchmarks does the process use for HCP digital channels?",
]


def discover_docs(exclude_master: bool = False) -> list[pathlib.Path]:
    """Every curated 'Omni OS *.md' process note in the vault, largest last (so the run's
    heaviest doc is visibly the final step, and --exclude-master simply drops it)."""
    docs = sorted(VAULT_DIR.glob("Omni OS *.md"), key=lambda p: p.stat().st_size)
    if exclude_master:
        docs = [p for p in docs if p.name != MASTER_DOC]
    return docs


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
