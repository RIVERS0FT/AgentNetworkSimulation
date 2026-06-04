import type { Village, Bridge } from '../types';

/**
 * Render villages as building clusters and bridges.
 */
export function renderSettlements(
  ctx: CanvasRenderingContext2D,
  _width: number, _height: number,
  villages: Village[],
  _bridges: Bridge[],
  scaleX: number,
  scaleY: number
): void {
  for (const village of villages) {
    const [vx, vy] = village.position;
    const sx = vx * scaleX;
    const sy = vy * scaleY;

    // Draw buildings
    for (const building of village.buildings) {
      ctx.beginPath();
      for (let i = 0; i < building.length; i++) {
        const [bx, by] = building[i];
        const bsx = bx * scaleX;
        const bsy = by * scaleY;
        if (i === 0) ctx.moveTo(bsx, bsy);
        else ctx.lineTo(bsx, bsy);
      }
      ctx.closePath();

      // Building fill and stroke
      ctx.fillStyle = '#c4b598';
      ctx.fill();
      ctx.strokeStyle = '#6b5d4a';
      ctx.lineWidth = 1.0;
      ctx.stroke();
    }

    // Village name label
    ctx.font = "bold 11px 'Oswald', sans-serif";
    ctx.fillStyle = '#2a1a08';
    ctx.textAlign = 'center';
    // White halo for readability
    ctx.strokeStyle = 'rgba(245,240,232,0.7)';
    ctx.lineWidth = 3;
    ctx.strokeText(village.name.toUpperCase(), sx, sy + 10);
    ctx.fillText(village.name.toUpperCase(), sx, sy + 10);
  }
}
