import type { TerrainWorld, Viewport, LayerVisibility, CursorInfo } from '../types';
import type { Biome } from '../terrain/biomes';
import { generatePaperTexture } from './PaperTexture';
import { renderTerrainLayer } from './TerrainLayer';
import { renderContours } from './Contours';
import { renderRivers } from './Rivers';
import { renderForests } from './Forests';
import { renderRoads } from './Roads';
import { renderSettlements } from './Settlements';
import { renderGridLayer } from './GridLayer';
import { classifyBiomes } from '../terrain/biomes';

const MAP_RES = 1024;

export class MapRenderer {
  private paperCanvas: HTMLCanvasElement | null = null;
  private staticCanvas: HTMLCanvasElement | null = null;
  private lastSeed: number | null = null;
  private _initialized = false;

  get initialized(): boolean { return this._initialized; }

  initialize(world: TerrainWorld): void {
    if (this.lastSeed === world.config.seed && this._initialized) return;
    this.lastSeed = world.config.seed;

    console.log('[MapRenderer.init] Starting — seed:', world.config.seed);
    const t0 = performance.now();

    const w = MAP_RES, h = MAP_RES;
    const sx = w / world.heightmap.width;
    const sy = h / world.heightmap.height;

    // Paper background
    this.paperCanvas = generatePaperTexture(w, h, world.config.seed);
    console.log('[MapRenderer.init] Paper texture done');

    // Static layers canvas
    this.staticCanvas = document.createElement('canvas');
    this.staticCanvas.width = w;
    this.staticCanvas.height = h;
    const sctx = this.staticCanvas.getContext('2d')!;

    // ── Layer order (bottom → top) ──
    // 1. Terrain colors from heightmap
    renderTerrainLayer(sctx, w, h, world.heightmap, world.config.seed);
    console.log('[MapRenderer.init] Terrain layer done');

    // 2. Forests from biome classification
    const biomes: Biome[] = classifyBiomes(world.heightmap, world.moisture);
    renderForests(sctx, w, h, world.heightmap, biomes, world.config.seed);
    console.log('[MapRenderer.init] Forests done — biomes:', biomes.filter(b => b === 'forest').length, 'forest cells');

    // 3. Rivers
    renderRivers(sctx, w, h, world.rivers, sx, sy);
    console.log('[MapRenderer.init] Rivers done —', world.rivers.length, 'rivers');

    // 4. Roads and bridges
    renderRoads(sctx, w, h, world.roads, world.bridges, sx, sy);
    console.log('[MapRenderer.init] Roads done —', world.roads.length, 'roads,', world.bridges.length, 'bridges');

    // 5. Settlements
    renderSettlements(sctx, w, h, world.villages, world.bridges, sx, sy);
    console.log('[MapRenderer.init] Settlements done —', world.villages.length, 'villages');

    // Verify static canvas has content (sample center pixel)
    const centerPixel = sctx.getImageData(w / 2, h / 2, 1, 1).data;
    console.log(`[MapRenderer.init] Static canvas center pixel RGBA: [${centerPixel[0]}, ${centerPixel[1]}, ${centerPixel[2]}, ${centerPixel[3]}]`);

    // NOTE: Contours are NOT rendered onto the static canvas.
    // They are drawn dynamically in render() as the top-most overlay,
    // so they never get occluded by forests, rivers, roads, or settlements.

    this._initialized = true;
    console.log(`[MapRenderer.init] Complete in ${(performance.now() - t0).toFixed(0)}ms — initialized=${this._initialized}`);
  }

  private _renderFrameCount = 0;

