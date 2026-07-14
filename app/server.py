"""FastAPI backend for the Omni OS campaign-planning agent.

Serves the agentic three-pane front-end plus:
  - project CRUD (left rail)                    /api/projects ...
  - conversational slot-filling (center chat)   /api/chat
  - multi-agent research run as SSE (right rail) /api/run-stream
The original single-shot endpoints are kept for backward compatibility / scripting.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_DIR = pathlib.Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from strategy.engine import generate_strategy, list_persona_options, list_stage_options, market_landscape  # noqa: E402
from strategy.positioning import build_positioning_statement  # noqa: E402
from strategy.kpi import build_kpi_framework  # noqa: E402
from strategy.lifecycle import list_lifecycle_options  # noqa: E402
from strategy.autorun import run_full_analysis  # noqa: E402
from competitive.swot import build_swot  # noqa: E402
from strategy import projects as pstore  # noqa: E402
from strategy.conversation import (new_state, opening_message, interpret_message, llm_enabled,  # noqa: E402
                                   get_llm_status, ask_clarify_group, clarify_payload)
from strategy import orchestrator  # noqa: E402
from strategy.orchestrator import run_agents  # noqa: E402
from strategy import open_questions as open_questions_mod  # noqa: E402  (phase-gated reveal)
from strategy.document_intake import extract_text  # noqa: E402
from strategy import dashboard as dashboard_mod  # noqa: E402
from strategy import feed as feed_mod  # noqa: E402
from strategy import campaign_store  # noqa: E402
from strategy import brand_memory  # noqa: E402
from strategy import blob_store  # noqa: E402  (serves real label images to the Claims Library)
from strategy import bootstrap  # noqa: E402  (first-boot seeding of an empty data disk)
from strategy import personas as personas_mod  # noqa: E402  (synthetic persona layer)
from strategy import persona_review as persona_review_mod  # noqa: E402
from strategy import plan_export  # noqa: E402  (Word/PDF export of the composed plan)
from strategy import plan_pdf  # noqa: E402  (pixel-faithful PDF via headless Chromium)

app = FastAPI(title="Omni OS Brand Engagement Planning Agent")


@app.on_event("startup")
def _seed_on_boot() -> None:
    """Seed an empty DATA_DIR (fresh persistent disk) with the committed KB + content
    library. Idempotent and non-blocking; a persistent disk makes this run only once."""
    try:
        print(f"[startup] bootstrap: {bootstrap.run(background=True)}")
    except Exception as e:  # noqa: BLE001 -- startup must never fail on seeding
        print(f"[startup] bootstrap skipped ({e})")


def _msg(role: str, text: str, extra: dict | None = None) -> dict:
    m = {"role": role, "text": text, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if extra:
        m.update(extra)
    return m


def _safe_filename(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (name or "brand-engagement-plan").lower()).strip("-") or "brand-engagement-plan"


def _freeze_project_state(state: dict) -> None:
    """'Close updates': lock the plan against further automatic adjustment (persona apply /
    per-section clarify updates), and force-close any clarify Q&A still in progress -- every
    remaining group is treated as answered so it can never resurface, even on a future full
    rerun of the agents."""
    state["plan_frozen"] = True
    groups = state.get("open_questions") or []
    idx = state.get("clarify_idx", 0)
    if idx < len(groups):
        resolved = set(state.get("clarify_resolved_ids") or [])
        resolved.update(g["id"] for g in groups[idx:])
        state["clarify_resolved_ids"] = sorted(resolved)
    state["clarify_idx"] = len(groups)
    state["awaiting_clarify"] = None


@app.get("/api/home")
def api_home():
    """Landing-page payload: per-brand performance dashboard + the ticker feed."""
    return {"dashboard": dashboard_mod.brand_performance(), "feed": feed_mod.build_feed()}


# ------------------------------------------------------------------ #
# Claims Library: browse the governed content library + its real assets
# ------------------------------------------------------------------ #

@app.get("/api/library")
def api_library():
    """Index of every brand holding library content, with claim/asset/image counts."""
    return campaign_store.library_brands()


@app.get("/api/library/{brand}")
def api_library_brand(brand: str):
    """One brand's full library: claims (with substantiating references), reusable modules,
    real label images and the rest of the DAM assets."""
    detail = campaign_store.brand_library_detail(brand)
    if not detail.get("found"):
        raise HTTPException(404, f"no library content for brand '{brand}'")
    return detail


@app.get("/api/blob/{blob_key}")
def api_blob(blob_key: str):
    """Serve raw bytes from the content-addressed blob store with the right Content-Type,
    so the library can render the real label images (and download other assets).
    Blob keys are sha256 hex, so content is immutable -- cache it hard."""
    if not (len(blob_key) == 64 and all(c in "0123456789abcdef" for c in blob_key.lower())):
        raise HTTPException(400, "blob_key must be a sha256 hex digest")
    meta = campaign_store.blob_meta(blob_key)
    data = blob_store.get(blob_key)
    if data is None or meta is None:
        raise HTTPException(404, "blob not found")
    return Response(content=data, media_type=meta.get("mime_type") or "application/octet-stream",
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "Content-Disposition": f'inline; filename="{meta.get("original_name") or blob_key}"'})


# ------------------------------------------------------------------ #
# Synthetic persona layer: pressure-test a finished plan against the
# audiences it is trying to reach.
# ------------------------------------------------------------------ #

@app.get("/api/personas")
def api_personas(project_id: str = ""):
    """Personas ranked by relevance to a project's plan (its therapy area / specialty), so the
    picker can pre-select the natural reviewers. With no project it matches on nothing (all
    become 'others')."""
    therapy_area = indication = ""
    if project_id:
        proj = pstore.get_project(project_id)
        if proj:
            slots = proj["state"]["slots"]
            therapy_area = (proj.get("result") or {}).get("therapy_area") or slots.get("therapy_area", "")
            indication = slots.get("indication", "")
    return personas_mod.match_to_plan(therapy_area, indication)


@app.get("/api/personas/{persona_id}")
def api_persona_detail(persona_id: str):
    """Full persona record (demographics, prescribing, channels, decision drivers, voice) --
    powers the picker's 'info' card."""
    p = personas_mod.get(persona_id)
    if not p:
        raise HTTPException(404, f"no persona '{persona_id}'")
    return p


