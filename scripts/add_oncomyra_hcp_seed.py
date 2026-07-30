"""Append a deterministic synthetic Oncomyra HCP cohort to config/hcp_360 JSON seeds.

The HCP 360 loader treats the JSON files as the source of truth for both local SQLite and
Prisma Postgres. This script keeps the seed idempotent: it removes any prior Oncomyra
synthetic cohort, then appends 538 HCPs and their related rows across all six tables.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config" / "hcp_360"
sys.path.insert(0, str(BASE_DIR / "strategy"))
import segment_labels  # noqa: E402  (SEGMENT_MIX owns the panel's segment shape)
COHORT_SIZE = 538
NPI_START = 190_000_000
SOURCE_OBJECT = "omnios_oncomyra_hcp_360"
SOURCE = "OMNIOS_SYNTHETIC"
LAST_REFRESH = "2026-07-26T00:00:00+00:00"


def _load(name: str) -> list[dict]:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def _write(name: str, rows: list[dict]) -> None:
    (CONFIG_DIR / name).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _npi_check_digit(first_9_digits: str) -> int:
    digits = [int(ch) for ch in "80840" + first_9_digits]
    total = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - (total % 10)) % 10


def _npi(offset: int) -> int:
    first_9 = f"{NPI_START + offset:09d}"
    return int(first_9 + str(_npi_check_digit(first_9)))


def _filter_out_oncomyra(rows: list[dict], npi_keys: tuple[str, ...] = ()) -> list[dict]:
    out = []
    for row in rows:
        if row.get("DataSourceObject__c") == SOURCE_OBJECT:
            continue
        if row.get("brand__c") == "Oncomyra":
            continue
        if npi_keys and any(str(row.get(key, "")).startswith(str(NPI_START)) for key in npi_keys):
            continue
        out.append(row)
    return out


def _choice_cycle(values: list, idx: int):
    return values[idx % len(values)]


def _score(rng: random.Random, base: int = 5) -> int:
    return max(0, min(10, int(round(rng.gauss(base, 2)))))


def _rank(value: int, high_label: str, med_label: str, low_label: str) -> str:
    if value >= 75:
        return high_label
    if value >= 40:
        return med_label
    if value > 0:
        return low_label
    return "0"


def main() -> None:
    rng = random.Random(426026)
    first_names = [
        "ALEX", "AMARA", "ANIKA", "BENJAMIN", "CAMILA", "DANIEL", "ELENA", "FARAH",
        "GABRIEL", "HANA", "ISAAC", "JULIA", "KIRAN", "LENA", "MARCUS", "NADIA",
        "OMAR", "PRIYA", "RAHUL", "SARA", "TARA", "VICTOR", "YARA", "ZOE",
    ]
    last_names = [
        "ADLER", "BANERJEE", "CHEN", "DIAZ", "ELLIS", "FOSTER", "GARCIA", "HASSAN",
        "IYER", "JOHNSON", "KAPOOR", "LEE", "MARTINEZ", "NGUYEN", "OKAFOR", "PATEL",
        "QUINN", "RIVERA", "SINGH", "THOMPSON", "USMAN", "VAZQUEZ", "WALKER", "YOUNG",
    ]
    markets = [
        ("NY", "NEW YORK", "10016"),
        ("CA", "SAN FRANCISCO", "94143"),
        ("TX", "HOUSTON", "77030"),
        ("MA", "BOSTON", "02115"),
        ("IL", "CHICAGO", "60612"),
        ("PA", "PHILADELPHIA", "19104"),
        ("FL", "MIAMI", "33136"),
        ("WA", "SEATTLE", "98195"),
        ("NC", "DURHAM", "27710"),
        ("OH", "CLEVELAND", "44195"),
    ]
    specialties = (
        ["Medical Oncology"] * 180
        + ["Hematology/Oncology"] * 140
        + ["Pulmonology"] * 90
        + ["Urology"] * 50
        + ["Radiation Oncology"] * 40
    )
    channels = ["Email", "Digital", "EHR", "Prog", "Tele"]
    content_tags = [
        "Efficacy Data",
        "Biomarker Testing",
        "Treatment Guidelines",
        "Safety Profile",
        "Dosing & Administration",
        "Clinical Trial Updates",
        "Peer Perspectives",
        "Access & Reimbursement",
        "Real World Evidence",
        "Adverse Event Management",
        "MOA",
        "Patient Support Programs",
    ]
    personas = ["New Writer", "Consistent Writer", "Occasional Writer", "Emergers", "Lapsed Writer"]
    trx_classes = [
        "ANTINEOPLASTIC TARGETED THERAPY",
        "ANTINEOPLASTIC IMMUNOTHERAPY",
        "ANTINEOPLASTIC CHEMOTHERAPY",
        "RESPIRATORY AGENTS",
        "SUPPORTIVE ONCOLOGY CARE",
    ]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    sessions = ["Morning", "Afternoon", "ooo_hours"]

    demo = _filter_out_oncomyra(_load("hcp_demographic_data__dlm.json"), ("npi_number__c",))
    channel = _filter_out_oncomyra(_load("global_channel_affinity_and_preference.json"), ("npi_number__c",))
    content = _filter_out_oncomyra(_load("global_content_affinity_score_data.json"), ("npi_num__c",))
    trx = _filter_out_oncomyra(_load("tbl_trx_therapeutic_data__dlm.json"), ("npi_number__c",))
    day_time = _filter_out_oncomyra(_load("global_day_time_preference_data.json"), ("npi_num__c",))
    tl = _filter_out_oncomyra(_load("tbl_tl_data__dlm.json"), ("npi_id__c",))

    for idx in range(COHORT_SIZE):
        npi = _npi(idx)
        first = _choice_cycle(first_names, idx)
        last = _choice_cycle(last_names, idx * 7)
        state, city, zip_code = _choice_cycle(markets, idx)
        specialty = _choice_cycle(specialties, idx)
        preferred_channel = _choice_cycle(channels, idx * 3)
        top_tag = _choice_cycle(content_tags, idx)
        second_tag = _choice_cycle(content_tags, idx + 4)
        third_tag = _choice_cycle(content_tags, idx + 8)
        # Weighted, not round-robin: cycling the list gave every segment an identical share.
        segment = segment_labels.pick_segment(rng)
        persona = _choice_cycle(personas, idx + 2)
        product_score = rng.randint(25, 98)
        market_score = rng.randint(20, 95)
        ros1_score = rng.randint(20, 90)
        digital_score = _score(rng, 7 if preferred_channel in ("Digital", "Email") else 5)
        email_score = _score(rng, 8 if preferred_channel == "Email" else 5)
        ehr_score = _score(rng, 8 if preferred_channel == "EHR" else 5)
        prog_score = _score(rng, 8 if preferred_channel == "Prog" else 5)
        tele_score = _score(rng, 8 if preferred_channel == "Tele" else 5)
        no_contact = "Y" if idx % 47 == 0 else "N"

        demo.append({
            "DataSourceObject__c": SOURCE_OBJECT,
            "DataSource__c": SOURCE,
            "InternalOrganization__c": None,
            "KQ_npi_number__c": None,
            "address__c": f"{100 + idx} ONCOMYRA CARE WAY",
            "age__c": None,
            "ama_no_contact__c": no_contact,
            "ama_pdrp_date__c": None,
            "ama_pdrp_flag__c": no_contact,
            "city__c": city,
            "credential_desc__c": "MD" if idx % 9 else "DO",
            "email__c": f"{first.lower()}.{last.lower()}.{idx}@oncomyra-hcp.example",
            "first_name__c": first,
            "full_name__c": f"{last} {first}",
            "gender__c": "F" if idx % 2 == 0 else "M",
            "last_name__c": last,
            "last_refresh_date__c": LAST_REFRESH,
            "me_number__c": None,
            "npi_number__c": npi,
            "phone_number__c": f"+1 555-{idx // 100:03d}-{idx % 10000:04d}",
            "practitioner_type_desc__c": "HCP",
            "primary_corp_specialty_desc__c": None,
            "primary_specialty_description__c": specialty,
            "rel_id__c": None,
            "spi_number__c": None,
            "state_code__c": state,
            "state_name__c": None,
            "zip_code__c": int(zip_code),
        })

        channel.append({
            "DataSourceObject__c": SOURCE_OBJECT,
            "DataSource__c": SOURCE,
            "InternalOrganization__c": None,
            "KQ_npi_number__c": None,
            "digitalscore_raw__c": digital_score,
            "ehrscore_raw__c": ehr_score,
            "emailscore_raw__c": email_score,
            "last_refresh_date__c": "2026-07-26",
            "npi_number__c": npi,
            "preferred_channel__c": preferred_channel,
            "progscore_raw__c": prog_score,
            "telescore_raw__c": tele_score,
        })

        content.append({
            "DataSourceObject__c": SOURCE_OBJECT,
            "DataSource__c": SOURCE,
            "InternalOrganization__c": None,
            "KQ_npi_num__c": None,
            "last_refresh_date__c": LAST_REFRESH,
            "month__c": "2026-07-01",
            "most_preferred_content_tag__c": top_tag,
            "npi_num__c": npi,
            "second_most_preferred_content_tag__c": second_tag,
            "third_most_preferred_content_tag__c": third_tag,
        })

        day_order = [_choice_cycle(days, idx), _choice_cycle(days, idx + 1), _choice_cycle(days, idx + 2)]
        session_order = [_choice_cycle(sessions, idx), _choice_cycle(sessions, idx + 1), _choice_cycle(sessions, idx + 2)]
        dt_row = {
            "DataSourceObject__c": SOURCE_OBJECT,
            "DataSource__c": SOURCE,
            "InternalOrganization__c": None,
            "KQ_npi_num__c": None,
            "last_refresh_date__c": LAST_REFRESH,
            "month__c": "2026-07-01",
            "npi_num__c": npi,
        }
        for channel_name in ["ehr", "email", "prog", "rte", "tele"]:
            for rank, day_value, session_value in [
                ("most", day_order[0], session_order[0]),
                ("second_most", day_order[1], session_order[1]),
                ("third_most", day_order[2], session_order[2]),
            ]:
                dt_row[f"{rank}_preferred_day_{channel_name}__c"] = day_value
                dt_row[f"{rank}_preferred_session_{channel_name}__c"] = session_value
                dt_row[f"{rank}_preferred_day_session_{channel_name}__c"] = f"{day_value}_{session_value}"
        day_time.append(dt_row)

        tl.append({
            "DataSourceObject__c": SOURCE_OBJECT,
            "DataSource__c": SOURCE,
            "InternalOrganization__c": None,
            "KQ_npi_id__c": None,
            "acc_affiliation_units_tier_non_writers__c": 0 if idx % 5 else rng.randint(1, 3),
            "ama_no_contact__c": no_contact,
            "besponsa_writer__c": 0,
            "bosulif_writers__c": 0,
            "brand__c": "Oncomyra",
            "digital_affinity__c": _rank(digital_score * 10, "1. High DA", "2. Med DA", "3. Low DA"),
            "duavee_writer__c": 0,
            "estring_writer__c": 0,
            "eucrisa_writers__c": 0,
            "last_refresh_date__c": LAST_REFRESH,
            "market_trx_tier__c": _rank(market_score, "1. High TRx Tier", "2. Med TRx Tier", "3. Low TRx Tier"),
            "mylotarg_writer__c": 0,
            "npi_id__c": npi,
            "nsclc_trx_tier__c": _rank(product_score, "1. High TRx Tier", "2. Med TRx Tier", "3. Low TRx Tier"),
            "number_of_brands_writer__c": 1 if idx % 7 else 2,
            "practitioner_first_name__c": first,
            "practitioner_last_name__c": last,
            "practitioner_state__c": state,
            "premarin_writer__c": 0,
            "prempro_writer__c": 0,
            "primary_specialty_desc__c": specialty.upper(),
            "product_trx_tier__c": _rank(product_score, "1. High TRx Tier", "2. Med TRx Tier", "3. Low TRx Tier"),
            "rep_potential__c": _rank(rng.randint(15, 95), "1. High Potential", "2. Med Potential", "3. Low Potential"),
            "rep_tier__c": _rank(rng.randint(15, 95), "1. High See", "2. Med See", "3. Low See"),
            "revenue_potential__c": rng.randint(15000, 260000),
            "ros1_trx_tier__c": _rank(ros1_score, "1. High TRx Tier", "2. Med TRx Tier", "3. Low TRx Tier"),
            "segment__c": segment,
            "writing_persona__c": persona,
            "xalkori_writer__c": 0,
        })

        for trx_idx, trx_class in enumerate(trx_classes[: 2 + (idx % 4 == 0)]):
            trx.append({
                "DataSourceObject__c": SOURCE_OBJECT,
                "DataSource__c": SOURCE,
                "InternalOrganization__c": None,
                "KQ_npi_number__c": None,
                "bb_usc_desc2__c": trx_class,
                "last_refresh_date__c": LAST_REFRESH,
                "npi_number__c": npi,
                "trx_count__c": max(1, product_score * (3 - trx_idx) + rng.randint(0, 40)),
            })

    _write("hcp_demographic_data__dlm.json", demo)
    _write("global_channel_affinity_and_preference.json", channel)
    _write("global_content_affinity_score_data.json", content)
    _write("tbl_trx_therapeutic_data__dlm.json", trx)
    _write("global_day_time_preference_data.json", day_time)
    _write("tbl_tl_data__dlm.json", tl)

    print({
        "oncomyra_hcps": COHORT_SIZE,
        "totals": {
            "hcp_demographic_data__dlm": len(demo),
            "global_channel_affinity_and_preference": len(channel),
            "global_content_affinity_score_data": len(content),
            "tbl_trx_therapeutic_data__dlm": len(trx),
            "global_day_time_preference_data": len(day_time),
            "tbl_tl_data__dlm": len(tl),
        },
    })


if __name__ == "__main__":
    main()