  render(
    ctx: CanvasRenderingContext2D,
    world: TerrainWorld,
    viewport: Viewport,
    visibility: LayerVisibility,
  ): void {
    const { zoom, panX, panY, width, height } = viewport;
    const worldW = world.heightmap.width;   // 512
    const worldH = world.heightmap.height;  // 512

    // Log first few frames for diagnosis
    if (++this._renderFrameCount <= 3) {
      console.log(`[MapRenderer.render] Frame #${this._renderFrameCount} — viewport: ${width}×${height}, zoom=${zoom.toFixed(3)}, panX=${panX.toFixed(1)}, panY=${panY.toFixed(1)}`);
      console.log(`[MapRenderer.render] initialized=${this._initialized}, paperCanvas=${!!this.paperCanvas}, staticCanvas=${!!this.staticCanvas}, vis.terrain=${visibility.terrain}, vis.contours=${visibility.contours}`);
    }

    // Fill canvas with dark military-olive background
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#2d3a1f';
    ctx.fillRect(0, 0, width, height);

    // Compute static-map-to-screen transform
    const mapScale = zoom * (width / MAP_RES);
    const mapScreenW = MAP_RES * mapScale;
    const mapScreenH = MAP_RES * mapScale;
    const mapScreenX = width / 2 + panX - mapScreenW / 2;
    const mapScreenY = height / 2 + panY - mapScreenH / 2;

    if (this._renderFrameCount <= 3) {
      console.log(`[MapRenderer.render] Map rect: (${mapScreenX.toFixed(0)}, ${mapScreenY.toFixed(0)}) ${mapScreenW.toFixed(0)}×${mapScreenH.toFixed(0)}`);
    }

    // Draw paper + static terrain layers
    if (this.paperCanvas) {
      ctx.drawImage(this.paperCanvas, mapScreenX, mapScreenY, mapScreenW, mapScreenH);
    }
    if (this.staticCanvas && visibility.terrain) {
      ctx.drawImage(this.staticCanvas, mapScreenX, mapScreenY, mapScreenW, mapScreenH);
      if (this._renderFrameCount === 2) {
        console.log('[MapRenderer.render] Static canvas drawn successfully');
      }
    } else if (this._renderFrameCount <= 3) {
      console.warn('[MapRenderer.render] Static canvas NOT drawn — staticCanvas=', !!this.staticCanvas, 'vis.terrain=', visibility.terrain);
    }

    // Dark border around the map
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 3;
    ctx.strokeRect(mapScreenX, mapScreenY, mapScreenW, mapScreenH);

    // ── Overlay layers: transform world coords → screen coords ──
    const wsx = mapScreenW / worldW;
    const wsy = mapScreenH / worldH;

    ctx.save();
    ctx.translate(mapScreenX, mapScreenY);
    ctx.scale(wsx, wsy);
    // Now ctx coordinates are in world units [0, worldW] × [0, worldH]

    if (visibility.sectors) {
      renderSectorsWorld(ctx, world);
    }
    if (visibility.fireFans) {
      renderFireFans(ctx, world.fireFans);
    }
    if (visibility.routes) {
      renderRoutes(ctx, world.routes);
    }
    if (visibility.symbols) {
      renderUnitSymbols(ctx, world.units);
      renderObservationPosts(ctx, world.observationPosts);
    }
    if (visibility.labels) {
      renderAnnotations(ctx, world.annotations);
    }

    // ── Contours: top-most overlay, never occluded ──
    // Rendered dynamically (not on static canvas) so they always sit
    // above forests, rivers, roads, and settlements.
    if (visibility.contours) {
      renderContours(ctx, world.heightmap, worldW, worldH);
    }

    ctx.restore();

    // Grid (in screen space, not world space)
    if (visibility.grid) {
      ctx.save();
      renderGridLayer(ctx, width, height, wsx, wsy, panX, panY, zoom);
      ctx.restore();
    }
  }

  queryTerrain(world: TerrainWorld, worldX: number, worldY: number): {
    elevation: number; sector: string | null; biome: string | null;
  } | null {
    const { heightmap } = world;
    const x = Math.floor(worldX);
    const y = Math.floor(worldY);
    if (x < 0 || x >= heightmap.width || y < 0 || y >= heightmap.height) return null;

    const elev = heightmap.data[y * heightmap.width + x];
    const biomes = classifyBiomes(heightmap, world.moisture);
    const biome = biomes[y * heightmap.width + x] || 'unknown';

    let sector: string | null = null;
    for (const sec of world.sectors) {
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const [px, py] of sec.polygon) {
        minX = Math.min(minX, px); maxX = Math.max(maxX, px);
        minY = Math.min(minY, py); maxY = Math.max(maxY, py);
      }
      if (worldX >= minX && worldX <= maxX && worldY >= minY && worldY <= maxY) {
        sector = sec.id; break;
      }
    }
    return { elevation: elev, sector, biome };
  }
}

// ── Overlay renderers (world-space, called inside ctx.translate+scale) ──

