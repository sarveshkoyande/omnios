"""First-boot data seeding for an empty data directory (a fresh persistent disk on Render,
or any machine where DATA_DIR does not yet exist).

Why this exists: the app's databases live under DATA_DIR (see paths.py), which is
gitignored and therefore absent on a fresh deploy. On a *persistent* disk that only
matters once -- the first boot -- after which the disk retains everything. This module
makes that first boot self-sufficient and fully offline:

  1. seed_kb()      -- copy the committed read-only knowledge base (assets/seed/omni_kb.db)
                       and competitor-intel checkpoint into DATA_DIR if missing. The KB is
                       never written at runtime, so a committed snapshot is the right shape.
  2. seed_library() -- when the campaign/content library is empty, rebuild it from the
                       committed inputs (KB seed + config JSON + the committed label-image
                       seed under assets/label_images). Uses the existing idempotent
                       builders; no network required.

Everything is idempotent: `run()` does real work only when something is actually missing,
so it is safe to call on every startup.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sqlite3
import sys
import threading
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "strategy"))
from paths import DATA_DIR, data_path, ensure_data_dir  # noqa: E402

SEED_DIR = ROOT / "assets" / "seed"
_SEED_FILES = ["omni_kb.db", "client_brand_intel.json"]
_KB_REQUIRED_OBJECTS = {
    "documents",
    "pharma_source",
    "brand_message",
    "regulatory_label_message",
    "v_oncology_brand_evidence_summary",
    "cms_open_payment_general",
    "openfda_event_reaction_count",
}

_seeding = threading.Lock()


def _sqlite_has_objects(path: pathlib.Path, names: set[str]) -> bool:
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(path)
        try:
            found = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name IN (%s)"
                    % ",".join("?" for _ in names),
                    tuple(names),
                )
            }
            return names.issubset(found)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _kb_needs_refresh(src: pathlib.Path, dst: pathlib.Path) -> bool:
    if not dst.exists():
        return True
    if not _sqlite_has_objects(dst, _KB_REQUIRED_OBJECTS):
        return True
    return src.exists() and src.stat().st_size > dst.stat().st_size and _sqlite_has_objects(src, _KB_REQUIRED_OBJECTS)


def seed_kb() -> list[str]:
    """Copy committed read-only seed files into DATA_DIR when absent. Returns what it copied."""
    ensure_data_dir()
    copied = []
    for name in _SEED_FILES:
        # The knowledge base is ALWAYS local SQLite now, regardless of DATABASE_URL
        # (strategy/db.py's LOCAL_ONLY_STORES) -- it's large, committed-seed reference data,
        # not per-run output, and loading it into a free-tier managed Postgres in one shot is
        # what previously locked a Prisma Postgres database (see POSTGRES_MIGRATION.md). This
        # used to skip copying the KB file whenever DATABASE_URL was set (back when the KB was
        # meant to live IN Postgres) -- that's now stale and must NOT skip, or the KB file
        # never lands on a fresh Render disk and every KB reader 500s on "no such table".
        src, dst = SEED_DIR / name, data_path(name)
        needs_copy = _kb_needs_refresh(src, dst) if name == "omni_kb.db" else not dst.exists()
        if src.exists() and needs_copy:
            shutil.copy2(src, dst)
            copied.append(name)
    return copied


def library_is_empty() -> bool:
    try:
        import campaign_store
        stats = campaign_store.library_stats()
        return not (stats.get("campaigns") or stats.get("claims") or stats.get("content_assets"))
    except Exception:  # noqa: BLE001 -- if we can't tell, treat as empty so seeding is attempted
        return True


def _load_builder(script_name: str):
    """Import a scripts/*.py module by path (they aren't a package)."""
    spec = importlib.util.spec_from_file_location(script_name, ROOT / "scripts" / f"{script_name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seed_library() -> dict:
    """Rebuild the content library + label images from committed inputs (offline)."""
    result = {}
    import awards_store
    import brand_lifecycle
    result["awards"] = awards_store.load_awards()
    result["market_intel"] = brand_lifecycle.load_market_intel()
    result["content_library"] = _load_builder("build_content_library").build()
    result["label_images"] = _load_builder("fetch_label_images").build()
    return result


def run(background: bool = True) -> dict:
    """Idempotent boot seeding. seed_kb() runs synchronously (fast, and the KB must exist
    before anything reads it); the heavier library rebuild runs only when the library is
    empty, in a background thread by default so the web server binds immediately."""
    ensure_data_dir()
    out = {"data_dir": str(DATA_DIR), "kb_copied": seed_kb(), "library": "present"}

    import hcp_360
    out["hcp_360"] = hcp_360.load_hcp_360()

    if not library_is_empty():
        return out

    def _work():
        if not _seeding.acquire(blocking=False):
            return
        try:
            print("[bootstrap] empty library detected -- rebuilding from committed seeds...")
            res = seed_library()
            print(f"[bootstrap] library seeded: {res}")
        except Exception:  # noqa: BLE001 -- never crash startup on a seeding failure
            print("[bootstrap] library seeding failed:\n" + traceback.format_exc())
        finally:
            _seeding.release()

    if background:
        threading.Thread(target=_work, name="omni-bootstrap", daemon=True).start()
        out["library"] = "seeding (background)"
    else:
        _work()
        out["library"] = "seeded"
    return out


if __name__ == "__main__":
    print(run(background=False))
