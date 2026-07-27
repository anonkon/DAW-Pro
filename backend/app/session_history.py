from __future__ import annotations

import logging

from pydantic import BaseModel

from .config import settings
from .schemas import FrequencyBand, Severity

logger = logging.getLogger("dawpro.session_history")

# How many past analyses in this session/project to look back over - same
# style as MAX_TIMING_EVENTS/MAX_TRANSIENT_EVENTS in the pipeline modules.
SESSION_HISTORY_LOOKBACK = 5

# Band-agnostic issues (no related_band) have no reliable dedup key across
# independent LLM calls, so they're capped by recency rather than deduped.
MAX_BAND_AGNOSTIC_ISSUES = 3
MAX_HISTORY_ISSUES = 5


class SessionHistoryIssue(BaseModel):
    """An issue raised in an earlier analysis of this project.

    Not part of the AnalysisResult contract - this is prompt-construction
    context for chain.py, not a dashboard-visible measurement. Carries the
    band's measured value both at the time the issue was raised and now (when
    available) rather than a resolved/ignored verdict: the model compares the
    two numbers itself and says what changed, the same way it's asked to
    ground every other claim.
    """

    title: str
    description: str
    severity: Severity
    related_band: str | None = None
    analyses_ago: int
    flagged_project_db: float | None = None
    flagged_reference_db: float | None = None
    current_project_db: float | None = None
    current_reference_db: float | None = None


def build_session_history(session_id: str, current_eq: list[FrequencyBand]) -> list[SessionHistoryIssue]:
    """Recent issues raised earlier in this project, for prompt continuity."""
    if not (settings.supabase_url and settings.supabase_service_key):
        return []

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_key)
        response = (
            client.table("analysis_results")
            .select("created_at, result")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(SESSION_HISTORY_LOOKBACK)
            .execute()
        )
        rows = response.data or []
    except Exception:  # noqa: BLE001
        logger.exception("failed to fetch session history for session %s", session_id)
        return []

    return _summarize_issues(rows, current_eq)


def _summarize_issues(rows: list[dict], current_eq: list[FrequencyBand]) -> list[SessionHistoryIssue]:
    """Pure grouping/dedup logic, kept separate from the Supabase fetch above
    so it's testable with a fabricated rows list and no live database."""
    current_by_band = {band.label: band for band in current_eq}

    seen_bands: set[str] = set()
    band_agnostic_count = 0
    summarized: list[SessionHistoryIssue] = []

    for analyses_ago, row in enumerate(rows, start=1):
        result = row.get("result") or {}
        issues = result.get("issues") or []
        eq_comparison = (result.get("measurements") or {}).get("eq_comparison") or []
        flagged_by_band = {band["label"]: band for band in eq_comparison if "label" in band}

        for issue in issues:
            related_band = issue.get("related_band")

            if related_band is None:
                if band_agnostic_count >= MAX_BAND_AGNOSTIC_ISSUES:
                    continue
                band_agnostic_count += 1
            else:
                if related_band in seen_bands:
                    continue
                seen_bands.add(related_band)

            flagged = flagged_by_band.get(related_band, {})
            current = current_by_band.get(related_band)

            summarized.append(
                SessionHistoryIssue(
                    title=issue.get("title", ""),
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "info"),
                    related_band=related_band,
                    analyses_ago=analyses_ago,
                    flagged_project_db=flagged.get("project_db"),
                    flagged_reference_db=flagged.get("reference_db"),
                    current_project_db=current.project_db if current else None,
                    current_reference_db=current.reference_db if current else None,
                )
            )
            if len(summarized) >= MAX_HISTORY_ISSUES:
                return summarized

    return summarized
