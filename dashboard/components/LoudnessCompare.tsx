import type { LoudnessComparison } from "@/lib/types";
import { formatDb } from "@/lib/scale";

const FLOOR_DB = -60;

const pct = (db: number | null) =>
  db == null ? 0 : Math.min(Math.max((db - FLOOR_DB) / -FLOOR_DB, 0), 1) * 100;

/** Peak and RMS for both sources. Two measures of the same unit on the same
 *  scale, so they share one axis - never a second scale to make them line up. */
export function LoudnessCompare({
  loudness,
  hasReference,
}: {
  loudness: LoudnessComparison;
  hasReference: boolean;
}) {
  const rows = [
    { label: "Your project", data: loudness.project, colour: "var(--viz-project)" },
    ...(hasReference
      ? [{ label: "Reference", data: loudness.reference, colour: "var(--viz-reference)" }]
      : []),
  ];

  return (
    <div className="space-y-4">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="flex items-baseline justify-between">
            <span className="text-small text-ink-secondary">{row.label}</span>
            <span className="font-mono text-label text-ink-muted">
              peak {formatDb(row.data.peak_db)} · rms {formatDb(row.data.rms_db)}
            </span>
          </div>
          {/* Peak and RMS are siblings, not nested: opacity on a parent applies
              to the whole subtree, so an RMS bar inside a translucent peak bar
              would be washed out to the same 35% and the two would not read as
              distinct. */}
          <div className="relative mt-1.5 h-3 w-full overflow-hidden rounded-sm bg-surface-raised">
            <div
              className="absolute inset-y-0 left-0 rounded-sm"
              style={{ width: `${pct(row.data.peak_db)}%`, background: row.colour, opacity: 0.35 }}
            />
            <div
              className="absolute inset-y-0 left-0 rounded-sm"
              style={{ width: `${pct(row.data.rms_db)}%`, background: row.colour }}
            />
          </div>
        </div>
      ))}
      <p className="text-label text-ink-muted">
        Solid is RMS, translucent is peak. Scale runs {FLOOR_DB} dB to 0 dB.
      </p>
    </div>
  );
}
