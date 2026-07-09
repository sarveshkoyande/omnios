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
from fastapi.responses import FileResponse, StreamingResponse
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
from strategy.orchestrator import run_agents  # noqa: E402
from strategy.document_intake import extract_text  # noqa: E402
from strategy import dashboard as dashboard_mod  # noqa: E402
from strategy import feed as feed_mod  # noqa: E402
from strategy import campaign_store  # noqa: E402

app = FastAPI(title="Omni OS Campaign Planning Agent")


def _msg(role: str, text: str, extra: dict | None = None) -> dict:
    m = {"role": role, "text": text, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if extra:
        m.update(extra)
    return m


@app.get("/api/home")
def api_home():
    """Landing-page payload: per-brand performance dashboard + the ticker feed."""
    return {"dashboard": dashboard_mod.brand_performance(), "feed": feed_mod.build_feed()}


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


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    proj = pstore.get_project(req.project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    messages = proj["messages"]
    state = proj["state"]
    messages.append(_msg("user", req.message))

    state, reply, action = interpret_message(req.message, state)
    clarify = clarify_payload(state)  # non-None only while the post-plan clarify Q&A is active
    messages.append(_msg("agent", reply, {"kind": "clarify", "clarify": clarify} if clarify else None))

    # Auto-name the project once brand + therapy area are known.
    name = proj["name"]
    slots = state["slots"]
    if name in ("Untitled plan", "New plan") and slots["brand"] and slots["therapy_area"]:
        name = f"{slots['brand']} · {slots.get('indication') or slots['therapy_area']}"

    pstore.save_project(req.project_id, name=name, state=state, messages=messages)
    return {"reply": reply, "slots": slots, "phase": state["phase"], "action": action, "name": name,
            "llm_status": get_llm_status(), "clarify": clarify}


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
def api_run_stream(project_id: str):
    proj = pstore.get_project(project_id)
    if not proj:
        raise HTTPException(404, "project not found")
    slots = proj["state"]["slots"]

    def event_gen():
        messages = proj["messages"]
        state = proj["state"]
        result = None
        plan_md = plan_html = None
        try:
            for ev in run_agents(slots["brand"], slots["therapy_area"], slots["lifecycle_key"], slots["budget"],
                                 slots.get("maturity_notes", ""), slots.get("indication", "")):
                if ev["type"] == "narration":
                    messages.append(_msg("agent", ev["text"]))
                elif ev["type"] == "plan":
                    plan_md, plan_html = ev["markdown"], ev["html"]
                elif ev["type"] == "result":
                    result = ev["result"]
                if ev["type"] == "done" and result and result.get("open_questions"):
                    # Seed the post-plan clarify phase: everything the toolkit templates
                    # flagged as 'needs alignment' becomes a grouped Q&A the agent leads
                    # in chat -- streamed before 'done' so it appears live.
                    state["open_questions"] = result["open_questions"]
                    state["clarify_idx"] = 0
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
            pstore.save_project(project_id, state=state, messages=messages,
                                result=result, plan_markdown=plan_md, plan_html=plan_html)
            # Persist the generated plan into the campaign & content data model (best-effort;
            # never let a persistence error break the streamed response).
            if result:
                try:
                    campaign_store.persist_campaign_from_result(result, slots, plan_md or "", project_id)
                except Exception as e:  # noqa: BLE001
                    print(f"[campaign_store] persist failed: {e}")

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
    return FileResponse(APP_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
