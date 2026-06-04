import type { CampusWorld } from '../types/urban';
import { generatePaperTexture } from './PaperTexture';

const ATLAS_RES = 1024;

const BUILDING_COLORS: Record<string, string> = {
  headquarters:        '#c8bda0',
  research_lab:        '#d0c8b0',
  office_tower:        '#ccc4a8',
  innovation_center:   '#cdc4a8',
  data_center:         '#c4baa0',
  conference_center:   '#d2c8b0',
  training_center:     '#cec6ac',
  exhibition_hall:     '#d4ccb4',
  cafeteria:           '#d8d0b8',
  library:             '#d0c8ac',
  gymnasium:           '#c8c0a4',
  hotel:               '#ccc4a8',
  visitor_center:      '#d4ccb4',
  utility:             '#c0b898',
};

const BUILDING_STROKE = '#6b5d4a';
const GREEN_COLOR = '#8aaa7a';
const GREEN_TREE = 'rgba(70,100,60,0.3)';
const WATER_COLOR = '#9ab8c8';
const WATER_LABEL_COLOR = '#5a8090';

export class UrbanRenderer {
  private paperCanvas: HTMLCanvasElement | null = null;
  private baseCanvas: HTMLCanvasElement | null = null;
  private lastSeed: number | null = null;

