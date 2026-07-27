# JSON Contract

This is the schema every other layer builds against. Fix this before writing backend or dashboard code — it's what lets [[04-backend-engine]], [[05-ai-brain]], and [[06-dashboard]] be built in parallel instead of sequentially. Referenced from [[00-overview]].

Canonical definition lives as Pydantic models in `backend/app/schemas.py`; the dashboard mirrors them as TypeScript types in `dashboard/lib/types.ts`. Keep both in sync manually — at this scale a shared codegen step (e.g. `datamodel-code-generator` or `openapi-typescript` off FastAPI's auto-generated OpenAPI spec) is a nice-to-have, not a blocker.

## `POST /analyze` — request

Multipart form, sent either by the plugin (captured audio) or the dashboard (reference track upload).

```python
class AnalyzeRequest(BaseModel):
    session_id: str
    persona_id: str
    sonic_intention: str          # free text, e.g. "modern trap beat, wide low end"
    genre: str | None = None
    source: Literal["plugin_capture", "reference_upload"]
    bpm: float | None = None      # from plugin's AudioPlayHead, if source == plugin_capture
    time_signature: str | None = None
# + file: UploadFile (WAV)
```

## `POST /analyze` — response (immediate)

```python
class AnalyzeAccepted(BaseModel):
    job_id: str
    status: Literal["queued"]
```

## `GET /jobs/{job_id}` — polled response

```python
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
    progress: float              # 0.0-1.0, coarse (one step = one stage above)
    error: str | None = None
    result: "AnalysisResult | None" = None   # populated only when status == "done"
```

## `AnalysisResult` — measurements plus the AI's reading of them

Split in two. **Measurements** are computed in `backend/app/pipeline/` and never
touch the model. **Narrative** is Gemini's entire structured-output surface (via
LangChain, see [[05-ai-brain]]). The dashboard renders both (see [[06-dashboard]]).

### Measured — computed, never generated

```python
class FrequencyBand(BaseModel):
    label: str            # e.g. "low", "low-mid", "mid", "high-mid", "high"
    hz_low: float
    hz_high: float
    project_db: float     # RMS energy in this band for the user's project
    reference_db: float   # same, for the reference track

class SpectrumPoint(BaseModel):
    hz: float
    db: float

class SpectrumComparison(BaseModel):
    project: list[SpectrumPoint]      # 64 log-spaced points, 20Hz-20kHz
    reference: list[SpectrumPoint]

class TimingEvent(BaseModel):
    reference_sec: float
    project_sec: float | None = None
    delta_ms: float | None = None     # positive = project hit is late
    severity: Literal["info", "warning", "critical"] = "info"

class TimingAnalysis(BaseModel):
    rhythmic_cohesion: float | None = None    # 0-100, phase concentration on the grid
    timing_offset_ms: float | None = None     # systematic; positive = behind
    timing_scatter_ms: float | None = None    # looseness around that offset
    grid_source: Literal["host_bpm", "estimated"] | None = None
    events: list[TimingEvent] = []

class PhaseAnalysis(BaseModel):
    correlation: float | None = None   # -1..+1 L/R Pearson; None when source is mono
    verdict: Literal["mono", "in_phase", "wide", "problematic"] | None = None

class Loudness(BaseModel):
    peak_db: float | None = None
    rms_db: float | None = None
    crest_factor_db: float | None = None      # peak_db - rms_db
    integrated_lufs: float | None = None
    short_term_lufs: float | None = None      # representative value, not a time series
    true_peak_dbtp: float | None = None
    loudness_range_lu: float | None = None    # LRA; simplified derivation, see pipeline/features.py

class LoudnessComparison(BaseModel):
    project: Loudness
    reference: Loudness

class StereoWidthBand(BaseModel):
    label: str
    hz_low: float
    hz_high: float
    width_db: float    # side energy relative to mid energy; positive = wider than centred

class TransientEvent(BaseModel):
    onset_sec: float
    attack_ms: float   # 10-90% envelope rise time

class StemSummary(BaseModel):
    band_energy_db: dict[str, float] = {}
    loudness: Loudness = Loudness()

class Measurements(BaseModel):
    eq_comparison: list[FrequencyBand]
    spectrum: SpectrumComparison
    timing: TimingAnalysis
    phase: PhaseAnalysis
    loudness: LoudnessComparison
    stereo_width: list[StereoWidthBand] = []
    transients: list[TransientEvent] = []
    key: str | None = None
    key_confidence: float | None = None
    reference_key: str | None = None              # same detection, run on the reference track
    reference_key_confidence: float | None = None
    tempo_bpm: float | None = None
    stems: dict[str, StemSummary] = {}    # per Demucs stem (drums/bass/vocals/other), when separation succeeded
```

