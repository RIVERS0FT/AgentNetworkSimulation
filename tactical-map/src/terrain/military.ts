import type { Heightmap, MilitaryUnit, TacticalRoute, FireFan, ObservationPost, AnnotationBox, Sector } from '../types';
import type { Force, UnitType, Echelon } from '../types';
import type { Village } from '../types';
import { dist } from '../utils/geometry';

/** Generate military units deployed on the map */
export function generateMilitaryUnits(
  heightmap: Heightmap,
  villages: Village[],
  sectors: Sector[],
  seed: number
): MilitaryUnit[] {
  const { width, height } = heightmap;
  let s = seed + 333;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const units: MilitaryUnit[] = [];

  // Friendly units
  const friendlyDefs: { type: UnitType; echelon: Echelon; label: string }[] = [
    { type: 'headquarters', echelon: 'battalion', label: 'HQ' },
    { type: 'recon', echelon: 'platoon', label: 'R1' },
    { type: 'recon', echelon: 'platoon', label: 'R2' },
    { type: 'infantry', echelon: 'company', label: 'B1' },
    { type: 'infantry', echelon: 'company', label: 'B2' },
    { type: 'armor', echelon: 'platoon', label: 'A1' },
    { type: 'artillery', echelon: 'platoon', label: 'ARTY1' },
    { type: 'supply', echelon: 'platoon', label: 'LOG1' },
  ];

  // Place friendly units around villages in sector A or B
  for (const def of friendlyDefs) {
    const baseVillage = villages[Math.floor(rng() * Math.min(villages.length, 4))];
    const vx = baseVillage?.position[0] ?? width * 0.3;
    const vy = baseVillage?.position[1] ?? height * 0.3;

    units.push({
      id: `FR-${def.label}`,
      force: 'friendly',
      type: def.type,
      echelon: def.echelon,
      position: [vx + rng() * 30 - 15, vy + rng() * 30 - 15],
      label: def.label,
      heading: rng() * Math.PI * 2,
      strength: 70 + rng() * 30,
    });
  }

  // Enemy units — deeper into the map
  const enemyDefs: { type: UnitType; echelon: Echelon; label: string }[] = [
    { type: 'headquarters', echelon: 'battalion', label: 'E-HQ' },
    { type: 'infantry', echelon: 'company', label: 'E1' },
    { type: 'infantry', echelon: 'company', label: 'E2' },
    { type: 'armor', echelon: 'platoon', label: 'E-A1' },
    { type: 'artillery', echelon: 'platoon', label: 'E-ARTY' },
  ];

  for (const def of enemyDefs) {
    const ex = width * 0.5 + rng() * width * 0.4;
    const ey = height * 0.2 + rng() * height * 0.6;

    units.push({
      id: `EN-${def.label}`,
      force: 'enemy',
      type: def.type,
      echelon: def.echelon,
      position: [ex, ey],
      label: def.label,
      heading: Math.PI + rng() * Math.PI * 0.5,
      strength: 50 + rng() * 40,
    });
  }

  // Enemy strongholds
  const strongholdLabels = ['STRONGHOLD ALPHA', 'STRONGHOLD BRAVO'];
  for (const label of strongholdLabels) {
    const sx = width * 0.55 + rng() * width * 0.35;
    const sy = height * 0.2 + rng() * height * 0.6;
    units.push({
      id: `EN-${label}`,
      force: 'enemy',
      type: 'infantry',
      echelon: 'company',
      position: [sx, sy],
      label,
      heading: 0,
      strength: 80 + rng() * 20,
    });
  }

  return units;
}

