# Agentic Brand Journey — handoff (2026-09-24)

Plan: `docs/plans/2026-09-24-0629-feat-agentic-brand-journey-plan.md` (implementation-ready).
Branch: `feat/brand-plan-update-interface`.

## Where the run stopped

The autonomous pipeline (lfg) was paused after step 4 (code review), before applying review fixes.

- Done: plan, document review, all 8 units (U1-U8) built and committed, simplify pass applied.
- Verified: `python scripts/verify_brand_journey.py` 38/38; `cockpit/`: `npx tsc -b --noEmit`, `npm run lint`, `npm run build` clean; browser-verified F2 (new brand from a sentence), keep/undo/confirm, F3 (flow build + chat edit + keep + reload), workspace "Plan in <step>" links.
- Step 5 done (2026-09-24, follow-up session): findings 1-4 applied; `verify_brand_journey.py` now 41/41
  (adds flow-turn LLM success + invalid-op fallback, and re-upload-does-not-stack checks) and seeds a
  Cardiovex fixture into its temp kit copy so it passes on a fresh checkout. `cockpit/tsconfig.app.json`
  excludes the parked `DispatchBoard.tsx`, whose `../gate` import was never committed.
- Not done: residual record (6), browser test pass (7); push + PR (8) opened from `claude/gallant-edison-m28ax4`; CI watch (9).
- Finding 1 note: a stale turn reply still applies its journey snapshot (so rail draft counts stay right)
  but no longer writes into the new step's chat.

## Review findings to apply next (step 5)

1. P1 — `cockpit/src/components/journey/JourneyScreen.tsx` `sendTurn`: switching steps while a turn is in flight lets the old step's reply overwrite the new step's chat. Fix: guard the continuation with a step ref / request id bumped by `goTo`; skip `setState`/`setTurn` when stale.
2. P1 — `scripts/verify_brand_journey.py`: no check drives `flow_turn`'s LLM-success path. Add a check patching `_llm_on` true and `_call_flow_llm` to return canned `{reply, ops}`; assert `mode == "llm"` and the draft; plus an invalid-op case that degrades to fallback.
3. P2 — `strategy/brand_journey.py` `apply_document` (~line 493): re-uploading a document stacks duplicate pending drafts. Fix: compare against `_effective_answers(b)` (kept + pending) instead of `answers_for(b)`, or clear existing pending set-mode drafts for the same field first.
4. P2 — `strategy/kit_chat.py`: `_FIELD_SHAPES` / `_parse_envelope` are used across modules; consider dropping the leading underscore and updating `brand_journey.py`.
5. Lower priority (advisory): `agent_turn` failure path can't undo drafts created mid-comprehension (build drafts in an explicit loop); `confirm("flow")` doesn't require a built flow; BriefCanvas territory chips don't disable while a turn is pending; keep into a confirmed step doesn't move it back to drafted; flow draft list shows temp refs (N1) instead of resolved block codes; chat prompt doesn't advance to the next question after Keep.
6. Keep deliberately: `_call_turn_llm` / `_call_flow_llm` wrappers — the verify script monkeypatches them.

## Local-only state (not in git)

- `config/brand_kits.json` has uncommitted local edits (brands Solaraid, NeuroVita, SoluVex etc.). A fresh checkout has only the committed kits.
- `data/` (SQLite stores incl. `brand_journey.db`) is gitignored; a fresh environment starts empty.
- LLM features need `AZURE_AI_FOUNDRY_*` env vars (see `strategy/conversation_llm.py`); without them the journey runs on the registry fallback.