### Narrative — the model's whole output surface

```python
class MixIssue(BaseModel):
    title: str
    description: str       # guidance-toward-exploration tone, not a prescriptive fix
    severity: Literal["info", "warning", "critical"]
    related_band: str | None = None   # references FrequencyBand.label, if applicable
    hz_low: float | None = None       # anchors the callout onto the spectrum curve
    hz_high: float | None = None

class MentorNarrative(BaseModel):
    summary: str                          # short chat-bubble-style message
    issues: list[MixIssue] = []
    suggested_exploration: str | None = None   # one thing to try, as an invitation
    suggested_path: str | None = None          # short label for that direction
```

### Combined

```python
class AnalysisResult(BaseModel):
    summary: str
    issues: list[MixIssue] = []
    suggested_exploration: str | None = None
    suggested_path: str | None = None
    measurements: Measurements
    eq_comparison: list[FrequencyBand] = []   # also at top level; predates measurements
    timing_markers: list[TimingMarker] = []
    mix_score: float | None = None
```

## Design notes

- **Guardrail is structural, not just prompted:** `MixIssue.description` is documented as "guidance-toward-exploration," matching the poster's stated philosophy ("we would never give a user specific instructions unless instructed to do so"). Enforced in the Gemini system prompt ([[05-ai-brain]]), but calling it out here keeps the contract self-documenting.
- **The model is never asked for a measurement.** Its structured output is `MentorNarrative`, not `AnalysisResult`. Anything numeric — band energies, cohesion, phase, peaks — is computed and handed to it as context. An LLM asked to emit `project_db` can only guess, and a plausible fabricated number is worse than no number.
- **`eq_comparison` is a fixed small band list** (5 bands) for the model to reason over; `spectrum` carries the 64-point curve the dashboard draws. Two resolutions, two purposes.
- **Timing is scored against the host BPM when available.** The plugin forwards Ableton's tempo, which is authoritative. A grid inferred from the audio drifts along with whatever timing error is being measured, making the result circular — `grid_source` records which was used so the dashboard can qualify the reading.
- **Cohesion and offset are separate numbers.** A part sitting consistently behind the beat is tight and intentional; random scatter is not. Collapsing both into one "timing accuracy" figure would call them the same thing.
- **`null` means not measurable, not zero.** A null `phase.correlation` means the source was mono, where the measurement is undefined — distinct from a measured `0.0`, which means a fully decorrelated stereo field. The same discipline applies to `key`/`key_confidence` (low-confidence best-fit correlations are dropped to `null` rather than guessed) and to loudness fields on very short/silent audio.
- **`stems` finally uses Demucs's per-instrument output.** `jobs.py` already runs stem separation and extracts features per stem; `stems` is where that per-instrument data reaches the model, so it can name which instrument a problem lives in instead of only which frequency band.
- **`progress` is coarse (stage-based), not fine-grained.** A real percentage would require instrumenting Demucs/Librosa internals for marginal UX gain — not worth it at this scope.
- **`job_id` is a UUID string**, generated by the backend on `POST /analyze`, used as the in-memory job-store key (see [[04-backend-engine]]).
- **No tuple fields anywhere in this schema.** `FrequencyBand` uses `hz_low`/`hz_high` floats rather than a `hz_range` tuple — Pydantic serializes tuples to JSON Schema via `prefixItems`, which Gemini's structured-output schema format (a restricted OpenAPI subset) doesn't support. Keep this in mind before adding new fields: stick to primitives, plain lists, and objects.
