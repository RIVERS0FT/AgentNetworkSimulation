import type { TacticalRoute, FireFan } from '../types';

/**
 * Render tactical movement arrows — thick colored arrows with arrowheads.
 */
export function renderRoutes(
  ctx: CanvasRenderingContext2D,
  routes: TacticalRoute[],
  scaleX: number, scaleY: number
): void {
  for (const route of routes) {
    if (route.waypoints.length < 2) continue;

    const color = route.force === 'friendly' ? '#3b6fa0' :
      route.force === 'enemy' ? '#c41e3a' : '#666';
    const alpha = route.planned ? 0.45 : 0.85;

    ctx.strokeStyle = color;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = route.planned ? 2.5 : 3.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (route.planned) {
      ctx.setLineDash([8, 6]);
    } else {
      ctx.setLineDash([]);
    }

    // Draw path
    ctx.beginPath();
    const [sx, sy] = route.waypoints[0];
    ctx.moveTo(sx * scaleX, sy * scaleY);

    for (let i = 1; i < route.waypoints.length; i++) {
      const [wx, wy] = route.waypoints[i];
      ctx.lineTo(wx * scaleX, wy * scaleY);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw arrowhead at last waypoint
    if (route.waypoints.length >= 2) {
      const last = route.waypoints[route.waypoints.length - 1];
      const prev = route.waypoints[route.waypoints.length - 2];
      drawArrowhead(
        ctx, prev[0] * scaleX, prev[1] * scaleY,
        last[0] * scaleX, last[1] * scaleY,
        color, alpha
      );
    }

    // Route label
    if (route.waypoints.length >= 2) {
      const midIdx = Math.floor(route.waypoints.length / 2);
      const [mx, my] = route.waypoints[midIdx];
      ctx.font = "bold 9px 'Oswald', sans-serif";
      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;
      ctx.textAlign = 'center';
      ctx.fillText(route.label, mx * scaleX, my * scaleY - 10);
    }

    ctx.globalAlpha = 1;
  }
}

function drawArrowhead(
  ctx: CanvasRenderingContext2D,
  x1: number, y1: number, x2: number, y2: number,
  color: string, alpha: number
): void {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const headLen = 12;

  ctx.fillStyle = color;
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(
    x2 - headLen * Math.cos(angle - Math.PI / 6),
    y2 - headLen * Math.sin(angle - Math.PI / 6)
  );
  ctx.lineTo(
    x2 - headLen * Math.cos(angle + Math.PI / 6),
    y2 - headLen * Math.sin(angle + Math.PI / 6)
  );
  ctx.closePath();
  ctx.fill();
}

/**
 * Render fire support coverage fans as semi-transparent arcs.
 */
export function renderFireFans(
  ctx: CanvasRenderingContext2D,
  fireFans: FireFan[],
  scaleX: number, scaleY: number
): void {
  for (const fan of fireFans) {
    const [ox, oy] = fan.origin;
    const sx = ox * scaleX;
    const sy = oy * scaleY;

    const color = fan.force === 'friendly' ? '#3b82f6' :
      fan.force === 'enemy' ? '#ef4444' : '#ff8c00';

    // Fill arc
    ctx.fillStyle = color.replace(')', ',0.12)').replace('rgb', 'rgba');
    if (color.startsWith('#')) {
      ctx.fillStyle = fan.force === 'friendly' ? 'rgba(59,130,246,0.12)' :
        fan.force === 'enemy' ? 'rgba(239,68,68,0.12)' : 'rgba(255,140,0,0.12)';
    }

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.arc(sx, sy, fan.maxRange * scaleX, fan.azimuth - fan.arc / 2, fan.azimuth + fan.arc / 2);
    ctx.closePath();
    ctx.fill();

    // Arc border
    ctx.strokeStyle = color.replace(')', ',0.3)').replace('rgb', 'rgba');
    if (color.startsWith('#')) {
      ctx.strokeStyle = fan.force === 'friendly' ? 'rgba(59,130,246,0.3)' :
        fan.force === 'enemy' ? 'rgba(239,68,68,0.3)' : 'rgba(255,140,0,0.3)';
    }
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.arc(sx, sy, fan.maxRange * scaleX, fan.azimuth - fan.arc / 2, fan.azimuth + fan.arc / 2);
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Range rings
    for (let r = fan.maxRange * 0.33; r < fan.maxRange; r += fan.maxRange * 0.33) {
      ctx.beginPath();
      ctx.arc(sx, sy, r * scaleX, fan.azimuth - fan.arc / 2, fan.azimuth + fan.arc / 2);
      ctx.stroke();
    }
  }
}
