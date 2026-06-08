import type { CampusWorld } from '../types/urban';
import { generatePaperTexture } from './PaperTexture';

const ATLAS_RES = 1024;

// WebStyle: unified building fill #D4CCBC with subtle type variations
const BUILDING_COLORS: Record<string, string> = {
  headquarters:        '#D4CCBC',
  research_lab:        '#D6CEBE',
  office_tower:        '#D5CDBD',
  innovation_center:   '#D6CEBE',
  data_center:         '#D3CBBA',
  conference_center:   '#D5CDBD',
  training_center:     '#D4CCBC',
  exhibition_hall:     '#D7CFBF',
  cafeteria:           '#D8D0C0',
  library:             '#D5CDBD',
  gymnasium:           '#D3CBBA',
  hotel:               '#D4CCBC',
  visitor_center:      '#D7CFBF',
  utility:             '#D0C8B8',
};

// WebStyle: building stroke #8B8475, roads #A89F90, water #AFC6D9, green #9CAF88
const BUILDING_STROKE = '#8B8475';
const GREEN_COLOR = '#9CAF88';
const GREEN_TREE = 'rgba(80,100,70,0.22)';
const WATER_COLOR = '#AFC6D9';
const WATER_LABEL_COLOR = '#7A95A8';
const PAPER_BG = '#ECE8DF';

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
      ctx.strokeStyle = 'rgba(100,120,140,0.20)';
      ctx.lineWidth = 1.0;
      drawPolygon(ctx, wb.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Water label — UPPERCASE, subtle
      const cx = centroid(wb.polygon)[0] * sx;
      const cy = centroid(wb.polygon)[1] * sy;
      ctx.font = "500 10px 'Inter', 'IBM Plex Sans', system-ui, sans-serif";
      ctx.letterSpacing = '0.08em';
      ctx.fillStyle = WATER_LABEL_COLOR;
      ctx.textAlign = 'center';
      ctx.fillText(wb.name.toUpperCase(), cx, cy);
      ctx.textAlign = 'start';
    }

    // ── 2. Green spaces ──
    for (const g of world.greenSpaces) {
      ctx.fillStyle = GREEN_COLOR;
      ctx.strokeStyle = 'rgba(70,90,60,0.20)';
      ctx.lineWidth = 0.5;
      drawPolygon(ctx, g.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Tree texture dots — reduced opacity per WebStyle (no bright green dots)
      const bounds = polygonBounds(g.polygon);
      const count = g.type === 'central_park' ? 160 : g.type === 'green_corridor' ? 40 : 30;
      for (let i = 0; i < count; i++) {
        const tx = (bounds.cx + (Math.random() - 0.5) * bounds.rx * 1.8) * sx;
        const ty = (bounds.cy + (Math.random() - 0.5) * bounds.ry * 1.8) * sy;
        ctx.fillStyle = GREEN_TREE;
        ctx.beginPath();
        ctx.arc(tx, ty, 1.4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // ── 3. Zone fills (subtle) ──
    for (const zone of world.zones) {
      ctx.fillStyle = zone.color;
      ctx.strokeStyle = 'rgba(0,0,0,0.06)';
      ctx.lineWidth = 0.3;
      ctx.setLineDash([3, 3]);
      drawPolygon(ctx, zone.polygon, sx, sy);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // ── 4. Roads — WebStyle: #A89F90, no black roads ──
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

    // ── 5. Buildings — architectural footprints ──
    for (const bldg of world.buildings) {
      const color = BUILDING_COLORS[bldg.type] || '#D4CCBC';
      ctx.fillStyle = color;
      ctx.strokeStyle = BUILDING_STROKE;
      ctx.lineWidth = 0.5;
      drawPolygon(ctx, bldg.footprint, sx, sy);
      ctx.fill();
      ctx.stroke();

      // Roof detail for larger buildings — subtle inner rectangle
      if (bldg.height > 5) {
        const b = polygonBounds(bldg.footprint);
        const innerSx = b.rx * 0.35 * sx;
        const innerSy = b.ry * 0.35 * sy;
        ctx.fillStyle = 'rgba(255,255,255,0.12)';
        ctx.fillRect((b.cx - innerSx / sx) * sx, (b.cy - innerSy / sy) * sy, innerSx * 2, innerSy * 2);
      }
    }

    // ── 6. Facilities (flat monochrome icons) ──
    for (const fac of world.facilities) {
      const fx = fac.position[0] * sx;
      const fy = fac.position[1] * sy;

      if (fac.type === 'metro') {
        // Metro: circle with M — Huawei Red accent
        ctx.fillStyle = '#F7F4EE';
        ctx.strokeStyle = '#CF0A2C';
        ctx.lineWidth = 1.6;
        ctx.beginPath(); ctx.arc(fx, fy, 4.5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = '#CF0A2C';
        ctx.font = "bold 7px 'Inter', 'IBM Plex Sans', system-ui, sans-serif";
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('M', fx, fy + 1);
        ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      } else if (fac.type === 'shuttle') {
        // Shuttle: small square
        ctx.fillStyle = '#F7F4EE';
        ctx.strokeStyle = '#6A665F';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(fx - 3.5, fy - 3.5, 7, 7);
      } else if (fac.type === 'parking') {
        ctx.fillStyle = '#8B8475';
        ctx.fillRect(fx - 4.5, fy - 2.5, 9, 5);
        ctx.strokeStyle = '#6A665F';
        ctx.lineWidth = 0.6;
        ctx.strokeRect(fx - 4.5, fy - 2.5, 9, 5);
        // P label
        ctx.fillStyle = '#F7F4EE';
        ctx.font = "bold 5px 'Inter', 'IBM Plex Sans', system-ui, sans-serif";
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText('P', fx, fy);
        ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      } else if (fac.type === 'ev_charging') {
        ctx.fillStyle = '#9CAF88';
        ctx.beginPath(); ctx.arc(fx, fy, 3, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#7A8B6E';
        ctx.lineWidth = 0.6;
        ctx.beginPath(); ctx.arc(fx, fy, 3, 0, Math.PI * 2); ctx.stroke();
      }
    }
  }

  render(
    ctx: CanvasRenderingContext2D,
    world: CampusWorld,
    zoom: number, panX: number, panY: number,
    canvasW: number, canvasH: number,
  ): void {
    // Paper background per WebStyle
    ctx.fillStyle = PAPER_BG;
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

    // Subtle border around atlas — not black
    ctx.strokeStyle = '#8B8475';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(screenX, screenY, screenW, screenH);

    // ── Dynamic labels ──
    ctx.save();
    const wsx = screenW / world.width;
    const wsy = screenH / world.height;
    ctx.translate(screenX, screenY);
    ctx.scale(wsx, wsy);

    // Zone labels — UPPERCASE, large, low opacity per WebStyle
    for (const zone of world.zones) {
      ctx.font = "500 13px 'Inter', 'IBM Plex Sans', system-ui, sans-serif";
      ctx.fillStyle = 'rgba(30,20,10,0.13)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(zone.name.toUpperCase(), zone.center[0], zone.center[1]);
    }

    // Landmark labels — removed to keep map clean (agents provide context)

    ctx.restore();

    // ── Scale bar (bottom-left, screen space, zoom-aware) ──
    // screenW = zoom * canvasW; each screen px = world.width / screenW meters
    const barMaxW = canvasW * 0.22;
    const barH = 5;
    const barX = 16;
    const barY = canvasH - 22;
    // Compute actual meters the bar represents, then snap to a nice round number
    const metersPerPx = world.width / (zoom * canvasW);
    const rawMeters = barMaxW * metersPerPx;
    const niceMeters = niceRound(rawMeters);
    const barW = niceMeters / metersPerPx;  // adjust bar width to match the nice value exactly

    // Subtle scale bar — no pure black
    ctx.fillStyle = '#D4CCBC';
    ctx.fillRect(barX, barY, barW, barH);
    ctx.strokeStyle = '#8B8475';
    ctx.lineWidth = 0.8;
    ctx.strokeRect(barX, barY, barW, barH);
    // Alternating segments
    const segs = 4;
    for (let i = 0; i < segs; i++) {
      if (i % 2 === 0) {
        ctx.fillStyle = '#8B8475';
        ctx.fillRect(barX + (barW / segs) * i, barY, barW / segs, barH);
      }
    }
    ctx.font = "500 8px 'Inter', 'IBM Plex Sans', system-ui, sans-serif";
    ctx.fillStyle = '#6A665F';
    ctx.textAlign = 'center';
    ctx.fillText(`${niceMeters}m`, barX + barW / 2, barY - 5);
    ctx.textAlign = 'start';
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

// Round to a "nice" number for scale bar (e.g. 10, 20, 50, 100, 200, 500, 1000...)
function niceRound(v: number): number {
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const norm = v / mag;
  let nice: number;
  if (norm <= 1.2) nice = 1;
  else if (norm <= 2.5) nice = 2;
  else if (norm <= 5.5) nice = 5;
  else nice = 10;
  return nice * mag;
}

// WebStyle: #A89F90 road color family, 1-2px, no black roads
function roadStyle(type: string): { color: string; width: number; dash?: number[] } {
  switch (type) {
    case 'ring_road':   return { color: '#9A9082', width: 2.0 };
    case 'main_avenue': return { color: '#A89F90', width: 1.6 };
    case 'internal':    return { color: '#B5AD9E', width: 0.9 };
    case 'pedestrian':  return { color: '#C2BBAE', width: 0.6, dash: [3, 4] };
    case 'cycling':     return { color: '#8A9E7A', width: 0.6, dash: [2, 3] };
    default:            return { color: '#A89F90', width: 0.9 };
  }
}
