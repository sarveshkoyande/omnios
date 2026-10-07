"""Brand Compass core (docs/redesign/engagement-plan-v2.md section 3): build or enrich a brand kit from
public sources only -- for brands with no uploaded brand plan (Jardiance, Keytruda).

What it does, per brand:
  1. FDA label + Drugs@FDA + NIH MeSH (public_sources), verbatim with citations.
  2. Indications as a LIST: the model splits the label's indications section into entries.
  3. Situation (lifecycle x archetype x access): the model PROPOSES it with evidence points;
     status "proposed" until a user confirms.
  4. Patient flow per priority indication: the model extracts real-world figures for the
     archetype's stages from recent PubMed abstracts, each with its PMID and year; stages with
     no figure are listed as gaps.
  5. Competitors and HCP segments: from the abstracts and the archetype, marked "proposed".

Rules R1/R2: free text is read only by the model; with no model the build stops with
LLMUnavailable and nothing is written. Every value carries a source.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import engagement_plans as ep  # noqa: E402
import public_sources as ps  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402

_SYS = ("You are a pharmaceutical brand analyst. Use ONLY the text provided. Never invent facts, "
        "numbers, dates or claims; if the text doesn't say it, leave it null and say so. Reply with JSON only.")


def split_indications(label_indications: str, brand: str) -> list[dict]:
    out = complete_json(_SYS + "\nSplit the FDA label's INDICATIONS section into one entry per indication "
                        "(group sub-indications that share a population only if the label groups them). Ignore "
                        "limitations of use. For each: id (short slug), name (short indication name), condition (the "
                        "disease as you'd search it in PubMed, e.g. 'type 2 diabetes', 'heart failure', 'non-small cell "
                        "lung cancer'), population (who, incl. age), line (line of therapy or setting, null if none), "
                        "criteria (biomarker / eligibility requirements, null if none), label_text (the exact sentence(s)).\n"
                        'Shape: {"indications":[{"id":"","name":"","condition":"","population":"","line":null,"criteria":null,"label_text":""}]}',
                        {"brand": brand, "indications_section": label_indications[:45000]}, max_tokens=16000)
    return [i for i in out.get("indications") or [] if isinstance(i, dict) and i.get("name")]


def propose_situation(brand: str, facts: dict) -> dict:
    fw = ep.framework()
    out = complete_json(_SYS + "\nClassify the brand's situation on three axes using the allowed ids only. Give 2-5 "
                        "evidence points, each citing which fact it rests on. If the facts can't support an axis, "
                        "set it to null and say what's missing.\n"
                        "Also give class_search_term: the drug class as you'd search it in PubMed (e.g. 'SGLT2 "
                        "inhibitor', 'PD-1 inhibitor').\n"
                        'Shape: {"lifecycle":"id","archetype":"id","access":"id","class_search_term":"","evidence":[{"point":"","source":""}],"missing":[""]}',
                        {"brand": brand, "facts": facts,
                         "allowed": {"lifecycle": [x["id"] for x in fw["lifecycle"]],
                                     "archetype": [{"id": a["id"], "label": a["label"]} for a in fw["archetypes"]],
                                     "access": [x["id"] for x in fw["access"]]}}, max_tokens=1500)
    return {**out, "status": "proposed"}


def patient_flow(brand: str, inn: str, indication: dict, archetype: dict) -> dict:
    """Real-world figures for the archetype's patient-flow stages, from PubMed abstracts."""
    cond = indication.get("condition") or indication["name"]
    cls = archetype.get("class_term") or inn
    # The model writes one targeted PubMed query per stage (real-world utilisation studies, not
    # trials), so each stage gets abstracts that can actually report its rate.
    plan = complete_json(_SYS + "\nWrite one PubMed search query per patient-flow stage that would find REAL-WORLD "
                         "studies reporting the share of patients passing that stage for this indication (e.g. "
                         "'testing rate', 'proportion of eligible patients prescribed', 'underuse', 'persistence', "
                         "'adherence', 'time to diagnosis'). Use PubMed syntax with the condition and the drug class "
                         "or drug; avoid trial-efficacy terms. Omni plans for the UNITED STATES: every query must "
                         "target US studies -- add (\"United States\"[MeSH Terms] OR US OR Medicare OR \"commercial "
                         "claims\" OR VA) or a similar US filter. Keep each query short.\n"
                         'Shape: {"queries":[{"stage":"","query":""}]}',
                         {"indication": indication, "condition": cond, "drug": inn, "drug_class": cls,
                          "stages": archetype["patient_flow"]}, max_tokens=1200)
    abstracts: list[dict] = []
    seen_pmids: set[str] = set()
    queries = [q for q in plan.get("queries") or [] if isinstance(q, dict) and q.get("query")]
    for q in queries:
        for a in ps.pubmed_abstracts(q["query"], n=6):
            if a["pmid"] not in seen_pmids:
                seen_pmids.add(a["pmid"])
                abstracts.append({**a, "found_for": q.get("stage")})
    term = " | ".join(f'{q.get("stage")}: {q["query"]}' for q in queries)
    out = complete_json(_SYS + "\nYou are filling a patient-flow 'leaky bucket' for one indication. For each stage in "
                        "`stages`, extract the best real-world figure the abstracts give (a rate or proportion such as "
                        "'% tested before first-line treatment' or '% of eligible patients initiated'), with the PMID "
                        "and year it comes from and the population/setting it applies to. The value is ALWAYS the share "
                        "of patients who PASS that stage (e.g. '% still on therapy'); if an abstract reports the opposite "
                        "('96% discontinued'), convert it (4%) and say so in `what`. Absolute counts (e.g. prevalence in "
                        "millions) keep their own unit. Omni plans for the UNITED STATES: use US figures; record the "
                        "country of the study in `setting`. Prefer figures specific to the US, this indication and drug "
                        "class. A stage with no figure in the abstracts gets value null. Then "
                        "list the leaks the evidence supports (where patients are lost) and any competitors / alternative "
                        "treatments the abstracts name for this indication.\n"
                        'Shape: {"stages":[{"stage":"","value":null,"unit":"%","what":"","setting":"","pmid":null,"year":null}],'
                        '"leaks":[{"stage":"","finding":"","pmids":[""]}],'
                        '"competitors":[{"name":"","type":"standard of care|direct|pipeline|alternative","pmids":[""]}]}',
                        {"brand": brand, "inn": inn, "indication": indication, "stages": archetype["patient_flow"],
                         "abstracts": abstracts}, max_tokens=4000)
    out["stages"] = _verify_stages(out.get("stages") or [], abstracts, indication)
    cites = {a["pmid"]: a for a in abstracts}
    for s in out.get("stages") or []:
        a = cites.get(str(s.get("pmid")))
        s["source"] = f"PubMed {s['pmid']} ({a['year']})" if a else None
        s["url"] = a["url"] if a else None
    gaps = [s["stage"] for s in out.get("stages") or [] if s.get("value") in (None, "")]  # incl. rejected figures
    return {"indication_id": indication["id"], "stages": out.get("stages") or [], "leaks": out.get("leaks") or [],
            "competitors": out.get("competitors") or [], "gaps": gaps, "query": term,
            "papers": [{k: a[k] for k in ("pmid", "title", "year", "url")} for a in abstracts]}


