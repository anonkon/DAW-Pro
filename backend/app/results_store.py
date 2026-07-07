from __future__ import annotations

import logging

from .config import settings
from .schemas import AnalysisResult

logger = logging.getLogger("dawpro.results_store")


def save_analysis_result(session_id: str, job_id: str, result: AnalysisResult) -> None:
    """Persist a completed analysis to Supabase for the dashboard's session
    history (see dashboard/app/session/[id]/page.tsx). No-ops if Supabase
    isn't configured yet - the in-memory job store already has the result
    for the current session's polling, this is only for later retrieval."""
    if not (settings.supabase_url and settings.supabase_service_key):
        return

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_key)
        client.table("analysis_results").insert(
            {
                "session_id": session_id,
                "job_id": job_id,
                "result": result.model_dump(),
            }
        ).execute()
    except Exception:  # noqa: BLE001
        logger.exception("failed to persist analysis result for job %s to Supabase", job_id)
