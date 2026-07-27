import type { ReactNode } from "react";

type Tone = "neutral" | "good" | "warning" | "critical";

const TONE: Record<Tone, string> = {
  neutral: "var(--text-primary)",
  good: "var(--accent)",
  warning: "var(--status-warning)",
  critical: "var(--status-critical)",
};

/** A single measured number. No plot, so no hover layer - the value is the
 *  whole content and it is already legible. */
export function StatTile({
  label,
  value,
  unit,
  tone = "neutral",
  note,
  meter,
}: {
  label: string;
  value: string | number | null;
  unit?: string;
  tone?: Tone;
  note?: ReactNode;
  /** 0..1, draws a bar underneath. */
  meter?: number | null;
}) {
  const unavailable = value === null || value === undefined;

  return (
    <div className="rounded border border-line bg-surface-panel p-4">
      <p className="label-caps">{label}</p>
      <p className="mt-2 font-mono text-2xl" style={{ color: unavailable ? "var(--text-muted)" : TONE[tone] }}>
        {unavailable ? "—" : value}
        {!unavailable && unit && <span className="ml-1 text-sm text-ink-muted">{unit}</span>}
      </p>
      {meter != null && !unavailable && (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-surface-raised">
          <div
            className="h-full rounded-full"
            style={{ width: `${Math.min(Math.max(meter, 0), 1) * 100}%`, background: TONE[tone] }}
          />
        </div>
      )}
      {note && <p className="mt-2 text-label text-ink-muted">{note}</p>}
    </div>
  );
}
