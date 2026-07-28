"use client";

import { useMemo, useState } from "react";
import { submitAnalysis } from "@/lib/api";
import { usePollJob } from "@/hooks/usePollJob";
import type { AnalysisResult, AnalyzeSource, Session } from "@/lib/types";
import { Waveform } from "./Waveform";
import { SpectrumChart } from "./SpectrumChart";
import { TimingGrid } from "./TimingGrid";
import { LoudnessCompare } from "./LoudnessCompare";
import { StereoWidthChart } from "./StereoWidthChart";
import { TransientAttackChart } from "./TransientAttackChart";
import { StemsBreakdown } from "./StemsBreakdown";
import { MentorRail } from "./MentorRail";
import { StatTile } from "./StatTile";
import { Panel } from "./Panel";

const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  separating_stems: "Separating stems",
  extracting_features: "Extracting features",
  analyzing: "Analyzing",
};

export function SessionView({
  session,
  initialResult,
  nav,
}: {
  session: Session;
  initialResult: AnalysisResult | null;
  /** Rendered on the server and passed in as a slot, so the nav's data
   *  fetching stays out of this client component. */
  nav?: React.ReactNode;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<AnalyzeSource>("reference_upload");
  const [sonicIntention, setSonicIntention] = useState("");
  const [genre, setGenre] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const audioUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  const job = usePollJob(jobId);
  const result = job?.result ?? initialResult;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose an audio file first.");
      return;
    }
    setSubmitting(true);
    try {
      const accepted = await submitAnalysis({
        file,
        sessionId: session.id,
        personaId: session.persona_id,
        sonicIntention,
        source,
        genre: genre || undefined,
      });
      setJobId(accepted.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit analysis.");
    } finally {
      setSubmitting(false);
    }
  };

  const isInFlight = job !== null && job.status !== "done" && job.status !== "failed";
  const m = result?.measurements;
  const hasReference = (m?.spectrum.reference.length ?? 0) > 0;

  return (
    <div
      className={`grid min-h-screen grid-cols-1 ${
        nav ? "lg:grid-cols-[240px_1fr_360px]" : "lg:grid-cols-[1fr_360px]"
      }`}
    >
      {nav}
      <main className="min-w-0 space-y-5 p-6">
        <header>
          <h1 className="text-display font-bold tracking-tight text-ink-primary">
            Comparative Mentorship
          </h1>
          <p className="mt-1 text-small text-ink-secondary">
            {session.project_name}
            {m?.tempo_bpm ? ` · ${Math.round(m.tempo_bpm)} BPM` : ""}
          </p>
        </header>

        <Panel title="Analyze">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex flex-wrap gap-4 text-small">
              {(
                [
                  ["reference_upload", "Reference track"],
                  ["plugin_capture", "My project audio"],
                ] as const
              ).map(([value, label]) => (
                <label key={value} className="flex items-center gap-2">
                  <input
                    type="radio"
                    checked={source === value}
                    onChange={() => setSource(value)}
                    className="accent-[var(--accent)]"
                  />
                  {label}
                </label>
              ))}
            </div>

            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-small text-ink-secondary file:mr-3 file:rounded file:border-0 file:bg-surface-raised file:px-3 file:py-1.5 file:text-small file:text-ink-primary"
            />

            <input
              placeholder="Sonic intention (e.g. modern trap beat, wide low end)"
              value={sonicIntention}
              onChange={(e) => setSonicIntention(e.target.value)}
              required
              className="w-full rounded border border-line bg-surface-raised px-3 py-2 text-small outline-none focus:border-accent"
            />
            <input
              placeholder="Genre (optional)"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              className="w-full rounded border border-line bg-surface-raised px-3 py-2 text-small outline-none focus:border-accent"
            />

            <button
              type="submit"
              disabled={submitting || isInFlight}
              className="rounded bg-accent px-4 py-2 text-small font-semibold text-ink-onAccent shadow-accent transition-colors hover:bg-accent-hover disabled:opacity-40 disabled:shadow-none"
            >
              {submitting ? "Uploading…" : "Analyze"}
            </button>

            {error && <p className="text-small text-status-critical">{error}</p>}
            {isInFlight && job && (
              <div>
                <p className="text-small text-ink-secondary">
                  {STAGE_LABEL[job.status] ?? job.status}… {Math.round(job.progress * 100)}%
                </p>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-raised">
                  <div
                    className="h-full rounded-full transition-[width]"
                    style={{ width: `${job.progress * 100}%`, background: "var(--accent)" }}
                  />
                </div>
              </div>
            )}
            {job?.status === "failed" && (
              <p className="text-small text-status-critical">Analysis failed: {job.error}</p>
            )}
          </form>
        </Panel>

        {audioUrl && (
          <Panel title="Waveform">
            <Waveform audioUrl={audioUrl} />
          </Panel>
        )}

        {result && m && (
          <>
            <Panel
              title="Frequency spectrum analyzer"
              aside={
                <span className="text-label text-ink-muted">
                  {hasReference ? "Project vs reference" : "Project only"}
                </span>
              }
            >
              <SpectrumChart
                spectrum={m.spectrum}
                issues={result.issues}
                hasReference={hasReference}
              />
            </Panel>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label="Rhythmic cohesion"
                value={m.timing.rhythmic_cohesion?.toFixed(1) ?? null}
                unit="%"
                tone={cohesionTone(m.timing.rhythmic_cohesion)}
                meter={m.timing.rhythmic_cohesion == null ? null : m.timing.rhythmic_cohesion / 100}
                note={m.timing.grid_source === "estimated" ? "Grid estimated from audio" : undefined}
              />
              <StatTile
                label="Timing offset"
                value={m.timing.timing_offset_ms?.toFixed(0) ?? null}
                unit="ms"
                tone="neutral"
                note={
                  m.timing.timing_offset_ms == null
                    ? undefined
                    : m.timing.timing_offset_ms > 0
                      ? "Behind the grid"
                      : "Ahead of the grid"
                }
              />
              <StatTile
                label="Timing scatter"
                value={m.timing.timing_scatter_ms?.toFixed(0) ?? null}
                unit="ms"
                tone="neutral"
                note="Looseness around the offset"
              />
              <StatTile
                label="Phase alignment"
                value={m.phase.verdict === "mono" ? "Mono" : (m.phase.correlation?.toFixed(2) ?? null)}
                tone={phaseTone(m.phase.verdict)}
                note={PHASE_NOTE[m.phase.verdict ?? "none"]}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label="Integrated loudness"
                value={m.loudness.project.integrated_lufs?.toFixed(1) ?? null}
                unit="LUFS"
                tone="neutral"
                note="Target depends on genre"
              />
              <StatTile
                label="Loudness range"
                value={m.loudness.project.loudness_range_lu?.toFixed(1) ?? null}
                unit="LU"
                tone="neutral"
              />
              <StatTile
                label="True peak"
                value={m.loudness.project.true_peak_dbtp?.toFixed(1) ?? null}
                unit="dBTP"
                tone={truePeakTone(m.loudness.project.true_peak_dbtp)}
                note={
                  m.loudness.project.true_peak_dbtp != null && m.loudness.project.true_peak_dbtp > 0
                    ? "Over full scale"
                    : undefined
                }
              />
              <StatTile
                label="Crest factor"
                value={m.loudness.project.crest_factor_db?.toFixed(1) ?? null}
                unit="dB"
                tone={crestFactorTone(m.loudness.project.crest_factor_db)}
                note="Peak-to-RMS gap"
              />
              <StatTile
                label="Detected key"
                value={m.key ?? null}
                tone="neutral"
                note={m.key_confidence != null ? `${Math.round(m.key_confidence * 100)}% confidence` : undefined}
              />
              {hasReference && (
                <StatTile
                  label="Reference key"
                  value={m.reference_key ?? null}
                  tone="neutral"
                  note={
                    m.reference_key_confidence != null
                      ? `${Math.round(m.reference_key_confidence * 100)}% confidence`
                      : undefined
                  }
                />
              )}
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <Panel title="Loudness">
                <LoudnessCompare loudness={m.loudness} hasReference={hasReference} />
              </Panel>
              <Panel title="Timing sync" aside={<span className="text-label text-ink-muted">16th grid</span>}>
                <TimingGrid timing={m.timing} tempoBpm={m.tempo_bpm} />
              </Panel>
            </div>

            {(m.stereo_width.length > 0 || m.transients.length > 0) && (
              <div className="grid gap-5 lg:grid-cols-2">
                <Panel title="Stereo width" aside={<span className="text-label text-ink-muted">side vs mid, per band</span>}>
                  <StereoWidthChart bands={m.stereo_width} />
                </Panel>
                <Panel
                  title="Transient attack"
                  aside={<span className="text-label text-ink-muted">{m.transients.length} onsets</span>}
                >
                  <TransientAttackChart transients={m.transients} />
                </Panel>
              </div>
            )}

            {Object.keys(m.stems).length > 0 && (
              <Panel
                title="Stem breakdown"
                aside={<span className="text-label text-ink-muted">{Object.keys(m.stems).length} stems</span>}
              >
                <StemsBreakdown stems={m.stems} />
              </Panel>
            )}
          </>
        )}
      </main>

      <MentorRail result={result} />
    </div>
  );
}

