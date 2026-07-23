# Omni OS — User Guide

Corrected against the actual current code (the big `omnios-v2` UI redesign) —
not the older layout described in earlier drafts of this doc.

Omni OS is a pharma omnichannel campaign-planning tool. You describe a brand and
campaign in plain conversation, and an agent researches it, composes a Campaign
Strategy + Campaign Brief, then carries it through orchestration, execution
tracking, and reporting — all in one workspace.

## Opening the app

**http://127.0.0.1:8731/v2**. Top nav: **Home**, **Workspace**, **Artefacts**.

## 1. Home

- A **market-events ticker** scrolls across the top (real approvals/indications
  from your knowledge base, e.g. "Fabhalta gains C3 glomerulopathy indication").
- A greeting — **"Hi [you]! What's on your mind today?"** — sits above a
  **requirement box**: type a one-line campaign requirement, or drag in a
  brand-plan file (.pdf/.docx/.txt/.md), then click **New plan** (or **Import
  file**). Below it are 4 quick-start suggestion chips: *Launch a new brand*,
  *Refresh a mature brand*, *LOE defense plan*, *Patient-support push* — click
  one to prefill the box.
- Stat row: **Brands / Clients / Plans in flight / Campaigns / Content assets**.
- **AI summary** — a plain-English (non-LLM, data-derived) read of your
  portfolio's state.
- **Your plans** — every saved plan, bucketed into tabs by which stage it's
  currently sitting in: **Planning & Strategy / Engagement Orchestration /
  Campaign Operations / Reporting & Insights**. Click a plan card to reopen it.

## 2. Workspace

Landing here (via "New plan" or opening a saved plan) always opens straight
into the brief — no empty "click to begin" screen.

**Layout:** left = chat with the agent; right = the live build canvas. A top
sub-bar shows the plan's (editable) title and the 4 stage tabs — all 4 are
clickable at any time, nothing is gated.

### Giving the brief

- If you didn't already type a one-liner on Home, an **intake card** asks for
  it directly in chat (or upload a brand-plan file instead).
- The agent extracts brand / therapy area / lifecycle / budget from what you
  type, asking for whatever's still missing, one thing at a time.

### Stage 1 — Planning & Strategy: the Sequential Plan Studio

Once the brief is complete, the right pane becomes an **assembly canvas**: the
agent builds the plan **section by section**, each one appearing as it's
composed rather than all at once. A **Decision trail** panel underneath logs
*why* each call was made — which record/data point drove that section.

When the build finishes, the standing output is:
- **Campaign Strategy** — the decision-trail summary (how and why each call
  was made).
- **Campaign Brief** — the operational brief derived from it.

The older 30-section Brand Engagement Plan document still exists — it's
collapsed under **"Previous plan views (archived)"** below the Campaign
Brief, with a **"View full plan →"** toggle if you want it (editable inline:
click any heading/paragraph/table cell to revise it directly, and export as
Word/PDF from there).

You can also ask the agent to **pressure-test the plan** against synthetic HCP
personas matched to the brief's specialty.

### Stage 2 — Engagement Orchestration

*"The plan becomes activity: touchpoints, entry/exit criteria, decision logic,
segmentation and the tactical plan turned into a setup checklist you can
track."* Includes a journey-orchestration view and an activities/setup-tasks
checklist.

### Stage 3 — Campaign Operations

*"The orchestrated journey becomes an editable engagement diagram: start to
close, with decision-split branches, segment volume and content readiness at
every step."* This is a full drag-and-drop flow-builder (nodes for
send/wait/decision/exit steps, lanes, branching) you can edit directly.

### Stage 4 — Reporting & Insights

*"The closed-loop scorecard: which KPIs prove the plan worked, how each
channel is measured, and what to learn next."* Shows insights/read-outs, a KPI
scorecard, and a channel measurement framework.

## 3. Artefacts

A library view (replacing the old "Claims Library" nav item) of supporting
content and reference material tied to your brands/campaigns.

## Tips

- **Nothing is gated** — jump between any of the 4 stage tabs at any time.
- **Plans auto-save** — reopen any past plan from the plans menu (**⋮** next to
  the project title) or from Home's "Your plans" section.
- **AI is optional everywhere it appears** — brief-intake parsing degrades to a
  deterministic rules engine if no LLM key is configured; the research/plan
  pipeline itself never depends on one.
- For local dev setup, the Gemini key, and inspecting the backend database, see
  [LOCAL_DEV_GUIDE.md](LOCAL_DEV_GUIDE.md).
