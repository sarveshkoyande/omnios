"""Builds a comparative SWOT, a positioning table, and messaging/target-audience
options for a target brand against user-supplied competitors -- entirely from
quantifiable signals in metrics.py (trial pipeline activity, FDA indication
footprint, publication recency, search interest). No invented facts: every
bullet cites the underlying numbers so it's auditable against the source data.
"""
from __future__ import annotations

from .metrics import gather_brand_metrics


def _avg(values: list[float]) -> float:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def _build_comparisons(target: dict, competitors: list[dict]) -> dict:
    comp_active = _avg([c["trials_active"] for c in competitors])
    comp_completed = _avg([c["trials_completed"] for c in competitors])
    comp_stopped = _avg([c["trials_stopped"] for c in competitors])
    comp_pubmed_recent = _avg([c["pubmed_recent_2yr"] for c in competitors])
    comp_trends = _avg([c["trends_avg_interest"] for c in competitors])
    comp_fda = _avg([c["fda_label_count"] for c in competitors])

    return {
        "trials_active": (target["trials_active"], comp_active),
        "trials_completed": (target["trials_completed"], comp_completed),
        "trials_stopped": (target["trials_stopped"], comp_stopped),
        "pubmed_recent_2yr": (target["pubmed_recent_2yr"], comp_pubmed_recent),
        "trends_avg_interest": (target["trends_avg_interest"] or 0, comp_trends),
        "fda_label_count": (target["fda_label_count"], comp_fda),
    }


def _strongest_competitor(competitors: list[dict]) -> dict | None:
    if not competitors:
        return None
    def score(c):
        return (c["trials_active"] * 2) + (c["pubmed_recent_2yr"]) + (c["trends_avg_interest"] or 0) / 10 + c["fda_label_count"]
    return max(competitors, key=score)


def build_swot(target_brand: str, competitor_brands: list[str], therapy_area: str = "", refresh: bool = True) -> dict:
    target = gather_brand_metrics(target_brand, refresh=refresh)
    competitors = [gather_brand_metrics(c, refresh=refresh) for c in competitor_brands if c.strip()]

    strengths, weaknesses, opportunities, threats = [], [], [], []

    if competitors:
        cmp = _build_comparisons(target, competitors)

        if cmp["trials_active"][0] > cmp["trials_active"][1]:
            strengths.append(
                f"More active clinical trial pipeline: {target['brand']} has {cmp['trials_active'][0]} active/recruiting trials vs. a {cmp['trials_active'][1]:.1f} average across competitors — signals stronger visible R&D investment."
            )
        elif cmp["trials_active"][0] < cmp["trials_active"][1]:
            weaknesses.append(
                f"Thinner active trial pipeline: {target['brand']} has {cmp['trials_active'][0]} active/recruiting trials vs. a {cmp['trials_active'][1]:.1f} average across competitors."
            )

        if cmp["trials_stopped"][0] > cmp["trials_stopped"][1]:
            weaknesses.append(
                f"Higher trial attrition: {target['brand']} has {cmp['trials_stopped'][0]} terminated/withdrawn/suspended trials vs. a {cmp['trials_stopped'][1]:.1f} average across competitors."
            )
        elif cmp["trials_stopped"][0] < cmp["trials_stopped"][1] and cmp["trials_stopped"][1] > 0:
            strengths.append(
                f"Lower trial attrition than competitors: {target['brand']} has {cmp['trials_stopped'][0]} stopped trials vs. a {cmp['trials_stopped'][1]:.1f} average — a more reliable evidence track record to lead with."
            )

        if cmp["pubmed_recent_2yr"][0] > cmp["pubmed_recent_2yr"][1]:
            strengths.append(
                f"Fresher scientific literature: {target['brand']} has {cmp['pubmed_recent_2yr'][0]} PubMed articles in the last 2 years vs. a {cmp['pubmed_recent_2yr'][1]:.1f} average across competitors — a stronger 'emerging evidence' narrative to lead with."
            )
        elif cmp["pubmed_recent_2yr"][0] < cmp["pubmed_recent_2yr"][1]:
            weaknesses.append(
                f"Less recent scientific literature: {target['brand']} has {cmp['pubmed_recent_2yr'][0]} PubMed articles in the last 2 years vs. a {cmp['pubmed_recent_2yr'][1]:.1f} average across competitors."
            )

        if cmp["trends_avg_interest"][0] < cmp["trends_avg_interest"][1]:
            weaknesses.append(
                f"Lower public search interest: {target['brand']}'s 12-month Google Trends average is {cmp['trends_avg_interest'][0]:.1f} vs. a {cmp['trends_avg_interest'][1]:.1f} average across competitors — an awareness/share-of-voice gap."
            )
        elif cmp["trends_avg_interest"][0] > cmp["trends_avg_interest"][1]:
            strengths.append(
                f"Higher public search interest: {target['brand']}'s 12-month Google Trends average is {cmp['trends_avg_interest'][0]:.1f} vs. a {cmp['trends_avg_interest'][1]:.1f} average across competitors."
            )

        if cmp["fda_label_count"][0] < cmp["fda_label_count"][1]:
            weaknesses.append(
                f"Narrower approved-label footprint: {target['brand']} has {cmp['fda_label_count'][0]} FDA label record(s) vs. a {cmp['fda_label_count'][1]:.1f} average across competitors — may indicate fewer approved indications or line extensions."
            )
        elif cmp["fda_label_count"][0] > cmp["fda_label_count"][1]:
            strengths.append(
                f"Broader approved-label footprint: {target['brand']} has {cmp['fda_label_count'][0]} FDA label record(s) vs. a {cmp['fda_label_count'][1]:.1f} average across competitors."
            )

        strongest = _strongest_competitor(competitors)
        if strongest:
            threats.append(
                f"{strongest['brand']} looks like the strongest competitor on current signals — {strongest['trials_active']} active trials, {strongest['pubmed_recent_2yr']} recent (2yr) publications, {strongest['trials_completed']} completed trials, and a Trends interest score of {strongest['trends_avg_interest'] or 'n/a'}. Its pipeline/evidence momentum is the one to watch most closely."
            )
        for c in competitors:
            if c["trials_stopped"] > 0:
                opportunities.append(
                    f"{c['brand']} has {c['trials_stopped']} stopped (terminated/withdrawn/suspended) trial(s) — a possible signal of a program setback worth monitoring for a messaging or evidence gap {target['brand']} could fill."
                )
    else:
        opportunities.append("No competitors supplied yet -- add competitor brand names to sharpen strengths/weaknesses into relative comparisons rather than absolute counts.")

    total_recent_pubmed = target["pubmed_recent_2yr"] + sum(c["pubmed_recent_2yr"] for c in competitors)
    if total_recent_pubmed > 0:
        opportunities.append(
            f"Category-wide scientific activity is live: {total_recent_pubmed} papers published across all brands in the last 2 years in this therapy area — an open window for unbranded disease-education content that captures the attention before competitors' branded follow-up."
        )
    if (target["trends_avg_interest"] or 0) < 20:
        opportunities.append(
            f"Overall public search interest in {target['brand']} is low (Trends avg {target['trends_avg_interest'] or 0:.1f}/100) — the whole category looks under-indexed on public digital reach, which rewards whoever invests first in owned-digital/unbranded content."
        )

    messaging_options, audience_options = generate_options(target, competitors, therapy_area)

    return {
        "target": target,
        "competitors": competitors,
        "swot": {
            "strengths": strengths or ["No clear quantitative strength detected yet from current signals -- refine with more competitors or a longer KB history."],
            "weaknesses": weaknesses or ["No clear quantitative weakness detected yet from current signals."],
            "opportunities": opportunities,
            "threats": threats or ["No standout competitor threat detected from current signals."],
        },
        "positioning_table": [target] + competitors,
        "messaging_options": messaging_options,
        "audience_options": audience_options,
        "caveat": "SWOT and positioning are derived from quantifiable public-data proxies (trial counts/status, FDA label count, PubMed recency, Google Trends interest) fetched live from public APIs -- not a substitute for a full competitive-intelligence or market-access review.",
    }


