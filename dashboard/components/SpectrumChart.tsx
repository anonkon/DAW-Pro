"use client";

import { useMemo, useRef, useState } from "react";
import type { MixIssue, SpectrumComparison } from "@/lib/types";
import { dbToUnit, formatDb, formatHz, hzToUnit, smoothPath, unitToHz } from "@/lib/scale";

const W = 800;
const H = 320;
const PAD = { top: 20, right: 16, bottom: 28, left: 44 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

const GRID_HZ = [20, 100, 1000, 5000, 20000];

type Props = {
  spectrum: SpectrumComparison;
  issues: MixIssue[];
  hasReference: boolean;
};

export function SpectrumChart({ spectrum, issues, hasReference }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverUnit, setHoverUnit] = useState<number | null>(null);

  const { range, project, reference, dbTicks } = useMemo(() => {
    const all = [...spectrum.project, ...spectrum.reference].map((p) => p.db);
    if (all.length === 0) {
      return { range: [0, 1] as const, project: [], reference: [], dbTicks: [] };
    }
    // Pad the range so the curves do not graze the frame.
    const floor = Math.floor((Math.min(...all) - 3) / 10) * 10;
    const ceil = Math.ceil((Math.max(...all) + 3) / 10) * 10;

    const toXY = (pts: typeof spectrum.project) =>
      pts.map((p) => ({
        x: PAD.left + hzToUnit(p.hz) * PLOT_W,
        y: PAD.top + (1 - dbToUnit(p.db, floor, ceil)) * PLOT_H,
      }));

    const ticks: number[] = [];
    for (let v = floor; v <= ceil; v += Math.max(10, Math.round((ceil - floor) / 4 / 10) * 10)) {
      ticks.push(v);
    }

    return {
      range: [floor, ceil] as const,
      project: toXY(spectrum.project),
      reference: toXY(spectrum.reference),
      dbTicks: ticks,
    };
  }, [spectrum]);

  // Only frequency-anchored issues can be drawn onto the curve.
  const anchored = issues.filter((i) => i.hz_low != null && i.hz_high != null);

  const readout = useMemo(() => {
    if (hoverUnit == null || spectrum.project.length === 0) return null;
    const hz = unitToHz(hoverUnit);
    const nearest = (pts: typeof spectrum.project) =>
      pts.length === 0
        ? null
        : pts.reduce((best, p) =>
            Math.abs(Math.log(p.hz) - Math.log(hz)) < Math.abs(Math.log(best.hz) - Math.log(hz))
              ? p
              : best,
          );
    return { hz, project: nearest(spectrum.project), reference: nearest(spectrum.reference) };
  }, [hoverUnit, spectrum]);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = ((e.clientX - rect.left) / rect.width) * W;
    setHoverUnit(Math.min(Math.max((x - PAD.left) / PLOT_W, 0), 1));
  };

  if (spectrum.project.length === 0) {
    return (
      <p className="py-12 text-center text-small text-ink-muted">
        No spectrum data in this analysis.
      </p>
    );
  }

  const hoverX = hoverUnit == null ? null : PAD.left + hoverUnit * PLOT_W;

  return (
    <figure className="m-0">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Frequency spectrum, your project compared with the reference track"
        onMouseMove={onMove}
        onMouseLeave={() => setHoverUnit(null)}
      >
        {/* gridlines — recessive, never competing with the data */}
        {GRID_HZ.map((hz) => {
          const x = PAD.left + hzToUnit(hz) * PLOT_W;
          return (
            <g key={hz}>
              <line
                x1={x}
                y1={PAD.top}
                x2={x}
                y2={PAD.top + PLOT_H}
                stroke="var(--viz-grid)"
                strokeWidth={1}
              />
              <text
                x={x}
                y={H - 8}
                textAnchor="middle"
                className="fill-ink-muted"
                style={{ fontSize: 10 }}
              >
                {formatHz(hz)}
              </text>
            </g>
          );
        })}
        {dbTicks.map((db) => {
          const y = PAD.top + (1 - dbToUnit(db, range[0], range[1])) * PLOT_H;
          return (
            <g key={db}>
              <line
                x1={PAD.left}
                y1={y}
                x2={PAD.left + PLOT_W}
                y2={y}
                stroke="var(--viz-grid)"
                strokeWidth={1}
              />
              <text
                x={PAD.left - 8}
                y={y + 3}
                textAnchor="end"
                className="fill-ink-muted"
                style={{ fontSize: 10 }}
              >
                {db}
              </text>
            </g>
          );
        })}

        {/* issue bands, drawn under the curves so they never obscure data */}
        {anchored.map((issue, i) => {
          const x1 = PAD.left + hzToUnit(issue.hz_low!) * PLOT_W;
          const x2 = PAD.left + hzToUnit(issue.hz_high!) * PLOT_W;
          const colour =
            issue.severity === "critical"
              ? "var(--status-critical)"
              : issue.severity === "warning"
                ? "var(--status-warning)"
                : "var(--status-info)";
          return (
            <rect
              key={i}
              x={x1}
              y={PAD.top}
              width={Math.max(x2 - x1, 2)}
              height={PLOT_H}
              fill={colour}
              opacity={0.1}
            />
          );
        })}

        {hasReference && (
          <path
            d={smoothPath(reference)}
            fill="none"
            stroke="var(--viz-reference)"
            strokeWidth={2}
            strokeLinejoin="round"
          />
        )}
        <path
          d={smoothPath(project)}
          fill="none"
          stroke="var(--viz-project)"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* crosshair */}
        {hoverX != null && (
          <line
            x1={hoverX}
            y1={PAD.top}
            x2={hoverX}
            y2={PAD.top + PLOT_H}
            stroke="var(--border-strong)"
            strokeWidth={1}
          />
        )}
      </svg>

      {/* Legend is always present for two series, so identity never rests on
          colour alone. */}
      <figcaption className="mt-2 flex flex-wrap items-center gap-4 text-small text-ink-secondary">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{ background: "var(--viz-project)" }} />
          Your project
        </span>
        {hasReference && (
          <span className="flex items-center gap-1.5">
            <span
              className="h-0.5 w-4 rounded-full"
              style={{ background: "var(--viz-reference)" }}
            />
            Reference
          </span>
        )}
        {readout && (
          <span className="ml-auto font-mono text-ink-muted">
            {formatHz(readout.hz)} · project {formatDb(readout.project?.db)}
            {hasReference && readout.reference ? ` · ref ${formatDb(readout.reference.db)}` : ""}
          </span>
        )}
      </figcaption>

      {anchored.length > 0 && (
        <ul className="mt-3 space-y-2">
          {anchored.map((issue, i) => (
            <IssueCallout key={i} issue={issue} />
          ))}
        </ul>
      )}
    </figure>
  );
}

function IssueCallout({ issue }: { issue: MixIssue }) {
  const tone =
    issue.severity === "critical"
      ? { fg: "var(--status-critical)", bg: "var(--status-critical-bg)" }
      : issue.severity === "warning"
        ? { fg: "var(--status-warning)", bg: "var(--status-warning-bg)" }
        : { fg: "var(--status-info)", bg: "var(--status-info-bg)" };

  return (
    <li
      className="rounded border-l-2 px-3 py-2"
      style={{ background: tone.bg, borderColor: tone.fg }}
    >
      <div className="flex items-baseline gap-2">
        {/* Severity carries a word as well as a colour. */}
        <span className="label-caps" style={{ color: tone.fg }}>
          {issue.severity}
        </span>
        <span className="text-small font-medium text-ink-primary">{issue.title}</span>
        <span className="ml-auto font-mono text-label text-ink-muted">
          {formatHz(issue.hz_low!)}–{formatHz(issue.hz_high!)}
        </span>
      </div>
      <p className="mt-1 text-small text-ink-secondary">{issue.description}</p>
    </li>
  );
}