class PersonaReviewRequest(BaseModel):
    project_id: str
    persona_ids: list[str]
    use_llm: bool = True


@app.post("/api/persona-review")
def api_persona_review(req: PersonaReviewRequest):
    """Run the finished plan past each selected persona and return their honest, in-character
    feedback. Persists the reviews on the project so they survive a reload."""
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    result = proj.get("result")
    if not result:
        raise HTTPException(400, "no plan to review yet — generate the plan first")
    chosen = [p for p in (personas_mod.get(pid) for pid in req.persona_ids) if p]
    if not chosen:
        raise HTTPException(400, "no valid personas selected")
    reviews = persona_review_mod.review_many(chosen, result, use_llm=req.use_llm)
    state = proj["state"]
    state["persona_reviews"] = reviews
    pstore.save_project(req.project_id, state=state)
    return {"reviews": reviews}


class PersonaApplyRequest(BaseModel):
    project_id: str
    persona_ids: list[str] = []   # empty -> use every persona from the last review batch


@app.post("/api/persona-apply")
def api_persona_apply(req: PersonaApplyRequest):
    """Automatically rebalance the plan's channel mix toward what the selected personas
    actually respond to, and re-render the plan document. Reuses the exact same compose_plan
    call the original run made -- run-stream snapshots the run's full ctx (server-side only,
    never sent to the client) precisely so this can happen without re-running the agents."""
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    state = proj["state"]
    if state.get("plan_frozen"):
        raise HTTPException(400, "updates are closed for this plan -- it's locked in")
    ctx = state.get("_plan_ctx")
    if not ctx:
        raise HTTPException(400, "this plan was generated before persona adjustments were "
                                  "supported -- regenerate the plan to enable this")
    reviews = state.get("persona_reviews") or []
    ids = req.persona_ids or [r["persona_id"] for r in reviews]
    chosen = [p for p in (personas_mod.get(pid) for pid in ids) if p]
    if not chosen:
        raise HTTPException(400, "no valid personas to apply")

    current_mix = persona_review_mod._plan_mix(proj["result"])
    adj = persona_review_mod.suggest_rebalance(chosen, current_mix)
    total_budget = ctx.get("budget") or 0
    ctx["budget_allocation"] = {
        b: {"pct": pct, "amount": round(total_budget * pct / 100, 2) if total_budget else None}
        for b, pct in adj["new_mix"].items()
    }
    result, plan_md, plan_html = orchestrator.recompose_plan(ctx)

    log_entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "persona_ids": ids,
                 "persona_names": [p["name"] for p in chosen], "changes": adj["changes"]}
    state.setdefault("persona_adjustments", []).append(log_entry)
    state["_plan_ctx"] = ctx
    pstore.save_project(req.project_id, state=state, result=result, plan_markdown=plan_md, plan_html=plan_html)
    return {"changes": adj["changes"], "new_mix": adj["new_mix"], "plan_html": plan_html, "plan_markdown": plan_md}


