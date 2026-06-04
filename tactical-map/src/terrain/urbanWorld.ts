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

const W = 800, H = 800;
const CX = W / 2, CY = H / 2;

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

  // 1. Water bodies (central lake + canals)
  const waterBodies = generateWaterBodies(rng);

  // 2. Zones
  const zones = generateZones(rng, waterBodies);

  // 3. Roads
  const roads = generateRoads(rng, zones, waterBodies);

  // 4. Buildings
  const buildings = generateBuildings(rng, zones, roads, waterBodies);

  // 5. Green spaces
  const greenSpaces = generateGreenSpaces(rng, zones, waterBodies);

  // 6. Facilities
  const facilities = generateFacilities(rng, zones, roads);

  // 7. Landmarks
  const landmarks = generateLandmarks(rng, zones);

  // 8. Stats
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
// WATER — Central lake + canals
// ═══════════════════════════════════════════════════════
function generateWaterBodies(rng: () => number): CampusWaterBody[] {
  const bodies: CampusWaterBody[] = [];

  // Central lake (organic shape — Songshan Lake style)
  const lakeCx = CX * 0.95 + rng() * 40;
  const lakeCy = CY * 1.05 + rng() * 30;
  const lakePoly: [number, number][] = [];
  const baseRx = 110 + rng() * 40;
  const baseRy = 70 + rng() * 30;
  const verts = 28 + Math.floor(rng() * 12);
  for (let i = 0; i < verts; i++) {
    const angle = (i / verts) * Math.PI * 2;
    const rx = baseRx * (0.6 + 0.4 * Math.sin(angle * 2.3 + rng()));
    const ry = baseRy * (0.6 + 0.4 * Math.sin(angle * 1.7 + rng() * 3));
    lakePoly.push([lakeCx + Math.cos(angle) * rx, lakeCy + Math.sin(angle) * ry]);
  }
  bodies.push({ id: 0, name: 'CAMPUS LAKE', polygon: lakePoly, type: 'lake' });

  // Canal from north into lake
  const canalStartX = lakeCx - 30 + rng() * 60;
  const canalY = lakeCy - baseRy - 10;
  const canalLen = 80 + rng() * 60;
  const canalW = 12 + rng() * 8;
  const canalPoly: [number, number][] = [
    [canalStartX - canalW / 2, canalY - canalLen],
    [canalStartX + canalW / 2, canalY - canalLen],
    [canalStartX + canalW / 2 + 5, canalY],
    [canalStartX - canalW / 2 - 5, canalY],
  ];
  bodies.push({ id: 1, name: 'INNOVATION CANAL', polygon: canalPoly, type: 'canal' });

  // Small pond (east garden)
  const pondCx = CX + 150 + rng() * 60;
  const pondCy = CY - 40 + rng() * 40;
  const pondPoly: [number, number][] = [];
  for (let a = 0; a <= Math.PI * 2; a += 0.25) {
    pondPoly.push([pondCx + Math.cos(a) * (18 + rng() * 15), pondCy + Math.sin(a) * (12 + rng() * 10)]);
  }
  bodies.push({ id: 2, name: 'LOTUS POND', polygon: pondPoly, type: 'pond' });

  return bodies;
}

