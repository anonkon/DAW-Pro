import type { StemSummary } from "@/lib/types";
import { formatDb } from "@/lib/scale";

const FREQ_BANDS = ["low", "low-mid", "mid", "high-mid", "high"] as const;
const FLOOR_DB = -60;
const CEIL_DB = 0;
const BAR_H = 56;

const heightPct = (db: number | undefined) => {
  if (db == null) return 0;
  return Math.min(Math.max((db - FLOOR_DB) / (CEIL_DB - FLOOR_DB), 0), 1) * 100;
};

/** Per-instrument breakdown from Demucs stem separation, one mini bar chart
 *  per stem so a problem can be traced to which instrument it lives in, not
 *  just which frequency band. All stems share the --viz-project colour and
 *  the same floor-to-0dB scale, so relative energy across stems stays
 *  directly comparable. No new per-stem hues: tokens.css only validates the
 *  two fixed data-series colours for contrast and colour-vision deficiency,
 *  and small multiples in one colour avoid needing more. */
export function StemsBreakdown({ stems }: { stems: Record<string, StemSummary> }) {
  const entries = Object.entries(stems);

  if (entries.length === 0) {
    return <p className="py-8 text-center text-small text-ink-muted">No stem separation for this analysis.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {entries.map(([name, stem]) => (
        <div key={name} className="rounded border border-line bg-surface-raised p-3">
          <p className="label-caps capitalize">{name}</p>
          <div className="mt-3 flex items-end gap-1.5" style={{ height: BAR_H }}>
            {FREQ_BANDS.map((band) => (
              <div
                key={band}
                className="flex-1 rounded-sm"
                style={{
                  height: `${heightPct(stem.band_energy_db[band])}%`,
                  background: "var(--viz-project)",
                  opacity: 0.75,
                }}
                title={`${band}: ${formatDb(stem.band_energy_db[band] ?? null)}`}
              />
            ))}
          </div>
          <div className="mt-1.5 flex gap-1">
            {FREQ_BANDS.map((band) => (
              <span key={band} className="flex-1 truncate text-center text-[0.6rem] text-ink-muted">
                {band}
              </span>
            ))}
          </div>
          <p className="mt-2 font-mono text-label text-ink-muted">
            peak {formatDb(stem.loudness.peak_db)} · rms {formatDb(stem.loudness.rms_db)}
          </p>
          {stem.loudness.crest_factor_db != null && (
            <p className="text-label text-ink-muted">crest {stem.loudness.crest_factor_db.toFixed(1)} dB</p>
          )}
        </div>
      ))}
    </div>
  );
}
