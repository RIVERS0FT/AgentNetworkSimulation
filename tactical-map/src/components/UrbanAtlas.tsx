import { useEffect, useRef, useCallback, useState } from 'react';
import type { CityWorld, CityStats } from '../types/urban';
import { UrbanRenderer } from '../rendering/UrbanRenderer';
import { useMapControls } from '../hooks/useMapControls';
import { useAnimationLoop } from '../hooks/useAnimationLoop';

interface UrbanAtlasProps {
  world: CityWorld;
  onStats?: (stats: CityStats) => void;
}

export function UrbanAtlas({ world, onStats }: UrbanAtlasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<UrbanRenderer>(new UrbanRenderer());
  const renderer = rendererRef.current;
  const [, setCursorWorld] = useState<{ x: number; y: number } | null>(null);

  const {
    viewport, updateViewportSize,
    handleWheel, handleMouseDown, handleMouseMove, handleMouseUp, handleDoubleClick, fitToMap,
  } = useMapControls({ canvasWidth: 1200, canvasHeight: 800 });

  // Initialize renderer
  useEffect(() => { renderer.initialize(world); }, [world, renderer]);

  // Push stats to parent
  useEffect(() => { onStats?.(world.stats); }, [world.stats, onStats]);

  // Fit on load
  useEffect(() => { fitToMap(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Resize
  const resize = useCallback(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    updateViewportSize(rect.width, rect.height);
  }, [updateViewportSize]);

  useEffect(() => {
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [resize]);

  // Render loop
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    ctx.save();
    ctx.scale(dpr, dpr);
    renderer.render(ctx, world, viewport.zoom, viewport.panX, viewport.panY,
      canvas.width / dpr, canvas.height / dpr);
    ctx.restore();
  }, [world, viewport, renderer]);

  useAnimationLoop(render, true);

  const handleMouseMoveUrban = useCallback((e: React.MouseEvent) => {
    handleMouseMove(e);
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const wx = (e.clientX - rect.left - viewport.width/2 - viewport.panX) / viewport.zoom + viewport.width/2;
    const wy = (e.clientY - rect.top - viewport.height/2 - viewport.panY) / viewport.zoom + viewport.height/2;
    setCursorWorld({ x: (wx / viewport.width) * world.width, y: (wy / viewport.height) * world.height });
  }, [handleMouseMove, viewport, world]);

  return (
    <div
      ref={containerRef}
      className="flex-1 relative overflow-hidden cursor-grab active:cursor-grabbing"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMoveUrban}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />
    </div>
  );
}