def generate_options(target: dict, competitors: list[dict], therapy_area: str) -> tuple[list[str], list[str]]:
    messaging_options: list[str] = []
    audience_options: list[str] = []

    comp_active_avg = _avg([c["trials_active"] for c in competitors]) if competitors else 0
    comp_trends_avg = _avg([c["trends_avg_interest"] for c in competitors]) if competitors else 0
    comp_fda_avg = _avg([c["fda_label_count"] for c in competitors]) if competitors else 0

    if target["trials_active"] >= comp_active_avg and target["trials_active"] > 0:
        messaging_options.append(
            "Pipeline-depth narrative: lead with 'active evidence generation' messaging (ongoing trials, expanding indications) rather than a static efficacy claim -- this is where the data currently favors you."
        )
        audience_options.append("Prioritize KOL/DOL and guideline-followers who respond to visible, ongoing evidence investment.")
    else:
        messaging_options.append(
            "Precision/specialization narrative: with a smaller visible trial footprint than competitors, lead with depth in the specific approved indication/patient subgroup rather than breadth-of-pipeline claims."
        )
        audience_options.append("Prioritize sub-specialists and high-decile writers in the precise approved indication rather than broad primary care reach.")

    if (target["trends_avg_interest"] or 0) < comp_trends_avg:
        messaging_options.append(
            "Category-awareness-first narrative: since public search interest trails competitors, open with unbranded disease-state/epidemiology messaging to build category awareness before brand-specific claims land."
        )
        audience_options.append("Weight targeting toward Unaware/Aware-stage HCPs and digital-first personas to close the awareness gap before investing in deeper-funnel messaging.")
    else:
        messaging_options.append(
            "Share-of-mind defense narrative: with stronger public awareness than competitors, prioritize retention/expansion messaging (broader patient-type use, real-world evidence) over basic awareness content."
        )
        audience_options.append("Weight targeting toward Adoption/Champion-stage HCPs already prescribing, to defend and expand share of mind.")

    if target["fda_label_count"] < comp_fda_avg:
        messaging_options.append(
            "Focused-claim narrative: with fewer approved-label records than competitors, avoid broad positioning claims and anchor messaging tightly to the specific approved indication and patient-selection criteria."
        )
    else:
        messaging_options.append(
            "Portfolio-breadth narrative: with a broader approved-label footprint than competitors, messaging can legitimately span multiple approved uses/patient types in the same campaign architecture."
        )

    if target["pubmed_recent_2yr"] > 0:
        audience_options.append("Include guideline-followers and academic/hospital-employed HCPs who weight recent peer-reviewed literature heavily in prescribing decisions.")

    if therapy_area:
        audience_options.append(f"Cross-check against real-world patient volume and referral patterns specific to '{therapy_area}' before finalizing target list -- these options are directional, not a validated segmentation.")

    return messaging_options, audience_options
