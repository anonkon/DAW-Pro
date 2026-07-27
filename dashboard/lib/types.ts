// Mirrors backend/app/schemas.py. Keep in sync manually - see docs/plan/01-json-contract.md.

export type Severity = "info" | "warning" | "critical";
export type SkillLevel = "beginner" | "intermediate" | "advanced";
export type FeedbackTone = "guided" | "direct" | "technical";
export type AnalyzeSource = "plugin_capture" | "reference_upload";

export interface FrequencyBand {
  label: string;
  hz_low: number;
  hz_high: number;
  project_db: number;
  reference_db: number;
}

export interface TimingMarker {
  time_sec: number;
  label: string;
  severity: Severity;
}

export interface MixIssue {
  title: string;
  description: string;
  severity: Severity;
  related_band: string | null;
  /** Anchors the callout onto the spectrum curve when the issue is frequency-specific. */
  hz_low: number | null;
  hz_high: number | null;
}

// --- Measured values -------------------------------------------------------
// Computed in the pipeline, never produced by the LLM.

export interface SpectrumPoint {
  hz: number;
  db: number;
}

export interface SpectrumComparison {
  project: SpectrumPoint[];
  reference: SpectrumPoint[];
}

export interface TimingEvent {
  reference_sec: number;
  project_sec: number | null;
  /** Positive means the project hit is late. Null when nothing matched. */
  delta_ms: number | null;
  severity: Severity;
}

export interface TimingAnalysis {
  /** 0-100 phase concentration around the grid. */
  rhythmic_cohesion: number | null;
  /** Systematic offset; positive is behind the beat. */
  timing_offset_ms: number | null;
  /** Looseness around that offset. */
  timing_scatter_ms: number | null;
  grid_source: "host_bpm" | "estimated" | null;
  events: TimingEvent[];
}

export interface PhaseAnalysis {
  /** -1..+1. Null when the source is mono. */
  correlation: number | null;
  verdict: "mono" | "in_phase" | "wide" | "problematic" | null;
}

export interface Loudness {
  peak_db: number | null;
  rms_db: number | null;
}

export interface LoudnessComparison {
  project: Loudness;
  reference: Loudness;
}

export interface Measurements {
  eq_comparison: FrequencyBand[];
  spectrum: SpectrumComparison;
  timing: TimingAnalysis;
  phase: PhaseAnalysis;
  loudness: LoudnessComparison;
  tempo_bpm: number | null;
}

export interface AnalysisResult {
  // narrative, from the model
  summary: string;
  issues: MixIssue[];
  suggested_exploration: string | null;
  suggested_path: string | null;

  // measured, from the pipeline
  measurements: Measurements;

  eq_comparison: FrequencyBand[];
  timing_markers: TimingMarker[];
  mix_score: number | null;
}

export type JobState =
  | "queued"
  | "separating_stems"
  | "extracting_features"
  | "analyzing"
  | "done"
  | "failed";

export interface JobStatus {
  job_id: string;
  status: JobState;
  progress: number;
  error: string | null;
  result: AnalysisResult | null;
}

export interface AnalyzeAccepted {
  job_id: string;
  status: "queued";
}

export interface Persona {
  id: string;
  account_id: string;
  name: string;
  skill_level: SkillLevel;
  preferred_genres: string[];
  feedback_tone: FeedbackTone;
}

export interface Session {
  id: string;
  account_id: string;
  persona_id: string;
  project_name: string;
  reference_track_s3_key: string | null;
  created_at: string;
}
