import type { Heightmap } from '../types';

/**
 * Renders the terrain base layer with watercolor-style elevation coloring.
 */
export function renderTerrainLayer(
  ctx: CanvasRenderingContext2D,
  width: number, height: number,
  heightmap: Heightmap,
  _seed: number
): void {
  const imageData = ctx.createImageData(width, height);
  const data = imageData.data;
  const hData = heightmap.data;
  const hw = heightmap.width;
  const hh = heightmap.height;

  for (let py = 0; py < height; py++) {
    for (let px = 0; px < width; px++) {
      // Map pixel to heightmap (bilinear interpolation)
      const hx = (px / width) * hw;
      const hy = (py / height) * hh;
      const elev = sampleBilinear(hData, hw, hh, hx, hy);

      // Watercolor terrain palette
      const color = elevationToTerrainColor(elev);
      const idx = (py * width + px) * 4;
      data[idx] = color[0];
      data[idx + 1] = color[1];
      data[idx + 2] = color[2];
      data[idx + 3] = 255;
    }
  }

  ctx.putImageData(imageData, 0, 0);
}

function sampleBilinear(
  data: Float32Array, w: number, h: number,
  x: number, y: number
): number {
  const ix = Math.floor(x), iy = Math.floor(y);
  const fx = x - ix, fy = y - iy;
  const x0 = Math.max(0, Math.min(w - 1, ix));
  const x1 = Math.max(0, Math.min(w - 1, ix + 1));
  const y0 = Math.max(0, Math.min(h - 1, iy));
  const y1 = Math.max(0, Math.min(h - 1, iy + 1));
  const v00 = data[y0 * w + x0];
  const v10 = data[y0 * w + x1];
  const v01 = data[y1 * w + x0];
  const v11 = data[y1 * w + x1];
  return (v00 * (1 - fx) + v10 * fx) * (1 - fy) +
    (v01 * (1 - fx) + v11 * fx) * fy;
}

/** Map elevation [0,1] to a watercolor-style terrain RGB color */
function elevationToTerrainColor(elev: number): [number, number, number] {
  if (elev < 0.15) return [160, 190, 210];    // blue water — darker for contrast
  if (elev < 0.22) return [175, 190, 165];     // wetland
  if (elev < 0.30) return [190, 182, 145];     // low plain — darker
  if (elev < 0.42) return [178, 170, 125];     // mid plain
  if (elev < 0.52) return [165, 155, 108];     // high plain / low hills
  if (elev < 0.62) return [152, 138, 92];      // hills
  if (elev < 0.72) return [138, 118, 78];      // highland
  if (elev < 0.82) return [125, 100, 65];      // mountain
  if (elev < 0.90) return [115, 90, 60];       // high mountain
  return [105, 85, 65];                         // peak
}
