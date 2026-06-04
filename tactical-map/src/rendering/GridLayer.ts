/**
 * Render MGRS-style grid lines with coordinate labels.
 */
export function renderGridLayer(
  ctx: CanvasRenderingContext2D,
  width: number, height: number,
  scaleX: number, scaleY: number,
  panX: number, panY: number,
  zoom: number
): void {
  const gridSpacing = 100 * zoom; // grid lines every 100 world units * zoom
  if (gridSpacing < 30) return; // too dense, skip

  ctx.strokeStyle = 'rgba(0, 0, 0, 0.08)';
  ctx.lineWidth = 1;

  // Vertical grid lines
  const startX = -panX % gridSpacing;
  for (let x = startX; x < width; x += gridSpacing) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  // Horizontal grid lines
  const startY = -panY % gridSpacing;
  for (let y = startY; y < height; y += gridSpacing) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Grid labels at intersection points (only at wider spacing)
  if (gridSpacing < 80) return;

  ctx.font = "8px 'JetBrains Mono', monospace";
  ctx.fillStyle = 'rgba(80, 60, 30, 0.5)';

  for (let x = startX; x < width; x += gridSpacing) {
    for (let y = startY; y < height; y += gridSpacing) {
      const gridX = Math.round(x / scaleX);
      const gridY = Math.round(y / scaleY);
      ctx.fillText(`${gridX},${gridY}`, x + 2, y - 2);
    }
  }
}
