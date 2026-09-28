"""The Flow Planner: a deterministic, SOP-driven segmentation + journey
diagram generator, ported from a Python reference project
(`github.com/sarveshkoyande/govex`, `campaign-accelerator-api/app/flow/*`,
branch `dev/flow-planner`) -- not from `novartis/accelerate-app`'s own
`server/segmentation/*.js`, which is itself a partial JS port of the same
reference project (Segmentation region only, per that port's own scope note).
This package ports the original Python source directly, module for module:

    sop.py          fixed SOP text/legend/suppression lists, from a JSON seed
    model.py        FlowNode/FlowEdge/FlowDesign, the node/edge vocabulary
    inputs.py       intake field parsing (FlowInputs) -- unchanged in shape
    segmentation.py SOP rows 1-9, the segmentation region
    journeybuild.py SOP rows 10-17, the email journey (once per segment)
    clarify.py      the SOP-driven clarifying questions
    llm.py          the 3 narrow model calls (segment names, unbranded-source
                    detection, last-touchpoint pick), on OmniOS's own LLM
                    client instead of the reference project's AWS Bedrock
    planner.py      the entry point: plan()/generate()
    demo_brief.py   the static campaign brief this generates against for now

Two pieces of the reference project are deliberately NOT ported, by explicit
product decision:

  - The intake form the reference project's field ids (e.g. "generic"/"1.1.6")
    belong to. OmniOS has no such form yet, so `demo_brief.py` supplies a
    fixed brief (verbatim from the reference project's own demo script)
    instead of live campaign data. `inputs.py`'s `FlowInputs` does not know or
    care where its `values` dict came from, so wiring a real form in later is
    a change to the caller, not to this package.

  - `app/core/journey.py`'s approval/versioning system: freezing a design
    against a source intake version, content-hashing it, and detecting which
    later intake edits invalidate an existing approval. That depends on
    SQLAlchemy models (CampaignVersion, JourneyVersion) and a diff/versioning
    layer OmniOS does not have. Every node this package emits still carries
    `derived_from`/`sop_ref`/`rationale`, so that system can be added later
    without regenerating anything.
"""
