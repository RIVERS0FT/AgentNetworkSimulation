import type { Heightmap } from '../types';

export type Biome = 'water' | 'wetland' | 'plain' | 'forest' | 'hills' | 'highland' | 'mountain' | 'peak';

/**
 * Classify each pixel into a biome based on elevation and moisture.
 */
export function classifyBiomes(
  heightmap: Heightmap,
  moisture: Float32Array
): Biome[] {
  const { data, width, height } = heightmap;
  const biomes: Biome[] = new Array(width * height);

  for (let i = 0; i < data.length; i++) {
    const elev = data[i];
    const moist = moisture[i] || 0.5;

    if (elev < 0.18) {
      biomes[i] = 'water';
    } else if (elev < 0.25) {
      biomes[i] = moist > 0.5 ? 'wetland' : 'plain';
    } else if (elev < 0.4) {
      biomes[i] = moist > 0.4 ? 'forest' : 'plain';
    } else if (elev < 0.55) {
      biomes[i] = moist > 0.35 ? 'forest' : 'hills';
    } else if (elev < 0.7) {
      biomes[i] = 'highland';
    } else if (elev < 0.85) {
      biomes[i] = 'mountain';
    } else {
      biomes[i] = 'peak';
    }
  }

  return biomes;
}

/** Generate a moisture map influenced by elevation and distance to water */
export function generateMoisture(
  heightmap: Heightmap,
  seed: number,
  riverMask?: Uint8Array
): Float32Array {
  const { data, width, height } = heightmap;
  const moisture = new Float32Array(width * height);

  // Seeded RNG for wind direction
  let s = seed + 777;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const windAngle = rng() * Math.PI * 2;
  const windX = Math.cos(windAngle);
  const windY = Math.sin(windAngle);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      const elev = data[idx];

      // Base moisture: 0.5
      let moist = 0.5;

      // Higher elevation = less moisture (orographic effect)
      moist -= elev * 0.4;

      // Windward side gets more moisture
      const windDist = (x / width) * windX + (y / height) * windY;
      moist += windDist * 0.2;

      // Near rivers = more moisture
      if (riverMask && riverMask[idx]) {
        moist += 0.35;
      }

      // Also check nearby river cells (spread moisture) — use smaller radius for perf
      if (riverMask) {
        const checkRadius = 3;
        for (let dy = -checkRadius; dy <= checkRadius; dy++) {
          for (let dx = -checkRadius; dx <= checkRadius; dx++) {
            const nx = x + dx, ny = y + dy;
            if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
              if (riverMask[ny * width + nx]) {
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < checkRadius) {
                  moist += (1 - dist / checkRadius) * 0.2;
                }
              }
            }
          }
        }
      }

      moisture[idx] = Math.max(0, Math.min(1, moist));
    }
  }

  return moisture;
}
