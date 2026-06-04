import type { TerrainWorld, TerrainConfig } from '../types';
import { generateHeightmap } from './heightmap';
import { generateRivers } from './hydrology';
import { generateSectors } from './voronoi';
import { classifyBiomes, generateMoisture } from './biomes';
import { generateVillages, generateRoads } from './features';
import {
  generateMilitaryUnits,
  generateRoutes,
  generateFireFans,
  generateObservationPosts,
  generateAnnotations,
} from './military';

/**
 * Top-level orchestrator: generates all terrain data for the tactical map.
 */
export function generateWorld(seed?: number): TerrainWorld {
  const config: TerrainConfig = {
    seed: seed ?? Math.floor(Math.random() * 2147483647),
    width: 512,
    height: 512,
  };

  // 1. Heightmap from fBm noise
  const heightmap = generateHeightmap(config);

  // 2. Initial river mask for moisture calculation
  const rivers = generateRivers(heightmap, config.seed);

  // Build river mask
  const riverMask = new Uint8Array(heightmap.width * heightmap.height);
  for (const river of rivers) {
    for (const [rx, ry] of river.points) {
      const ix = Math.floor(rx), iy = Math.floor(ry);
      if (ix >= 0 && ix < heightmap.width && iy >= 0 && iy < heightmap.height) {
        riverMask[iy * heightmap.width + ix] = 1;
      }
    }
  }

  // 3. Moisture map
  const moisture = generateMoisture(heightmap, config.seed, riverMask);

  // 4. Biome classification
  const biomes = classifyBiomes(heightmap, moisture);

  // 5. Sectors (Voronoi)
  const sectors = generateSectors(heightmap.width, heightmap.height, 6, config.seed);

  // Update sector info
  for (const sector of sectors) {
    let sumElev = 0, count = 0;
    const biomeCounts: Record<string, number> = {};
    for (let y = 0; y < heightmap.height; y += 4) {
      for (let x = 0; x < heightmap.width; x += 4) {
        const idx = y * heightmap.width + x;
        sumElev += heightmap.data[idx];
        const biome = biomes[idx];
        biomeCounts[biome] = (biomeCounts[biome] || 0) + 1;
        count++;
      }
    }
    sector.avgElevation = sumElev / Math.max(1, count);
    let dominant = 'mixed', maxCount = 0;
    for (const [b, c] of Object.entries(biomeCounts)) {
      if (c > maxCount) { maxCount = c; dominant = b; }
    }
    sector.dominantTerrain = dominant;
    sector.threatLevel = dominant === 'mountain' || dominant === 'peak' ? 'high' :
      dominant === 'forest' ? 'medium' : 'low';
    sector.keyTerrain = dominant === 'water' ? ['River crossing', 'Bridge'] :
      dominant === 'mountain' ? ['High ground', 'Pass'] : ['Open approach'];
  }

  // 6. Villages
  const villages = generateVillages(heightmap, biomes, rivers, config.seed, 12);

  // 7. Roads and bridges
  const { roads, bridges } = generateRoads(villages, heightmap, rivers, config.seed);

  // 8. Military units
  const units = generateMilitaryUnits(heightmap, villages, sectors, config.seed);

  const friendlyUnits = units.filter(u => u.force === 'friendly');
  const enemyUnits = units.filter(u => u.force === 'enemy');

  // 9. Tactical routes
  const routes = generateRoutes(friendlyUnits, enemyUnits, sectors, heightmap, config.seed);

  // 10. Fire support fans
  const fireFans = generateFireFans(units, heightmap, config.seed);

  // 11. Observation posts
  const observationPosts = generateObservationPosts(heightmap, config.seed);

  // 12. Annotations
  const annotations = generateAnnotations(sectors, heightmap, villages, config.seed);

  // Extract strongholds from enemy units
  const strongholds = units
    .filter(u => u.force === 'enemy' && u.label.startsWith('STRONGHOLD'))
    .map(u => ({ position: u.position, label: u.label, force: u.force }));

  return {
    config,
    heightmap,
    moisture,
    sectors,
    rivers,
    forests: [],  // forests rendered via biome data on the frontend
    roads,
    villages,
    bridges,
    strongholds,
    units,
    observationPosts,
    routes,
    fireFans,
    annotations,
  };
}
