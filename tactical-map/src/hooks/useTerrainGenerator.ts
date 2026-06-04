import { useState, useCallback, useRef } from 'react';
import type { TerrainWorld } from '../types';
import { generateWorld } from '../terrain/world';

export function useTerrainGenerator() {
  const [world, setWorld] = useState<TerrainWorld | null>(null);
  const [loading, setLoading] = useState(false);
  const [seed, setSeed] = useState<number>(42);
  const workerRef = useRef<Worker | null>(null);

  const generate = useCallback((newSeed?: number) => {
    setLoading(true);
    const s = newSeed ?? Math.floor(Math.random() * 2147483647);
    setSeed(s);

    // Use setTimeout to avoid blocking the UI
    // Actually for 512x512 heightmap, we should generate synchronously
    // but wrapped in a timeout so loading state renders first
    const timer = setTimeout(() => {
      try {
        console.log('[TerrainGen] Starting world generation with seed', s);
        const t0 = performance.now();
        const w = generateWorld(s);
        const elapsed = (performance.now() - t0).toFixed(0);
        console.log(`[TerrainGen] Done in ${elapsed}ms — ${w.heightmap.width}×${w.heightmap.height}, ${w.rivers.length} rivers, ${w.villages.length} villages, ${w.units.length} units`);
        setWorld(w);
      } catch (err) {
        console.error('[TerrainGen] FAILED:', err);
      } finally {
        setLoading(false);
      }
    }, 50);

    return () => clearTimeout(timer);
  }, []);

  const regenerate = useCallback(() => {
    const s = Math.floor(Math.random() * 2147483647);
    generate(s);
  }, [generate]);

  return { world, loading, seed, generate, regenerate };
}
