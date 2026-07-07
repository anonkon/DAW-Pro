from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    session_id: str
    persona_id: str
    sonic_intention: str
    genre: str | None = None
    source: Literal["plugin_capture", "reference_upload"]
    bpm: float | None = None
    time_signature: str | None = None


class AnalyzeAccepted(BaseModel):
    job_id: str
    status: Literal["queued"]


class FrequencyBand(BaseModel):
    label: str
    hz_low: float
    hz_high: float
    project_db: float
    reference_db: float


class TimingMarker(BaseModel):
    time_sec: float
    label: str
    severity: Literal["info", "warning", "critical"]


class MixIssue(BaseModel):
    title: str
    description: str
    severity: Literal["info", "warning", "critical"]
    related_band: str | None = None


class AnalysisResult(BaseModel):
    summary: str
    eq_comparison: list[FrequencyBand]
    timing_markers: list[TimingMarker]
    issues: list[MixIssue]
    mix_score: float | None = None


class JobStatus(BaseModel):
    job_id: str
    status: Literal[
        "queued",
        "separating_stems",
        "extracting_features",
        "analyzing",
        "done",
        "failed",
    ]
    progress: float = 0.0
    error: str | None = None
    result: AnalysisResult | None = None


class Persona(BaseModel):
    id: str
    skill_level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    preferred_genres: list[str] = []
    feedback_tone: Literal["guided", "direct", "technical"] = "guided"
