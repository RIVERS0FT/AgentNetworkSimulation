// ── Huawei Smart Campus Atlas Types ──────────────────

export type CampusZoneType =
  | 'headquarters' | 'research' | 'office' | 'innovation'
  | 'data_center' | 'conference' | 'training' | 'exhibition'
  | 'logistics' | 'residential' | 'dining' | 'sports'
  | 'central_plaza' | 'lake_district';

export type CampusRoadType = 'ring_road' | 'main_avenue' | 'internal' | 'pedestrian' | 'cycling';

export type CampusBuildingType =
  | 'headquarters' | 'research_lab' | 'office_tower' | 'innovation_center'
  | 'data_center' | 'conference_center' | 'training_center'
  | 'exhibition_hall' | 'cafeteria' | 'library'
  | 'gymnasium' | 'hotel' | 'visitor_center' | 'utility';

export interface CampusZone {
  id: string;
  name: string;
  type: CampusZoneType;
  polygon: [number, number][];
  center: [number, number];
  color: string;
}

export interface CampusBuilding {
  id: number;
  footprint: [number, number][];
  type: CampusBuildingType;
  height: number;
  name?: string;
}

export interface CampusRoad {
  id: number;
  points: [number, number][];
  type: CampusRoadType;
  width: number;
  name?: string;
}

export interface CampusGreenSpace {
  id: number;
  name: string;
  polygon: [number, number][];
  center: [number, number];
  type: 'central_park' | 'lake' | 'garden' | 'green_corridor' | 'tree_belt';
}

export interface CampusWaterBody {
  id: number;
  name: string;
  polygon: [number, number][];
  type: 'lake' | 'canal' | 'pond' | 'water_garden';
}

export interface CampusFacility {
  id: number;
  position: [number, number];
  name: string;
  type: 'metro' | 'shuttle' | 'parking' | 'ev_charging' | 'bus_stop';
}

export interface CampusLandmark {
  id: number;
  position: [number, number];
  name: string;
  type: 'headquarters' | 'tower' | 'plaza' | 'center';
}

// Compatibility aliases for existing component interfaces
export type CityWorld = CampusWorld;
export type CityStats = CampusStats;
export type CityDistrict = CampusZone;
export type CityRoad = CampusRoad;
export type CityBuilding = CampusBuilding;
export type CityPark = CampusGreenSpace;
export type CityWaterBody = CampusWaterBody;
export type CityLandmark = CampusLandmark;

export interface CampusWorld {
  seed: number;
  width: number;
  height: number;
  zones: CampusZone[];
  roads: CampusRoad[];
  buildings: CampusBuilding[];
  greenSpaces: CampusGreenSpace[];
  waterBodies: CampusWaterBody[];
  facilities: CampusFacility[];
  landmarks: CampusLandmark[];
  stats: CampusStats;
}

export interface CampusStats {
  buildingCount: number;
  researchCenters: number;
  employees: number;
  roadLengthKm: number;
  greenCoverage: number;
  waterCoverage: number;
  parkingSpaces: number;
  campusArea: number;
}