def _verify_stages(stages: list[dict], abstracts: list[dict], indication: dict) -> list[dict]:
    """Second pass: keep a figure only if it really measures the share of patients passing that
    stage (not survival, response or biomarker-positivity rates). Rejected figures become null
    with the reason kept, so the gap stays visible."""
    candidates = [s for s in stages if s.get("value") not in (None, "")]
    if not candidates:
        return stages
    by_pmid = {a["pmid"]: a for a in abstracts}
    out = complete_json(_SYS + "\nCheck each candidate figure against its abstract and give a verdict:\n"
                        "- match: it measures the share of patients passing that patient-flow stage, in this "
                        "indication's setting, in a UNITED STATES population (or an absolute US count for a "
                        "prevalence stage).\n"
                        "- proxy: the same KIND of measure for that stage, but a nearby setting (earlier disease stage, "
                        "related population, trial baseline) -- or a non-US study, which can never be a match; give the "
                        "caveat in one short sentence (name the country when it isn't the US).\n"
                        "- reject: a different kind of measure -- survival, response, efficacy, biomarker POSITIVITY "
                        "(not a testing rate), or a different stage.\n"
                        'Shape: {"checks":[{"stage":"","verdict":"match|proxy|reject","caveat":"","reason":""}]}',
                        {"indication": indication.get("name"), "candidates": [
                            {"stage": s["stage"], "value": s.get("value"), "unit": s.get("unit"), "what": s.get("what"),
                             "abstract": (by_pmid.get(str(s.get("pmid"))) or {}).get("abstract", "")[:1800]} for s in candidates]},
                        max_tokens=1500)
    verdict = {c.get("stage"): c for c in out.get("checks") or []}
    for s in stages:
        v = verdict.get(s.get("stage"))
        if not v or s.get("value") in (None, ""):
            continue
        s["verdict"] = v.get("verdict")
        if v.get("verdict") == "proxy":
            s["caveat"] = v.get("caveat") or v.get("reason")
        elif v.get("verdict") == "reject":
            s["rejected"] = {"value": s.get("value"), "what": s.get("what"), "pmid": s.get("pmid"), "reason": v.get("reason")}
            s.update(value=None, what=None, pmid=None, year=None)
    return stages


