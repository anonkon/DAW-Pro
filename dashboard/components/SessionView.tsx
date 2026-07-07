"use client";

import { useMemo, useState } from "react";
import { submitAnalysis } from "@/lib/api";
import { usePollJob } from "@/hooks/usePollJob";
import type { AnalysisResult, AnalyzeSource, Session } from "@/lib/types";
import { Waveform } from "./Waveform";
import { EqComparisonChart } from "./EqComparisonChart";
import { ChatPanel } from "./ChatPanel";

export function SessionView({
  session,
  initialResult,
}: {
  session: Session;
  initialResult: AnalysisResult | null;
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

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 space-y-6">
      <h1 className="text-lg font-semibold">{session.project_name}</h1>

      {audioUrl && <Waveform audioUrl={audioUrl} />}

      <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-sm font-medium text-zinc-300">Upload audio</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex gap-2 text-sm">
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={source === "reference_upload"}
                onChange={() => setSource("reference_upload")}
              />
              Reference track
            </label>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={source === "plugin_capture"}
                onChange={() => setSource("plugin_capture")}
              />
              My project audio
            </label>
          </div>

          <input
            type="file"
            accept="audio/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />

          <input
            placeholder="Sonic intention (e.g. modern trap beat, wide low end)"
            value={sonicIntention}
            onChange={(e) => setSonicIntention(e.target.value)}
            required
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-500"
          />
          <input
            placeholder="Genre (optional)"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-500"
          />

          <button
            type="submit"
            disabled={submitting || isInFlight}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            {submitting ? "Uploading..." : "Analyze"}
          </button>

          {error && <p className="text-sm text-red-400">{error}</p>}
          {isInFlight && (
            <p className="text-sm text-zinc-400">
              {job?.status.replace("_", " ")}... ({Math.round((job?.progress ?? 0) * 100)}%)
            </p>
          )}
          {job?.status === "failed" && (
            <p className="text-sm text-red-400">Analysis failed: {job.error}</p>
          )}
        </form>
      </section>

      {result && (
        <div className="grid gap-6 sm:grid-cols-2">
          <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <h2 className="text-sm font-medium text-zinc-300">Comparative EQ</h2>
            <EqComparisonChart bands={result.eq_comparison} />
          </section>
          <section className="space-y-3">
            <h2 className="text-sm font-medium text-zinc-300">Mentor feedback</h2>
            <ChatPanel result={result} />
          </section>
        </div>
      )}
    </main>
  );
}
