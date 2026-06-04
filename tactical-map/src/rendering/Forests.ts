import type { Heightmap } from '../types';
import type { Biome } from '../terrain/biomes';

/**
 * Render forest areas with watercolor-style irregular clusters.
 * Instead of individual trees, draws smooth organic blobs in dark green.
 */
export function renderForests(
  ctx: CanvasRenderingContext2D,
  width: number, height: number,
  heightmap: Heightmap,
  biomes: Biome[],
  seed: number
): void {
  const { width: hw, height: hh } = heightmap;
  const scaleX = width / hw;
  const scaleY = height / hh;

  // Find forest regions
  const forestMask = new Uint8Array(hw * hh);
  for (let i = 0; i < biomes.length; i++) {
    if (biomes[i] === 'forest') forestMask[i] = 1;
  }

  // Use BFS to find connected forest clusters
  const visited = new Uint8Array(hw * hh);
  const clusters: { cx: number; cy: number; cells: [number, number][] }[] = [];

  for (let y = 0; y < hh; y += 2) {
    for (let x = 0; x < hw; x += 2) {
      const idx = y * hw + x;
      if (forestMask[idx] && !visited[idx]) {
        // BFS to collect cluster
        const cells: [number, number][] = [];
        const queue: [number, number][] = [[x, y]];
        visited[idx] = 1;

        while (queue.length > 0) {
          const [cx, cy] = queue.shift()!;
          cells.push([cx, cy]);

          for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
            const nx = cx + dx, ny = cy + dy;
            if (nx >= 0 && nx < hw && ny >= 0 && ny < hh) {
              const ni = ny * hw + nx;
              if (forestMask[ni] && !visited[ni]) {
                visited[ni] = 1;
                queue.push([nx, ny]);
              }
            }
          }
        }

        if (cells.length > 10) {
          const avgX = cells.reduce((s, c) => s + c[0], 0) / cells.length;
          const avgY = cells.reduce((s, c) => s + c[1], 0) / cells.length;
          clusters.push({ cx: avgX, cy: avgY, cells });
        }
      }
    }
  }

  // Render each cluster as an organic blob
  // Seeded RNG for jitter
  let s = seed + 7777;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  for (const cluster of clusters) {
    const numBlobs = Math.min(5, Math.ceil(cluster.cells.length / 30));
    const baseCx = cluster.cx * scaleX;
    const baseCy = cluster.cy * scaleY;
    const radius = Math.sqrt(cluster.cells.length) * scaleX * 1.2;

    for (let b = 0; b < numBlobs; b++) {
      const bx = baseCx + (rng() - 0.5) * radius;
      const by = baseCy + (rng() - 0.5) * radius;
      const br = radius * (0.6 + rng() * 0.6);

      // Draw organic blob
      ctx.save();
      ctx.beginPath();
      const verts = 12 + Math.floor(rng() * 8);
      for (let v = 0; v < verts; v++) {
        const angle = (v / verts) * Math.PI * 2;
        const r = br * (0.7 + rng() * 0.5);
        const vx = bx + Math.cos(angle) * r;
        const vy = by + Math.sin(angle) * r;
        if (v === 0) ctx.moveTo(vx, vy);
        else ctx.lineTo(vx, vy);
      }
      ctx.closePath();

      // Watercolor effect: multiple semi-transparent fills
      // Dark base
      ctx.fillStyle = 'rgba(35, 80, 35, 0.35)';
      ctx.fill();

      // Lighter patchy overlay
      ctx.fillStyle = 'rgba(55, 105, 50, 0.2)';
      ctx.fill();

      // Rim highlight
      ctx.strokeStyle = 'rgba(60, 110, 55, 0.25)';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.restore();
    }
  }
}
