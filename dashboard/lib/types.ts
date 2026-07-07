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
}

export interface AnalysisResult {
  summary: string;
  eq_comparison: FrequencyBand[];
  timing_markers: TimingMarker[];
  issues: MixIssue[];
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
