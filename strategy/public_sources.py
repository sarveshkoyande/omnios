"""Public, authoritative facts about a marketed drug: the FDA label (openFDA), its approval
(Drugs@FDA), the condition's NIH MeSH descriptor and category, and molecule details (PubChem for
small molecules; biologics fall back to the label's own description section).

Everything returned is a structured field from those APIs, verbatim, with the source URL and the
date it was fetched -- nothing is inferred or matched out of free text. Anything a source doesn't
have comes back as None so the kit can show "Needs input" rather than a guess. Network failures
are reported per source, never raised: the brand plan stays the source of truth either way.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.parse
import urllib.request

TIMEOUT = 20
_UA = {"User-Agent": "OmniOS/1.0 (brand-kit public sources)"}


def _get(url: str, params: dict | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _first(d: dict, key: str) -> str | None:
    v = d.get(key)
    return (v[0] if isinstance(v, list) and v else v) or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _fact(value, source: str, url: str) -> dict:
    return {"value": value, "source": source, "url": url, "fetched_at": _today()}


def fda_label(generic: str, brand: str | None = None) -> dict:
    """The current FDA label for `generic`, section by section, from openFDA. With `brand`, the
    label must carry that brand name -- a generic alone can match a combination product
    (empagliflozin -> Synjardy)."""
    if brand:
        q = f'openfda.brand_name:"{brand}" AND openfda.generic_name:"{generic}"'
        hits = _get("https://api.fda.gov/drug/label.json", {"search": q, "limit": 10})["results"]
        # exact single-ingredient match first (the brand's own label, not a combination)
        exact = [h for h in hits if [g.lower() for g in h.get("openfda", {}).get("generic_name", [])] == [generic.lower()]
                 and brand.lower() in [b.lower() for b in h.get("openfda", {}).get("brand_name", [])]]
        res = (exact or hits)[0]
    else:
        q = f'openfda.generic_name:"{generic}"'
        res = _get("https://api.fda.gov/drug/label.json", {"search": q, "limit": 1})["results"][0]
    of = res.get("openfda", {})
    set_id = res.get("set_id")
    url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}" if set_id else "https://open.fda.gov"
    src = f"FDA label (DailyMed) v{res.get('version', '?')}, {res.get('effective_time', '')}"
    sec = lambda k: _fact(_first(res, k), src + f" · {k.replace('_', ' ')}", url)
    return {
        "labeler": _fact(_first(of, "manufacturer_name"), src, url),
        "brand_names": _fact(of.get("brand_name"), src, url),
        "route": _fact(of.get("route"), src, url),
        "pharm_class": _fact((of.get("pharm_class_epc") or []) + (of.get("pharm_class_moa") or []) or None, src, url),
        "indication": sec("indications_and_usage"),
        "mechanism_of_action": sec("mechanism_of_action"),
        "molecule_description": sec("description"),
        "dosing": sec("dosage_and_administration"),
        "dosage_forms": sec("dosage_forms_and_strengths"),
        "boxed_warning": _fact(_first(res, "boxed_warning") or "No boxed warning in the current label", src, url),
        "warnings": sec("warnings_and_cautions"),
        "contraindications": sec("contraindications"),
        "clinical_studies": sec("clinical_studies"),
        "label_version": _fact({"version": res.get("version"), "effective": res.get("effective_time"), "set_id": set_id}, src, url),
    }


def fda_approval(generic: str, brand: str | None = None) -> dict:
    """Application number and original approval date from Drugs@FDA. With `brand`, only that
    brand's applications count, and the EARLIEST original approval wins -- a generic can also
    match later applications (pembrolizumab -> the 2025 subcutaneous Keytruda Qlex BLA)."""
    q = f'openfda.generic_name:"{generic}"'
    results = _get("https://api.fda.gov/drug/drugsfda.json", {"search": q, "limit": 20})["results"]
    if brand:
        mine = [r for r in results if any((p.get("brand_name") or "").lower() == brand.lower() for p in r.get("products", []))]
        results = mine or results
    best = None
    for r in results:
        for sub in r.get("submissions", []):
            if sub.get("submission_type") == "ORIG" and sub.get("submission_status_date"):
                if best is None or sub["submission_status_date"] < best[1]:
                    best = (r.get("application_number"), sub["submission_status_date"])
    appl, d = best or (results[0].get("application_number") if results else None, None)
    url = f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={(appl or '')[3:]}"
    return {"us_approval": _fact({"application": appl, "date": f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else None}, "Drugs@FDA", url)}


_SPARQL = "https://id.nlm.nih.gov/mesh/sparql"


def mesh_condition(label: str) -> dict:
    """The MeSH descriptor for a condition, plus the category names above it in the MeSH tree
    (e.g. Hematologic Diseases > Blood Platelet Disorders) -- the therapy-area context."""
    hits = _get("https://id.nlm.nih.gov/mesh/lookup/descriptor", {"label": label, "match": "exact", "limit": 1})
    if not hits:
        hits = _get("https://id.nlm.nih.gov/mesh/lookup/descriptor", {"label": label, "match": "contains", "limit": 1})
    if not hits:
        return {"mesh_condition": _fact(None, "NIH MeSH", "https://meshb.nlm.nih.gov")}
    uri, name = hits[0]["resource"], hits[0]["label"]
    ui = uri.rsplit("/", 1)[-1]
    trees = _get(f"https://id.nlm.nih.gov/mesh/{ui}.json").get("treeNumber", [])
    trees = [t.rsplit("/", 1)[-1] for t in (trees if isinstance(trees, list) else [trees])]
    # Ancestors of the first disease (C) tree: C15, C15.378, C15.378.140 ...
    main = next((t for t in trees if t.startswith("C")), trees[0] if trees else "")
    parts = main.split(".")
    ancestors = [".".join(parts[:i]) for i in range(1, len(parts))]
    names: dict[str, str] = {}
    if ancestors:
        values = " ".join(f"mesh:{a}" for a in ancestors)
        q = ("PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#> PREFIX mesh: <http://id.nlm.nih.gov/mesh/> "
             "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
             f"SELECT ?t ?l WHERE {{ VALUES ?t {{ {values} }} ?d meshv:treeNumber ?t . ?d rdfs:label ?l }}")
        for b in _get(_SPARQL, {"query": q, "format": "JSON"})["results"]["bindings"]:
            names[b["t"]["value"].rsplit("/", 1)[-1]] = b["l"]["value"]
    url = f"https://meshb.nlm.nih.gov/record/ui?ui={ui}"
    return {"mesh_condition": _fact({"id": ui, "name": name, "tree": main,
                                     "categories": [names[a] for a in ancestors if a in names]}, "NIH MeSH", url)}


def pubchem(generic: str) -> dict:
    """Formula, weight and structure image for a small molecule. Biologics have no PubChem
    compound; that is reported plainly, and the label's description covers the molecule."""
    url = f"https://pubchem.ncbi.nlm.nih.gov/#query={urllib.parse.quote(generic)}"
    try:
        props = _get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(generic)}/property/"
                     "MolecularFormula,MolecularWeight,IUPACName/JSON")["PropertyTable"]["Properties"][0]
    except Exception:  # noqa: BLE001 -- 404 means "not a small molecule in PubChem"
        return {"structure": _fact({"kind": "biologic_or_not_found",
                                    "note": "No PubChem compound: typical for biologics (antibodies, nanobodies). See the molecule description from the label."},
                                   "PubChem", url)}
    cid = props["CID"]
    return {"structure": _fact({"kind": "small_molecule", "cid": cid, "formula": props.get("MolecularFormula"),
                                "weight": props.get("MolecularWeight"), "iupac": props.get("IUPACName"),
                                "image": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG"},
                               "PubChem", f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}")}


def fetch_product_profile(generic: str, condition: str) -> dict:
    """Every public source, each fetched independently; one source failing leaves the others."""
    out: dict = {"fetched_at": _today(), "errors": {}}
    for name, fn in (("fda_label", lambda: fda_label(generic)), ("fda_approval", lambda: fda_approval(generic)),
                     ("mesh", lambda: mesh_condition(condition)), ("pubchem", lambda: pubchem(generic))):
        try:
            out.update(fn())
        except Exception as e:  # noqa: BLE001 -- report, never raise
            out["errors"][name] = f"{type(e).__name__}: {e}"
    return out


# ---------------------------------------------------------------- audience / persona sources

def pubmed_authors(term: str, years: int = 6, top: int = 10) -> dict:
    """Most-published authors on `term` in the last `years` years (PubMed) -- key opinion
    leader candidates. Counted from each paper's structured author list (esummary)."""
    this_year = _dt.date.today().year
    q = f"({term}) AND ({this_year - years}:{this_year}[dp])"
    ids = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
               {"db": "pubmed", "term": q, "retmax": 200, "retmode": "json", "sort": "pub_date"})["esearchresult"]["idlist"]
    url = f"https://pubmed.ncbi.nlm.nih.gov/?term={urllib.parse.quote(q)}"
    if not ids:
        return {"kol_publications": _fact([], "PubMed", url)}
    summ = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                {"db": "pubmed", "id": ",".join(ids), "retmode": "json"})["result"]
    stats: dict[str, dict] = {}
    for pmid in summ.get("uids", []):
        doc = summ[pmid]
        for a in doc.get("authors", []):
            if a.get("authtype") != "Author":
                continue
            s = stats.setdefault(a["name"], {"author": a["name"], "papers": 0, "latest_title": doc.get("title", ""),
                                             "latest_year": (doc.get("pubdate") or "")[:4], "pmid": pmid})
            s["papers"] += 1
    ranked = sorted(stats.values(), key=lambda s: -s["papers"])[:top]
    for r in ranked:
        r["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/"
    return {"kol_publications": _fact({"papers_scanned": len(ids), "query": q, "authors": ranked}, "PubMed", url)}


def trial_footprint(condition: str, intervention: str) -> dict:
    """Where the treaters are: trial sites by country and named investigators (ClinicalTrials.gov)."""
    res = _get("https://clinicaltrials.gov/api/v2/studies",
               {"query.cond": condition, "query.intr": intervention, "pageSize": 100,
                "fields": "NCTId,BriefTitle,OverallStatus,OverallOfficial,LocationCountry,LocationFacility"})
    countries: dict[str, int] = {}
    investigators = []
    for st in res.get("studies", []):
        ps = st["protocolSection"]
        nct = ps["identificationModule"]["nctId"]
        for loc in ps.get("contactsLocationsModule", {}).get("locations", []):
            c = loc.get("country")
            if c:
                countries[c] = countries.get(c, 0) + 1
        for o in ps.get("contactsLocationsModule", {}).get("overallOfficials", []):
            if o.get("role") == "PRINCIPAL_INVESTIGATOR":
                investigators.append({"name": o.get("name"), "affiliation": o.get("affiliation"), "nct": nct,
                                      "url": f"https://clinicaltrials.gov/study/{nct}"})
    url = f"https://clinicaltrials.gov/search?cond={urllib.parse.quote(condition)}&intr={urllib.parse.quote(intervention)}"
    return {"trial_footprint": _fact({"studies": len(res.get("studies", [])),
                                      "sites_by_country": sorted(({"country": c, "sites": n} for c, n in countries.items()), key=lambda x: -x["sites"]),
                                      "investigators": investigators}, "ClinicalTrials.gov", url)}


def patient_resources(condition: str) -> dict:
    """Plain-language patient pages from MedlinePlus (NIH) for the patient persona."""
    import xml.etree.ElementTree as ET
    q = urllib.parse.urlencode({"db": "healthTopics", "term": condition})
    with urllib.request.urlopen(urllib.request.Request(f"https://wsearch.nlm.nih.gov/ws/query?{q}", headers=_UA), timeout=TIMEOUT) as r:
        root = ET.fromstring(r.read())
    docs = []
    for d in root.iter("document"):
        title = next((c.text for c in d.findall("content") if c.get("name") == "title"), None)
        snippet = next((c.text for c in d.findall("content") if c.get("name") == "snippet"), None)
        docs.append({"title": title, "url": d.get("url"), "snippet": snippet})
    return {"patient_resources": _fact(docs, "MedlinePlus (NIH)", f"https://medlineplus.gov/search?query={urllib.parse.quote(condition)}")}


def fetch_audience_intel(condition: str, intervention: str, pubmed_term: str) -> dict:
    out: dict = {"fetched_at": _today(), "errors": {}}
    for name, fn in (("pubmed", lambda: pubmed_authors(pubmed_term)),
                     ("clinicaltrials", lambda: trial_footprint(condition, intervention)),
                     ("medlineplus", lambda: patient_resources(condition))):
        try:
            out.update(fn())
        except Exception as e:  # noqa: BLE001 -- report, never raise
            out["errors"][name] = f"{type(e).__name__}: {e}"
    return out


def pubmed_abstracts(term: str, n: int = 10, years: int = 8) -> list[dict]:
    """Recent PubMed abstracts for `term` (title, year, abstract text, PMID, URL) -- raw material
    for the model to extract cited real-world figures from. Nothing is interpreted here."""
    import xml.etree.ElementTree as ET
    this_year = _dt.date.today().year
    q = f"({term}) AND ({this_year - years}:{this_year}[dp])"
    ids = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
               {"db": "pubmed", "term": q, "retmax": n, "retmode": "json", "sort": "relevance"})["esearchresult"]["idlist"]
    if not ids:
        return []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=TIMEOUT) as r:
        root = ET.fromstring(r.read())
    out = []
    for art in root.iter("PubmedArticle"):
        pmid = art.findtext(".//PMID")
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        abstract = " ".join("".join(t.itertext()) for t in art.iter("AbstractText"))
        year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4]
        if abstract:
            out.append({"pmid": pmid, "title": title, "year": year, "abstract": abstract[:2500],
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
    return out
