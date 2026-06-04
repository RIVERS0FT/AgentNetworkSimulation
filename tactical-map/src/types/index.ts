// ── Core Terrain Types ─────────────────────────────────

export interface TerrainConfig {
  seed: number;
  width: number;
  height: number;
}

export interface Heightmap {
  data: Float32Array;
  width: number;
  height: number;
  min: number;
  max: number;
}

// ── Geographic Features ────────────────────────────────

export interface River {
  id: number;
  points: [number, number][];
  width: number;
  flow: number;
  isMain: boolean;
}

export interface Forest {
  id: number;
  polygon: [number, number][];
  center: [number, number];
  density: number;
  radius: number;
}

export interface Road {
  id: number;
  points: [number, number][];
  type: 'primary' | 'secondary' | 'trail';
}

export interface Village {
  id: number;
  position: [number, number];
  name: string;
  size: number;
  buildings: [number, number][][];
}

export interface Bridge {
  id: number;
  position: [number, number];
  roadId: number;
  riverId: number;
}

// ── Military ───────────────────────────────────────────

export type Force = 'friendly' | 'enemy' | 'neutral';
export type UnitType = 'infantry' | 'armor' | 'artillery' | 'recon' | 'headquarters' | 'supply';
export type Echelon = 'squad' | 'platoon' | 'company' | 'battalion';

export interface MilitaryUnit {
  id: string;
  force: Force;
  type: UnitType;
  echelon: Echelon;
  position: [number, number];
  label: string;
  heading: number;
  strength: number;
}

export interface TacticalRoute {
  id: number;
  waypoints: [number, number][];
  type: 'advance' | 'flanking' | 'recon' | 'withdrawal';
  force: Force;
  label: string;
  planned: boolean;
}

export interface FireFan {
  id: number;
  origin: [number, number];
  azimuth: number;
  arc: number;
  minRange: number;
  maxRange: number;
  force: Force;
  type: 'mortar' | 'artillery' | 'machinegun';
}

export interface ObservationPost {
  id: number;
  position: [number, number];
  label: string;
  azimuth: number;
  arc: number;
  range: number;
}

// ── Terrain Analysis ───────────────────────────────────

export interface Sector {
  id: string;
  polygon: [number, number][];
  center: [number, number];
  dominantTerrain: string;
  avgElevation: number;
  threatLevel: 'low' | 'medium' | 'high';
  keyTerrain: string[];
}

export interface AnnotationBox {
  id: number;
  position: [number, number];
  label: string;
  text: string;
  sectorId?: string;
}

// ── Complete World ─────────────────────────────────────

export interface TerrainWorld {
  config: TerrainConfig;
  heightmap: Heightmap;
  moisture: Float32Array;
  sectors: Sector[];
  rivers: River[];
  forests: Forest[];
  roads: Road[];
  villages: Village[];
  bridges: Bridge[];
  strongholds: { position: [number, number]; label: string; force: Force }[];
  units: MilitaryUnit[];
  observationPosts: ObservationPost[];
  routes: TacticalRoute[];
  fireFans: FireFan[];
  annotations: AnnotationBox[];
}

// ── Rendering ──────────────────────────────────────────

export interface Viewport {
  zoom: number;
  panX: number;
  panY: number;
  width: number;
  height: number;
}

export interface LayerVisibility {
  terrain: boolean;
  contours: boolean;
  rivers: boolean;
  forests: boolean;
  roads: boolean;
  settlements: boolean;
  grid: boolean;
  symbols: boolean;
  routes: boolean;
  fireFans: boolean;
  labels: boolean;
  sectors: boolean;
}

export interface CursorInfo {
  worldX: number;
  worldY: number;
  elevation: number | null;
  sector: string | null;
  terrain: string | null;
}