function renderUnitSymbols(ctx: CanvasRenderingContext2D, units: TerrainWorld['units']): void {
  const UNIT_SIZE = 14;
  for (const unit of units) {
    const [ux, uy] = unit.position;
    const color = unit.force === 'friendly' ? '#4a7db4' :
      unit.force === 'enemy' ? '#c41e3a' : '#4a7d4a';

    ctx.save();
    ctx.translate(ux, uy);

    // Unit frame
    ctx.fillStyle = color;
    ctx.fillRect(-UNIT_SIZE / 2, -UNIT_SIZE / 2, UNIT_SIZE, UNIT_SIZE);

    // Echelon bar
    if (unit.echelon !== 'squad') {
      ctx.fillStyle = 'rgba(255,255,255,0.25)';
      const eh = unit.echelon === 'battalion' ? 4 : unit.echelon === 'company' ? 3 : 2;
      ctx.fillRect(-UNIT_SIZE / 2, -UNIT_SIZE / 2 - eh, UNIT_SIZE, eh);
    }

    // Type symbol
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.2;
    drawSymbol(ctx, unit.type, UNIT_SIZE);

    // Direction indicator
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, -UNIT_SIZE / 2 - 6);
    ctx.lineTo(0, -UNIT_SIZE / 2 - 2);
    ctx.stroke();

    ctx.restore();

    // Label
    ctx.font = "8px 'Oswald', sans-serif";
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(unit.label, ux, uy + UNIT_SIZE / 2 + 2);
  }
}

