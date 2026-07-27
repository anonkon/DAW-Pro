from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warning", "critical"]


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


# --- Measured values -------------------------------------------------------
# Everything below is computed in pipeline/, never produced by the LLM. The
# model is told about these numbers so it can reason over them; it is not asked
# to emit them, because it can only guess at a measurement.


class FrequencyBand(BaseModel):
    label: str
    hz_low: float
    hz_high: float
    project_db: float
    reference_db: float


class SpectrumPoint(BaseModel):
    hz: float
    db: float


class SpectrumComparison(BaseModel):
    """Log-spaced spectra for the overlaid curve view."""

    project: list[SpectrumPoint] = []
    reference: list[SpectrumPoint] = []


class TimingEvent(BaseModel):
    """One reference onset paired with the nearest project onset."""

    reference_sec: float
    project_sec: float | None = None
    delta_ms: float | None = None  # positive = project is late
    severity: Severity = "info"


class TimingAnalysis(BaseModel):
    rhythmic_cohesion: float | None = None  # 0-100, phase concentration
    timing_offset_ms: float | None = None  # systematic; positive = behind
    timing_scatter_ms: float | None = None  # looseness around that offset
    grid_source: Literal["host_bpm", "estimated"] | None = None
    events: list[TimingEvent] = []


class PhaseAnalysis(BaseModel):
    correlation: float | None = None  # -1..+1, None when the source is mono
    verdict: Literal["mono", "in_phase", "wide", "problematic"] | None = None


class Loudness(BaseModel):
    peak_db: float | None = None
    rms_db: float | None = None
    crest_factor_db: float | None = None  # peak_db - rms_db; low means little dynamic range left
    integrated_lufs: float | None = None
    short_term_lufs: float | None = None  # representative short-term value, not a time series
    true_peak_dbtp: float | None = None
    loudness_range_lu: float | None = None  # LRA; see pipeline/features.py for the simplified derivation


class LoudnessComparison(BaseModel):
    project: Loudness = Loudness()
    reference: Loudness = Loudness()


class StereoWidthBand(BaseModel):
    label: str
    hz_low: float
    hz_high: float
    width_db: float  # side-energy relative to mid-energy; positive = wider than centred


class TransientEvent(BaseModel):
    onset_sec: float
    attack_ms: float  # 10%-90% envelope rise time


class StemSummary(BaseModel):
    """Per-instrument breakdown from Demucs stem separation."""

    band_energy_db: dict[str, float] = {}
    loudness: Loudness = Loudness()


class Measurements(BaseModel):
    eq_comparison: list[FrequencyBand] = []
    spectrum: SpectrumComparison = SpectrumComparison()
    timing: TimingAnalysis = TimingAnalysis()
    phase: PhaseAnalysis = PhaseAnalysis()
    loudness: LoudnessComparison = LoudnessComparison()
    stereo_width: list[StereoWidthBand] = []
    transients: list[TransientEvent] = []
    key: str | None = None
    key_confidence: float | None = None
    reference_key: str | None = None
    reference_key_confidence: float | None = None
    tempo_bpm: float | None = None
    stems: dict[str, StemSummary] = {}


# --- Narrative -------------------------------------------------------------
# The LLM's entire structured output surface. Prose and judgement only.


class MixIssue(BaseModel):
    title: str
    description: str
    severity: Severity
    related_band: str | None = None
    hz_low: float | None = None  # anchors the callout onto the spectrum curve
    hz_high: float | None = None


class MentorNarrative(BaseModel):
    summary: str
    issues: list[MixIssue] = []
    suggested_exploration: str | None = None
    suggested_path: str | None = None


# --- Combined result -------------------------------------------------------


class TimingMarker(BaseModel):
    time_sec: float
    label: str
    severity: Severity


class AnalysisResult(BaseModel):
    # narrative, from the model
    summary: str
    issues: list[MixIssue] = []
    suggested_exploration: str | None = None
    suggested_path: str | None = None

    # measured, from the pipeline
    measurements: Measurements = Measurements()

    # eq_comparison stays at the top level: it predates measurements and the
    # dashboard still reads it there.
    eq_comparison: list[FrequencyBand] = []
    timing_markers: list[TimingMarker] = []
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


# --- Plugin-facing listings -------------------------------------------------
# The plugin has no Supabase client, so it reads these through the backend.


class SessionSummary(BaseModel):
    id: str
    project_name: str
    persona_id: str
    created_at: str | None = None


class AnalysisEntry(BaseModel):
    job_id: str | None = None
    created_at: str | None = None
    summary: str | None = None
    rhythmic_cohesion: float | None = None
