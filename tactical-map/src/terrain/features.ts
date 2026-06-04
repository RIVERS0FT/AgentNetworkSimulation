import type { Heightmap, Road, Village, Bridge, River } from '../types';
import type { Biome } from './biomes';
import { dist } from '../utils/geometry';

/** Place villages on flat, dry land near rivers or road intersections */
export function generateVillages(
  heightmap: Heightmap,
  biomes: Biome[],
  rivers: River[],
  seed: number,
  numVillages: number
): Village[] {
  const { width, height } = heightmap;
  let s = seed + 111;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const villageNames = [
    'Ashford', 'Bentham', 'Crosshill', 'Danbury', 'Elmsworth',
    'Farndon', 'Glenville', 'Hawkstead', 'Inwood', 'Jarrow',
    'Kelsby', 'Lindle', 'Merton', 'Norbridge', 'Oakvale',
    'Preston', 'Quinton', 'Rosedale', 'Stanby', 'Thorndale',
    'Upton', 'Vernwood', 'Whitby', 'Yorkley',
  ];

  // Score each candidate cell
  const candidates: { x: number; y: number; score: number }[] = [];

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const biome = biomes[y * width + x];
      if (biome === 'water' || biome === 'wetland' || biome === 'mountain' || biome === 'peak') continue;

      let score = 0;
      if (biome === 'plain') score += 3;
      if (biome === 'forest') score += 1;
      if (biome === 'hills') score += 1;

      // Bonus for proximity to rivers
      let minRiverDist = Infinity;
      for (const river of rivers) {
        for (const [rx, ry] of river.points) {
          const d = Math.hypot(x - rx, y - ry);
          if (d < minRiverDist) minRiverDist = d;
        }
      }
      if (minRiverDist < 15) score += 5;
      if (minRiverDist < 8) score += 3;

      // Penalty for proximity to other villages (avoid clustering too much)
      score += rng() * 4;

      candidates.push({ x, y, score });
    }
  }

  candidates.sort((a, b) => b.score - a.score);

  const villages: Village[] = [];
  const minVillageDist = 20;

  for (const c of candidates) {
    if (villages.length >= numVillages) break;
    // Ensure minimum spacing
    let tooClose = false;
    for (const v of villages) {
      if (dist([c.x, c.y], v.position) < minVillageDist) {
        tooClose = true;
        break;
      }
    }
    if (tooClose) continue;

    const size = 3 + Math.floor(rng() * 6);
    const buildings: [number, number][][] = [];

    for (let b = 0; b < size; b++) {
      const bx = c.x + (rng() - 0.5) * 8;
      const by = c.y + (rng() - 0.5) * 8;
      const bw = 1 + rng() * 2;
      const bh = 1 + rng() * 2;
      buildings.push([
        [bx - bw / 2, by - bh / 2],
        [bx + bw / 2, by - bh / 2],
        [bx + bw / 2, by + bh / 2],
        [bx - bw / 2, by + bh / 2],
      ]);
    }

    villages.push({
      id: villages.length,
      position: [c.x, c.y],
      name: villageNames[villages.length % villageNames.length],
      size,
      buildings,
    });
  }

  return villages;
}

/** Build roads connecting villages and key locations */
export function generateRoads(
  villages: Village[],
  heightmap: Heightmap,
  rivers: River[],
  seed: number
): { roads: Road[]; bridges: Bridge[] } {
  const { width, height } = heightmap;
  let s = seed + 222;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const roads: Road[] = [];
  const bridges: Bridge[] = [];
  const connected = new Set<number>();

  if (villages.length < 2) return { roads, bridges };

  // Build MST-like network: connect each village to its nearest neighbor
  for (let i = 0; i < villages.length; i++) {
    let bestJ = -1, bestDist = Infinity;
    for (let j = 0; j < villages.length; j++) {
      if (i === j) continue;
      const d = dist(villages[i].position, villages[j].position);
      if (d < bestDist) {
        bestDist = d;
        bestJ = j;
      }
    }

    if (bestJ >= 0 && !connected.has(i)) {
      connected.add(i);
      connected.add(bestJ);

      const start = villages[i].position;
      const end = villages[bestJ].position;

      // Pathfinding with terrain cost
      const path = findRoadPath(heightmap, rivers, start, end, width, height, rng);

      const roadType = bestDist > 60 ? 'trail' : bestDist > 30 ? 'secondary' : 'primary';

      roads.push({
        id: roads.length,
        points: path,
        type: roadType as 'primary' | 'secondary' | 'trail',
      });

      // Check for river crossings and place bridges
      for (let pi = 0; pi < path.length; pi++) {
        for (const river of rivers) {
          for (const [rx, ry] of river.points) {
            if (dist(path[pi], [rx, ry]) < 3) {
              // Check if not already bridged here
              let alreadyBridged = false;
              for (const bridge of bridges) {
                if (dist(bridge.position, [rx, ry]) < 5) {
                  alreadyBridged = true;
                  break;
                }
              }
              if (!alreadyBridged) {
                bridges.push({
                  id: bridges.length,
                  position: [rx, ry],
                  roadId: roads.length - 1,
                  riverId: river.id,
                });
              }
            }
          }
        }
      }
    }
  }

  // Add a few extra roads between larger villages (skip some to reduce density)
  if (villages.length > 4) {
    for (let i = 0; i < Math.floor(villages.length / 3); i++) {
      const a = Math.floor(rng() * villages.length);
      let b = Math.floor(rng() * villages.length);
      if (b === a) b = (a + 1) % villages.length;

      const start = villages[a].position;
      const end = villages[b].position;
      const path = findRoadPath(heightmap, rivers, start, end, width, height, rng);

      roads.push({
        id: roads.length,
        points: path,
        type: 'secondary',
      });
    }
  }

  return { roads, bridges };
}

/** Simple A*-like pathfinding for roads (avoiding water and peaks) */
function findRoadPath(
  heightmap: Heightmap,
  _rivers: River[],
  start: [number, number],
  end: [number, number],
  width: number,
  height: number,
  rng: () => number
): [number, number][] {
  const { data } = heightmap;
  const path: [number, number][] = [start];

  let [cx, cy] = start;
  const [ex, ey] = end;
  const steps = Math.ceil(dist(start, end));

  for (let step = 0; step < steps; step++) {
    const progress = step / steps;
    const tx = cx + (ex - cx) * (1 / (steps - step));
    const ty = cy + (ey - cy) * (1 / (steps - step));

    // Adjust slightly to avoid water/mountains
    let bestX = tx, bestY = ty, bestCost = Infinity;
    for (let dy = -3; dy <= 3; dy++) {
      for (let dx = -3; dx <= 3; dx++) {
        const nx = tx + dx;
        const ny = ty + dy;
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;

        const elev = data[Math.floor(ny) * width + Math.floor(nx)];
        const straggle = Math.abs(dx) + Math.abs(dy);

        // Avoid high elevations (mountains), prefer gentle terrain
        if (elev > 0.7) continue;

        const cost = straggle * 1.5 + elev * 3 + (elev > 0.5 ? 10 : 0);
        if (cost < bestCost) {
          bestCost = cost;
          bestX = nx;
          bestY = ny;
        }
      }
    }

    cx = bestX;
    cy = bestY;
    path.push([cx, cy]);
  }

  path.push(end);

  // Slight randomization for natural look
  for (let i = 1; i < path.length - 1; i++) {
    path[i][0] += rng() * 2 - 1;
    path[i][1] += rng() * 2 - 1;
  }

  return path;
}