@app.post("/api/projects/{pid}/close-updates")
def api_close_updates(pid: str):
    """Lock the plan against further automatic adjustment (persona apply / per-section
    clarify updates) and force-close any clarify Q&A still in progress. Same effect as
    typing 'close updates' in chat -- exposed as a button too."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    state = proj["state"]
    _freeze_project_state(state)
    # Reveal every remaining toolkit phase on lock-in so nothing stays gated.
    ctx = state.get("_plan_ctx")
    plan_html = plan_markdown = result_for_save = None
    if ctx:
        state["revealed_phases"] = list(open_questions_mod.PHASE_ORDER)
        result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx)
    pstore.save_project(pid, state=state, result=result_for_save,
                        plan_markdown=plan_markdown, plan_html=plan_html)
    return {"ok": True, "plan_frozen": True, "plan_html": plan_html, "plan_markdown": plan_markdown}


# ------------------------------------------------------------------ #
# Agentic workspace: projects + chat + streaming run
# ------------------------------------------------------------------ #

class NewProjectRequest(BaseModel):
    name: str = "Untitled plan"


class ChatRequest(BaseModel):
    project_id: str
    message: str


@app.get("/api/projects")
def api_list_projects():
    return pstore.list_projects()


@app.post("/api/projects")
def api_create_project(req: NewProjectRequest):
    state = new_state()
    messages = [_msg("agent", opening_message())]
    return pstore.create_project(req.name, state, messages)


@app.get("/api/projects/{pid}")
def api_get_project(pid: str):
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    return proj


@app.delete("/api/projects/{pid}")
def api_delete_project(pid: str):
    pstore.delete_project(pid)
    return {"ok": True}


class PlanContentRequest(BaseModel):
    html: str
    markdown: str


@app.post("/api/projects/{pid}/plan-content")
def api_save_plan_content(pid: str, req: PlanContentRequest):
    """Persist a manual edit made in the plan panel (each heading/paragraph/list item/simple
    table cell is directly editable in the UI). The client derives `markdown` from the same
    edited DOM client-side, so Word/PDF exports reflect the edit too. Note: a later clarify
    auto-update or persona 'apply feedback' recomposes the plan from the run's snapshotted
    state and will overwrite a manual edit -- there's no merge between the two."""
    proj = pstore.get_project(pid)
    if not proj:
        raise HTTPException(404, "project not found")
    if not req.html.strip():
        raise HTTPException(400, "empty plan content")
    pstore.save_project(pid, plan_markdown=req.markdown, plan_html=req.html)
    return {"ok": True}


