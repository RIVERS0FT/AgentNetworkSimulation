import type {
  CampusWorld, CampusZone, CampusRoad, CampusBuilding, CampusBuildingType,
  CampusGreenSpace, CampusWaterBody, CampusFacility, CampusLandmark, CampusStats,
} from '../types/urban';

// ── Seeded RNG ───────────────────────────────────────
function makeRng(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const W = 400, H = 400;
const CX = W / 2, CY = H / 2;
const SPACING = 28; // 全局街区网格基础大小

// ── Zone base colors (paper-toned, subtle) ────────────
const ZONE_COLORS: Record<string, string> = {
  headquarters:  '#efe4d4',
  research:      '#ede6da',
  office:        '#eee5d8',
  innovation:    '#ece4d6',
  data_center:   '#e8e0d2',
  conference:    '#ede4d8',
  training:      '#ebe2d4',
  exhibition:    '#ece3d6',
  logistics:     '#e6ded0',
  residential:   '#f0e8dc',
  dining:        '#ede6da',
  sports:        '#e9e4d4',
  central_plaza: '#f2ece0',
  lake_district: '#e2dfd8',
};

// ── Main Generator ───────────────────────────────────
export function generateUrbanWorld(seed?: number): CampusWorld {
  const s = seed ?? Math.floor(Math.random() * 2147483647);
  const rng = makeRng(s);

  const waterBodies = generateWaterBodies(rng);
  const zones = generateZones(rng, waterBodies);
  const roads = generateRoads(rng, zones, waterBodies);
  
  const pocketParks: CampusGreenSpace[] = [];
  const buildings = generateBuildings(rng, zones, waterBodies, pocketParks);
  const greenSpaces = generateGreenSpaces(rng, zones, waterBodies).concat(pocketParks);
  
  const facilities = generateFacilities(rng, zones, roads);
  const landmarks = generateLandmarks(rng, zones);

  // Stats calculation
  let totalRoadKm = 0;
  for (const road of roads) {
    for (let i = 1; i < road.points.length; i++) {
      const dx = road.points[i][0] - road.points[i - 1][0];
      const dy = road.points[i][1] - road.points[i - 1][1];
      totalRoadKm += Math.sqrt(dx * dx + dy * dy);
    }
  }
  totalRoadKm = Math.round(totalRoadKm / 5) / 100;

  let greenArea = 0;
  for (const g of greenSpaces) greenArea += polygonArea(g.polygon);
  const greenCoverage = Math.round((greenArea / (W * H)) * 100);

  let waterArea = 0;
  for (const wb of waterBodies) waterArea += polygonArea(wb.polygon);
  const waterCoverage = Math.round((waterArea / (W * H)) * 100);

  const researchCenters = zones.filter(z => z.type === 'research' || z.type === 'innovation' || z.type === 'data_center').length;

  const stats: CampusStats = {
    buildingCount: buildings.length,
    researchCenters,
    employees: Math.round(buildings.length * 120 + rng() * 5000),
    roadLengthKm: totalRoadKm,
    greenCoverage,
    waterCoverage,
    parkingSpaces: Math.round(buildings.length * 1.5),
    campusArea: 5.8,
  };

  return {
    seed: s, width: W, height: H,
    zones, roads, buildings, greenSpaces,
    waterBodies, facilities, landmarks, stats,
  };
}

// ═══════════════════════════════════════════════════════
// 1. WATER
// ═══════════════════════════════════════════════════════
function generateWaterBodies(rng: () => number): CampusWaterBody[] {
  const bodies: CampusWaterBody[] = [];
  
  // 生成一条贯穿画布的河流，轻微弯曲
  const riverW = 40 + rng() * 10;
  const leftBank: [number, number][] = [];
  const rightBank: [number, number][] = [];
  
  for (let y = -50; y <= H + 50; y += 20) {
    const x = CX + Math.sin(y * 0.01) * 35 + (y * 0.1); // 略带倾斜和波浪
    leftBank.push([x - riverW / 2, y]);
    rightBank.unshift([x + riverW / 2, y]); 
  }
  
  const riverPoly = [...leftBank, ...rightBank];
  bodies.push({ id: 0, name: 'CAMPUS RIVER', polygon: riverPoly, type: 'canal' });

  return bodies;
}

// 修改为较少顶点数的生成器，以形成类似建筑底座融合的“块状”外观
function generateBlockyPolygon(cx: number, cy: number, baseRx: number, baseRy: number, rng: () => number): [number, number][] {
  const poly: [number, number][] = [];
  const verts = 7 + Math.floor(rng() * 3); // 7-9个顶点，形成块状折角
  const phase = rng() * Math.PI * 2;
  for (let i = 0; i < verts; i++) {
    const angle = (i / verts) * Math.PI * 2 + phase;
    const noise = 0.6 + 0.5 * rng(); // 随机外扩凸起
    poly.push([cx + Math.cos(angle) * baseRx * noise, cy + Math.sin(angle) * baseRy * noise]);
  }
  return poly;
}

// ═══════════════════════════════════════════════════════
// 2. ZONES (Full canvas spread & River avoidance)
// ═══════════════════════════════════════════════════════
function generateZones(rng: () => number, water: CampusWaterBody[]): CampusZone[] {
  const zones: CampusZone[] = [];
  
  const zoneTypes: { type: CampusZone['type']; name: string; baseR: number }[] = [
    { type: 'headquarters', name: 'CAMPUS HQ', baseR: 65 },
    { type: 'research', name: 'RESEARCH A', baseR: 60 },
    { type: 'research', name: 'RESEARCH B', baseR: 60 },
    { type: 'innovation', name: 'INNOVATION', baseR: 55 },
    { type: 'office', name: 'OFFICE', baseR: 70 },
    { type: 'data_center', name: 'DATA CENTER', baseR: 50 },
    { type: 'conference', name: 'CONFERENCE', baseR: 55 },
    { type: 'residential', name: 'RESIDENTIAL', baseR: 75 },
    { type: 'sports', name: 'SPORTS', baseR: 65 },
    { type: 'logistics', name: 'LOGISTICS', baseR: 50 },
  ];

  // 初始均匀散布在整个地图区域内（带少许边距）
  const tempZones = zoneTypes.map((zt) => ({
    ...zt,
    x: 40 + rng() * (W - 80),
    y: 40 + rng() * (H - 80),
  }));

  // 物理推挤：保证均匀分布且避开中心河流
  for (let step = 0; step < 30; step++) {
    for (let i = 0; i < tempZones.length; i++) {
      const a = tempZones[i];

      // 区域间互斥
      for (let j = i + 1; j < tempZones.length; j++) {
        const b = tempZones[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.hypot(dx, dy);
        const minDist = a.baseR + b.baseR + 15; // 保持间距，形成呼吸感

        if (dist < minDist && dist > 0.1) {
          const push = (minDist - dist) * 0.3;
          const px = (dx / dist) * push, py = (dy / dist) * push;
          a.x += px; a.y += py;
          b.x -= px; b.y -= py;
        }
      }
      
      // 河流排斥（避免色块完全覆盖河流导致截断视觉）
      const riverCenterX = CX + Math.sin(a.y * 0.01) * 35 + (a.y * 0.1);
      const distToRiver = Math.abs(a.x - riverCenterX);
      const riverAvoidance = 55; // 避让半径
      if (distToRiver < riverAvoidance) {
        a.x += (a.x > riverCenterX ? 1 : -1) * (riverAvoidance - distToRiver) * 0.4;
      }

      // 画布边界反弹，防止被推出版图
      const margin = 50;
      if (a.x < margin) a.x += (margin - a.x) * 0.2;
      if (a.x > W - margin) a.x -= (a.x - (W - margin)) * 0.2;
      if (a.y < margin) a.y += (margin - a.y) * 0.2;
      if (a.y > H - margin) a.y -= (a.y - (H - margin)) * 0.2;
    }
  }

  tempZones.forEach((zt, index) => {
    zones.push({
      id: `Z${index}`, name: zt.name, type: zt.type as CampusZone['type'], center: [zt.x, zt.y],
      polygon: generateBlockyPolygon(zt.x, zt.y, zt.baseR, zt.baseR * (0.8 + rng() * 0.4), rng),
      color: ZONE_COLORS[zt.type] || '#eee8dc',
    });
  });

  return zones;
}

// ═══════════════════════════════════════════════════════
// 3. ROADS (Organic connection paths & Sparse internals)
// ═══════════════════════════════════════════════════════
function generateRoads(rng: () => number, zones: CampusZone[], water: CampusWaterBody[]): CampusRoad[] {
  const roads: CampusRoad[] = [];
  let rid = 0;

  // 1. 生成自然弯曲的区域间连接道路
  const connections = new Set<string>();
  zones.forEach((z1, i) => {
    // 寻找最近的2个邻居进行连线
    const neighbors = zones
      .map((z2, j) => ({ index: j, dist: Math.hypot(z1.center[0] - z2.center[0], z1.center[1] - z2.center[1]) }))
      .filter(n => n.index !== i)
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 2);

    neighbors.forEach(n => {
      const minI = Math.min(i, n.index);
      const maxI = Math.max(i, n.index);
      const key = `${minI}-${maxI}`;
      if (!connections.has(key)) {
        connections.add(key);
        const z2 = zones[n.index];
        const path = createCurvedPath(z1.center, z2.center, rng);
        roads.push({ id: rid++, points: path, type: 'main_avenue', width: 1.2 });
      }
    });
  });

  // 2. 在各个区域内生成极少数的直线轴道，打破纯曲线的视觉疲劳
  for (const zone of zones) {
    const gridAngle = Math.abs(Math.sin(zone.center[0] * zone.center[1])) * Math.PI / 2;
    const cos = Math.cos(gridAngle), sin = Math.sin(gridAngle);
    const bounds = polygonBounds(zone.polygon);
    const r = Math.max(bounds.rx, bounds.ry) * 0.6; // 短主轴

    const px1 = zone.center[0] - r * cos, py1 = zone.center[1] - r * sin;
    const px2 = zone.center[0] + r * cos, py2 = zone.center[1] + r * sin;

    if (!isPointInWater(px1, py1, water) && !isPointInWater(px2, py2, water)) {
      roads.push({
        id: rid++, 
        points: [[px1, py1], [px2, py2]], 
        type: 'internal', 
        width: 1.0 
      });
    }
  }

  return roads;
}

function createCurvedPath(p1: [number, number], p2: [number, number], rng: () => number): [number, number][] {
  const pts: [number, number][] = [];
  const steps = 12;
  const dx = p2[0] - p1[0];
  const dy = p2[1] - p1[1];
  const dist = Math.hypot(dx, dy);
  const midX = (p1[0] + p2[0]) / 2;
  const midY = (p1[1] + p2[1]) / 2;
  
  // 法线偏移控制点，产生有机曲线
  const perpX = -dy / dist;
  const perpY = dx / dist;
  const offset = (rng() - 0.5) * dist * 0.35; // 偏移量
  
  const cx = midX + perpX * offset;
  const cy = midY + perpY * offset;
  
  for(let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = (1-t)*(1-t)*p1[0] + 2*(1-t)*t*cx + t*t*p2[0];
    const y = (1-t)*(1-t)*p1[1] + 2*(1-t)*t*cy + t*t*p2[1];
    pts.push([x, y]);
  }
  return pts;
}

// ═══════════════════════════════════════════════════════
// 4. BUILDINGS (Distance Falloff instead of PointInPoly)
// ═══════════════════════════════════════════════════════
function generateBuildings(
  rng: () => number,
  zones: CampusZone[],
  water: CampusWaterBody[],
  pocketParksOut: CampusGreenSpace[]
): CampusBuilding[] {
  const buildings: CampusBuilding[] = [];
  let bid = 0;
  let pid = 10000;

  for (const zone of zones) {
    if (['lake_district', 'central_plaza', 'sports'].includes(zone.type)) continue;

    const gridAngle = Math.abs(Math.sin(zone.center[0] * zone.center[1])) * Math.PI / 2;
    const cos = Math.cos(gridAngle), sin = Math.sin(gridAngle);
    const bounds = polygonBounds(zone.polygon);
    const maxR = Math.max(bounds.rx, bounds.ry) + SPACING;

    for (let lx = -maxR; lx <= maxR; lx += SPACING) {
      for (let ly = -maxR; ly <= maxR; ly += SPACING) {
        const bcx = lx + SPACING / 2;
        const bcy = ly + SPACING / 2;
        
        const gx = zone.center[0] + bcx * cos - bcy * sin;
        const gy = zone.center[1] + bcx * sin + bcy * cos;
        
        // 核心改动：不再局限于区域多边形内部，使用距离中心点的衰减判定，允许建筑自然“溢出”
        const distFromCenter = Math.hypot(gx - zone.center[0], gy - zone.center[1]);
        const dynamicThreshold = maxR * (0.65 + rng() * 0.3); // 允许一定程度的随机边界
        if (distFromCenter > dynamicThreshold) continue;
        
        // 严格水体避让 (边缘保护)
        const safeDist = SPACING * 0.45;
        if (
          isPointInWater(gx, gy, water) ||
          isPointInWater(gx + safeDist, gy + safeDist, water) ||
          isPointInWater(gx - safeDist, gy - safeDist, water) ||
          isPointInWater(gx + safeDist, gy - safeDist, water) ||
          isPointInWater(gx - safeDist, gy + safeDist, water)
        ) {
          continue;
        }

        const maxBuildingSize = SPACING * 0.75;
        const bAngle = gridAngle + Math.floor(rng() * 4) * (Math.PI / 2);

        if (rng() < 0.15) {
          pocketParksOut.push({
            id: pid++, name: 'POCKET PARK', type: 'garden', center: [gx, gy],
            polygon: createRotatedRect(gx, gy, maxBuildingSize, maxBuildingSize, bAngle)
          });
          continue; 
        }

        const shapeType = rng();
        let footprint: [number, number][];

        if (shapeType < 0.4) {
          footprint = createRotatedRect(gx, gy, maxBuildingSize, maxBuildingSize * (0.5 + rng() * 0.5), bAngle);
        } else if (shapeType < 0.7) {
          footprint = createLShape(gx, gy, maxBuildingSize, maxBuildingSize, maxBuildingSize * 0.4, bAngle);
        } else {
          footprint = createUShape(gx, gy, maxBuildingSize, maxBuildingSize, maxBuildingSize * 0.4, bAngle);
        }

        const bType = rng() < 0.7 ? zoneBuildingType(zone.type) : secondaryBuildingType(zone.type, rng);

        buildings.push({
          id: bid++,
          footprint,
          type: bType,
          height: buildingHeight(bType, rng),
        });
      }
    }
  }

  return buildings;
}

function createRotatedRect(cx: number, cy: number, w: number, h: number, angle: number): [number, number][] {
  const cos = Math.cos(angle), sin = Math.sin(angle);
  return [[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]].map(([dx, dy]) => 
    [cx + dx * cos - dy * sin, cy + dx * sin + dy * cos]
  );
}

function createLShape(cx: number, cy: number, w: number, h: number, thick: number, angle: number): [number, number][] {
  const pts: [number, number][] = [
    [-w/2, -h/2], [w/2, -h/2], [w/2, -h/2 + thick], 
    [-w/2 + thick, -h/2 + thick], [-w/2 + thick, h/2], [-w/2, h/2]
  ];
  const cos = Math.cos(angle), sin = Math.sin(angle);
  return pts.map(([dx, dy]) => [cx + dx * cos - dy * sin, cy + dx * sin + dy * cos]);
}

function createUShape(cx: number, cy: number, w: number, h: number, thick: number, angle: number): [number, number][] {
  const pts: [number, number][] = [
    [-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [w/2 - thick, h/2], 
    [w/2 - thick, -h/2 + thick], [-w/2 + thick, -h/2 + thick], 
    [-w/2 + thick, h/2], [-w/2, h/2]
  ];
  const cos = Math.cos(angle), sin = Math.sin(angle);
  return pts.map(([dx, dy]) => [cx + dx * cos - dy * sin, cy + dx * sin + dy * cos]);
}

function zoneBuildingType(zoneType: string): CampusBuildingType {
  switch (zoneType) {
    case 'headquarters': return 'headquarters';
    case 'research': return 'research_lab';
    case 'office': return 'office_tower';
    case 'innovation': return 'innovation_center';
    case 'data_center': return 'data_center';
    case 'conference': return 'conference_center';
    case 'training': return 'training_center';
    case 'exhibition': return 'exhibition_hall';
    case 'residential': return 'hotel';
    default: return 'office_tower';
  }
}

function secondaryBuildingType(zoneType: string, rng: () => number): CampusBuildingType {
  const opts: CampusBuildingType[] = ['cafeteria', 'library', 'utility'];
  return opts[Math.floor(rng() * opts.length)];
}

function buildingHeight(type: CampusBuildingType, rng: () => number): number {
  return type === 'headquarters' ? 12 + rng() * 18 : 3 + rng() * 10;
}

// ═══════════════════════════════════════════════════════
// 5. GREEN SPACES
// ═══════════════════════════════════════════════════════
function generateGreenSpaces(rng: () => number, zones: CampusZone[], water: CampusWaterBody[]): CampusGreenSpace[] {
  return []; 
}

// ═══════════════════════════════════════════════════════
// 6 & 7. FACILITIES AND LANDMARKS
// ═══════════════════════════════════════════════════════
function generateFacilities(rng: () => number, zones: CampusZone[], _roads: CampusRoad[]): CampusFacility[] {
  const facilities: CampusFacility[] = [];
  let fid = 0;
  const metroZones = zones.slice(0, 4);
  metroZones.forEach((z, i) => {
    facilities.push({
      id: fid++, position: [z.center[0], z.center[1]],
      name: `METRO ${['A','B','C','D'][i]}`, type: 'metro',
    });
  });
  return facilities;
}

function generateLandmarks(rng: () => number, zones: CampusZone[]): CampusLandmark[] {
  const landmarks: CampusLandmark[] = [];
  const hqZone = zones.find(z => z.type === 'headquarters');
  if (hqZone) landmarks.push({ id: 0, position: hqZone.center, name: 'CAMPUS HQ', type: 'headquarters' });
  return landmarks;
}

// ═══════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════
function isPointInWater(x: number, y: number, water: CampusWaterBody[]): boolean {
  return water.some(w => pointInPoly(x, y, w.polygon));
}

function pointInPoly(px: number, py: number, poly: [number, number][]): boolean {
  if (!poly || !poly.length) return false;
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1];
    const xj = poly[j][0], yj = poly[j][1];
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function polygonArea(poly: [number, number][]): number {
  if (!poly || poly.length < 3) return 0;
  let area = 0;
  for (let i = 0; i < poly.length; i++) {
    const j = (i + 1) % poly.length;
    area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1];
  }
  return Math.abs(area) / 2;
}

function polygonBounds(poly: [number, number][]): { cx: number; cy: number; rx: number; ry: number } {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of poly) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, rx: (maxX - minX) / 2, ry: (maxY - minY) / 2 };
}