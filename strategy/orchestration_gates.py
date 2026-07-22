"""Engagement Orchestration -- gate / context integrations (PRD 6.5 F5.2, M5).

Veeva PromoMats and SFMC are NOT task targets (we never create generic tasks in them); they are
read/gate/context sources that drive gate status and the asset-expiry + AE/MIR nudge paths:

  Veeva PromoMats  -> AFU (approved-for-use) status, job code, and asset EXPIRY date. The expiry
                      date feeds the 30/60/90-day nudge (orchestration_nudge expiry hook).
  SFMC             -> journey/send state for execution-phase activities (deployed / live / paused).

Same stub-first shape as the connectors: a read-only provider interface with a StubVeeva /
StubSFMC that returns demonstrable context, and credential-gated real providers whose read bodies
are the wiring points. `apply_context` attaches the fetched context onto activities (afu_expiry /
send_state) so downstream schedule/nudge logic picks it up -- only when a provider is available, so
no fake expiry alerts appear while running on stubs by default.
"""
from __future__ import annotations

import datetime as _dt
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import orchestration_taxonomy as tax  # noqa: E402


class GateContextProvider:
    system = "base"

    def available(self) -> bool:
        return False

    def read(self, project_id: str, activity: dict) -> dict:
        """Return a context dict for this activity, e.g. {afu_expiry, job_code, send_state}."""
        return {}


class StubVeeva(GateContextProvider):
    """Demonstrable AFU/expiry context for content/scientific activities. Deterministic dates so a
    demo shows the expiry nudge path without a real Veeva connection. Only used when explicitly
    invoked (see apply_context)."""
    system = "veeva"

    def available(self) -> bool:
        return True

    def read(self, project_id, activity):
        tier = activity.get("compliance_tier")
        if tier not in (tax.TIER_FULL_MLR, tax.TIER_LIGHT):
            return {}
        # a stub expiry ~75 days out -- inside the 90-day prompt window, outside 30/60.
        expiry = (_dt.date.today() + _dt.timedelta(days=75)).isoformat()
        return {"afu_expiry": expiry, "job_code": f"JOB-{activity.get('id','')[:6].upper()}", "afu_status": "Approved for Use"}


class StubSFMC(GateContextProvider):
    """Demonstrable send/journey state for execution-phase activities."""
    system = "sfmc"

    def available(self) -> bool:
        return True

    def read(self, project_id, activity):
        if activity.get("phase") != tax.PHASE_EXECUTION:
            return {}
        return {"send_state": "Configured — not yet live"}


class _CredentialGateProvider(GateContextProvider):
    _env_keys: tuple[str, ...] = ()

    def available(self) -> bool:
        return all(os.getenv(k) for k in self._env_keys)


class VeevaProvider(_CredentialGateProvider):
    """Real Veeva PromoMats. Wiring point: query the document/binder for this activity's asset ->
    AFU status, job code, expiration_date__v. Map onto {afu_expiry, job_code, afu_status}."""
    system = "veeva"
    _env_keys = ("VEEVA_DNS", "VEEVA_USERNAME", "VEEVA_PASSWORD")

    def read(self, project_id, activity):  # pragma: no cover - wiring point
        raise NotImplementedError("Veeva read not implemented -- supply VAULT credentials, then map expiration_date__v -> afu_expiry.")


class SFMCProvider(_CredentialGateProvider):
    """Real SFMC. Wiring point: query Journey Builder / send state for the activity's journey."""
    system = "sfmc"
    _env_keys = ("SFMC_CLIENT_ID", "SFMC_CLIENT_SECRET", "SFMC_SUBDOMAIN")

    def read(self, project_id, activity):  # pragma: no cover - wiring point
        raise NotImplementedError("SFMC read not implemented -- supply API credentials, then map journey status -> send_state.")


# Providers: prefer the real credential-gated one when configured, else the stub. Set
# ORCHESTRATION_GATES_LIVE=1 to require real providers (stub disabled) in production.
def _providers() -> list[GateContextProvider]:
    live = os.getenv("ORCHESTRATION_GATES_LIVE") == "1"
    veeva_real, sfmc_real = VeevaProvider(), SFMCProvider()
    providers: list[GateContextProvider] = []
    providers.append(veeva_real if veeva_real.available() else (StubVeeva() if not live else veeva_real))
    providers.append(sfmc_real if sfmc_real.available() else (StubSFMC() if not live else sfmc_real))
    return [p for p in providers if p.available()]


def gate_context(project_id: str, activities: list[dict]) -> dict:
    """Per-activity gate context from all available providers. Read-only; does not mutate."""
    out: dict[str, dict] = {}
    provs = _providers()
    for a in activities:
        ctx: dict = {}
        for p in provs:
            try:
                ctx.update(p.read(project_id, a))
            except NotImplementedError:
                continue
        if ctx:
            out[a["id"]] = ctx
    return out


def apply_context(project_id: str, activities: list[dict]) -> list[dict]:
    """Attach gate context (afu_expiry / send_state / job_code) onto activities in place so the
    scheduler + nudge agent (expiry path) pick it up. Returns the same list."""
    ctx = gate_context(project_id, activities)
    for a in activities:
        c = ctx.get(a["id"])
        if c:
            a.update(c)
    return activities
