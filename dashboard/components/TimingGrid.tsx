"use client";

import { useState } from "react";
import type { TimingAnalysis } from "@/lib/types";

const ROW_H = 28;
const PAD_X = 8;

/** Reference onsets against the matched project onsets, laid out by position
 *  within one bar. Absolute time is meaningless across two different records,
 *  so the backend folds both onto the bar - see measurements._pair_onsets. */
export function TimingGrid({ timing, tempoBpm }: { timing: TimingAnalysis; tempoBpm: number | null }) {
  const [hover, setHover] = useState<number | null>(null);

  if (timing.events.length === 0) {
    return (
      <p className="py-8 text-center text-small text-ink-muted">
        No paired timing events. This needs a reference track at a matching tempo.
      </p>
    );
  }

  const barSec = tempoBpm ? (60 / tempoBpm) * 4 : null;
  const events = timing.events;

  // Lay events out by bar position when we know the bar length, otherwise
  // spread them evenly - the pairing is still valid, only the spacing is not.
  const positionOf = (i: number) => {
    const e = events[i];
    if (barSec) return ((e.reference_sec % barSec) / barSec) * 100;
    return (i / Math.max(events.length - 1, 1)) * 100;
  };

  const colourOf = (severity: string) =>
    severity === "critical"
      ? "var(--status-critical)"
      : severity === "warning"
        ? "var(--status-warning)"
        : "var(--viz-project)";

  return (
    <div>
      <div className="relative rounded bg-surface-raised px-2 py-3">
        {/* 16th-note gridlines, the grid timing is actually scored against */}
        {barSec &&
          Array.from({ length: 17 }, (_, i) => (
            <div
              key={i}
              className="absolute top-0 bottom-0 w-px"
              style={{
                left: `calc(${PAD_X}px + ${(i / 16) * 100}% - ${(PAD_X * 2 * i) / 16}px)`,
                background: i % 4 === 0 ? "var(--viz-axis)" : "var(--viz-grid)",
              }}
            />
          ))}

        {(["reference", "project"] as const).map((row) => (
          <div key={row} className="relative flex items-center" style={{ height: ROW_H }}>
            <span className="label-caps z-10 w-12 shrink-0">
              {row === "reference" ? "Ref" : "You"}
            </span>
            <div className="relative h-full flex-1">
              {events.map((e, i) => {
                if (row === "project" && e.project_sec == null) return null;
                const colour =
                  row === "reference" ? "var(--viz-reference)" : colourOf(e.severity);
                return (
                  <button
                    key={i}
                    type="button"
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                    className="absolute top-1/2 h-3 w-2 -translate-y-1/2 rounded-sm transition-transform hover:scale-150"
                    style={{
                      left: `${positionOf(i)}%`,
                      background: colour,
                      // 2px surface ring keeps overlapping marks readable
                      boxShadow:
                        hover === i ? `0 0 0 2px var(--surface-raised), 0 0 0 3px ${colour}` : undefined,
                    }}
                    aria-label={`${row} onset at ${e.reference_sec.toFixed(2)}s${
                      e.delta_ms != null ? `, ${e.delta_ms > 0 ? "late" : "early"} ${Math.abs(e.delta_ms).toFixed(0)}ms` : ""
                    }`}
                  />
                );
              })}
            </div>
          </div>
        ))}

        {hover != null && events[hover].delta_ms != null && (
          <div
            className="pointer-events-none absolute -top-1 z-20 -translate-x-1/2 rounded px-2 py-1 font-mono text-label"
            style={{
              left: `calc(3rem + ${positionOf(hover)}%)`,
              background: "var(--surface-hover)",
              color: colourOf(events[hover].severity),
              border: "1px solid var(--border-strong)",
            }}
          >
            {events[hover].delta_ms! > 0 ? "LATE" : "EARLY"} {Math.abs(events[hover].delta_ms!).toFixed(0)}ms
          </div>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-4 text-small text-ink-secondary">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2 rounded-sm" style={{ background: "var(--viz-reference)" }} />
          Reference
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2 rounded-sm" style={{ background: "var(--viz-project)" }} />
          Your project
        </span>
        {timing.grid_source === "estimated" && (
          <span className="ml-auto text-label text-ink-muted">
            Grid estimated from audio — connect the plugin for exact tempo
          </span>
        )}
      </div>
    </div>
  );
}
