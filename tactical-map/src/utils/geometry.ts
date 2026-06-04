/** Distance between two 2D points */
export function dist(a: [number, number], b: [number, number]): number {
  const dx = a[0] - b[0], dy = a[1] - b[1];
  return Math.sqrt(dx * dx + dy * dy);
}

/** Linear interpolation */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Clamp value to [lo, hi] */
export function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

/** Point-in-polygon (ray casting) */
export function pointInPolygon(px: number, py: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1];
    const xj = poly[j][0], yj = poly[j][1];
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/** Find nearest point on a segment to a point */
export function closestPointOnSegment(
  px: number, py: number,
  ax: number, ay: number, bx: number, by: number
): [number, number] {
  const dx = bx - ax, dy = by - ay;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return [ax, ay];
  let t = ((px - ax) * dx + (py - ay) * dy) / len2;
  t = clamp(t, 0, 1);
  return [ax + t * dx, ay + t * dy];
}

/** Distance from point to line segment */
export function distToSegment(
  px: number, py: number,
  ax: number, ay: number, bx: number, by: number
): number {
  const [cx, cy] = closestPointOnSegment(px, py, ax, ay, bx, by);
  return dist([px, py], [cx, cy]);
}

/** Normalize angle to [-PI, PI] */
export function normAngle(a: number): number {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a < -Math.PI) a += 2 * Math.PI;
  return a;
}
