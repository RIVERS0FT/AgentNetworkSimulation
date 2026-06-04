import { useEffect, useRef } from 'react';

/**
 * Simple animation loop hook using requestAnimationFrame.
 * Calls the callback every frame when active.
 */
export function useAnimationLoop(
  callback: (dt: number) => void,
  active: boolean
): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!active) return;

    let lastTime = performance.now();
    let frameId: number;

    const loop = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      callbackRef.current(dt);
      frameId = requestAnimationFrame(loop);
    };

    frameId = requestAnimationFrame(loop);

    return () => cancelAnimationFrame(frameId);
  }, [active]);
}
