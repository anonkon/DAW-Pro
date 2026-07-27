/** Shared scale helpers for the SVG charts. */

export const HZ_MIN = 20;
export const HZ_MAX = 20000;

/** Frequency -> 0..1 across a log axis. Audio is heard logarithmically, so a
 *  linear frequency axis would squeeze everything below 1kHz into a sliver. */
export function hzToUnit(hz: number): number {
  const clamped = Math.min(Math.max(hz, HZ_MIN), HZ_MAX);
  return Math.log10(clamped / HZ_MIN) / Math.log10(HZ_MAX / HZ_MIN);
}

export function unitToHz(unit: number): number {
  return HZ_MIN * (HZ_MAX / HZ_MIN) ** Math.min(Math.max(unit, 0), 1);
}

/** dB -> 0..1, where 0 is the floor of the visible range. */
export function dbToUnit(db: number, floor: number, ceil: number): number {
  if (ceil === floor) return 0;
  return Math.min(Math.max((db - floor) / (ceil - floor), 0), 1);
}

export function formatHz(hz: number): string {
  return hz >= 1000 ? `${(hz / 1000).toFixed(hz >= 10000 ? 0 : 1)}kHz` : `${Math.round(hz)}Hz`;
}

export function formatDb(db: number | null | undefined): string {
  return db == null ? "—" : `${db >= 0 ? "+" : ""}${db.toFixed(1)} dB`;
}

/** Round path coordinates before they reach the DOM.
 *
 *  Two reasons. Math.log10 and ** are not guaranteed bit-identical between
 *  Node's V8 and the browser's, so full-precision coordinates differ in the
 *  last digit and React reports a hydration mismatch on the `d` attribute.
 *  Rounding also drops a 16-digit float to 5 characters, which is most of the
 *  weight of a 64-point path. Sub-pixel precision is not visible anyway.
 */
const r = (n: number) => Math.round(n * 100) / 100;

/** Catmull-Rom through the points as a smooth SVG path. Cheaper visually than
 *  polyline for 64 points and it does not overshoot the way a naive bezier does. */
export function smoothPath(points: Array<{ x: number; y: number }>): string {
  if (points.length === 0) return "";
  if (points.length < 3) {
    return points.map((p, i) => `${i === 0 ? "M" : "L"}${r(p.x)} ${r(p.y)}`).join(" ");
  }

  let d = `M${r(points[0].x)} ${r(points[0].y)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${r(c1x)} ${r(c1y)}, ${r(c2x)} ${r(c2y)}, ${r(p2.x)} ${r(p2.y)}`;
  }
  return d;
}
