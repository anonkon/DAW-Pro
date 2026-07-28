"use client";

import { useState } from "react";
import type { TransientEvent } from "@/lib/types";

const BAR_H = 72; // px
// Mirrors backend/app/knowledge/retrieval.py SOFT_TRANSIENT_MEAN_MS - same
// "worth flagging" line, not a separately invented UI threshold.
const SOFT_THRESHOLD_MS = 30;
const CEIL_MS = 60; // tallest bar this chart draws before clamping

/** One vertical tick per detected onset, laid out along the track timeline.
 *  Height encodes attack time (10-90% envelope rise) - taller is a softer,
 *  slower-forming transient, and short and dense is a sharp, punchy one. */
export function TransientAttackChart({ transients }: { transients: TransientEvent[] }) {
  const [hover, setHover] = useState<number | null>(null);

  if (transients.length === 0) {
    return <p className="py-8 text-center text-small text-ink-muted">No transients detected.</p>;
  }

  const maxOnset = Math.max(...transients.map((t) => t.onset_sec), 0.001);
  const meanAttack = transients.reduce((sum, t) => sum + t.attack_ms, 0) / transients.length;

  return (
    <div>
      <div className="relative rounded bg-surface-raised px-3 pt-2" style={{ height: BAR_H }}>
        {transients.map((t, i) => {
          const heightPx = (Math.min(t.attack_ms, CEIL_MS) / CEIL_MS) * (BAR_H - 12);
          const soft = t.attack_ms > SOFT_THRESHOLD_MS;
          const colour = soft ? "var(--status-warning)" : "var(--viz-project)";
          return (
            <button
              key={i}
              type="button"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              className="absolute bottom-2 w-1 -translate-x-1/2 rounded-full transition-[opacity,transform] hover:scale-x-150"
              style={{
                left: `${(t.onset_sec / maxOnset) * 100}%`,
                height: heightPx,
                background: colour,
                opacity: hover === i ? 1 : 0.7,
              }}
              aria-label={`Onset at ${t.onset_sec.toFixed(2)}s, ${t.attack_ms.toFixed(1)}ms attack`}
            />
          );
        })}
        {hover != null && (
          <div
            className="pointer-events-none absolute -top-7 z-10 -translate-x-1/2 whitespace-nowrap rounded px-2 py-1 font-mono text-label"
            style={{
              left: `${(transients[hover].onset_sec / maxOnset) * 100}%`,
              background: "var(--surface-hover)",
              color: transients[hover].attack_ms > SOFT_THRESHOLD_MS ? "var(--status-warning)" : "var(--viz-project)",
              border: "1px solid var(--border-strong)",
            }}
          >
            {transients[hover].attack_ms.toFixed(1)}ms @ {transients[hover].onset_sec.toFixed(2)}s
          </div>
        )}
      </div>
      <p className="mt-2 text-label text-ink-muted">
        Taller is a slower, softer attack. Average {meanAttack.toFixed(1)}ms · amber crosses{" "}
        {SOFT_THRESHOLD_MS}ms.
      </p>
    </div>
  );
}