def propose_audiences(brand: str, archetype: dict, indications: list[dict]) -> list[dict]:
    out = complete_json(_SYS + "\nPropose 3-6 HCP and patient audience segments for this brand from the archetype's "
                        "audience list and the indications (which specialties treat them). For each: name, who, why "
                        "they matter for this brand, the adoption-ladder rung they likely sit on (one of `ladder`) and why. "
                        "These are proposals for the brand team to confirm.\n"
                        'Shape: {"segments":[{"name":"","who":"","why":"","ladder_rung":"","ladder_reason":"","tier":"Primary|Secondary"}]}',
                        {"brand": brand, "archetype": archetype, "ladder": ep.framework()["adoption_ladder"],
                         "indications": [{k: i.get(k) for k in ("name", "population", "line")} for i in indications]},
                        max_tokens=2500)
    return [{**s, "status": "proposed"} for s in out.get("segments") or []]


def build_public_kit(brand: str, inn: str, condition_for_mesh: str, priority_indications: int = 3) -> dict:
    """Create or refresh `brand`'s kit from public sources only, and save it to the kit store."""
    label = ps.fda_label(inn, brand)
    approval = ps.fda_approval(inn, brand)
    try:
        mesh = ps.mesh_condition(condition_for_mesh)
    except Exception as e:  # noqa: BLE001 -- one source failing leaves the others
        mesh = {"mesh_condition": {"value": None, "source": f"NIH MeSH (failed: {e})"}}
    profile = {**label, **approval, **mesh, "fetched_at": ps._today(), "errors": {}}
    profile.update(ps.pubchem(inn))

    indications = split_indications(label["indication"]["value"] or "", brand)
    situation = propose_situation(brand, {
        "today": ps._today(),
        "us_approval": approval["us_approval"]["value"], "label_version": label["label_version"]["value"],
        "pharm_class": label["pharm_class"]["value"], "route": label["route"]["value"],
        "indications": [{"name": i["name"], "line": i.get("line"), "criteria": i.get("criteria")} for i in indications],
        "labeler": label["labeler"]["value"]})
    fw = ep.framework(situation.get("archetype") or "chronic_primary")
    arch = {**fw["archetype"], "class_term": situation.get("class_search_term") or inn}

    # One flow per distinct condition (several label entries can share a disease).
    # Priority = conditions with the most label entries first (a deterministic proxy for how
    # central a disease is to the brand, e.g. Keytruda's NSCLC); the user can reorder later.
    counts: dict[str, int] = {}
    for ind in indications:
        c = (ind.get("condition") or ind["name"]).lower()
        counts[c] = counts.get(c, 0) + 1
    seen, firsts = set(), []
    for ind in sorted(indications, key=lambda i: -counts[(i.get("condition") or i["name"]).lower()]):
        c = (ind.get("condition") or ind["name"]).lower()
        if c not in seen:
            seen.add(c)
            firsts.append(ind)
    flows = [patient_flow(brand, inn, ind, arch) for ind in firsts[:priority_indications]]
    competitors: dict[str, dict] = {}
    for f in flows:
        for c in f["competitors"]:
            key = (c.get("name") or "").strip().lower()
            if key and key not in competitors:
                competitors[key] = {"name": c["name"], "type": c.get("type"), "status": None,
                                    "threat": None, "threat_status": "proposed",
                                    "source": "PubMed " + ", ".join(map(str, c.get("pmids") or [])),
                                    "indication": f["indication_id"]}
    segments = propose_audiences(brand, fw["archetype"], indications)
    import us_geography
    try:
        geography = us_geography.build(brand, indications)
    except Exception as e:  # noqa: BLE001 -- geography is additive; report and continue
        geography = {"country": "US", "layers": [], "error": str(e)}

    key = brand_kit.canonical_key(brand)
    if not key:
        brand_kit.create_brand(brand, ["US"])
    fields = {
        "source_label": f"{brand}: public sources only (FDA, Drugs@FDA, NIH MeSH, PubMed)",
        "source_note": "No brand plan uploaded. Built from public sources; situation, audiences and competitors are proposals to confirm.",
        "company": label["labeler"]["value"],
        "generic": inn,
        "indication": "; ".join(i["name"] for i in indications[:6]) + (" …" if len(indications) > 6 else ""),
        "approved_indication": label["indication"]["value"],
        "safety_reference": label["warnings"]["value"],
        "product_profile": profile,
        "public_source_query": {"generic": inn, "condition": condition_for_mesh},
        "brand_situation": situation,
        "indications": indications,
        "patient_flow": flows,
        "competitors": list(competitors.values()),
        "audience_segments": segments,
        "us_geography": geography,
        "lifecycle_stage": situation.get("lifecycle"),
    }
    return brand_kit.apply_diff(brand, fields)


__all__ = ["build_public_kit", "LLMUnavailable"]