@app.get("/api/projects/{pid}/export.docx")
def api_export_docx(pid: str):
    proj = pstore.get_project(pid)
    if not proj or not proj.get("plan_markdown"):
        raise HTTPException(404, "no plan to export yet")
    data = plan_export.markdown_to_docx(proj["plan_markdown"], proj["name"])
    filename = _safe_filename(proj["name"]) + ".docx"
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/projects/{pid}/export.pdf")
def api_export_pdf(pid: str):
    proj = pstore.get_project(pid)
    if not proj or not proj.get("plan_markdown"):
        raise HTTPException(404, "no plan to export yet")
    # Prefer the pixel-faithful renderer (real HTML + the app's own CSS via headless
    # Chromium) so the PDF actually looks like the plan; fall back to the plain
    # reportlab-from-markdown renderer if Chromium isn't installed on this host, so the
    # export still works (with lower fidelity) rather than failing outright.
    try:
        if not proj.get("plan_html"):
            raise ValueError("no plan_html on this project")
        data = plan_pdf.render_plan_pdf(proj["plan_html"], proj["name"])
    except Exception as e:  # noqa: BLE001
        print(f"[export.pdf] Chromium renderer unavailable, using markdown fallback ({e})")
        data = plan_export.markdown_to_pdf(proj["plan_markdown"], proj["name"])
    filename = _safe_filename(proj["name"]) + ".pdf"
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    messages = proj["messages"]
    state = proj["state"]
    messages.append(_msg("user", req.message))

    # Snapshot whether the post-plan clarify Q&A was in progress BEFORE this turn, so we can
    # tell the client the exact turn it finishes on -- that's the moment the synthetic-persona
    # offer should appear (never before the brand team's open questions are captured). Also
    # snapshot which group ids were already resolved, and an id->title lookup, so we can tell
    # the client exactly which section(s) this turn just folded into the plan.
    prev_groups = state.get("open_questions") or []
    prev_idx = state.get("clarify_idx", 0)
    was_clarifying = bool(prev_groups) and prev_idx < len(prev_groups)
    prev_resolved = set(state.get("clarify_resolved_ids") or [])
    id_to_title = {g["id"]: g["title"] for g in prev_groups}

    state, reply, action = interpret_message(req.message, state)
    clarify = clarify_payload(state)  # non-None only while the post-plan clarify Q&A is active

    now_groups = state.get("open_questions") or []
    now_idx = state.get("clarify_idx", 0)
    now_clarifying = bool(now_groups) and now_idx < len(now_groups)
    clarify_just_completed = was_clarifying and not now_clarifying

    # When the user signs off a phase's questions, the NEXT toolkit phase's agents start next
    # (the front-end triggers /api/run-stream?phase=<next_phase>). Announce the hand-off in the
    # reply instead of the generic per-phase "that's everything" close. next_phase=None means
    # Deploy (the last phase) was just signed off, so the whole build is complete.
    next_phase = None
    if clarify_just_completed and not state.get("plan_frozen"):
        cur_phase = state.get("current_phase")
        if cur_phase in orchestrator.PHASE_ORDER:
            i = orchestrator.PHASE_ORDER.index(cur_phase)
            if i + 1 < len(orchestrator.PHASE_ORDER):
                next_phase = orchestrator.PHASE_ORDER[i + 1]
            if next_phase:
                reply = (f"✅ **Phase {orchestrator.PHASE_NO[cur_phase]} · {orchestrator.PHASE_LABELS[cur_phase]}** "
                         f"is signed off and folded into the plan. Bringing the agents in for **Phase "
                         f"{orchestrator.PHASE_NO[next_phase]} · {orchestrator.PHASE_LABELS[next_phase]}** now…")
            else:
                reply = ("✅ **Phase 4 · Deploy the campaign** is signed off. That completes all four toolkit phases — "
                         "the plan is fully built and every section is live on the right. Pressure-test it with "
                         "synthetic personas next, or say **close updates** to lock it in.")

    messages.append(_msg("agent", reply, {"kind": "clarify", "clarify": clarify} if clarify else None))

    # 'update_plan': fold this clarify answer (or skip / skip-all) into the plan immediately --
    # no waiting for the whole Q&A to finish and no manual 'regenerate'. Recomposes from the
    # run's snapshotted ctx (never re-runs the agents); a project created before ctx snapshots
    # existed just skips this silently (plan_updated stays False).
    plan_updated = False
    plan_html = plan_markdown = None
    updated_sections: list[str] = []
    result_for_save = None
    if action == "update_plan":
        newly_resolved = set(state.get("clarify_resolved_ids") or []) - prev_resolved
        updated_sections = [id_to_title.get(gid, gid) for gid in newly_resolved]
        ctx = state.get("_plan_ctx")
        if ctx:
            ctx = orchestrator.refresh_after_clarify(
                ctx, state["slots"].get("maturity_notes", ""), set(state.get("clarify_resolved_ids") or []))
            # The plan is revealed up to the phase currently being validated -- driven by the
            # phased run, not the clarify cursor (each run seeds only its own phase's questions).
            cur_phase = state.get("current_phase", "align")
            revealed = orchestrator._phase_reveal(cur_phase)
            state["revealed_phases"] = sorted(revealed)
            result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx, revealed_phases=revealed)
            state["_plan_ctx"] = ctx
            plan_updated = True
    elif action == "freeze":
        _freeze_project_state(state)
        # Locking the plan in reveals every remaining phase -- the user is done building,
        # so nothing stays locked once the document is finalized.
        ctx = state.get("_plan_ctx")
        if ctx:
            state["revealed_phases"] = list(open_questions_mod.PHASE_ORDER)
            result_for_save, plan_markdown, plan_html = orchestrator.recompose_plan(ctx)
            plan_updated = True

    # Auto-name the project once brand + therapy area are known.
    name = proj["name"]
    slots = state["slots"]
    if name in ("Untitled plan", "New plan") and slots["brand"] and slots["therapy_area"]:
        name = f"{slots['brand']} · {slots.get('indication') or slots['therapy_area']}"

    pstore.save_project(req.project_id, name=name, state=state, messages=messages,
                        result=result_for_save, plan_markdown=plan_markdown, plan_html=plan_html)
    return {"reply": reply, "slots": slots, "phase": state["phase"], "action": action, "name": name,
            "llm_status": get_llm_status(), "clarify": clarify, "clarify_just_completed": clarify_just_completed,
            "next_phase": next_phase,
            "plan_updated": plan_updated, "plan_html": plan_html, "plan_markdown": plan_markdown,
            "updated_sections": updated_sections, "plan_frozen": bool(state.get("plan_frozen"))}


