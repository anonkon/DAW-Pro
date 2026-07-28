"use client";

import { useState } from "react";
import type { StereoWidthBand } from "@/lib/types";
import { formatHz } from "@/lib/scale";

const FLOOR_DB = -24; // most negative value the chart draws (narrow/mono)
const CEIL_DB = 6; // most positive value the chart draws (wide)
const BAR_H = 96; // px

// Space above/below the zero line, in px - not symmetric, since FLOOR_DB and
// CEIL_DB are not symmetric around zero.
const NEGATIVE_SPAN_PX = (BAR_H * -FLOOR_DB) / (CEIL_DB - FLOOR_DB);
const POSITIVE_SPAN_PX = BAR_H - NEGATIVE_SPAN_PX;

/** Diverging bars around a zero baseline: side-energy relative to mid-energy,
 *  per band. Zero means centred, and positive means wider than centred, which in
 *  the low band specifically risks mono-cancellation - see
 *  backend/app/knowledge/retrieval.py WIDE_LOW_STEREO_THRESHOLD_DB, mirrored
 *  here as the same -6dB "worth flagging" line rather than a new number. */
const WIDE_THRESHOLD_DB = -6;

function barGeometry(db: number): { fromZero: "bottom" | "top"; offsetPx: number; heightPx: number } {
  if (db >= 0) {
    const heightPx = (Math.min(db, CEIL_DB) / CEIL_DB) * POSITIVE_SPAN_PX;
    return { fromZero: "bottom", offsetPx: NEGATIVE_SPAN_PX, heightPx };
  }
  const heightPx = (Math.min(-db, -FLOOR_DB) / -FLOOR_DB) * NEGATIVE_SPAN_PX;
  return { fromZero: "top", offsetPx: POSITIVE_SPAN_PX, heightPx };
}

export function StereoWidthChart({ bands }: { bands: StereoWidthBand[] }) {
  const [hover, setHover] = useState<number | null>(null);

  if (bands.length === 0) {
    return <p className="py-8 text-center text-small text-ink-muted">No stereo data - mono source.</p>;
  }

  return (
    <div>
      <div className="relative flex items-stretch gap-3" style={{ height: BAR_H }}>
        {/* Zero baseline: "as wide as centred" */}
        <div
          className="pointer-events-none absolute right-0 left-0 h-px bg-[var(--viz-axis)]"
          style={{ top: POSITIVE_SPAN_PX }}
        />
        {bands.map((band, i) => {
          const wide = band.label === "low" && band.width_db > WIDE_THRESHOLD_DB;
          const colour = wide ? "var(--status-warning)" : "var(--viz-project)";
          const geo = barGeometry(band.width_db);
          return (
            <button
              key={band.label}
              type="button"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              className="relative flex-1"
              aria-label={`${band.label} band, ${formatHz(band.hz_low)}-${formatHz(band.hz_high)}: ${band.width_db.toFixed(1)}dB side relative to mid`}
            >
              <div
                className="absolute right-0 left-0 rounded-sm transition-opacity"
                style={{
                  [geo.fromZero]: geo.offsetPx,
                  height: geo.heightPx,
                  background: colour,
                  opacity: hover === i ? 1 : 0.75,
                }}
              />
              {hover === i && (
                <div
                  className="pointer-events-none absolute -top-7 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded px-2 py-1 font-mono text-label"
                  style={{
                    background: "var(--surface-hover)",
                    color: colour,
                    border: "1px solid var(--border-strong)",
                  }}
                >
                  {band.width_db > 0 ? "+" : ""}
                  {band.width_db.toFixed(1)} dB
                </div>
              )}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex gap-3">
        {bands.map((band) => (
          <span key={band.label} className="flex-1 text-center text-label text-ink-muted">
            {band.label}
          </span>
        ))}
      </div>
      <p className="mt-3 text-label text-ink-muted">
        Side energy relative to mid, per band. 0 dB is centred, positive is wider than centred.
        Amber marks the low band crossing {WIDE_THRESHOLD_DB} dB, where a wide low end risks
        cancelling out when summed to mono.
      </p>
    </div>
  );
}
