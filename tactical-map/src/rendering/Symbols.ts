import type { MilitaryUnit, ObservationPost, Sector } from '../types';

const UNIT_SIZE = 14;
const FONT_SIZE = 8;

/**
 * Draw NATO APP-6A style military unit symbols.
 */
export function renderUnitSymbols(
  ctx: CanvasRenderingContext2D,
  units: MilitaryUnit[],
  scaleX: number, scaleY: number
): void {
  for (const unit of units) {
    const [ux, uy] = unit.position;
    const sx = ux * scaleX;
    const sy = uy * scaleY;
    const color = unit.force === 'friendly' ? '#4a7db4' :
      unit.force === 'enemy' ? '#c41e3a' : '#4a7d4a';

    ctx.save();
    ctx.translate(sx, sy);

    // Draw unit frame (rectangle)
    ctx.fillStyle = color;
    ctx.fillRect(-UNIT_SIZE / 2, -UNIT_SIZE / 2, UNIT_SIZE, UNIT_SIZE);

    // Echelon indicator (top bar)
    if (unit.echelon !== 'squad') {
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      const echelonH = unit.echelon === 'battalion' ? 4 : unit.echelon === 'company' ? 3 : 2;
      ctx.fillRect(-UNIT_SIZE / 2, -UNIT_SIZE / 2 - echelonH, UNIT_SIZE, echelonH);
    }

    // Unit type symbol (white)
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.2;
    drawUnitTypeSymbol(ctx, unit.type, UNIT_SIZE);

    // Force indicator (bottom bar)
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.fillRect(-UNIT_SIZE / 2, UNIT_SIZE / 2 + 1, UNIT_SIZE, 2);

    // Direction indicator
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, -UNIT_SIZE / 2 - 6);
    ctx.lineTo(0, -UNIT_SIZE / 2 - 2);
    ctx.stroke();

    ctx.restore();

    // Label below the unit
    ctx.font = `${FONT_SIZE}px 'Oswald', sans-serif`;
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(unit.label, sx, sy + UNIT_SIZE / 2 + 4);
  }
}

function drawUnitTypeSymbol(ctx: CanvasRenderingContext2D, type: string, size: number): void {
  const hs = size / 2;
  const q = size / 4;

  switch (type) {
    case 'infantry':
      // Crossed lines (diagonal)
      ctx.beginPath();
      ctx.moveTo(-q, -q); ctx.lineTo(q, q);
      ctx.moveTo(q, -q); ctx.lineTo(-q, q);
      ctx.stroke();
      break;

    case 'armor':
      // Ellipse
      ctx.beginPath();
      ctx.ellipse(0, 0, q, q * 0.7, 0, 0, Math.PI * 2);
      ctx.stroke();
      break;

    case 'artillery':
      // Filled circle
      ctx.beginPath();
      ctx.arc(0, 0, q * 0.7, 0, Math.PI * 2);
      ctx.fill();
      break;

    case 'recon':
      // Diamond with cross
      ctx.beginPath();
      ctx.moveTo(0, -q); ctx.lineTo(q, 0); ctx.lineTo(0, q); ctx.lineTo(-q, 0); ctx.closePath();
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-q * 0.5, 0); ctx.lineTo(q * 0.5, 0);
      ctx.stroke();
      break;

    case 'headquarters':
      // Flag
      ctx.beginPath();
      ctx.moveTo(-q, -q * 0.3);
      ctx.lineTo(q, -q * 0.8);
      ctx.lineTo(q, q * 0.3);
      ctx.closePath();
      ctx.stroke();
      break;

    case 'supply':
      // Circle with dot
      ctx.beginPath();
      ctx.arc(0, 0, q * 0.7, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(0, 0, q * 0.2, 0, Math.PI * 2);
      ctx.fill();
      break;

    default:
      // Simple rectangle outline
      ctx.beginPath();
      ctx.rect(-q, -q, size / 2, size / 2);
      ctx.stroke();
      break;
  }
}

/**
 * Render observation posts as black diamonds.
 */
export function renderObservationPosts(
  ctx: CanvasRenderingContext2D,
  posts: ObservationPost[],
  scaleX: number, scaleY: number
): void {
  for (const op of posts) {
    const [px, py] = op.position;
    const sx = px * scaleX;
    const sy = py * scaleY;
    const q = 6;

    // Black diamond
    ctx.fillStyle = '#222';
    ctx.beginPath();
    ctx.moveTo(sx, sy - q);
    ctx.lineTo(sx + q, sy);
    ctx.lineTo(sx, sy + q);
    ctx.lineTo(sx - q, sy);
    ctx.closePath();
    ctx.fill();

    // Label
    ctx.font = "9px 'Oswald', sans-serif";
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.fillText(op.label, sx, sy + q + 12);

    // Observation arc
    ctx.strokeStyle = 'rgba(0,0,0,0.15)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);
    ctx.beginPath();
    ctx.arc(sx, sy, op.range * scaleX, op.azimuth - op.arc / 2, op.azimuth + op.arc / 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

/**
 * Render sector boundaries and labels.
 */
export function renderSectors(
  ctx: CanvasRenderingContext2D,
  sectors: Sector[],
  scaleX: number, scaleY: number
): void {
  for (const sector of sectors) {
    // Sector boundary (dashed)
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 6]);

    ctx.beginPath();
    for (let i = 0; i < sector.polygon.length; i++) {
      const [px, py] = sector.polygon[i];
      const sx = px * scaleX;
      const sy = py * scaleY;
      if (i === 0) ctx.moveTo(sx, sy);
      else ctx.lineTo(sx, sy);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Sector label
    const [cx, cy] = sector.center;
    ctx.font = "bold 16px 'Oswald', sans-serif";
    ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`SECTOR ${sector.id}`, cx * scaleX, cy * scaleY);
  }
}