function drawSymbol(ctx: CanvasRenderingContext2D, type: string, size: number): void {
  const q = size / 4;
  switch (type) {
    case 'infantry':
      ctx.beginPath(); ctx.moveTo(-q, -q); ctx.lineTo(q, q);
      ctx.moveTo(q, -q); ctx.lineTo(-q, q); ctx.stroke(); break;
    case 'armor':
      ctx.beginPath(); ctx.ellipse(0, 0, q, q * 0.7, 0, 0, Math.PI * 2); ctx.stroke(); break;
    case 'artillery':
      ctx.beginPath(); ctx.arc(0, 0, q * 0.7, 0, Math.PI * 2); ctx.fill(); break;
    case 'recon':
      ctx.beginPath(); ctx.moveTo(0, -q); ctx.lineTo(q, 0); ctx.lineTo(0, q); ctx.lineTo(-q, 0);
      ctx.closePath(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-q * 0.5, 0); ctx.lineTo(q * 0.5, 0); ctx.stroke(); break;
    case 'headquarters':
      ctx.beginPath(); ctx.moveTo(-q, -q * 0.3); ctx.lineTo(q, -q * 0.8); ctx.lineTo(q, q * 0.3);
      ctx.closePath(); ctx.stroke(); break;
    case 'supply':
      ctx.beginPath(); ctx.arc(0, 0, q * 0.7, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(0, 0, q * 0.2, 0, Math.PI * 2); ctx.fill(); break;
    default:
      ctx.strokeRect(-q, -q, size / 2, size / 2); break;
  }
}

function renderObservationPosts(ctx: CanvasRenderingContext2D, posts: TerrainWorld['observationPosts']): void {
  for (const op of posts) {
    const [px, py] = op.position;
    const q = 6;
    ctx.fillStyle = '#222';
    ctx.beginPath();
    ctx.moveTo(px, py - q); ctx.lineTo(px + q, py);
    ctx.lineTo(px, py + q); ctx.lineTo(px - q, py);
    ctx.closePath(); ctx.fill();

    ctx.font = "9px 'Oswald', sans-serif";
    ctx.fillStyle = '#333';
    ctx.textAlign = 'center';
    ctx.fillText(op.label, px, py + q + 12);

    ctx.strokeStyle = 'rgba(0,0,0,0.15)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);
    ctx.beginPath();
    ctx.arc(px, py, op.range, op.azimuth - op.arc / 2, op.azimuth + op.arc / 2);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function renderSectorsWorld(ctx: CanvasRenderingContext2D, world: TerrainWorld): void {
  for (const sector of world.sectors) {
    ctx.strokeStyle = 'rgba(0,0,0,0.2)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 6]);
    ctx.beginPath();
    for (let i = 0; i < sector.polygon.length; i++) {
      const [px, py] = sector.polygon[i];
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath(); ctx.stroke();
    ctx.setLineDash([]);

    const [cx, cy] = sector.center;
    ctx.font = "bold 16px 'Oswald', sans-serif";
    ctx.fillStyle = 'rgba(0,0,0,0.12)';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(`SECTOR ${sector.id}`, cx, cy);
  }
}

function renderRoutes(ctx: CanvasRenderingContext2D, routes: TerrainWorld['routes']): void {
  for (const route of routes) {
    if (route.waypoints.length < 2) continue;
    const color = route.force === 'friendly' ? '#3b6fa0' : route.force === 'enemy' ? '#c41e3a' : '#666';
    const alpha = route.planned ? 0.45 : 0.85;

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = route.planned ? 2.5 : 3.5;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (route.planned) ctx.setLineDash([8, 6]);

    ctx.beginPath();
    ctx.moveTo(route.waypoints[0][0], route.waypoints[0][1]);
    for (let i = 1; i < route.waypoints.length; i++) {
      ctx.lineTo(route.waypoints[i][0], route.waypoints[i][1]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Arrowhead
    if (route.waypoints.length >= 2) {
      const n = route.waypoints.length;
      const [x2, y2] = route.waypoints[n - 1];
      const [x1, y1] = route.waypoints[n - 2];
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const hl = 12;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - hl * Math.cos(angle - Math.PI / 6), y2 - hl * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(x2 - hl * Math.cos(angle + Math.PI / 6), y2 - hl * Math.sin(angle + Math.PI / 6));
      ctx.closePath(); ctx.fill();

      // Label
      const mi = Math.floor(n / 2);
      ctx.font = "bold 9px 'Oswald', sans-serif";
      ctx.fillStyle = color;
      ctx.textAlign = 'center';
      ctx.fillText(route.label, route.waypoints[mi][0], route.waypoints[mi][1] - 10);
    }
    ctx.restore();
  }
}

function renderFireFans(ctx: CanvasRenderingContext2D, fans: TerrainWorld['fireFans']): void {
  for (const fan of fans) {
    const [ox, oy] = fan.origin;
    const fillColor = fan.force === 'friendly' ? 'rgba(59,130,246,0.12)' :
      fan.force === 'enemy' ? 'rgba(239,68,68,0.12)' : 'rgba(255,140,0,0.12)';
    const strokeColor = fan.force === 'friendly' ? 'rgba(59,130,246,0.3)' :
      fan.force === 'enemy' ? 'rgba(239,68,68,0.3)' : 'rgba(255,140,0,0.3)';

    ctx.fillStyle = fillColor;
    ctx.beginPath(); ctx.moveTo(ox, oy);
    ctx.arc(ox, oy, fan.maxRange, fan.azimuth - fan.arc / 2, fan.azimuth + fan.arc / 2);
    ctx.closePath(); ctx.fill();

    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(ox, oy);
    ctx.arc(ox, oy, fan.maxRange, fan.azimuth - fan.arc / 2, fan.azimuth + fan.arc / 2);
    ctx.closePath(); ctx.stroke();
    ctx.setLineDash([]);
  }
}

function renderAnnotations(ctx: CanvasRenderingContext2D, annotations: TerrainWorld['annotations']): void {
  for (const anno of annotations) {
    const [ax, ay] = anno.position;
    const boxW = 160, boxH = 32, pad = 8;

    ctx.font = "9px 'Oswald', sans-serif";
    const m = ctx.measureText(anno.text);
    const aw = Math.max(boxW, m.width + pad * 2);
    const bx = ax - aw / 2, by = ay - boxH - 12;

    // Box
    ctx.fillStyle = '#faf6ef'; ctx.strokeStyle = '#222'; ctx.lineWidth = 0.8;
    roundRect(ctx, bx, by, aw, boxH, 3);
    ctx.fill(); ctx.stroke();

    // Header
    ctx.fillStyle = '#222';
    ctx.fillRect(bx, by, aw, 14);
    ctx.fillStyle = '#faf6ef';
    ctx.font = "8px 'Oswald', sans-serif";
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(anno.label, bx + aw / 2, by + 7);

    // Body
    ctx.fillStyle = '#333';
    ctx.font = "9px 'Oswald', sans-serif";
    ctx.fillText(anno.text, bx + aw / 2, by + 23);

    // Leader line
    ctx.strokeStyle = '#222'; ctx.lineWidth = 0.8;
    ctx.setLineDash([2, 2]);
    ctx.beginPath(); ctx.moveTo(ax, by + boxH); ctx.lineTo(ax, ay);
    ctx.stroke(); ctx.setLineDash([]);
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