const PHASE_NOTE: Record<string, string | undefined> = {
  mono: "Mono source — nothing to measure",
  in_phase: "Sums cleanly to mono",
  wide: "Wide stereo image",
  problematic: "Partial cancellation in mono",
  none: undefined,
};

function cohesionTone(v: number | null): "neutral" | "good" | "warning" | "critical" {
  if (v == null) return "neutral";
  if (v >= 70) return "good";
  if (v >= 45) return "warning";
  return "critical";
}

function phaseTone(v: string | null): "neutral" | "good" | "warning" | "critical" {
  if (v === "problematic") return "critical";
  if (v === "in_phase") return "good";
  return "neutral";
}

// Mirrors backend/app/knowledge/retrieval.py CREST_FACTOR_LOW_THRESHOLD_DB
// (6dB) and the "<4dB reads flat/fatiguing" figure in technique_crest_factor
// - same thresholds, not separately invented for the UI.
function crestFactorTone(db: number | null | undefined): "neutral" | "good" | "warning" | "critical" {
  if (db == null) return "neutral";
  if (db < 4) return "critical";
  if (db < 6) return "warning";
  return "good";
}

// -1 dBTP is the ceiling this app's own knowledge base cites for every
// seeded genre (see knowledge/base.py). Above 0 dBTP is over full scale.
function truePeakTone(dbtp: number | null | undefined): "neutral" | "good" | "warning" | "critical" {
  if (dbtp == null) return "neutral";
  if (dbtp > 0) return "critical";
  if (dbtp > -1) return "warning";
  return "good";
}
