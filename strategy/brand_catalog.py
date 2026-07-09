"""Fixed brand -> therapy-area -> indications catalog (config/client_brands.json).

A brand maps to a single therapy area (occasionally a broad umbrella area); the
variable dimension is the INDICATION. This module is the lookup the conversation
layer uses so that, once a brand is named, the agent can auto-fill the (fixed)
therapy area and offer the brand's indications as explicit choices rather than
asking therapy area as an open free-text question.
"""
from __future__ import annotations

import json
import pathlib

_CATALOG_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "client_brands.json"

_BY_NAME: dict[str, dict] = {}


def _load() -> None:
    if _BY_NAME:
        return
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- catalog is optional; unknown brands just fall back to free-text TA
        return
    for client, brands in data.get("clients", {}).items():
        for b in brands:
            _BY_NAME[b["brand"].strip().lower()] = {
                "brand": b["brand"],
                "client": client,
                "generic": b.get("generic", ""),
                "therapy_area": b.get("therapy_area", ""),
                "indications": list(b.get("indications", [])),
                "lifecycle_key": b.get("lifecycle_key", ""),
            }


def lookup_brand(name: str) -> dict | None:
    """Case-insensitive exact-name lookup; None for brands not in the catalog."""
    if not name:
        return None
    _load()
    return _BY_NAME.get(name.strip().lower())


def all_brand_names() -> list[str]:
    _load()
    return sorted(v["brand"] for v in _BY_NAME.values())
