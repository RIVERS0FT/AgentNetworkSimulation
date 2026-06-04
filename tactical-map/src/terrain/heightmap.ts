import type { Heightmap, TerrainConfig } from '../types';
import { SimplexNoise } from './noise';

/**
 * Generate a heightmap using fBm (fractional Brownian motion) with
 * domain warping for natural-looking ridgelines.
 */
export function generateHeightmap(config: TerrainConfig): Heightmap {
  const { seed, width, height } = config;
  const simplex = new SimplexNoise(seed);
  const data = new Float32Array(width * height);

  const octaves = 7;
  const lacunarity = 2.3;
  const gain = 0.55;
  const initialScale = 0.004;
  const warpStrength = 0.018;

  let min = Infinity, max = -Infinity;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      // Domain warp: distort input coordinates
      const wx = x + simplex.noise2D(x * 0.003, y * 0.003) * width * warpStrength;
      const wy = y + simplex.noise2D(x * 0.003 + 5.2, y * 0.003 + 5.2) * height * warpStrength;

      let amplitude = 1;
      let frequency = initialScale;
      let value = 0;
      let maxVal = 0;

      for (let o = 0; o < octaves; o++) {
        value += simplex.noise2D(wx * frequency, wy * frequency) * amplitude;
        maxVal += amplitude;
        amplitude *= gain;
        frequency *= lacunarity;
      }

      // Normalize to [0, 1]
      value = (value / maxVal) * 0.5 + 0.5;

      data[y * width + x] = value;
      if (value < min) min = value;
      if (value > max) max = value;
    }
  }

  return { data, width, height, min, max };
}