// ═══════════════════════════════════════════════════════
// ZONES — Campus functional areas
// ═══════════════════════════════════════════════════════
function generateZones(rng: () => number, water: CampusWaterBody[]): CampusZone[] {
  const zones: CampusZone[] = [];
  const lakePoly = water[0]?.polygon || [];

  const defs: { type: CampusZone['type']; name: string; cx: number; cy: number; rx: number; ry: number }[] = [
    { type: 'headquarters',  name: 'HEADQUARTERS',      cx: CX - 5,   cy: CY - 110, rx: 90,  ry: 55 },
    { type: 'research',      name: 'RESEARCH ZONE A',   cx: CX - 120, cy: CY - 60,  rx: 75,  ry: 70 },
    { type: 'research',      name: 'RESEARCH ZONE B',   cx: CX + 110, cy: CY - 55,  rx: 80,  ry: 65 },
    { type: 'innovation',    name: 'INNOVATION CENTER',  cx: CX + 100, cy: CY - 150, rx: 70,  ry: 50 },
    { type: 'office',        name: 'OFFICE DISTRICT',   cx: CX - 30,  cy: CY + 140, rx: 110, ry: 60 },
    { type: 'data_center',   name: 'COMPUTING CENTER',  cx: CX + 160, cy: CY + 80,  rx: 55,  ry: 50 },
    { type: 'conference',    name: 'CONFERENCE CENTER', cx: CX - 200, cy: CY - 30,  rx: 50,  ry: 55 },
    { type: 'training',      name: 'TRAINING CENTER',   cx: CX - 160, cy: CY + 120, rx: 55,  ry: 45 },
    { type: 'exhibition',    name: 'EXHIBITION HALL',   cx: CX + 70,  cy: CY - 200, rx: 60,  ry: 40 },
    { type: 'residential',   name: 'RESIDENTIAL AREA',  cx: CX - 20,  cy: CY - 250, rx: 100, ry: 50 },
    { type: 'sports',        name: 'SPORTS COMPLEX',    cx: CX - 10,  cy: CY + 240, rx: 70,  ry: 50 },
    { type: 'dining',        name: 'DINING DISTRICT',   cx: CX + 180, cy: CY - 130, rx: 40,  ry: 35 },
    { type: 'logistics',     name: 'LOGISTICS CENTER',  cx: CX - 220, cy: CY + 200, rx: 50,  ry: 40 },
    { type: 'lake_district', name: 'LAKE DISTRICT',     cx: CX,       cy: CY + 20,  rx: 130, ry: 90 },
  ];

  for (const d of defs) {
    const verts = 8 + Math.floor(rng() * 8);
    const poly: [number, number][] = [];
    for (let v = 0; v < verts; v++) {
      const angle = (v / verts) * Math.PI * 2 + rng() * 0.2;
      const r = 0.7 + rng() * 0.45;
      let px = d.cx + Math.cos(angle) * d.rx * r;
      let py = d.cy + Math.sin(angle) * d.ry * r;
      // Push away from lake
      if (pointInPoly(px, py, lakePoly)) {
        px = d.cx + Math.cos(angle) * d.rx * r * 1.3;
        py = d.cy + Math.sin(angle) * d.ry * r * 1.3;
      }
      poly.push([px, py]);
    }

    zones.push({
      id: `Z${zones.length + 1}`,
      name: d.name,
      type: d.type,
      polygon: poly,
      center: [d.cx, d.cy],
      color: ZONE_COLORS[d.type] || '#eee8dc',
    });
  }

  return zones;
}