  initialize(world: CampusWorld): void {
    if (this.lastSeed === world.seed) return;
    this.lastSeed = world.seed;

    const w = ATLAS_RES, h = ATLAS_RES;
    const sx = w / world.width;
    const sy = h / world.height;

    // Paper background
    this.paperCanvas = generatePaperTexture(w, h, world.seed);

    // Base layers canvas
    this.baseCanvas = document.createElement('canvas');
    this.baseCanvas.width = w;
    this.baseCanvas.height = h;
    const ctx = this.baseCanvas.getContext('2d')!;

    // ── 1. Water bodies (bottom) ──
    for (const wb of world.waterBodies) {
      ctx.fillStyle = WATER_COLOR;
      ctx.strokeStyle = 'rgba(60,80,100,0.25)';
      ctx.lineWidth = 1.2;
      drawPolygon(ctx, wb.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Water body label
      const cx = centroid(wb.polygon)[0] * sx;
      const cy = centroid(wb.polygon)[1] * sy;
      ctx.font = "italic 11px 'Source Serif 4', serif";
      ctx.fillStyle = WATER_LABEL_COLOR;
      ctx.textAlign = 'center';
      ctx.fillText(wb.name, cx, cy);
      ctx.textAlign = 'start';
    }

    // ── 2. Green spaces ──
    for (const g of world.greenSpaces) {
      ctx.fillStyle = GREEN_COLOR;
      ctx.strokeStyle = 'rgba(50,70,40,0.25)';
      ctx.lineWidth = 0.6;
      drawPolygon(ctx, g.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Tree texture dots
      const bounds = polygonBounds(g.polygon);
      const count = g.type === 'central_park' ? 200 : g.type === 'green_corridor' ? 50 : 40;
      for (let i = 0; i < count; i++) {
        const tx = (bounds.cx + (Math.random() - 0.5) * bounds.rx * 1.8) * sx;
        const ty = (bounds.cy + (Math.random() - 0.5) * bounds.ry * 1.8) * sy;
        ctx.fillStyle = GREEN_TREE;
        ctx.beginPath();
        ctx.arc(tx, ty, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // ── 3. Zone fills (subtle) ──
    for (const zone of world.zones) {
      ctx.fillStyle = zone.color;
      ctx.strokeStyle = 'rgba(0,0,0,0.08)';
      ctx.lineWidth = 0.4;
      ctx.setLineDash([3, 3]);
      drawPolygon(ctx, zone.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // ── 4. Roads ──
    for (const road of world.roads) {
      const style = roadStyle(road.type);
      ctx.strokeStyle = style.color;
      ctx.lineWidth = style.width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      if (style.dash) ctx.setLineDash(style.dash);

      ctx.beginPath();
      ctx.moveTo(road.points[0][0] * sx, road.points[0][1] * sy);
      for (let i = 1; i < road.points.length; i++) {
        ctx.lineTo(road.points[i][0] * sx, road.points[i][1] * sy);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // ── 5. Buildings ──
    for (const bldg of world.buildings) {
      const color = BUILDING_COLORS[bldg.type] || '#d0c8b0';
      ctx.fillStyle = color;
      ctx.strokeStyle = BUILDING_STROKE;
      ctx.lineWidth = 0.5;
      drawPolygon(ctx, bldg.footprint, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Roof detail for larger buildings
      if (bldg.height > 5) {
        const b = polygonBounds(bldg.footprint);
        const innerSx = b.rx * 0.4 * sx;
        const innerSy = b.ry * 0.4 * sy;
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.fillRect((b.cx - innerSx / sx) * sx, (b.cy - innerSy / sy) * sy, innerSx * 2, innerSy * 2);
      }
    }

    // ── 6. Facilities (icons) ──
    for (const fac of world.facilities) {
      const fx = fac.position[0] * sx;
      const fy = fac.position[1] * sy;

      if (fac.type === 'metro') {
        // Metro: circle with M
        ctx.fillStyle = '#faf6ef';
        ctx.strokeStyle = '#c41e3a';
        ctx.lineWidth = 1.8;
        ctx.beginPath(); ctx.arc(fx, fy, 5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#c41e3a';
        ctx.font = "bold 8px 'Oswald', sans-serif";
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('M', fx, fy + 1);
        ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      } else if (fac.type === 'shuttle') {
        // Shuttle: small square
        ctx.fillStyle = '#faf6ef';
        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(fx - 4, fy - 4, 8, 8);
      } else if (fac.type === 'parking') {
        ctx.fillStyle = '#888';
        ctx.fillRect(fx - 5, fy - 3, 10, 6);
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 0.8;
        ctx.strokeRect(fx - 5, fy - 3, 10, 6);
        // P label
        ctx.fillStyle = '#faf6ef';
        ctx.font = "bold 6px 'Oswald', sans-serif";
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('P', fx, fy);
        ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      } else if (fac.type === 'ev_charging') {
        ctx.fillStyle = '#4ade80';
        ctx.beginPath(); ctx.arc(fx, fy, 3.5, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#16a34a';
        ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.arc(fx, fy, 3.5, 0, Math.PI * 2); ctx.stroke();
      }
    }
  }

  render(
    ctx: CanvasRenderingContext2D,
    world: CampusWorld,
    zoom: number, panX: number, panY: number,
    canvasW: number, canvasH: number,
  ): void {
    // Dark background
    ctx.fillStyle = '#2d3a1f';
    ctx.fillRect(0, 0, canvasW, canvasH);

    const centerX = canvasW / 2 + panX;
    const centerY = canvasH / 2 + panY;
    const scale = zoom * (canvasW / ATLAS_RES);

    const screenW = ATLAS_RES * scale;
    const screenH = ATLAS_RES * scale;
    const screenX = centerX - screenW / 2;
    const screenY = centerY - screenH / 2;

    // Paper + base layers
    if (this.paperCanvas) {
      ctx.drawImage(this.paperCanvas, screenX, screenY, screenW, screenH);
    }
    if (this.baseCanvas) {
      ctx.drawImage(this.baseCanvas, screenX, screenY, screenW, screenH);
    }

    // Dark border around atlas
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 3;
    ctx.strokeRect(screenX, screenY, screenW, screenH);

    // ── Dynamic labels ──
    ctx.save();
    const wsx = screenW / world.width;
    const wsy = screenH / world.height;
    ctx.translate(screenX, screenY);
    ctx.scale(wsx, wsy);

    // Zone labels
    for (const zone of world.zones) {
      ctx.font = "bold 14px 'Oswald', sans-serif";
      ctx.fillStyle = 'rgba(30,20,10,0.18)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(zone.name, zone.center[0], zone.center[1]);
    }

    // Landmark labels
    for (const lm of world.landmarks) {
      const lx = lm.position[0], ly = lm.position[1];
      ctx.font = "bold 10px 'Oswald', sans-serif";
      const m = ctx.measureText(lm.name);
      const bw = m.width + 14, bh = 16;

      // White label box
      ctx.fillStyle = '#faf6ef';
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 1;
      roundRect(ctx, lx - bw / 2, ly - bh / 2, bw, bh, 3);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#333';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(lm.name, lx, ly + 1);
    }

    ctx.restore();
  }
}

// ── Drawing Utilities ────────────────────────────────

function drawPolygon(ctx: CanvasRenderingContext2D, poly: [number, number][], sx: number, sy: number): void {
  if (!poly.length) return;
  ctx.beginPath();
  ctx.moveTo(poly[0][0] * sx, poly[0][1] * sy);
  for (let i = 1; i < poly.length; i++) {
    ctx.lineTo(poly[i][0] * sx, poly[i][1] * sy);
  }
  ctx.closePath();
}

function centroid(poly: [number, number][]): [number, number] {
  let cx = 0, cy = 0;
  for (const [x, y] of poly) { cx += x; cy += y; }
  return [cx / poly.length, cy / poly.length];
}

function polygonBounds(poly: [number, number][]): { cx: number; cy: number; rx: number; ry: number } {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of poly) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, rx: (maxX - minX) / 2, ry: (maxY - minY) / 2 };
}

function roadStyle(type: string): { color: string; width: number; dash?: number[] } {
  switch (type) {
    case 'ring_road':   return { color: '#3a3a3a', width: 2.4 };
    case 'main_avenue': return { color: '#4a4a4a', width: 1.8 };
    case 'internal':    return { color: '#6b6b6b', width: 1.0 };
    case 'pedestrian':  return { color: '#999',    width: 0.6, dash: [4, 4] };
    case 'cycling':     return { color: '#7a9a6a', width: 0.7, dash: [2, 3] };
    default:            return { color: '#666',     width: 1.0 };
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}
