"""The Campaign Planner's create-campaign flow, ported from Camille (Camille Version 15,
`Camille2/backend`: index.js's /campaign-briefing/* and /flows/* routes, reasoningEngine.js,
flowValidator.js, mermaidValidator.js) onto OmniOS's own stack.

What it does, end to end (the same steps Camille runs):

    1. Intake         typed requirements and/or an uploaded brief (PDF/DOCX/TXT/MD)
    2. Clarification  the Campaign Consultant reads the brief and asks up to 3 questions,
                      only about genuinely missing, campaign-critical details
    3. Assumptions    after the answers, up to 3 impactful assumptions to confirm or override
    4. Brief          an 11-section Campaign Briefing Document, bound to the facts given;
                      editable by plain-language change requests (every change is a version)
    5. Blueprint      seven agents turn the approved brief into a Salesforce Flow spec and a
                      journey diagram: Document Analyst -> Salesforce Architect -> Flow QA
                      Tester -> Visual Designer <-> Tester Agent -> Flow Validator ->
                      Technical Writer, their reasoning streamed live
    6. Deploy         the spec becomes Flow metadata XML, zipped and pushed through the
                      Salesforce Metadata API (or downloaded as a deployable package)

Modules:

    llm.py          model access (Claude via Azure AI Foundry, else Gemini) + Camille's
                    JSON recovery (bracket matching, truncated-JSON repair)
    briefing.py     the Campaign Consultant: analysis, clarifying questions, assumption
                    review, briefing generation/update; briefing normalising and export
    agents.py       the seven blueprint agents and their briefing-derived fallbacks
    mermaid.py      Mermaid sanitising + a deterministic spec -> diagram renderer
    flow_xml.py     flow-spec validation and Salesforce Flow XML / package generation
    salesforce.py   OAuth (web-server flow), org metadata, Metadata API deploy
    store.py        sessions (one per brand + campaign) and briefing versions
    jobs.py         background jobs whose events stream to the browser (SSE)
    service.py      the actions the HTTP routes call; owns every state transition

Deliberate differences from Camille (each a Camille bug or an OmniOS rule):

  - LLM: Camille called gpt-5 through a LiteLLM gateway; this uses OmniOS's configured
    provider, and like every OmniOS LLM call site it degrades to rules when no model is
    configured or a call fails: the brief is assembled from the typed text, and each
    blueprint agent falls back to output derived from the approved briefing.
  - The approved briefing (not just the raw intake text) drives the blueprint, so edits to
    the brief reach the journey; the uploaded document's text is kept through every step.
  - "Make changes" edits the briefing the user is looking at (Camille sent a template).
  - Refining the journey feeds the current spec back to the Architect (Camille parsed it
    and never used it).
  - The QA Tester and Architect prompts no longer hard-code one sample campaign's Day 1-16
    touchpoint list; they check against the touchpoints the requirements actually describe.
  - State is saved per campaign on the server (Camille kept it in the browser only).
"""
