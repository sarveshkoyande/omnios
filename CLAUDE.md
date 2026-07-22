---
type: Concept
title: CLAUDE
timestamp: 2026-07-18T09:52:26Z
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Omni OS" — a pharma omnichannel-activation campaign planning tool. FastAPI backend
(`app/server.py` + `strategy/*.py`) that runs a multi-agent pipeline to compose a Brand
Engagement Plan, plus a separate React/Vite/MUI frontend (`frontend/`) that's built and
served as static assets by the same FastAPI app.

## ⚠️ Root-level contamination — read this first

This directory's root also contains an unrelated `create-next-app` + Prisma scaffold
(`app/layout.tsx`, `app/page.tsx`, `app/favicon.ico`, `app/globals.css`, `app/posts/`,
`prisma/`, `lib/`, `public/`, plus root-level `package.json` (`"name": "nextjs"`),
`package-lock.json`, `next.config.ts`, `tailwind.config.ts`, `postcss.config.mjs`,
`eslint.config.mjs`, `prisma.config.ts`, `.gitignore`, `README.md`). None of it is part of
this app — don't read the root `README.md` or root `.gitignore` for guidance (they're the
generic Next.js/Prisma boilerplate text), don't run `npm install`/`npm run dev` from the
repo root, and don't touch `db/schema.prisma`. The real app's `app/` directory is
`app/server.py` + `app/static/`; the real frontend lives entirely under `frontend/` with
its own `package.json`.

This directory is **not a git repository**. The version-controlled, deployed copy is a
separate sibling checkout (`OmniOS`, remote `github.com/shaswata-bhowmick/OmniOS`) whose
`main` branch auto-deploys to Render. Changes made here exist only locally until you
explicitly copy the relevant files over and commit/push from that other checkout — treat
this one as the working/superset environment, not the source of truth for what's live.

## Commands

