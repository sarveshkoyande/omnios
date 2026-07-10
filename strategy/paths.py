"""Central data-directory resolution.

Every SQLite database and the blob store live under ONE root so it can be redirected to a
persistent disk on a host whose own filesystem is ephemeral (e.g. Render, where the
container disk -- including the repo checkout -- is thrown away on every deploy and every
restart, so anything written next to the code does not survive).

  * Local dev:   <repo>/data           (unchanged -- no env var needed)
  * Production:  set OMNI_DATA_DIR to the mounted persistent disk, e.g. /var/data

Nothing else in the app knows where the data lives: modules ask for `data_path("x.db")`.
This is also the single seam a future Postgres/object-store backend slots behind
(see POSTGRES_MIGRATION.md).
"""
from __future__ import annotations

import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv_value(key: str) -> str:
    """Read one key from <repo>/.env without a dependency, so OMNI_DATA_DIR can be set
    there for local testing the same way the LLM credentials are. A real environment
    variable always wins (checked first by the caller)."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return ""
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


_env = (os.environ.get("OMNI_DATA_DIR") or _load_dotenv_value("OMNI_DATA_DIR")).strip()
DATA_DIR = pathlib.Path(_env).expanduser() if _env else (BASE_DIR / "data")


def data_path(*parts: str) -> pathlib.Path:
    """Absolute path to a file/dir under the data root (does not create anything)."""
    return DATA_DIR.joinpath(*parts)


def ensure_data_dir() -> pathlib.Path:
    """Create the data root if missing and return it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
