import { useCallback, useRef, useState } from 'react';
import type { Viewport } from '../types';

interface UseMapControlsProps {
  canvasWidth: number;
  canvasHeight: number;
}

export function useMapControls({ canvasWidth, canvasHeight }: UseMapControlsProps) {
  const [viewport, setViewport] = useState<Viewport>({
    zoom: 1,
    panX: 0,
    panY: 0,
    width: canvasWidth,
    height: canvasHeight,
  });
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);

  const isPanning = useRef(false);
  const lastPan = useRef({ x: 0, y: 0 });
  const targetZoom = useRef(1);
  const targetPanX = useRef(0);
  const targetPanY = useRef(0);
  const animFrame = useRef<number | null>(null);

  const updateViewportSize = useCallback((w: number, h: number) => {
    setViewport(prev => ({ ...prev, width: w, height: h }));
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.88 : 1.14;
    targetZoom.current = Math.max(0.2, Math.min(4, targetZoom.current * factor));

    // Animate toward target
    if (!animFrame.current) {
      const animate = () => {
        let changed = false;
        setViewport(prev => {
          const dz = (targetZoom.current - prev.zoom) * 0.2;
          const dpx = (targetPanX.current - prev.panX) * 0.2;
          const dpy = (targetPanY.current - prev.panY) * 0.2;
          if (Math.abs(dz) < 0.001 && Math.abs(dpx) < 0.1 && Math.abs(dpy) < 0.1) {
            animFrame.current = null;
            return prev;
          }
          changed = true;
          return {
            ...prev,
            zoom: prev.zoom + dz,
            panX: prev.panX + dpx,
            panY: prev.panY + dpy,
          };
        });
        if (changed && animFrame.current !== null) {
          animFrame.current = requestAnimationFrame(animate);
        } else {
          animFrame.current = null;
        }
      };
      animFrame.current = requestAnimationFrame(animate);
    }
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      isPanning.current = true;
      lastPan.current = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isPanning.current) {
      const dx = e.clientX - lastPan.current.x;
      const dy = e.clientY - lastPan.current.y;
      lastPan.current = { x: e.clientX, y: e.clientY };
      targetPanX.current += dx;
      targetPanY.current += dy;
      setViewport(prev => ({ ...prev, panX: prev.panX + dx, panY: prev.panY + dy }));
    }

    // Update cursor position
    setCursor({ x: e.clientX, y: e.clientY });
  }, []);

  const handleMouseUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  const handleDoubleClick = useCallback(() => {
    // Reset to initial view
    targetZoom.current = 1;
    targetPanX.current = 0;
    targetPanY.current = 0;
    setViewport(prev => ({ ...prev, zoom: 1, panX: 0, panY: 0 }));
  }, []);

  const fitToMap = useCallback(() => {
    const fitZoom = Math.min(
      canvasWidth / 1024,
      canvasHeight / 1024
    ) * 0.92;
    targetZoom.current = fitZoom;
    targetPanX.current = 0;
    targetPanY.current = 0;
    setViewport(prev => ({ ...prev, zoom: fitZoom, panX: 0, panY: 0 }));
  }, [canvasWidth, canvasHeight]);

  return {
    viewport,
    cursor,
    updateViewportSize,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleDoubleClick,
    fitToMap,
  };
}
