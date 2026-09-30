"""Segmentation Planner: Camille v15's Segmentation Agent (backend/segmentationAgent.js and
frontend/src/SegmentationAgent.js) on OmniOS, behind the Cockpit's v3 "segmentation-planner".

The flow, as in Camille:
  1. Describe the audience in plain English.
  2. Pick the email consent statuses to include (or skip the consent filter).
  3. The Segmentation Agent writes Salesforce Data Cloud DBT SQL on the HCP segmentation data
     model object and suggests a name and description.
  4. Name the segment; it is sized with a count on the Data Cloud Query API.
  5. Confirm, and it is created in Data Cloud (duplicate-name check, creation with up to two
     self-healing retries where the model fixes the SQL from Data Cloud's error, then publish).

Modules: dataset (the data model object's columns and real values), sqltools (sanitizing and
checking the SQL), prompts (Camille's prompts), rules (the no-model fallback), datacloud (the
Data Cloud APIs), store (sessions), service (the actions, as background jobs).

Deliberate differences from Camille:
  * The column values in the prompt are the dataset's real ones, profiled from Data Cloud (and
    cached; config/segmentation_dataset.json is the fallback) instead of a hand-written list
    that had drifted from the data (missing brands, specialties, segments; states that don't
    exist, so Camille's own "HCPs in New York" example matched nobody).
  * The record count is read correctly (Query API rows are arrays; Camille read `row.cnt` and
    always showed 0), and when a count can't be run the planner says so instead of showing
    a made-up number (Camille's "simulated" count was derived from the SQL's length).
  * A count that fails on the SQL is self-healed like a failed creation, before you confirm.
  * The duplicate-name check reads every page of segments (Camille read only the first 20).
  * Developer names are always valid API names (no double or trailing underscores).
  * "Published" reports whether the publish call actually succeeded.
  * An empty name uses the suggested one, as the question promises.
  * Steps run as background jobs whose events stream to the browser and survive a reload;
    the conversation is saved per brand + campaign.
  * Without a model, a rules engine builds the SQL from the values and simple numeric phrases
    it finds in the request, and says exactly what it understood.
"""
