"""CMS Open Payments general-payment scraper.

Open Payments files are very large, so this scraper uses CMS' DKAN query API and
pulls only bounded, brand-matched rows for configured oncology priority brands.
"""
from __future__ import annotations

import json
import pathlib
import re
import time
from typing import Any

import requests

from storage import get_db, save_blob, upsert_document

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SEEDS_PATH = BASE_DIR / "config" / "pharma_intel_seed_terms.json"
METASTORE_URL = "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items"
QUERY_URL = "https://openpaymentsdata.cms.gov/api/1/datastore/query/{dataset_id}/0"
USER_AGENT = "OmniDataHubResearchBot/0.1 (+local research; bounded CMS Open Payments queries)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

PRODUCT_FIELDS = [
    "name_of_drug_or_biological_or_device_or_medical_supply_1",
    "name_of_drug_or_biological_or_device_or_medical_supply_2",
    "name_of_drug_or_biological_or_device_or_medical_supply_3",
    "name_of_drug_or_biological_or_device_or_medical_supply_4",
    "name_of_drug_or_biological_or_device_or_medical_supply_5",
]

PROPERTIES = [
    "record_id",
    "covered_recipient_type",
    "covered_recipient_profile_id",
    "covered_recipient_npi",
    "covered_recipient_first_name",
    "covered_recipient_middle_name",
    "covered_recipient_last_name",
    "recipient_city",
    "recipient_state",
    "recipient_country",
    "covered_recipient_primary_type_1",
    "covered_recipient_specialty_1",
    "submitting_applicable_manufacturer_or_applicable_gpo_name",
    "applicable_manufacturer_or_applicable_gpo_making_payment_name",
    "total_amount_of_payment_usdollars",
    "date_of_payment",
    "form_of_payment_or_transfer_of_value",
    "nature_of_payment_or_transfer_of_value",
    "contextual_information",
    "related_product_indicator",
    "product_category_or_therapeutic_area_1",
    "name_of_drug_or_biological_or_device_or_medical_supply_1",
    "product_category_or_therapeutic_area_2",
    "name_of_drug_or_biological_or_device_or_medical_supply_2",
    "product_category_or_therapeutic_area_3",
    "name_of_drug_or_biological_or_device_or_medical_supply_3",
    "product_category_or_therapeutic_area_4",
    "name_of_drug_or_biological_or_device_or_medical_supply_4",
    "product_category_or_therapeutic_area_5",
    "name_of_drug_or_biological_or_device_or_medical_supply_5",
    "program_year",
    "payment_publication_date",
]


def _latest_general_dataset() -> dict[str, Any]:
    resp = requests.get(METASTORE_URL, params={"show-reference-ids": "true", "page-size": 100}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("value", []) if isinstance(payload, dict) else payload
    candidates: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title", ""))
        match = re.match(r"(\d{4})\s+General Payment Data", title)
        if not match:
            continue
        dist = (item.get("distribution") or [{}])[0].get("data", {})
        candidates.append(
            {
                "dataset_id": item.get("identifier", ""),
                "distribution_id": (item.get("distribution") or [{}])[0].get("identifier", ""),
                "year": int(match.group(1)),
                "title": title,
                "issued": item.get("issued", ""),
                "modified": item.get("modified", ""),
                "download_url": dist.get("downloadURL", ""),
                "dictionary_url": dist.get("describedBy", ""),
            }
        )
    if not candidates:
        raise RuntimeError("No General Payment Data dataset found in CMS Open Payments metastore")
    return sorted(candidates, key=lambda row: row["year"], reverse=True)[0]


def _query_brand(dataset_id: str, brand: str, per_field_limit: int, product_slots: int = 1) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    url = QUERY_URL.format(dataset_id=dataset_id)
    for field in PRODUCT_FIELDS[: max(1, min(product_slots, len(PRODUCT_FIELDS)))]:
        params: dict[str, Any] = {
            "limit": str(per_field_limit),
            "conditions[0][property]": field,
            "conditions[0][operator]": "contains",
            "conditions[0][value]": brand,
        }
        for idx, prop in enumerate(PROPERTIES):
            params[f"properties[{idx}]"] = prop
        resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if resp.status_code in {400, 404}:
            # Dataset schemas occasionally change. Keep other product slots alive.
            continue
        resp.raise_for_status()
        payload = resp.json()
        for row in payload.get("results", []):
            record_id = str(row.get("record_id") or "").strip()
            if record_id:
                row["matched_product_field"] = field
                rows_by_id[record_id] = row
        time.sleep(0.15)
    return list(rows_by_id.values())


def run(brands: list[str] | None = None, per_brand_limit: int = 25, max_brands: int | None = None, product_slots: int = 1) -> int:
    if brands is None:
        seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
        brands = seeds.get("priority_oncology_brands", [])
    if max_brands:
        brands = brands[:max_brands]

    dataset = _latest_general_dataset()
    conn = get_db()
    saved = 0
    try:
        metadata_blob = save_blob("open_payments", f"general_payments_{dataset['year']}_dataset.json", json.dumps(dataset, indent=2))
        upsert_document(
            conn,
            source="cms_open_payments:dataset",
            external_id=f"general_payments_{dataset['year']}",
            search_term="CMS Open Payments",
            title=dataset["title"],
            doc_type="open_payments_dataset_metadata",
            url=f"https://openpaymentsdata.cms.gov/dataset/{dataset['dataset_id']}",
            blob_path=metadata_blob,
            metadata=dataset,
        )
        saved += 1

        for brand in brands:
            try:
                rows = _query_brand(dataset["dataset_id"], brand, per_brand_limit, product_slots=product_slots)
                blob_path = save_blob(
                    "open_payments",
                    f"general_payments_{dataset['year']}_{brand.lower().replace(' ', '_')}.json",
                    json.dumps({"dataset": dataset, "brand": brand, "rows": rows}, indent=2),
                )
                upsert_document(
                    conn,
                    source="cms_open_payments:general_payments",
                    external_id=f"{dataset['year']}_{brand.lower()}",
                    search_term=brand,
                    title=f"CMS Open Payments general payments for {brand} ({dataset['year']})",
                    doc_type="open_payments_general_payments",
                    url=f"https://openpaymentsdata.cms.gov/dataset/{dataset['dataset_id']}",
                    blob_path=blob_path,
                    metadata={
                        "brand": brand,
                        "program_year": dataset["year"],
                        "row_count": len(rows),
                        "dataset_id": dataset["dataset_id"],
                        "download_url": dataset["download_url"],
                    },
                )
                saved += 1
                print(f"[open_payments] {brand}: {len(rows)} rows")
            except Exception as exc:
                print(f"[open_payments] {brand}: FAILED ({exc})")
            time.sleep(0.2)
    finally:
        conn.close()
    return saved


if __name__ == "__main__":
    run(max_brands=12, product_slots=1)