**Backend** (from repo root):
- Install: `pip install -r requirements.txt`
- Run dev server: `.\restart-server-tmp.ps1` — kills any existing `uvicorn app.server:app`
  process on port 8731 and relaunches with `--reload`, blocking until the port answers.
  Equivalent manual command: `python -m uvicorn app.server:app --host 127.0.0.1 --port 8731 --reload`.
  **Gotcha**: on Windows, `--reload`'s multiprocessing worker process can outlive the
  supervisor process the restart script kills (it matches on command line, and the worker's
  command line doesn't contain `uvicorn`/`app.server:app`). If a restart seems to succeed but
  code changes aren't reflected, check what's actually bound to the port before trusting it:
  `Get-NetTCPConnection -LocalPort 8731 -State Listen` → `Get-CimInstance Win32_Process
  -Filter "ProcessId=<pid>"` — kill that PID directly if it's a stale `multiprocessing.spawn`
  process, then restart.
- Syntax-check a changed file without running it: `python -m py_compile <path>`.
- No test suite exists in this codebase (no pytest config, no test files) — don't invent one.
- No Python lint config exists.

**Frontend** (from `frontend/`):
- Dev server: `npm run dev` (Vite)
- Typecheck only: `npx tsc -b --noEmit`
- Production build: `npm run build` (`tsc -b && vite build`) — **outputs directly into
  `../app/static/v2`** per `vite.config.ts`'s `outDir` (not `frontend/dist`), and clears
  stale hashed bundle files on each build. There is no separate copy step. The backend does
  not auto-reload static assets, so after a frontend build you must restart the server for
  the new bundle to be served.
- No frontend test runner or lint script is configured (`package.json` has only
  `dev`/`build`/`preview`).

## Architecture

**Two runtimes glued together.** `app/server.py` is a single large FastAPI file: every
route lives there (no routers/blueprints split), importing business logic from `strategy/*`
modules. The frontend is an independent Vite SPA that gets built to static files and served
by the same process (`StaticFiles` mount at `/static`, plus explicit page routes like `/`,
`/v2`, `/legacy`, `/hcp360`). There's no API versioning or separate deploy for the two.

**Data layer**: `strategy/paths.py` is the single seam for where data lives — `DATA_DIR`
resolves to `OMNI_DATA_DIR` (env var or `.env`) or `<repo>/data`, gitignored. Every store is
its own flat SQLite file under `DATA_DIR` (`projects.db`, `campaigns.db`, `hcp_360.db`,
`tab_chat.db`, `brand_memory.db`, ...) opened directly via `sqlite3` — there is no shared
connection pool or ORM. `strategy/db.py` is a **drafted, not-yet-wired-in** dual-dialect
SQLite/Postgres translation layer (see its own docstring and `POSTGRES_MIGRATION.md`); every
store still talks to `sqlite3` directly today. On Render, `DATA_DIR` is a persistent disk
(`render.yaml`) — without it, every deploy wipes all SQLite data, which is why
`strategy/bootstrap.py` runs on FastAPI startup (`server.py`'s `@app.on_event("startup")`)
to idempotently reseed an empty `DATA_DIR` from committed inputs (`assets/seed/`,
`config/*.json`). A store that seeds itself from committed JSON follows the same repeated
pattern: a `load_x()` function that's a no-op if data already exists, upserting from
`config/*.json` into its own table(s) — see `strategy/brand_lifecycle.py`, `strategy/hcp_360.py`.

**Multi-agent plan orchestration** (`strategy/orchestrator.py`): five named agents
(`AGENT_ROSTER`: planner/intel/strategy/inspiration/activation) compose a Brand Engagement
Plan section-by-section, streamed as SSE events the frontend renders live. Two parallel
entry points share the same underlying `ctx` (brand/therapy_area/persona/... plus grounding
data computed once per run): `run_agents()` is the original phase-gated flow
(`PHASE_ORDER = align/select/create/deploy`, human approves each phase before the next
starts); `strategy/studio_run.py` is the newer "Sequential Plan Studio" — an 11-step
`SEQUENCE` with its own SSE v2 event shape (`phase_open`/`grounding`/`ask`/`section_html`/...),
each step owned by one agent. Grounding is additive and uniform: `ctx["process_grounding"]`,
`ctx["external_evidence"]`, `ctx["audience_profile"]`, `ctx["hcp_360_grounding"]`, etc. are
computed once and rendered into an agent's bullets via `_agent_grounding_bullets()` +
`_AGENT_TOPICS` in `orchestrator.py` (classic flow) or `grounding_items()` in `studio_run.py`
(Studio flow) — a new grounding source needs wiring into **both**.

**Campaign Operations / flow-builder**: `strategy/campaign_ops.py` builds an initial flat
`CampaignFlow` (node types `send`/`wait`/`decision`/`exit`/`followup`/`closure`). The
frontend converts that once into a general-purpose `WorkflowDocument` (Zod schemas under
`frontend/src/workspace/stages/operations/flowbuilder/schema/` — a full node/edge/group/
layer graph spec, not campaign-specific) and every edit after that is persisted as a **full
document overwrite** via `PATCH /api/projects/{pid}/campaign-plan-layout` — there is no
partial-patch protocol, and no path back from `WorkflowDocument` to `CampaignFlow`.

**Per-tab chat + agent identity**: `frontend/src/workspace/types.ts`'s `STAGE_AGENTS` names
one agent persona per workspace tab (planning/orchestration/operations/reporting).
`strategy/tab_chat.py` is the backend counterpart — a dedicated SQLite-backed chat history
per `(project_id, stage_id)`, independent of the plan-run's own streamed narration (which
stays in `strategy/projects.py`'s flat `messages` column). The `operations` tab's agent can
read and rewrite the live `WorkflowDocument` (LLM asked for a strict JSON envelope
`{reply, document}`, `document` validated against a Python port of a subset of the
frontend's flowchart validation rules before being persisted) — this is the only agent with
write access to app state; the other three are grounded read-only Q&A.

**LLM access**: `strategy/conversation_llm.py` wraps `anthropic.AnthropicFoundry` (Azure AI
Foundry passthrough — set `AZURE_AI_FOUNDRY_RESOURCE`/`AZURE_AI_FOUNDRY_DEPLOYMENT`/
`AZURE_AI_FOUNDRY_API_KEY`, *not* a direct Anthropic API key). Every LLM call site follows
the same resilience idiom: attempt the call, catch broadly, fall back to a deterministic/
rules-based path — the app must degrade gracefully (rules engine only), never hard-fail,
when the LLM is unavailable or misconfigured.

**Design tokens**: `frontend/src/theme/tokens.ts` is the literal single source of truth for
color/spacing/radius (`frontend/src/theme/theme.ts` derives the MUI theme from it, nothing
else should hardcode raw hex/rgba). `DESIGN_BRIEF.md` documents the intended "light liquid
glass" visual language but can drift out of sync with the actual token values — treat
`tokens.ts` as authoritative over the brief's example hex codes. A few color maps are
**deliberately not** token-driven because they're functional multi-hue legends, not brand
decoration — don't fold these into the brand palette without being asked:
`frontend/src/workspace/planDocSkinCss.ts` (4-color toolkit-phase legend), and the
flow-builder's per-category node/lane colors (`flowbuilder/nodes/styleDefaults.ts`'s
`CATEGORY_COLORS`, `flowbuilder/canvas/LaneNode.tsx`'s `KIND_COLOR`).
