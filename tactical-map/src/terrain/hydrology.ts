import type { Heightmap, River } from '../types';

/**
 * Simulate river formation via water-drop erosion.
 * Drops rain at random high-elevation points and traces
 * flow downhill following the steepest descent.
 */
export function generateRivers(
  heightmap: Heightmap,
  seed: number,
  numDrops = 16000
): River[] {
  const { data, width, height } = heightmap;

  // Accumulate flow
  const flow = new Float32Array(width * height);

  // Simple seeded RNG
  let s = seed | 0;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  for (let d = 0; d < numDrops; d++) {
    // Start at a random relatively high point
    let cx = rng() * width;
    let cy = rng() * height;
    const startElev = sampleElev(data, width, height, cx, cy);
    if (startElev < 0.45) continue; // skip low starts

    // Trace downhill
    for (let step = 0; step < 300; step++) {
      const idx = Math.floor(cy) * width + Math.floor(cx);
      if (idx >= 0 && idx < flow.length) flow[idx] += 0.001;

      const [dx, dy] = steepestDescent(data, width, height, cx, cy);
      if (dx === 0 && dy === 0) break; // local minimum

      cx += dx * 0.6;
      cy += dy * 0.6;
      if (cx < 0 || cx >= width || cy < 0 || cy >= height) break;
    }
  }

  // Extract rivers from flow accumulation
  return extractRiverPaths(flow, width, height, seed);
}

function sampleElev(
  data: Float32Array, w: number, _h: number,
  x: number, y: number
): number {
  const ix = Math.floor(x), iy = Math.floor(y);
  const fx = x - ix, fy = y - iy;
  const x0 = Math.max(0, Math.min(w - 1, ix));
  const x1 = Math.max(0, Math.min(w - 1, ix + 1));
  const y0 = Math.max(0, Math.min(_h - 1, iy));
  const y1 = Math.max(0, Math.min(_h - 1, iy + 1));
  const v00 = data[y0 * w + x0];
  const v10 = data[y0 * w + x1];
  const v01 = data[y1 * w + x0];
  const v11 = data[y1 * w + x1];
  return (v00 * (1 - fx) + v10 * fx) * (1 - fy) + (v01 * (1 - fx) + v11 * fx) * fy;
}

function steepestDescent(
  data: Float32Array, w: number, h: number,
  x: number, y: number
): [number, number] {
  const elev = sampleElev(data, w, h, x, y);
  let bestDx = 0, bestDy = 0, bestDrop = 0;

  for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    const nx = x + dx, ny = y + dy;
    if (nx < 0 || nx >= w || ny < 0 || ny >= h) continue;
    const neighborElev = sampleElev(data, w, h, nx, ny);
    const drop = elev - neighborElev;
    if (drop > bestDrop) {
      bestDrop = drop;
      bestDx = dx;
      bestDy = dy;
    }
  }
  return [bestDx, bestDy];
}

function extractRiverPaths(
  flow: Float32Array, width: number, height: number, _seed: number
): River[] {
  // Find the threshold for significant flow
  const sorted = Array.from(flow).sort((a, b) => b - a);
  const thresholdIdx = Math.floor(sorted.length * 0.02); // top 2% (was 0.5% — too narrow)
  const threshold = sorted[thresholdIdx] || 0;

  // Mark significant cells
  const isRiver = new Uint8Array(width * height);
  for (let i = 0; i < flow.length; i++) {
    if (flow[i] > threshold) isRiver[i] = 1;
  }

  // Use BFS to trace each river path
  const visited = new Uint8Array(width * height);
  const rivers: River[] = [];
  let riverId = 0;

  // Find start points — highest flow cells that aren't visited
  const starts: number[] = [];
  for (let i = 0; i < sorted.length && starts.length < 20; i++) {
    if (sorted[i] > threshold * 1.2) { // was threshold*2 — too strict
      const idx = flow.indexOf(sorted[i]);
      if (idx >= 0 && !visited[idx]) starts.push(idx);
    }
  }

  for (const startIdx of starts) {
    const points: [number, number][] = [];
    let current = startIdx;
    let flowSum = 0;
    let steps = 0;

    while (steps < 500) {
      const cy = Math.floor(current / width);
      const cx = current % width;
      if (cx < 0 || cx >= width || cy < 0 || cy >= height) break;
      if (visited[current]) break;

      visited[current] = 1;
      points.push([cx, cy]);
      flowSum += flow[current] || 0;
      steps++;

      // Move to highest-flow neighbor
      let bestNext = -1, bestFlow = 0;
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0], [1, 1], [-1, 1], [1, -1], [-1, -1]]) {
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
        const ni = ny * width + nx;
        if (visited[ni]) continue;
        if (isRiver[ni] && flow[ni] > bestFlow) {
          bestFlow = flow[ni];
          bestNext = ni;
        }
      }

      if (bestNext < 0) break;
      current = bestNext;
    }

    if (points.length > 5) {
      const avgFlow = flowSum / points.length;
      rivers.push({
        id: riverId++,
        points: simplifyPoints(points, 3),
        width: Math.max(1, Math.min(6, avgFlow * 800)),
        flow: avgFlow,
        isMain: avgFlow > threshold * 4,
      });
    }
  }

  return rivers;
}

/** Simple Douglas-Peucker-style point simplification */
function simplifyPoints(points: [number, number][], tolerance: number): [number, number][] {
  if (points.length <= 2) return points;
  const result: [number, number][] = [points[0]];

  for (let i = 1; i < points.length - 1; i++) {
    const prev = result[result.length - 1];
    const dx = points[i][0] - prev[0];
    const dy = points[i][1] - prev[1];
    if (dx * dx + dy * dy >= tolerance * tolerance) {
      result.push(points[i]);
    }
  }
  result.push(points[points.length - 1]);
  return result;
}