/** Generate tactical movement routes */
export function generateRoutes(
  friendlyUnits: MilitaryUnit[],
  enemyUnits: MilitaryUnit[],
  sectors: Sector[],
  heightmap: Heightmap,
  _seed: number
): TacticalRoute[] {
  const { width, height } = heightmap;
  const routes: TacticalRoute[] = [];
  let routeId = 0;

  // Advance route: friendly HQ toward enemy positions
  const hq = friendlyUnits.find(u => u.label === 'HQ');
  const enemyHQ = enemyUnits.find(u => u.label === 'E-HQ');
  if (hq && enemyHQ) {
    const mid: [number, number] = [
      (hq.position[0] + enemyHQ.position[0]) / 2,
      (hq.position[1] + enemyHQ.position[1]) / 2,
    ];
    routes.push({
      id: routeId++,
      waypoints: [hq.position, mid, enemyHQ.position],
      type: 'advance',
      force: 'friendly',
      label: 'AXIS MAIN',
      planned: false,
    });

    // Flanking route
    const flankMid: [number, number] = [
      mid[0] + width * 0.08,
      mid[1] - height * 0.05,
    ];
    routes.push({
      id: routeId++,
      waypoints: [hq.position, flankMid, enemyHQ.position],
      type: 'flanking',
      force: 'friendly',
      label: 'AXIS FLANK',
      planned: true,
    });
  }

  // Recon routes
  const recon = friendlyUnits.filter(u => u.type === 'recon');
  for (const r of recon) {
    const targetEnemy = enemyUnits[Math.floor(Math.random() * enemyUnits.length)];
    if (targetEnemy) {
      const sweepMid: [number, number] = [
        r.position[0] + (targetEnemy.position[0] - r.position[0]) * 0.6,
        r.position[1] + (targetEnemy.position[1] - r.position[1]) * 0.4 - height * 0.03,
      ];
      routes.push({
        id: routeId++,
        waypoints: [r.position, sweepMid, targetEnemy.position],
        type: 'recon',
        force: 'friendly',
        label: `RECON ${r.label}`,
        planned: false,
      });
    }
  }

  return routes;
}

/** Generate fire support coverage fans */
export function generateFireFans(
  units: MilitaryUnit[],
  _heightmap: Heightmap,
  _seed: number
): FireFan[] {
  const fireFans: FireFan[] = [];
  let fanId = 0;

  for (const unit of units) {
    if (unit.type === 'artillery') {
      fireFans.push({
        id: fanId++,
        origin: unit.position,
        azimuth: unit.heading,
        arc: Math.PI / 3,
        minRange: 10,
        maxRange: 60,
        force: unit.force,
        type: unit.force === 'friendly' ? 'artillery' : 'mortar',
      });
    }
    if (unit.type === 'infantry' && unit.echelon === 'company') {
      fireFans.push({
        id: fanId++,
        origin: unit.position,
        azimuth: unit.heading,
        arc: Math.PI / 4,
        minRange: 0,
        maxRange: 15,
        force: unit.force,
        type: 'machinegun',
      });
    }
  }

  return fireFans;
}

/** Generate observation posts */
export function generateObservationPosts(
  heightmap: Heightmap,
  seed: number
): ObservationPost[] {
  const { width, height } = heightmap;
  let s = seed + 444;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const ops: ObservationPost[] = [];
  for (let i = 0; i < 3; i++) {
    const x = width * 0.2 + rng() * width * 0.4;
    const y = height * 0.2 + rng() * height * 0.4;
    ops.push({
      id: i,
      position: [x, y],
      label: `OP${i + 1}`,
      azimuth: rng() * Math.PI * 2,
      arc: Math.PI / 2 + rng() * Math.PI / 2,
      range: 20 + rng() * 30,
    });
  }

  return ops;
}

/** Generate annotation boxes for terrain analysis */
export function generateAnnotations(
  sectors: Sector[],
  _heightmap: Heightmap,
  _villages: Village[],
  _seed: number
): AnnotationBox[] {
  const annotations: AnnotationBox[] = [];
  let annoId = 0;

  const terrainNotes = [
    'DENSE FOREST — LIMITED VISIBILITY',
    'OPEN GROUND — SUITABLE FOR ARMOR',
    'ROCKY TERRAIN — SLOW MOVEMENT',
    'RIVER CROSSING — ENGINEER SUPPORT REQD',
    'ELEVATED POSITION — GOOD OBSERVATION',
    'DEFILADE — COVER FROM DIRECT FIRE',
    'CHOKE POINT — KEY TERRAIN',
  ];

  for (let i = 0; i < Math.min(terrainNotes.length, sectors.length * 2); i++) {
    const sector = sectors[i % sectors.length];
    annotations.push({
      id: annoId++,
      position: [
        sector.center[0] + (Math.random() - 0.5) * 30,
        sector.center[1] + (Math.random() - 0.5) * 30,
      ],
      label: 'TERRAIN ANALYSIS',
      text: terrainNotes[i % terrainNotes.length],
      sectorId: sector.id,
    });
  }

  return annotations;
}
