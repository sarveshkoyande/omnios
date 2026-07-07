# Omni Data Hub

Local knowledge repository + campaign strategy generator, built to accompany
[[Omni OS — Campaign Planning & Strategy Deep Dive]].

## What's here

- `scrapers/` — pulls real data from five public, keyless APIs (DailyMed, openFDA,
  ClinicalTrials.gov, PubMed, Google Trends) into `data/raw/<source>/` (local
  "S3-style" bucket/key files) and indexes it into `data/omni_kb.db` (SQLite).
- `config/seed_terms.json` — the drug/therapy-area list the scrapers run against.
  Edit this to broaden or refresh the knowledge base.
- `strategy/` — `rules.py` encodes the five-tenet / journey-stage / channel-mix
  framework from the deep-dive doc; `engine.py`, `positioning.py`, `kpi.py`,
  `lifecycle.py` combine it with live KB lookups. The agentic layer:
  `conversation.py` (chat slot-filling — extracts brand/therapy/lifecycle/budget
  from free text; deterministic, no LLM key needed; single seam `interpret_message`
  for a future LLM swap), `orchestrator.py` (streams the 9 research agents and
  composes the campaign-plan doc), `projects.py` (project persistence in
  `data/projects.db`), `autorun.py` (legacy one-shot pipeline).
- `competitive/` — `discovery.py` auto-finds competitors from ClinicalTrials.gov;
  `metrics.py` + `swot.py` build the comparative SWOT and positioning table.
- `app/` — FastAPI backend (`server.py`) + a single-page front-end
  (`static/index.html`): a **three-pane agentic console** — saved plans (left),
  chat with the planning agent (centre), live agent workspace + campaign plan (right).
- `Omni OS — Data Sources & Planning Phases.xlsx` (in the vault root) — static
  reference workbook: data sources by planning phase, the five tenets, the
  6-stage HCP journey, the touchpoint catalogue, and a live tab showing what's
  currently in the knowledge repository.

## Running it

```powershell
# one-time setup
python -m pip install requests openpyxl fastapi "uvicorn[standard]" pytrends pydantic

# (re-)seed the knowledge repository from the public APIs
cd omni-data-hub\scrapers
python run_all.py

# rebuild the Excel reference workbook (picks up latest KB stats)
python build_excel_reference.py

# start the agentic planning console
cd ..
python -m uvicorn app.server:app --host 127.0.0.1 --port 8731
```

Then open **http://127.0.0.1:8731** in a browser. Click **+ New**, then just talk
to the agent — tell it the brand, therapy area, and where the brand is in its
lifecycle (it asks for whatever you leave out). It captures the brief on the
right, runs its research agents live (market landscape, competitor discovery,
segmentation/journey, SWOT, positioning, channel mix/budget, KPIs), and composes
a downloadable **campaign-plan document**. Everything is grounded in real data
pulled from the local knowledge repository (clinical trials, FDA label, PubMed
literature,
Google Trends interest).

## Notes on what's real vs. illustrative

- The knowledge-repository documents (trial records, FDA labels, PubMed
  articles, DailyMed SPLs, Google Trends series) are **real, live-fetched
  data** — not synthetic.
- The **channel-mix percentages** the strategy engine outputs are an
  illustrative starting allocation synthesized from the stage/persona
  framework in the deep-dive doc — not measured MMx output. Replace with real
  spend/response data once available (see §6 of the deep-dive doc on
  MMx vs. NBA).
- YouTube and Reddit were left out of the scrapers because both require API
  credentials this environment doesn't have. Add a `youtube.py` / `reddit.py`
  scraper following the same pattern as the others if/when keys are available.

## Corporate proxy note

If a scraper fails with `SSL: CERTIFICATE_VERIFY_FAILED`, it's almost always
the corporate network's TLS-inspecting proxy. Fix: `pip install
pip-system-certs`, which makes Python trust the Windows certificate store
(where IT already installed the proxy's root CA) instead of only the
`certifi` bundle. Already applied in this environment.
