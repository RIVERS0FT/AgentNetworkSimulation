import type { Road, Bridge } from '../types';

/**
 * Render road network with type-based styling.
 */
export function renderRoads(
  ctx: CanvasRenderingContext2D,
  _width: number, _height: number,
  roads: Road[],
  bridges: Bridge[],
  scaleX: number,
  scaleY: number
): void {
  // Draw roads
  for (const road of roads) {
    if (road.points.length < 2) continue;

    const style = roadTypeStyle(road.type);
    ctx.strokeStyle = style.color;
    ctx.lineWidth = style.width;

    if (style.dash) {
      ctx.setLineDash(style.dash);
    } else {
      ctx.setLineDash([]);
    }

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    const [sx, sy] = road.points[0];
    ctx.moveTo(sx * scaleX, sy * scaleY);

    for (let i = 1; i < road.points.length; i++) {
      const [px, py] = road.points[i];
      ctx.lineTo(px * scaleX, py * scaleY);
    }
    ctx.stroke();
  }

  ctx.setLineDash([]);

  // Draw bridges
  for (const bridge of bridges) {
    const [bx, by] = bridge.position;
    ctx.fillStyle = '#faf6ef';
    ctx.fillRect(bx * scaleX - 3, by * scaleY - 2, 6, 4);
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    ctx.strokeRect(bx * scaleX - 3, by * scaleY - 2, 6, 4);
  }
}

function roadTypeStyle(type: string): { color: string; width: number; dash?: number[] } {
  switch (type) {
    case 'primary': return { color: '#8a7e6b', width: 2.5 };
    case 'secondary': return { color: '#a09880', width: 1.8 };
    case 'trail': return { color: '#b5ad98', width: 1.0, dash: [4, 3] };
    default: return { color: '#a09880', width: 1.5 };
  }
}
