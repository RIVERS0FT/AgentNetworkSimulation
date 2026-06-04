import { useEffect, useRef, useCallback, useState } from 'react';
import type { TerrainWorld, LayerVisibility, CursorInfo } from '../types';
import { MapRenderer } from '../rendering/MapRenderer';
import { useMapControls } from '../hooks/useMapControls';
import { useAnimationLoop } from '../hooks/useAnimationLoop';

interface TacticalMapProps {
  world: TerrainWorld;
  visibility: LayerVisibility;
  onCursorInfo?: (info: CursorInfo | null) => void;
}

export function TacticalMap({ world, visibility, onCursorInfo }: TacticalMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<MapRenderer | null>(null);
  const [initError, setInitError] = useState<string | null>(null);

  // Lazy-init renderer
  if (!rendererRef.current) {
    rendererRef.current = new MapRenderer();
  }
  const renderer = rendererRef.current;

  const {
    viewport, updateViewportSize,
    handleWheel, handleMouseDown, handleMouseMove, handleMouseUp, handleDoubleClick, fitToMap,
  } = useMapControls({ canvasWidth: 1200, canvasHeight: 800 });

  // Initialize renderer
  useEffect(() => {
    console.log('[TacticalMap] useEffect init — world seed:', world.config.seed);
    try {
      renderer.initialize(world);
      setInitError(null);
      console.log('[TacticalMap] Renderer initialized OK');
    } catch (e) {
      console.error('[TacticalMap] MapRenderer.init failed:', e);
      setInitError(String(e));
    }
  }, [world, renderer]);

  // Fit map on first load
  useEffect(() => { fitToMap(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Resize
  const resize = useCallback(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) { console.warn('[TacticalMap] resize: container or canvas missing'); return; }
    const rect = container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    updateViewportSize(rect.width, rect.height);
    console.log(`[TacticalMap] Canvas sized: ${rect.width}×${rect.height} CSS, ${canvas.width}×${canvas.height} physical (dpr=${dpr})`);
  }, [updateViewportSize]);

  useEffect(() => {
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [resize]);

  // Render loop
  const frameCountRef = useRef(0);
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) { console.warn('[TacticalMap] render: canvas missing'); return; }
    const ctx = canvas.getContext('2d');
    if (!ctx) { console.warn('[TacticalMap] render: 2d context null'); return; }

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;

    const fc = ++frameCountRef.current;
    if (fc <= 3) {
      console.log(`[TacticalMap] Render frame #${fc}: canvas ${canvas.width}×${canvas.height} (${w.toFixed(0)}×${h.toFixed(0)} CSS), initError=${initError}`);
    }

    // Fill canvas with dark background first — map renderer will draw on top
    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.fillStyle = '#2d3a1f';
    ctx.fillRect(0, 0, w, h);

    // If init failed, show error message
    if (initError) {
      ctx.fillStyle = '#c41e3a';
      ctx.font = "14px 'JetBrains Mono', monospace";
      ctx.textAlign = 'center';
      ctx.fillText(`RENDER ERROR: ${initError}`, w / 2, h / 2);
      ctx.restore();
      return;
    }

    // Draw map
    try {
      const vp = { ...viewport, width: w, height: h };
      renderer.render(ctx, world, vp, visibility);

      // Debug indicator: shows render loop is alive + renderer state
      const isInit = renderer.initialized;
      ctx.strokeStyle = isInit ? 'rgba(0,128,0,0.5)' : 'rgba(200,0,0,0.5)';
      ctx.lineWidth = 2;
      ctx.strokeRect(8, 8, 8, 8);
      ctx.fillStyle = isInit ? '#2a5a1a' : '#8b0000';
      ctx.fillRect(10, 10, 4, 4);
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillStyle = '#333';
      ctx.fillText(isInit ? 'RENDER OK' : 'RENDER INIT...', 20, 18);
    } catch (e) {
      console.error('Render error:', e);
      ctx.fillStyle = '#c41e3a';
      ctx.font = "14px 'JetBrains Mono', monospace";
      ctx.textAlign = 'center';
      ctx.fillText(`RENDER ERROR: ${String(e)}`, w / 2, h / 2);
    }

    ctx.restore();
  }, [world, viewport, visibility, renderer, initError]);

  useAnimationLoop(render, true);

  // Cursor
  const handleMouseMoveWithQuery = useCallback((e: React.MouseEvent) => {
    handleMouseMove(e);
    if (!onCursorInfo) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const cx = (sx - viewport.width / 2 - viewport.panX) / viewport.zoom + viewport.width / 2;
    const cy = (sy - viewport.height / 2 - viewport.panY) / viewport.zoom + viewport.height / 2;
    const worldX = (cx / viewport.width) * world.heightmap.width;
    const worldY = (cy / viewport.height) * world.heightmap.height;
    const info = renderer.queryTerrain(world, worldX, worldY);
    onCursorInfo(info ? {
      worldX, worldY,
      elevation: info.elevation,
      sector: info.sector,
      terrain: info.biome,
    } : null);
  }, [handleMouseMove, onCursorInfo, world, viewport, renderer]);

  return (
    <div
      ref={containerRef}
      className="flex-1 relative overflow-hidden cursor-grab active:cursor-grabbing"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMoveWithQuery}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <canvas ref={canvasRef} className="absolute inset-0" />
    </div>
  );
}