@app.post("/api/upload")
async def api_upload(project_id: str = Form(...), file: UploadFile = File(...)):
    """Extracts text from an uploaded brand-plan document (PDF/DOCX/text) and feeds it
    through the same interpret_message seam as a normal chat turn -- so brand/therapy/
    lifecycle/budget mentioned in the document get picked up without retyping them."""
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")

    content = await file.read()
    try:
        text = extract_text(file.filename or "upload", content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not text:
        raise HTTPException(400, "Could not extract any text from that file.")

    messages = proj["messages"]
    state = proj["state"]
    messages.append(_msg("user", f"📎 Uploaded **{file.filename}**"))

    prompt = (f"[The user attached a document named \"{file.filename}\". Extract the brand, therapy area, "
              f"lifecycle stage, and budget (if mentioned) from its content below, the same as if they had "
              f"typed this in chat.]\n\n{text}")
    state, reply, action = interpret_message(prompt, state)
    messages.append(_msg("agent", reply))

    name = proj["name"]
    slots = state["slots"]
    if name in ("Untitled plan", "New plan") and slots["brand"] and slots["therapy_area"]:
        name = f"{slots['brand']} · {slots.get('indication') or slots['therapy_area']}"

    pstore.save_project(project_id, name=name, state=state, messages=messages)
    return {"reply": reply, "slots": slots, "phase": state["phase"], "action": action, "name": name,
            "llm_status": get_llm_status(), "filename": file.filename}


@app.get("/api/run-stream")
def api_run_stream(project_id: str, phase: str = "align"):
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    slots = proj["state"]["slots"]
    if phase not in orchestrator.PHASE_ORDER:
        phase = "align"

    def event_gen():
        messages = proj["messages"]
        state = proj["state"]
        result = None
        ctx_snapshot = None
        plan_md = plan_html = None
        try:
            # Show the team the INSTANT the phase starts -- before the (possibly 30-60s, on
            # Align, of live network calls) compute below -- so the client never sits on a
            # silent stream with nothing rendered. compute_plan_ctx runs every agent's work for
            # every phase once, up front, on Align; later phases replay the same ctx as theater.
            for ev in orchestrator.phase_open(phase):
                if ev["type"] == "narration":
                    messages.append(_msg("agent", ev["text"]))
                yield f"data: {json.dumps(ev)}\n\n"

            if phase == "align" or not state.get("_plan_ctx"):
                ctx = orchestrator.compute_plan_ctx(
                    slots["brand"], slots["therapy_area"], slots["lifecycle_key"], slots["budget"],
                    slots.get("maturity_notes", ""), slots.get("indication", ""), brief=slots)
            else:
                ctx = state["_plan_ctx"]

            for ev in orchestrator.run_phase(phase, ctx, opened=True):
                if ev["type"] == "narration":
                    messages.append(_msg("agent", ev["text"]))
                elif ev["type"] == "plan":
                    plan_md, plan_html = ev["markdown"], ev["html"]
                elif ev["type"] == "result":
                    result = ev["result"]
                    ctx_snapshot = ev.pop("ctx", None)  # server-only; stripped before the wire
                if ev["type"] == "done":
                    # Human gate: seed ONLY this phase's validation questions and ask the first,
                    # then the stream ends -- the next phase's agents don't start until the user
                    # signs off in chat (see the /api/chat 'next_phase' advance).
                    already_resolved = set(state.get("clarify_resolved_ids") or [])
                    phase_groups = [g for g in (result or {}).get("open_questions", [])
                                    if g.get("phase") == phase and g["id"] not in already_resolved]
                    state["open_questions"] = phase_groups
                    state["clarify_idx"] = 0
                    state["current_phase"] = phase
                    state["revealed_phases"] = sorted(orchestrator._phase_reveal(phase))
                    first_ask = ask_clarify_group(state)
                    payload = clarify_payload(state)
                    if first_ask:
                        messages.append(_msg("agent", first_ask, {"kind": "clarify", "clarify": payload}))
                        yield f"data: {json.dumps({'type': 'clarify', 'text': first_ask, 'clarify': payload})}\n\n"
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # surface failures to the UI rather than hanging
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            state["phase"] = "done"
            if ctx_snapshot is not None:
                state["_plan_ctx"] = ctx_snapshot
            pstore.save_project(project_id, state=state, messages=messages,
                                result=result, plan_markdown=plan_md, plan_html=plan_html)
            # Persist the completed plan into the campaign & content data model only on the
            # final phase (Deploy) -- earlier phases are partial. Best-effort; never let a
            # persistence error break the streamed response.
            if result and phase == orchestrator.PHASE_ORDER[-1]:
                try:
                    campaign_store.persist_campaign_from_result(result, slots, plan_md or "", project_id)
                except Exception as e:  # noqa: BLE001
                    print(f"[campaign_store] persist failed: {e}")
                try:
                    brand_memory.save_brand_memory(slots.get("brand", ""), slots)
                except Exception as e:  # noqa: BLE001
                    print(f"[brand_memory] save failed: {e}")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ------------------------------------------------------------------ #
# Legacy single-shot endpoints (kept for scripting / backward compat)
# ------------------------------------------------------------------ #

class StrategyRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    persona: str
    stage_key: str


class CompetitiveRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    competitors: list[str] = []


class MarketLandscapeRequest(BaseModel):
    brand: str
    therapy_area: str = ""


class PositioningRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    persona: str
    stage_key: str
    competitors: list[str] = []


class KpiRequest(BaseModel):
    stage_key: str
    channel_mix_pct: dict[str, float] = {}


class AutoRunRequest(BaseModel):
    brand: str
    therapy_area: str = ""
    lifecycle_key: str
    budget: float = 0


@app.get("/api/options")
def get_options():
    return {"stages": list_stage_options(), "personas": list_persona_options(),
            "lifecycle_stages": list_lifecycle_options(), "llm_enabled": llm_enabled(),
            "llm_status": get_llm_status()}


@app.post("/api/auto-run")
def post_auto_run(req: AutoRunRequest):
    return run_full_analysis(req.brand, req.therapy_area, req.lifecycle_key, req.budget)


@app.post("/api/generate-strategy")
def post_generate_strategy(req: StrategyRequest):
    return generate_strategy(req.brand, req.therapy_area, req.persona, req.stage_key)


@app.post("/api/competitive-analysis")
def post_competitive_analysis(req: CompetitiveRequest):
    competitors = [c.strip() for c in req.competitors if c.strip()]
    return build_swot(req.brand, competitors, req.therapy_area)


@app.post("/api/market-landscape")
def post_market_landscape(req: MarketLandscapeRequest):
    return market_landscape(req.brand, req.therapy_area)


@app.post("/api/positioning-statement")
def post_positioning_statement(req: PositioningRequest):
    competitors = [c.strip() for c in req.competitors if c.strip()]
    return build_positioning_statement(req.brand, req.therapy_area, req.persona, req.stage_key, competitors)


@app.post("/api/kpi-framework")
def post_kpi_framework(req: KpiRequest):
    return build_kpi_framework(req.stage_key, req.channel_mix_pct)


@app.get("/")
def root():
    """New React + MUI front-end (built by frontend/ via Vite into static/v2) is now the
    default landing experience -- migration complete enough to promote it off /v2."""
    return FileResponse(APP_DIR / "static" / "v2" / "index.html")


@app.get("/v2")
def root_v2():
    """Kept as an alias to / so any existing /v2 links/bookmarks keep working."""
    return FileResponse(APP_DIR / "static" / "v2" / "index.html")


@app.get("/legacy")
def root_legacy():
    """Old static/JS front-end, kept reachable (not deleted) in case of rollback or reference
    during the migration."""
    return FileResponse(APP_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
