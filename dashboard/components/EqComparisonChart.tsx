import type { FrequencyBand } from "@/lib/types";

// dB values are negative (e.g. -6 to -60); map to a 0-100% bar width.
// -60dB or quieter -> 0%, 0dB (full scale) -> 100%.
function dbToPercent(db: number): number {
  const clamped = Math.max(-60, Math.min(0, db));
  return ((clamped + 60) / 60) * 100;
}

export function EqComparisonChart({ bands }: { bands: FrequencyBand[] }) {
  return (
    <div className="space-y-3">
      {bands.map((band) => (
        <div key={band.label} className="space-y-1">
          <div className="flex justify-between text-xs text-zinc-500">
            <span>
              {band.label} ({band.hz_low}-{band.hz_high}Hz)
            </span>
          </div>
          <div className="space-y-1">
            <div className="h-2 w-full rounded bg-zinc-800">
              <div
                className="h-2 rounded bg-emerald-500"
                style={{ width: `${dbToPercent(band.project_db)}%` }}
                title={`Your project: ${band.project_db.toFixed(1)} dB`}
              />
            </div>
            <div className="h-2 w-full rounded bg-zinc-800">
              <div
                className="h-2 rounded bg-sky-500"
                style={{ width: `${dbToPercent(band.reference_db)}%` }}
                title={`Reference: ${band.reference_db.toFixed(1)} dB`}
              />
            </div>
          </div>
        </div>
      ))}
      <div className="flex gap-4 pt-1 text-xs text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> your project
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-sky-500" /> reference
        </span>
      </div>
    </div>
  );
}
