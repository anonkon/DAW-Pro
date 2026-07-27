from __future__ import annotations

import asyncio
import logging

from .ai.chain import analyze as ai_analyze
from .personas import get_persona
from .pipeline.demucs_separate import separate_stems
from .pipeline.features import extract_features
from .results_store import save_analysis_result
from .schemas import AnalysisResult, AnalyzeRequest, JobStatus
from .storage import save_audio, workspace_dir

logger = logging.getLogger("dawpro.jobs")

JOB_STORE: dict[str, JobStatus] = {}

# Reference-track features are session-scoped: extracted once on upload, reused
# for every subsequent plugin-capture analysis in that session.
_REFERENCE_FEATURE_CACHE: dict[str, dict] = {}


def _set(job_id: str, **kwargs) -> None:
    JOB_STORE[job_id] = JOB_STORE[job_id].model_copy(update=kwargs)


async def run_pipeline(job_id: str, request: AnalyzeRequest, audio_bytes: bytes, filename: str) -> None:
    try:
        _set(job_id, status="queued", progress=0.05)
        local_path = await asyncio.to_thread(save_audio, request.session_id, filename, audio_bytes)

        _set(job_id, status="separating_stems", progress=0.2)
        stem_dir = workspace_dir(request.session_id) / "stems" / job_id
        stems = await asyncio.to_thread(separate_stems, local_path, stem_dir)

        _set(job_id, status="extracting_features", progress=0.55)
        # The DAW's own tempo, when the plugin sent it. Timing is scored against
        # this rather than a grid estimated from the audio - see features._timing.
        project_features = await asyncio.to_thread(extract_features, str(local_path), request.bpm)
        stem_features = {}
        for name, path in stems.items():
            stem_features[name] = await asyncio.to_thread(extract_features, str(path), request.bpm)
        project_features["stems"] = stem_features

        if request.source == "reference_upload":
            _REFERENCE_FEATURE_CACHE[request.session_id] = project_features
        reference_features = _REFERENCE_FEATURE_CACHE.get(request.session_id, {})

        _set(job_id, status="analyzing", progress=0.8)
        persona = await asyncio.to_thread(get_persona, request.persona_id)
        result: AnalysisResult = await asyncio.to_thread(
            ai_analyze,
            project_features,
            reference_features,
            persona,
            request.sonic_intention,
            request.genre,
            request.bpm,
            request.session_id,
        )

        _set(job_id, status="done", progress=1.0, result=result)
        await asyncio.to_thread(save_analysis_result, request.session_id, job_id, result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("pipeline failed for job %s", job_id)
        _set(job_id, status="failed", error=str(exc))
