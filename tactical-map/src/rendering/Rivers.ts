import type { River } from '../types';

/**
 * Render rivers as smooth bezier curves with width variation.
 */
export function renderRivers(
  ctx: CanvasRenderingContext2D,
  width: number, height: number,
  rivers: River[],
  scaleX: number,
  scaleY: number
): void {
  for (const river of rivers) {
    if (river.points.length < 2) continue;

    const baseWidth = river.isMain ? 5.5 : 3.0;
    const color = river.isMain ? '#3d6d8a' : '#6b9ab8';

    // Filter points to screen coordinates
    const pts = river.points.map(([x, y]) => [x * scaleX, y * scaleY] as [number, number]);

    // Draw river body with width variation
    ctx.strokeStyle = color;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Draw main body
    ctx.lineWidth = baseWidth + river.width * 0.5;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);

    for (let i = 1; i < pts.length - 1; i++) {
      const [px, py] = pts[i - 1];
      const [cx, cy] = pts[i];
      const [nx, ny] = pts[i + 1];
      const mx = (cx + nx) / 2;
      const my = (cy + ny) / 2;
      ctx.quadraticCurveTo(cx, cy, mx, my);
    }
    if (pts.length > 1) {
      const last = pts[pts.length - 1];
      ctx.lineTo(last[0], last[1]);
    }
    ctx.stroke();

    // Highlight stripe (lighter center)
    ctx.strokeStyle = 'rgba(200, 220, 235, 0.4)';
    ctx.lineWidth = baseWidth * 0.4;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length - 1; i++) {
      const [px, py] = pts[i - 1];
      const [cx, cy] = pts[i];
      const [nx, ny] = pts[i + 1];
      const mx = (cx + nx) / 2;
      const my = (cy + ny) / 2;
      ctx.quadraticCurveTo(cx, cy, mx, my);
    }
    if (pts.length > 1) {
      const last = pts[pts.length - 1];
      ctx.lineTo(last[0], last[1]);
    }
    ctx.stroke();
  }
}
