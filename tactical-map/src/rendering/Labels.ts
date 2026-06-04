import type { AnnotationBox } from '../types';

/**
 * Render annotation label boxes with leader lines.
 * White fill, black border, uppercase text — like field commander notes.
 */
export function renderAnnotations(
  ctx: CanvasRenderingContext2D,
  annotations: AnnotationBox[],
  scaleX: number, scaleY: number
): void {
  for (const anno of annotations) {
    const [ax, ay] = anno.position;
    const sx = ax * scaleX;
    const sy = ay * scaleY;

    const boxW = 160;
    const boxH = 32;
    const padding = 8;

    ctx.font = "9px 'Oswald', sans-serif";
    const textW = ctx.measureText(anno.text).width;
    const actualW = Math.max(boxW, textW + padding * 2);

    // White box with black border
    ctx.fillStyle = '#faf6ef';
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 1.2;

    const bx = sx - actualW / 2;
    const by = sy - boxH - 12;

    // Rounded rectangle
    roundRect(ctx, bx, by, actualW, boxH, 3);
    ctx.fill();
    ctx.stroke();

    // Label header (top strip)
    ctx.fillStyle = '#222';
    ctx.fillRect(bx, by, actualW, 14);

    ctx.fillStyle = '#faf6ef';
    ctx.font = "8px 'Oswald', sans-serif";
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(anno.label, bx + actualW / 2, by + 7);

    // Body text
    ctx.fillStyle = '#333';
    ctx.font = "9px 'Oswald', sans-serif";
    ctx.fillText(anno.text, bx + actualW / 2, by + 23);

    // Leader line (from box bottom to anchor point)
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 0.8;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(sx, by + boxH);
    ctx.lineTo(sx, sy);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}