// ═══════════════════════════════════════════════════════
// ROADS — Ring road, avenues, internal roads
// ═══════════════════════════════════════════════════════
function generateRoads(rng: () => number, zones: CampusZone[], water: CampusWaterBody[]): CampusRoad[] {
  const roads: CampusRoad[] = [];
  let rid = 0;
  const lakePoly = water[0]?.polygon || [];

  // Ring road — elliptical around campus center
  const ringRx = 250 + rng() * 20;
  const ringRy = 200 + rng() * 20;
  const ringPts: [number, number][] = [];
  for (let a = 0; a <= Math.PI * 2; a += 0.06) {
    let px = CX + Math.cos(a) * ringRx;
    let py = CY + Math.sin(a) * ringRy;
    // Push ring road outward if it crosses the lake
    if (pointInPoly(px, py, lakePoly)) {
      const distToCenter = Math.hypot(px - CX, py - CY);
      const scale = (distToCenter + 80) / distToCenter;
      px = CX + (px - CX) * scale;
      py = CY + (py - CY) * scale;
    }
    ringPts.push([px, py]);
  }
  ringPts.push(ringPts[0]); // close
  roads.push({ id: rid++, points: ringPts, type: 'ring_road', width: 4, name: 'CAMPUS RING ROAD' });

  // Main Avenue — N-S, curving around lake
  const aveNPts: [number, number][] = [];
  for (let y = 0; y <= H; y += 20) {
    const x = CX + Math.sin(y * 0.006) * 40 + (y > CY - 80 && y < CY + 80 ? (y < CY ? -60 : 60) : 0);
    if (!pointInPoly(x, y, lakePoly)) {
      aveNPts.push([x, y]);
    }
  }
  roads.push({ id: rid++, points: aveNPts, type: 'main_avenue', width: 3.5, name: 'MAIN AVENUE' });

  // Cross Avenue — E-W
  const crossPts: [number, number][] = [];
  for (let x = 0; x <= W; x += 20) {
    const y = CY + Math.sin(x * 0.005) * 25;
    if (!pointInPoly(x, y, lakePoly)) {
      crossPts.push([x, y]);
    }
  }
  roads.push({ id: rid++, points: crossPts, type: 'main_avenue', width: 3, name: 'INNOVATION AVENUE' });

  // Internal grid roads within each zone
  for (const zone of zones) {
    if (zone.type === 'lake_district') continue;
    const [cx, cy] = zone.center;
    const spacing = zone.type === 'headquarters' ? 25 : zone.type === 'research' ? 30 : 35;
    const rx = polygonBounds(zone.polygon).rx * 0.8;
    const ry = polygonBounds(zone.polygon).ry * 0.8;

    for (let lx = cx - rx; lx <= cx + rx; lx += spacing) {
      const pts: [number, number][] = [[lx, cy - ry], [lx, cy + ry]];
      roads.push({ id: rid++, points: pts, type: 'internal', width: 1.5 });
    }
    for (let ly = cy - ry; ly <= cy + ry; ly += spacing) {
      const pts: [number, number][] = [[cx - rx, ly], [cx + rx, ly]];
      roads.push({ id: rid++, points: pts, type: 'internal', width: 1.5 });
    }
  }

  // Pedestrian paths around lake
  const lakePedPts: [number, number][] = [];
  const lakeBounds = polygonBounds(lakePoly);
  for (let a = 0; a <= Math.PI * 2; a += 0.04) {
    const px = lakeBounds.cx + Math.cos(a) * (lakeBounds.rx + 15);
    const py = lakeBounds.cy + Math.sin(a) * (lakeBounds.ry + 15);
    lakePedPts.push([px, py]);
  }
  lakePedPts.push(lakePedPts[0]);
  roads.push({ id: rid++, points: lakePedPts, type: 'pedestrian', width: 0.8, name: 'LAKE PROMENADE' });

  return roads;
}

