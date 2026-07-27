import type { AnalysisResult } from "@/lib/types";

const SEVERITY: Record<string, { fg: string; bg: string }> = {
  info: { fg: "var(--status-info)", bg: "var(--status-info-bg)" },
  warning: { fg: "var(--status-warning)", bg: "var(--status-warning-bg)" },
  critical: { fg: "var(--status-critical)", bg: "var(--status-critical-bg)" },
};

export function MentorRail({ result }: { result: AnalysisResult | null }) {
  return (
    <aside className="flex h-full flex-col gap-5 border-l border-line bg-surface-panel p-5">
      <header className="flex items-center gap-3">
        <span
          className="flex h-9 w-9 items-center justify-center rounded-lg border font-semibold"
          style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
        >
          D
        </span>
        <div>
          <p className="font-semibold text-ink-primary">DAWpro</p>
          <p className="label-caps" style={{ color: result ? "var(--accent)" : undefined }}>
            {result ? "Analysis ready" : "Ready to assist"}
          </p>
        </div>
      </header>

      {!result && (
        <p className="text-small text-ink-muted">
          Upload a reference track or capture from the plugin, and the analysis will appear here.
        </p>
      )}

      {result && (
        <div className="flex-1 space-y-4 overflow-y-auto">
          <Bubble>{result.summary}</Bubble>

          {/* Frequency-anchored issues are rendered as callouts on the spectrum
              chart, where they can point at the band they describe. Repeating
              them here would say the same thing twice. */}
          {result.issues
            .filter((issue) => issue.hz_low == null || issue.hz_high == null)
            .map((issue, i) => {
              const tone = SEVERITY[issue.severity] ?? SEVERITY.info;
              return (
                <div
                  key={i}
                  className="rounded border-l-2 px-3 py-2"
                  style={{ background: tone.bg, borderColor: tone.fg }}
                >
                  <div className="flex items-baseline gap-2">
                    <span className="label-caps" style={{ color: tone.fg }}>
                      {issue.severity}
                    </span>
                    <span className="text-small font-medium text-ink-primary">{issue.title}</span>
                  </div>
                  <p className="mt-1 text-small text-ink-secondary">{issue.description}</p>
                </div>
              );
            })}

          {result.suggested_exploration && (
            <section>
              <p className="label-caps" style={{ color: "var(--accent)" }}>
                Suggested exploration
              </p>
              <div
                className="mt-2 rounded border-l-2 px-3 py-3 text-small text-ink-secondary"
                style={{ borderColor: "var(--accent)", background: "var(--accent-dim)" }}
              >
                {result.suggested_exploration}
                {result.suggested_path && (
                  <p className="label-caps mt-3" style={{ color: "var(--accent)" }}>
                    {result.suggested_path}
                  </p>
                )}
              </div>
            </section>
          )}

          {result.mix_score !== null && (
            <section>
              <div className="flex items-baseline justify-between">
                <span className="label-caps">Mix score</span>
                <span className="font-mono text-ink-primary">{result.mix_score}</span>
              </div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-raised">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(Math.max(result.mix_score, 0), 100)}%`,
                    background: "var(--accent)",
                  }}
                />
              </div>
            </section>
          )}
        </div>
      )}
    </aside>
  );
}

function Bubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded rounded-tl-none border border-line bg-surface-raised px-4 py-3 text-small text-ink-primary">
      {children}
    </div>
  );
}
