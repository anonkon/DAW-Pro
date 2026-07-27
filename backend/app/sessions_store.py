from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger("dawpro.sessions_store")


def _client():
    if not (settings.supabase_url and settings.supabase_service_key):
        return None
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_key)


def list_sessions(limit: int = 50) -> list[dict]:
    """Sessions for the plugin's picker, so nobody has to paste a UUID.

    NOTE: this reads with the service key, which bypasses row-level security,
    so it returns every account's sessions. That is acceptable only because the
    backend is a localhost single-user service today and /analyze already
    accepts any session_id without authenticating. Before this is exposed off
    localhost the plugin needs to authenticate and this must be scoped to the
    caller's account_id - see docs/plan/02-accounts-and-personas.md.
    """
    client = _client()
    if client is None:
        return []

    try:
        response = (
            client.table("sessions")
            .select("id, project_name, persona_id, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:  # noqa: BLE001
        logger.exception("failed to list sessions from Supabase")
        return []


def list_analyses(session_id: str, limit: int = 10) -> list[dict]:
    """Recent analyses for one session, trimmed to what the plugin displays."""
    client = _client()
    if client is None:
        return []

    try:
        response = (
            client.table("analysis_results")
            .select("job_id, created_at, result")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to list analyses for session %s", session_id)
        return []

    entries = []
    for row in response.data or []:
        result = row.get("result") or {}
        measurements = result.get("measurements") or {}
        timing = measurements.get("timing") or {}
        entries.append(
            {
                "job_id": row.get("job_id"),
                "created_at": row.get("created_at"),
                "summary": result.get("summary"),
                "rhythmic_cohesion": timing.get("rhythmic_cohesion"),
            }
        )
    return entries