// ═══════════════════════════════════════════════════════
// BUILDINGS — Campus architecture
// ═══════════════════════════════════════════════════════
function generateBuildings(
  rng: () => number,
  zones: CampusZone[],
  _roads: CampusRoad[],
  _water: CampusWaterBody[],
): CampusBuilding[] {
  const buildings: CampusBuilding[] = [];
  let bid = 0;

  for (const zone of zones) {
    if (zone.type === 'lake_district' || zone.type === 'central_plaza') continue;
    const [cx, cy] = zone.center;
    const bounds = polygonBounds(zone.polygon);
    const rx = bounds.rx * 0.7;
    const ry = bounds.ry * 0.7;

    // Building type mapping by zone
    const primaryType = zoneBuildingType(zone.type);
    const spacing = zone.type === 'headquarters' ? 14 : zone.type === 'research' ? 16 : zone.type === 'office' ? 18 : 22;

    for (let x = cx - rx; x < cx + rx; x += spacing) {
      for (let y = cy - ry; y < cy + ry; y += spacing) {
        if (!pointInPoly(x, y, zone.polygon)) continue;

        const jx = x + (rng() - 0.5) * spacing * 0.3;
        const jy = y + (rng() - 0.5) * spacing * 0.3;

        const bw = spacing * (0.4 + rng() * 0.35);
        const bh = spacing * (0.35 + rng() * 0.35);

        // Rectangular footprint (some rotated)
        const angle = rng() < 0.1 ? (rng() - 0.5) * 0.3 : 0;
        const cos = Math.cos(angle), sin = Math.sin(angle);
        const hw = bw / 2, hh = bh / 2;
        const corners: [number, number][] = [
          [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh],
        ];
        const footprint: [number, number][] = corners.map(([dx, dy]) =>
          [jx + dx * cos - dy * sin, jy + dx * sin + dy * cos] as [number, number]
        );

        // Varied building type
        const bType = rng() < 0.7 ? primaryType : secondaryBuildingType(zone.type, rng);

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
    case 'dining': return 'cafeteria';
    case 'sports': return 'gymnasium';
    case 'residential': return 'hotel';
    case 'logistics': return 'utility';
    default: return 'office_tower';
  }
}

function secondaryBuildingType(zoneType: string, rng: () => number): CampusBuildingType {
  const opts: CampusBuildingType[] = zoneType === 'headquarters'
    ? ['office_tower', 'conference_center', 'visitor_center']
    : zoneType === 'research'
    ? ['innovation_center', 'library', 'training_center']
    : zoneType === 'office'
    ? ['conference_center', 'cafeteria', 'innovation_center']
    : ['cafeteria', 'library', 'utility'];
  return opts[Math.floor(rng() * opts.length)];
}

function buildingHeight(type: CampusBuildingType, rng: () => number): number {
  switch (type) {
    case 'headquarters': return 12 + rng() * 18;
    case 'office_tower': return 8 + rng() * 16;
    case 'research_lab': return 4 + rng() * 8;
    case 'innovation_center': return 5 + rng() * 10;
    case 'data_center': return 2 + rng() * 3;
    case 'conference_center': return 2 + rng() * 4;
    case 'training_center': return 3 + rng() * 6;
    case 'exhibition_hall': return 1 + rng() * 2;
    case 'cafeteria': return 1 + rng() * 2;
    case 'library': return 3 + rng() * 5;
    case 'gymnasium': return 1 + rng() * 2;
    case 'hotel': return 8 + rng() * 12;
    case 'visitor_center': return 2 + rng() * 3;
    case 'utility': return 1 + rng() * 2;
    default: return 2 + rng() * 6;
  }
}

// ═══════════════════════════════════════════════════════
// GREEN SPACES — Parks, gardens, green corridors
// ═══════════════════════════════════════════════════════
function generateGreenSpaces(rng: () => number, zones: CampusZone[], water: CampusWaterBody[]): CampusGreenSpace[] {
  const greens: CampusGreenSpace[] = [];
  let gid = 0;

  // Central park around lake
  const lakePoly = water[0]?.polygon || [];
  if (lakePoly.length) {
    const lakeBounds = polygonBounds(lakePoly);
    const parkPoly: [number, number][] = [];
    for (let a = 0; a <= Math.PI * 2; a += 0.08) {
      const px = lakeBounds.cx + Math.cos(a) * (lakeBounds.rx + 20 + rng() * 15);
      const py = lakeBounds.cy + Math.sin(a) * (lakeBounds.ry + 20 + rng() * 15);
      parkPoly.push([px, py]);
    }
    greens.push({ id: gid++, name: 'LAKE PARK', polygon: parkPoly, center: [lakeBounds.cx, lakeBounds.cy], type: 'central_park' });
  }

  // Green corridors between zones (tree-lined connectors)
  const corridorZones = zones.filter(z => z.type === 'research' || z.type === 'office');
  for (let i = 0; i < corridorZones.length - 1; i++) {
    const a = corridorZones[i].center;
    const b = corridorZones[i + 1].center;
    const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const angle = Math.atan2(b[1] - a[1], b[0] - a[0]) + Math.PI / 2;
    const w = 12 + rng() * 8;
    const cw = w / 2;
    const cos = Math.cos(angle) * cw, sin = Math.sin(angle) * cw;
    const beltPoly: [number, number][] = [
      [a[0] - cos, a[1] - sin],
      [a[0] + cos, a[1] + sin],
      [b[0] + cos, b[1] + sin],
      [b[0] - cos, b[1] - sin],
    ];
    greens.push({ id: gid++, name: 'GREEN CORRIDOR', polygon: beltPoly, center: mid, type: 'green_corridor' });
  }

  // Gardens in each zone
  for (const zone of zones) {
    if (zone.type === 'lake_district' || zone.type === 'logistics' || zone.type === 'data_center') continue;
    const [cx, cy] = zone.center;
    // Small pocket garden
    const gr = 8 + rng() * 12;
    const gardenPoly: [number, number][] = [];
    for (let a = 0; a <= Math.PI * 2; a += 0.3) {
      gardenPoly.push([cx + Math.cos(a) * gr * (1 + rng() * 0.3), cy + Math.sin(a) * gr * (1 + rng() * 0.3)]);
    }
    greens.push({ id: gid++, name: `${zone.name} GARDEN`, polygon: gardenPoly, center: [cx, cy], type: 'garden' });
  }

  return greens;
}

// ═══════════════════════════════════════════════════════
// FACILITIES — Transit, parking, charging
// ═══════════════════════════════════════════════════════
function generateFacilities(rng: () => number, zones: CampusZone[], _roads: CampusRoad[]): CampusFacility[] {
  const facilities: CampusFacility[] = [];
  let fid = 0;

  // Metro entrances (near main zones)
  const metroZones = zones.filter(z => ['headquarters', 'research', 'office', 'innovation'].includes(z.type));
  for (let i = 0; i < Math.min(metroZones.length, 4); i++) {
    const z = metroZones[i];
    facilities.push({
      id: fid++, position: [z.center[0] + (rng() - 0.5) * 40, z.center[1] + (rng() - 0.5) * 30],
      name: `METRO ${['A','B','C','D'][i]}`,
      type: 'metro',
    });
  }

  // Shuttle stations (along ring road)
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    facilities.push({
      id: fid++,
      position: [CX + Math.cos(angle) * 280, CY + Math.sin(angle) * 220],
      name: `SHUTTLE STOP ${i + 1}`,
      type: 'shuttle',
    });
  }

  // Parking hubs (near zone edges)
  for (const zone of zones.slice(0, 6)) {
    facilities.push({
      id: fid++,
      position: [zone.center[0] + zone.polygon[0][0] * 0.2, zone.center[1] + zone.polygon[0][1] * 0.2],
      name: `PARKING`,
      type: 'parking',
    });
  }

  // EV charging stations
  for (let i = 0; i < 6; i++) {
    facilities.push({
      id: fid++,
      position: [W * 0.1 + rng() * W * 0.8, H * 0.1 + rng() * H * 0.8],
      name: 'EV CHARGE',
      type: 'ev_charging',
    });
  }

  return facilities;
}

// ═══════════════════════════════════════════════════════
// LANDMARKS — Key campus points
// ═══════════════════════════════════════════════════════
function generateLandmarks(rng: () => number, zones: CampusZone[]): CampusLandmark[] {
  const landmarks: CampusLandmark[] = [];

  const hqZone = zones.find(z => z.type === 'headquarters');
  if (hqZone) landmarks.push({ id: 0, position: hqZone.center, name: 'CAMPUS HQ', type: 'headquarters' });

  const innovZone = zones.find(z => z.type === 'innovation');
  if (innovZone) landmarks.push({ id: 1, position: innovZone.center, name: 'AI RESEARCH TOWER', type: 'tower' });

  const dcZone = zones.find(z => z.type === 'data_center');
  if (dcZone) landmarks.push({ id: 2, position: dcZone.center, name: 'COMPUTING CENTER', type: 'center' });

  landmarks.push({
    id: 3,
    position: [CX + (rng() - 0.5) * 30, CY + (rng() - 0.5) * 20],
    name: 'INNOVATION PLAZA',
    type: 'plaza',
  });

  return landmarks;
}

// ═══════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════

function pointInPoly(px: number, py: number, poly: [number, number][]): boolean {
  if (!poly.length) return false;
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
