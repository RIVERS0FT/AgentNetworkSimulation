import type { Sector } from '../types';

/**
 * Generate sector regions using random seed points and
 * nearest-neighbor assignment (basic Voronoi on a grid).
 * Also runs a few Lloyd relaxation iterations for better shapes.
 */
export function generateSectors(
  width: number, height: number,
  numSectors: number,
  seed: number
): Sector[] {
  // Seeded RNG
  let s = seed + 999;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  // Generate seed points with Lloyd relaxation
  interface SeedPt { x: number; y: number; }
  let seeds: SeedPt[] = [];

  for (let i = 0; i < numSectors; i++) {
    seeds.push({
      x: width * 0.2 + rng() * width * 0.6,
      y: height * 0.2 + rng() * height * 0.6,
    });
  }

  // Lloyd relaxation (3 iterations)
  for (let iter = 0; iter < 3; iter++) {
    // Assign each pixel to nearest seed
    const sums: { sx: number; sy: number; count: number }[] =
      seeds.map(() => ({ sx: 0, sy: 0, count: 0 }));

    for (let y = 0; y < height; y += 4) {
      for (let x = 0; x < width; x += 4) {
        let best = 0, bestDist = Infinity;
        for (let i = 0; i < seeds.length; i++) {
          const dx = x - seeds[i].x, dy = y - seeds[i].y;
          const d = dx * dx + dy * dy;
          if (d < bestDist) { bestDist = d; best = i; }
        }
        sums[best].sx += x;
        sums[best].sy += y;
        sums[best].count++;
      }
    }

    // Move seeds to centroids
    for (let i = 0; i < seeds.length; i++) {
      if (sums[i].count > 0) {
        seeds[i].x = sums[i].sx / sums[i].count;
        seeds[i].y = sums[i].sy / sums[i].count;
      }
    }
  }

  // Create sectors with polygon boundaries
  const sectorLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const sectors: Sector[] = [];

  for (let i = 0; i < seeds.length; i++) {
    const cx = seeds[i].x;
    const cy = seeds[i].y;
    // Create a rough polygon around the seed point
    const polygon: [number, number][] = [];
    const numVerts = 8;
    const rx = width * (0.15 + rng() * 0.2);
    const ry = height * (0.15 + rng() * 0.2);

    for (let v = 0; v < numVerts; v++) {
      const angle = (v / numVerts) * Math.PI * 2 + rng() * 0.3;
      const r = (0.7 + rng() * 0.3);
      polygon.push([
        cx + Math.cos(angle) * rx * r,
        cy + Math.sin(angle) * ry * r,
      ]);
    }

    sectors.push({
      id: sectorLabels[i] || `X${i}`,
      polygon,
      center: [cx, cy],
      dominantTerrain: 'mixed',
      avgElevation: 0,
      threatLevel: 'medium',
      keyTerrain: [],
    });
  }

  return sectors;
}
