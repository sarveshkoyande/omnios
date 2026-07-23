# Local dev guide — running Omni OS + Gemini fallback + inspecting the database

This is a personal working guide for the `llm-gemini-fallback` branch, running locally
only (nothing here is pushed to GitHub yet).

## 1. Start the app

From the repo root (`C:\Users\Admin\Desktop\omnios`):

```powershell
python -m uvicorn app.server:app --host 127.0.0.1 --port 8731
```

Open **http://127.0.0.1:8731/v2** in a browser.

If you changed frontend code (`frontend/src/...`), rebuild first — the backend doesn't
auto-serve new frontend code, and Vite doesn't run in dev mode against this backend:

```powershell
cd frontend
npm run build
cd ..
```

Then restart uvicorn (Ctrl+C, rerun the command above) so it picks up any Python changes
too — `--reload` isn't used here, so nothing hot-reloads.

## 2. Set your Gemini key (one-time)

Edit `.env` at the repo root (already gitignored, never pushed):

```
GEMINI_API_KEY=your-key-here
```

Get a key at https://aistudio.google.com/apikey. Restart uvicorn after changing `.env` —
it's only read once, at process startup.

**Provider priority**, decided automatically, no toggle needed:
1. `GEMINI_API_KEY` set → uses Gemini
2. else `AZURE_AI_FOUNDRY_API_KEY` set → uses Claude via Azure Foundry
3. else → deterministic rules engine (no AI)

## 3. Use the app

1. Click **Workspace** in the top nav.
2. Click **+ New plan**.
3. Type a message describing a campaign — **use a brand name that is NOT "Oncomyra"**
   (Oncomyra is the one demo brand hardcoded to always use the deterministic rules path,
   regardless of which LLM is configured — good for a fast no-AI demo, bad for testing Gemini).

   Example:
   > planning a launch for a drug called Vestrolin in cystic fibrosis, budget 2 million

4. The agent will extract brand / therapy area / lifecycle / budget from your message
   (via Gemini) and ask for whatever's still missing, one thing at a time.
5. Once all fields are captured, it kicks off the multi-agent research run (Stage 1 —
   deterministic, no LLM involved) and composes the Brand Engagement Plan.
6. Stage tabs across the top (Planning & Strategy → Engagement Orchestration → Campaign
   Operations → Reporting & Insights) unlock once Stage 1 finishes.

## 4. Confirm which engine answered a message

Two ways:

- **Console** — the terminal running uvicorn prints a line on every successful LLM turn:
  ```
  [conversation] Gemini answered this turn.
  ```
  (or `Claude (via Microsoft Foundry) answered this turn.` if using Foundry). On failure it
  prints why, and falls back to rules automatically — chat never breaks.

- **API directly** — call `/api/chat` yourself and check `llm_status` in the response:
  ```powershell
  curl http://127.0.0.1:8731/api/chat -X POST -H "Content-Type: application/json" `
    -d '{"project_id":"<id>","message":"your message"}'
  ```
  Look for:
  ```json
  "llm_status": { "engine": "gemini", "ok": true, "detail": "Gemini answered this turn." }
  ```

## 5. Inspect the backend database tables (in browser)

A small read-only DB viewer is included (`scripts/db_viewer.py`, not part of the app,
safe to delete anytime). Start it:

```powershell
python scripts/db_viewer.py
```

Then open **http://127.0.0.1:8899/** in a browser.

- Click a database name at the top (e.g. `projects.db`) to see its tables + row counts.
- Click a table name to see its schema (columns) and first 200 rows.
- Fully read-only — nothing you click can modify data.

**The databases**, all SQLite files under `data/`:

| File | What it stores |
|---|---|
| `projects.db` | Every planning project — chat history, captured slots, the composed plan, campaign-ops layout |
| `omni_kb.db` | Scraped knowledge base (ClinicalTrials.gov, PubMed, openFDA, DailyMed, Google Trends) |
| `campaigns.db` | Campaign/content model — brands, segments, messages, claims, content assets, KPIs |
| `brand_memory.db` | Per-brand memory of previously captured chat answers |
| `hcp_360.db` | HCP demographics, channel/content affinity, TRx history, day/time preference |

(Cognee's own grounding store lives at `data/cognee/` — not a plain SQLite file, not
shown in the viewer.)

## 6. Cleaning up test data

Projects created while testing show up in `projects.db` → `projects` table. To delete one:

```powershell
python -c "from strategy import projects as pstore; pstore.delete_project('PROJECT_ID_HERE')"
```

## 7. Current branch state

- `main` — up to date with GitHub as of the last pull.
- `llm-gemini-fallback` — rebased on top of latest `main`. Contains only the
  Gemini-priority LLM change. **Not pushed to GitHub yet** — stays local until you say so.
