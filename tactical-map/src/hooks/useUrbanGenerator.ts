import { useState, useCallback } from 'react';
import type { CityWorld } from '../types/urban';
import { generateUrbanWorld } from '../terrain/urbanWorld';

export function useUrbanGenerator() {
  const [world, setWorld] = useState<CityWorld | null>(null);
  const [loading, setLoading] = useState(false);
  const [seed, setSeed] = useState<number>(123);

  const generate = useCallback((newSeed?: number) => {
    setLoading(true);
    const s = newSeed ?? Math.floor(Math.random() * 2147483647);
    setSeed(s);

    const timer = setTimeout(() => {
      try {
        const w = generateUrbanWorld(s);
        setWorld(w);
      } catch (err) {
        console.error('Urban generation failed:', err);
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
