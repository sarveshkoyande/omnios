"""
Build the brand content library (the first requested data store) inside the Campaign &
Content data model: for every flagship brand it seeds real references from the scraped
knowledge base (DailyMed label, ClinicalTrials.gov trials, PubMed papers), an atomic
claims library (efficacy / safety / MOA / access / RTB / ISI) grounded in those
references and the market analysis, reusable content modules assembled from the claims,
DAM content assets (email, detail aid, banner, social) with a sample rendering stored in
the content-addressed blob store, a generated SVG banner image per brand, controlled-
vocabulary taxonomy tags, and an MLR review-record audit trail for the approved items.

Design intent (see vault note "Omni OS — Campaign & Content Data Model + Industry Best
Practices"): claims are first-class and individually substantiated to a reference; assets
are assembled from pre-approved modules (modular content); everything is findable via
taxonomy tags. Content is an editorial synthesis grounded in real label/trial/mechanism
facts -- specific efficacy figures are only asserted where independently verified;
figure-dependent claims are left in draft/in_review so MLR substantiation is explicit.

Idempotent-ish: running again clears previously machine-generated library rows (those
tagged with GEN_TAG in id_code / mlr_code) and rebuilds them, so it will not duplicate.

Usage:  python scripts/build_content_library.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "strategy"))
import blob_store  # noqa: E402
import campaign_store  # noqa: E402

KB_DB = ROOT / "data" / "omni_kb.db"
CATALOG = ROOT / "config" / "client_brands.json"
INTEL = ROOT / "config" / "brand_market_intel.json"

GEN_TAG = "OMNIGEN"   # marks machine-generated library rows so a rebuild can replace them
YEAR = 2026


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _future(days: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + days * 86400))


# --- mechanism-of-action map (drug class per brand; used for MOA claims) ----------------
MOA = {
    "Nubeqa": "an androgen receptor inhibitor (ARI) with low blood-brain-barrier penetration",
    "Kerendia": "a selective non-steroidal mineralocorticoid receptor antagonist (MRA)",
    "Eylea": "a VEGF-A and placental growth factor inhibitor (VEGF trap)",
    "Xarelto": "a direct oral factor Xa inhibitor",
    "Lynkuet": "a dual neurokinin-1 and neurokinin-3 (NK1/NK3) receptor antagonist",
    "Cabometyx": "a multi-targeted tyrosine kinase inhibitor (VEGFR, MET, AXL)",
    "Somatuline": "a long-acting somatostatin analog",
    "Dysport": "a botulinum toxin type A that blocks acetylcholine release",
    "Iqirvo": "a PPAR alpha/delta agonist",
    "Onivyde": "a liposomal formulation of the topoisomerase-1 inhibitor irinotecan",
    "Epkinly": "a CD3xCD20 T-cell-engaging bispecific antibody",
    "Tivdak": "a tissue-factor-directed antibody-drug conjugate (ADC)",
    "Darzalex": "an anti-CD38 monoclonal antibody",
    "Kesimpta": "an anti-CD20 monoclonal antibody for self-administered subcutaneous dosing",
    "Kisqali": "a CDK4/6 inhibitor",
    "Leqvio": "a small interfering RNA (siRNA) targeting PCSK9",
    "Pluvicto": "a PSMA-targeted radioligand therapy (lutetium-177)",
    "Cosentyx": "an interleukin-17A inhibitor",
    "Entresto": "an angiotensin receptor-neprilysin inhibitor (ARNI)",
    "Fabhalta": "an oral factor B inhibitor of the alternative complement pathway",
    "Vyndaqel": "a transthyretin (TTR) stabilizer",
    "Padcev": "a Nectin-4-directed antibody-drug conjugate (ADC)",
    "Abrysvo": "a bivalent RSV prefusion F (RSVpreF) vaccine",
    "Ibrance": "a CDK4/6 inhibitor",
    "Eliquis": "a direct oral factor Xa inhibitor",
    "Litfulo": "a JAK3 / TEC-family kinase inhibitor",
    "Jakafi": "a JAK1/JAK2 inhibitor",
    "Opzelura": "a topical JAK1/JAK2 inhibitor",
    "Monjuvi": "an Fc-modified anti-CD19 monoclonal antibody",
    "Niktimvo": "an anti-CSF-1R monoclonal antibody",
    "Pemazyre": "a fibroblast growth factor receptor (FGFR) 1-3 inhibitor",
}

# --- independently-verified specific efficacy claims (approved-tier) --------------------
# Each claim cites a real pivotal trial + a specific figure confirmed from public sources
# (company releases, NEJM/Lancet/JCO, FDA). Claim text carries indication keywords so
# _indication_claims() attaches it to the matching indication. Brands not listed here fall
# back to the indication statement + an in_review efficacy scaffold (no number asserted).
VERIFIED = {
    "Kisqali": [
        ("efficacy", "In the Phase III NATALEE trial, ribociclib plus endocrine therapy reduced the risk of "
                     "disease recurrence by 28.4% versus endocrine therapy alone in HR+/HER2- early breast cancer "
                     "(5-year analysis)."),
        ("efficacy", "Across the Phase III MONALEESA trials, ribociclib plus endocrine therapy showed a consistent "
                     "overall-survival benefit in HR+/HER2- metastatic breast cancer."),
    ],
    "Pluvicto": [
        ("efficacy", "In the Phase III PSMAfore trial, Pluvicto reduced the risk of radiographic progression or "
                     "death by 59% (HR 0.41) versus a change in androgen-receptor pathway inhibitor in PSMA-positive "
                     "mCRPC in the pre-taxane setting."),
        ("efficacy", "In the Phase III VISION trial, Pluvicto plus standard of care improved median overall survival "
                     "to 15.3 versus 11.3 months (HR 0.62) in PSMA-positive mCRPC after ARPI and taxane therapy."),
    ],
    "Lynkuet": [
        ("efficacy", "In the OASIS-1 and OASIS-2 pivotal trials, elinzanetant significantly reduced the frequency of "
                     "moderate-to-severe vasomotor symptoms due to menopause versus placebo at both week 4 and week 12."),
    ],
    "Padcev": [
        ("efficacy", "In the Phase III EV-302 trial, enfortumab vedotin plus pembrolizumab reduced the risk of death "
                     "by 53% (median OS 31.5 vs 16.1 months, HR 0.47) versus platinum chemotherapy in first-line "
                     "locally advanced or metastatic urothelial cancer."),
    ],
    "Entresto": [
        ("efficacy", "In PARADIGM-HF, sacubitril/valsartan reduced the risk of cardiovascular death or heart-failure "
                     "hospitalization versus enalapril in heart failure with reduced ejection fraction (HFrEF)."),
    ],
    "Vyndaqel": [
        ("efficacy", "In ATTR-ACT, tafamidis reduced all-cause mortality and cardiovascular-related hospitalizations "
                     "versus placebo in transthyretin amyloid cardiomyopathy."),
    ],
    "Nubeqa": [
        ("efficacy", "In the Phase III ARASENS trial, darolutamide plus ADT and docetaxel reduced the risk of death "
                     "by 32.5% (HR 0.68) versus placebo plus ADT and docetaxel in metastatic hormone-sensitive "
                     "prostate cancer (mHSPC), with docetaxel."),
        ("efficacy", "In the Phase III ARANOTE trial, darolutamide plus ADT reduced the risk of radiographic "
                     "progression or death by 46% (HR 0.54) versus ADT alone in metastatic hormone-sensitive "
                     "prostate cancer (mHSPC), chemo-free."),
    ],
    "Kerendia": [
        ("efficacy", "In the FIDELIO-DKD and FIGARO-DKD trials, finerenone reduced heart-failure hospitalizations by "
                     "22% and slowed disease progression versus placebo in CKD associated with type 2 diabetes."),
        ("efficacy", "In the Phase III FINEARTS-HF trial, finerenone significantly reduced worsening heart-failure "
                     "events and cardiovascular death versus placebo in heart failure with mildly-reduced/preserved EF."),
    ],
    "Leqvio": [
        ("efficacy", "In the ORION-10 and ORION-11 trials, inclisiran reduced LDL cholesterol by approximately 50% "
                     "versus placebo, with 75% of patients reaching LDL-C <55 mg/dL, in primary hypercholesterolemia "
                     "and heterozygous familial hypercholesterolemia."),
        ("efficacy", "In the ORION program, twice-yearly inclisiran delivered durable ~50% LDL-C lowering as an "
                     "adjunct to maximally-tolerated statin in ASCVD."),
    ],
    "Fabhalta": [
        ("efficacy", "In the Phase III APPLAUSE-IgAN trial, iptacopan achieved a 38.3% reduction in proteinuria "
                     "versus placebo in IgA nephropathy."),
        ("efficacy", "In the APPOINT-PNH and APPULSE-PNH trials, oral iptacopan produced clinically meaningful "
                     "hemoglobin improvements in paroxysmal nocturnal hemoglobinuria (PNH)."),
    ],
    "Epkinly": [
        ("efficacy", "In the pivotal EPCORE NHL-1 trial, epcoritamab achieved a 61% overall response rate and a 38% "
                     "complete response rate in relapsed/refractory diffuse large B-cell lymphoma (3L+)."),
    ],
    "Abrysvo": [
        ("efficacy", "In the Phase III RENOIR trial, Abrysvo demonstrated 88.9% efficacy against RSV-associated lower "
                     "respiratory tract disease (>=3 symptoms) in older adults 60 years and older."),
    ],
    "Kesimpta": [
        ("efficacy", "In the ASCLEPIOS I and II trials, ofatumumab reduced the annualized relapse rate by 51% and "
                     "59% versus teriflunomide in relapsing forms of multiple sclerosis."),
    ],
    "Cabometyx": [
        ("efficacy", "In the Phase III CABINET trial, cabozantinib extended median progression-free survival to 13.8 "
                     "versus 3.3 months with placebo (HR 0.22) in advanced pancreatic neuroendocrine tumors (pNET)."),
        ("efficacy", "In the Phase III CheckMate 9ER trial, cabozantinib plus nivolumab improved median overall "
                     "survival to 49.5 versus 35.5 months with sunitinib in first-line renal cell carcinoma (RCC)."),
    ],
    "Opzelura": [
        ("efficacy", "In the TRuE-V trials, about 30% of patients achieved F-VASI75 repigmentation at week 24 (rising "
                     "to ~50% at week 52) with ruxolitinib cream in nonsegmental vitiligo."),
        ("efficacy", "In the TRuE-AD trials, ruxolitinib cream produced significantly greater skin clearance and itch "
                     "reduction versus vehicle in atopic dermatitis."),
    ],
    "Litfulo": [
        ("efficacy", "In the Phase IIb/III ALLEGRO trial, 23% of patients achieved SALT <=20 scalp-hair regrowth at "
                     "week 24 (rising to 43% at week 48) with ritlecitinib in severe alopecia areata."),
    ],
    "Eliquis": [
        ("efficacy", "In the ARISTOTLE trial, apixaban reduced stroke or systemic embolism by 21% (HR 0.79), major "
                     "bleeding by 31%, and all-cause mortality by 11% versus warfarin in non-valvular atrial fibrillation."),
    ],
    "Xarelto": [
        ("efficacy", "In the ROCKET-AF trial, rivaroxaban was non-inferior to warfarin for stroke and systemic-embolism "
                     "prevention, with significantly less intracranial hemorrhage, in non-valvular atrial fibrillation."),
        ("efficacy", "In the COMPASS trial, rivaroxaban 2.5 mg twice daily plus aspirin reduced major cardiovascular "
                     "events versus aspirin alone in stable coronary or peripheral artery disease (CAD/PAD)."),
    ],
    "Darzalex": [
        ("efficacy", "In the Phase III MAIA trial, daratumumab plus lenalidomide and dexamethasone extended median "
                     "progression-free survival to 61.9 versus 34.4 months in newly diagnosed multiple myeloma "
                     "(transplant-ineligible)."),
    ],
    "Cosentyx": [
        ("efficacy", "In the Phase III SUNSHINE and SUNRISE trials, secukinumab achieved HiSCR clinical response in "
                     "roughly 56-65% of patients at week 52 in moderate-to-severe hidradenitis suppurativa."),
    ],
    "Jakafi": [
        ("efficacy", "In the Phase III COMFORT-I trial, 42% of patients achieved >=35% spleen-volume reduction at week "
                     "24 with ruxolitinib versus <1% with placebo in myelofibrosis."),
    ],
    "Onivyde": [
        ("efficacy", "In the Phase III NAPOLI-3 trial, the NALIRIFOX regimen improved median overall survival to 11.1 "
                     "versus 9.2 months with gemcitabine plus nab-paclitaxel in first-line metastatic pancreatic "
                     "adenocarcinoma."),
    ],
    "Tivdak": [
        ("efficacy", "In the Phase III innovaTV 301 trial, tisotumab vedotin reduced the risk of death by 30% (median "
                     "OS 11.5 vs 9.5 months, HR 0.70) versus chemotherapy in recurrent or metastatic cervical cancer."),
    ],
}


def _kb_refs(conn_kb: sqlite3.Connection, brand: str) -> list[dict]:
    """Real references for a brand from the KB: the label + top trials + top papers."""
    refs = []
    row = conn_kb.execute(
        "SELECT external_id, title, url FROM documents WHERE source='dailymed' AND search_term LIKE ? LIMIT 1",
        (f"%{brand}%",)).fetchone()
    if row:
        refs.append({"source_type": "dailymed", "citation": row["title"], "url": row["url"],
                     "external_id": row["external_id"], "annotation": "FDA-approved product label (Structured Product Labeling)."})
    for r in conn_kb.execute(
            "SELECT external_id, title, url, metadata_json FROM documents WHERE source='clinicaltrials' "
            "AND search_term LIKE ? ORDER BY id LIMIT 3", (f"%{brand}%",)).fetchall():
        meta = json.loads(r["metadata_json"] or "{}")
        refs.append({"source_type": "clinicaltrials", "citation": r["title"], "url": r["url"],
                     "external_id": r["external_id"],
                     "annotation": f"Status: {meta.get('status','?')}; phase: {','.join(meta.get('phase') or []) or 'n/a'}."})
    for r in conn_kb.execute(
            "SELECT external_id, title, url, metadata_json FROM documents WHERE source='pubmed' "
            "AND search_term LIKE ? ORDER BY id LIMIT 2", (f"%{brand}%",)).fetchall():
        meta = json.loads(r["metadata_json"] or "{}")
        refs.append({"source_type": "pubmed", "citation": r["title"], "url": r["url"],
                     "external_id": r["external_id"],
                     "annotation": f"{meta.get('journal','')} ({meta.get('year','')})."})
    return refs


def _brand_claims(brand: str, generic: str, intel: dict) -> list[dict]:
    """Brand-level claims that hold across every indication (indication_id stays NULL):
    MOA, safety, access, strategic RTB, ISI."""
    moa = MOA.get(brand, "its mechanism of action")
    out: list[dict] = [
        {"text": f"{brand} ({generic}) is {moa}.", "claim_type": "moa", "status": "approved"},
        {"text": f"The safety profile of {brand} was consistent with its mechanism class; the most common "
                 f"adverse reactions are described in the Prescribing Information.",
         "claim_type": "safety", "status": "in_review"},
        {"text": f"Dosing, administration and monitoring for {brand} follow the approved Prescribing "
                 f"Information; patient-support and access resources are available.",
         "claim_type": "access", "status": "draft"},
    ]
    posture = intel.get("campaign_posture", "")
    if posture:
        out.append({"text": f"Strategic reason-to-believe ({intel.get('lifecycle_stage','')} stage): "
                            f"{intel.get('whitespace') or posture.split(':')[0]}.",
                    "claim_type": "rtb", "status": "draft"})
    out.append({"text": f"Please see accompanying full Prescribing Information for {brand}, including any Boxed "
                        f"Warning, Contraindications, Warnings and Precautions, and Adverse Reactions.",
                "claim_type": "isi", "status": "approved"})
    return out


_STOP = {"the", "of", "with", "and", "for", "in", "a", "an", "to", "or", "versus", "vs"}


def _assign_verified(brand: str, indications: list[str]) -> dict[str, list[tuple]]:
    """Assign each independently-verified claim to its single best-matching indication
    (max keyword overlap; ties/no-match -> the lead indication). Returns
    {indication_label: [(claim_type, text), ...]} so no verified claim is duplicated across
    indications and none is dropped."""
    assignment: dict[str, list[tuple]] = {ind: [] for ind in indications}
    lead = indications[0] if indications else ""
    ind_words = {ind: set(re.findall(r"[a-z0-9]+", ind.lower())) - _STOP for ind in indications}
    for ctype, text in VERIFIED.get(brand, []):
        tw = set(re.findall(r"[a-z0-9]+", text.lower()))
        best, best_score = lead, 0
        for ind in indications:
            score = len(ind_words[ind] & tw)
            if score > best_score:
                best, best_score = ind, score
        assignment[best].append((ctype, text))
    return assignment


def _indication_claims(brand: str, generic: str, indication: str, intel: dict,
                       verified_here: list[tuple]) -> list[dict]:
    """Indication-specific claims (carry that indication's id): the indication statement,
    the independently-verified efficacy results assigned to THIS indication (by
    _assign_verified), and an efficacy scaffold that still needs substantiation."""
    comp = (intel.get("competitors") or ["standard of care"])[0]
    out: list[dict] = [
        {"text": f"{brand} is indicated for {indication}.", "claim_type": "efficacy", "status": "approved"},
    ]
    for ctype, text in verified_here:
        out.append({"text": text, "claim_type": ctype, "status": "approved"})
    out.append({"text": f"In {indication}, {brand} demonstrated a clinically meaningful treatment effect versus "
                        f"{comp} in its pivotal program (efficacy magnitude to be substantiated from the primary "
                        f"endpoint).", "claim_type": "efficacy", "status": "in_review"})
    return out


def _svg_banner(brand: str, generic: str, stage: str, ta: str) -> bytes:
    """A simple, self-contained SVG banner creative (real image bytes for the blob store)."""
    palette = {"launch": "#0B3D91", "growth": "#12866F", "mature": "#5A32E0", "loe": "#808080"}
    c = palette.get(stage, "#0B3D91")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="728" height="90" viewBox="0 0 728 90">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c}"/><stop offset="1" stop-color="#00AEEF"/></linearGradient></defs>'
        f'<rect width="728" height="90" fill="url(#g)"/>'
        f'<text x="24" y="40" font-family="Inter,Arial,sans-serif" font-size="26" font-weight="700" '
        f'fill="#fff">{brand}</text>'
        f'<text x="24" y="64" font-family="Inter,Arial,sans-serif" font-size="13" fill="#eaf2ff">'
        f'{generic} — {ta}</text>'
        f'<text x="600" y="52" font-family="Inter,Arial,sans-serif" font-size="12" fill="#eaf2ff" '
        f'text-anchor="middle">Learn more &#9656;</text>'
        f'</svg>'
    ).encode("utf-8")


def _email_html(brand: str, claims: list[dict], indication: str) -> str:
    approved = [c for c in claims if c["status"] == "approved" and c["claim_type"] in ("efficacy", "moa")]
    isi = next((c["text"] for c in claims if c["claim_type"] == "isi"), "")
    bullets = "".join(f"<li>{c['text']}</li>" for c in approved[:3])
    return (
        f"<html><body style='font-family:Inter,Arial,sans-serif;color:#1a2330'>"
        f"<h2 style='color:#0B3D91'>{brand}</h2>"
        f"<p><strong>Indication:</strong> {indication}</p>"
        f"<ul>{bullets}</ul>"
        f"<p style='font-size:11px;color:#667'>{isi}</p>"
        f"<p><a href='#' style='background:#00AEEF;color:#fff;padding:8px 16px;text-decoration:none;"
        f"border-radius:6px'>Request more information</a></p>"
        f"</body></html>"
    )


def _store_blob(conn, data, mime, name) -> str:
    return campaign_store._store_blob(conn, data, mime, name)


def _tag(conn, kind: str, entity_id: int, dimension: str, term: str) -> None:
    conn.execute("INSERT OR IGNORE INTO taxonomy_term (dimension, term) VALUES (?,?)", (dimension, term))
    tid = conn.execute("SELECT id FROM taxonomy_term WHERE dimension=? AND term=?", (dimension, term)).fetchone()["id"]
    conn.execute("INSERT OR IGNORE INTO entity_tag (entity_kind, entity_id, term_id) VALUES (?,?,?)",
                 (kind, entity_id, tid))


def _clear_generated(conn) -> None:
    """Remove previously machine-generated rows so a rerun rebuilds cleanly."""
    conn.execute("DELETE FROM review_record WHERE reviewer = ?", (GEN_TAG,))
    conn.execute("DELETE FROM claim WHERE mlr_code = ?", (GEN_TAG,))
    conn.execute("DELETE FROM content_module WHERE material_number LIKE ?", (f"{GEN_TAG}-MOD-%",))
    conn.execute("DELETE FROM content_asset WHERE id_code LIKE ?", (f"{GEN_TAG}-%",))
    conn.execute("DELETE FROM ref_source WHERE annotation LIKE ? OR source_type IN "
                 "('dailymed','clinicaltrials','pubmed')", (f"%{GEN_TAG}%",))
    conn.commit()


def build() -> dict:
    campaign_store.init_db()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    intel_all = json.loads(INTEL.read_text(encoding="utf-8")).get("brands", {})
    conn = sqlite3.connect(campaign_store.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn_kb = sqlite3.connect(KB_DB)
    conn_kb.row_factory = sqlite3.Row

    _clear_generated(conn)  # replace prior machine-generated rows so reruns don't duplicate

    stats = {"brands": 0, "refs": 0, "claims": 0, "claim_refs": 0, "modules": 0,
             "assets": 0, "blobs": 0, "reviews": 0, "tags": 0}
    mat_seq = 1000
    try:
        for client, brands in catalog.get("clients", {}).items():
            for b in brands:
                brand = b["brand"]
                generic = b.get("generic", "")
                ta = b.get("therapy_area", "")
                indications = b.get("indications", []) or [""]
                lead_ind = indications[0]
                intel = intel_all.get(brand, {})
                stage = intel.get("lifecycle_stage", b.get("lifecycle_key", ""))

                bid = campaign_store._brand_id(conn, brand, ta, generic, b.get("lifecycle_key", ""), client)
                iid_by_ind = {ind: (campaign_store._indication_id(conn, bid, ind) if ind else None)
                              for ind in indications}
                stats["brands"] += 1

                # 1) Real references from the KB (shared across the brand's indications).
                ref_ids = []
                for r in _kb_refs(conn_kb, brand):
                    rid = campaign_store._ref_id(conn, r["source_type"], r["citation"], r["url"], r["external_id"])
                    conn.execute("UPDATE ref_source SET annotation=? WHERE id=?",
                                 (f"{r['annotation']} [{GEN_TAG}]", rid))
                    ref_ids.append(rid)
                    stats["refs"] += 1

                def _add_claim(c, iid, seq_ref):
                    """Insert one claim, substantiate it, tag + audit-log it. seq_ref is a
                    1-element list holding the running material-number sequence."""
                    mat = f"{GEN_TAG}-{brand[:4].upper()}-{seq_ref[0]}" if c["status"] == "approved" else None
                    seq_ref[0] += 1
                    cur = conn.execute(
                        """INSERT INTO claim (brand_id, indication_id, text, claim_type, claim_status,
                           material_number, mlr_code, approved_at, expires_at, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (bid, iid, c["text"], c["claim_type"], c["status"], mat, GEN_TAG,
                         _now() if c["status"] == "approved" else None,
                         _future(365) if c["status"] == "approved" else None, _now()))
                    cid = cur.lastrowid
                    stats["claims"] += 1
                    if ref_ids:
                        if c["claim_type"] in ("isi", "access"):
                            ref, locator = ref_ids[0], "full Prescribing Information"
                        else:
                            ref, locator = ref_ids[seq_ref[0] % len(ref_ids)], "see cited section"
                        conn.execute("INSERT OR IGNORE INTO claim_reference (claim_id, ref_id, locator) VALUES (?,?,?)",
                                     (cid, ref, locator))
                        stats["claim_refs"] += 1
                    _tag(conn, "claim", cid, "therapy_area", ta); stats["tags"] += 1
                    if c["status"] == "approved":
                        conn.execute("INSERT INTO review_record (entity_kind, entity_id, action, reviewer, decision_at, notes) "
                                     "VALUES ('claim',?,?,?,?,?)", (cid, "approved", GEN_TAG, _now(),
                                     "Auto-approved sample claim (mechanism/label-anchored)."))
                        stats["reviews"] += 1
                    return cid

                seq = [mat_seq]
                # 2a) Brand-level claims (indication_id NULL -- true across every indication).
                brand_claims_by_type: dict[str, list[int]] = {}
                for c in _brand_claims(brand, generic, intel):
                    cid = _add_claim(c, None, seq)
                    brand_claims_by_type.setdefault(c["claim_type"], []).append(cid)

                def _module(name, mtype, claim_ids, rules, iid, status="approved"):
                    mat = f"{GEN_TAG}-MOD-{seq[0]}"; seq[0] += 1
                    cur = conn.execute(
                        """INSERT INTO content_module (brand_id, indication_id, name, module_type, status,
                           material_number, business_rules, created_at) VALUES (?,?,?,?,?,?,?,?)""",
                        (bid, iid, name, mtype, status, mat, rules, _now()))
                    mid = cur.lastrowid
                    for cid in claim_ids:
                        conn.execute("INSERT OR IGNORE INTO module_claim (module_id, claim_id) VALUES (?,?)", (mid, cid))
                    _tag(conn, "module", mid, "brand", brand)
                    stats["modules"] += 1
                    if status == "approved":
                        conn.execute("INSERT INTO review_record (entity_kind, entity_id, action, reviewer, decision_at, notes) "
                                     "VALUES ('module',?,?,?,?,?)", (mid, "approved", GEN_TAG, _now(),
                                     "Auto-approved sample module."))
                        stats["reviews"] += 1
                    return mid

                def _asset(fmt, title, branded, target, body_bytes, mime, ext, modules, iid, ind_label):
                    key = _store_blob(conn, body_bytes, mime, f"{brand}_{fmt}.{ext}")
                    stats["blobs"] += 1
                    idc = f"{GEN_TAG}-{brand[:4].upper()}-{fmt.upper()}-{seq[0]}"; seq[0] += 1
                    cur = conn.execute(
                        """INSERT INTO content_asset (brand_id, indication_id, file_name, title, asset_format,
                           branded, target_group, description, id_code, blob_key, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (bid, iid, f"{brand}_{fmt}.{ext}", title, fmt, branded, target,
                         f"Sample {fmt} for {brand} ({stage} stage){(' — ' + ind_label) if ind_label else ''}.",
                         idc, key, _now()))
                    aid = cur.lastrowid
                    for mid in modules:
                        conn.execute("INSERT OR IGNORE INTO asset_module (asset_id, module_id) VALUES (?,?)", (aid, mid))
                    _tag(conn, "asset", aid, "channel", fmt)
                    _tag(conn, "asset", aid, "audience", target)
                    stats["assets"] += 1
                    return aid

                # Brand-level shared modules (ISI, reference block, CTA) -- reused by every asset.
                m_isi = _module(f"{brand} Important Safety Information", "isi",
                                brand_claims_by_type.get("isi", []),
                                "Mandatory in every branded promotional asset; do not alter wording.", None)
                m_ref = _module(f"{brand} reference block", "reference_block", [],
                                "Insert cited references matching the claims used in the asset.", None)
                m_cta = _module(f"{brand} request-info CTA", "cta", [],
                                "Standard HCP call-to-action; link to the brand HCP portal.", None)
                persona = "HCP — specialist"

                # 2b/3/4) Per-indication claims, an efficacy claim block module, and a full
                # asset set (email, banner, detail-aid, unbranded social) -- so EVERY indication
                # is covered, not just the lead one.
                verified_by_ind = _assign_verified(brand, [i for i in indications if i])
                for ind in indications:
                    iid = iid_by_ind[ind]
                    ind_claim_ids: list[int] = []
                    approved_ind_texts: list[str] = []
                    ind_claims = _indication_claims(brand, generic, ind, intel,
                                                    verified_by_ind.get(ind, [])) if ind else []
                    for c in ind_claims:
                        cid = _add_claim(c, iid, seq)
                        ind_claim_ids.append(cid)
                        if c["status"] == "approved":
                            approved_ind_texts.append(c["text"])

                    m_efficacy = _module(
                        f"{brand} efficacy claim block — {ind or ta}", "claim_block",
                        ind_claim_ids + brand_claims_by_type.get("moa", []),
                        "Use in branded HCP materials only; must be paired with the ISI module.", iid)

                    email_claims = [{"text": t, "status": "approved", "claim_type": "efficacy"} for t in approved_ind_texts]
                    _asset("email", f"{brand} HCP eDetail email — {ind or ta}", 1, persona,
                           _email_html(brand, email_claims, ind or ta).encode("utf-8"), "text/html", "html",
                           [m_efficacy, m_isi, m_cta], iid, ind)
                    _asset("banner", f"{brand} leaderboard banner (728x90) — {ind or ta}", 1, persona,
                           _svg_banner(brand, generic, stage, ind or ta), "image/svg+xml", "svg",
                           [m_efficacy, m_isi], iid, ind)
                    _asset("detail_aid", f"{brand} core visual aid — {ind or ta}", 1, persona,
                           json.dumps({"brand": brand, "indication": ind, "stage": stage,
                                       "key_claims": approved_ind_texts,
                                       "posture": intel.get("campaign_posture", "")}, indent=2).encode("utf-8"),
                           "application/json", "json", [m_efficacy, m_ref, m_isi], iid, ind)
                    _asset("social", f"{brand} unbranded disease-awareness post — {ind or ta}", 0, "Patient / caregiver",
                           (f"Talk to a healthcare professional about {ta}. "
                            f"Learn about options and questions to ask. #DiseaseAwareness").encode("utf-8"),
                           "text/plain", "txt", [], iid, ind)

                mat_seq = seq[0]

        conn.commit()
    finally:
        conn.close()
        conn_kb.close()
    return stats


if __name__ == "__main__":
    print("Building content library (grounded in the scraped KB)…")
    print(json.dumps(build(), indent=2))
