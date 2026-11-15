// Points preloaded in the committed cache (backend/app/cache/snapshots/, docs/deploy.md).
// In production (cached mode) any other point answers 503 cache_miss.
export interface DemoField {
  id: string;
  name: string;
  lat: number;
  lon: number;
  description: string;
}

export const DEMO_FIELDS: DemoField[] = [
  {
    // Relabeled from "San Carlos" (decisions.md 2026-11-15): the point is ~12 km from Los Chiles.
    id: "los-chiles",
    name: "Los Chiles",
    lat: 11.0,
    lon: -84.6,
    description: "Northern zone",
  },
  {
    id: "alajuela",
    name: "Alajuela",
    lat: 10.0,
    lon: -84.2,
    description: "Central Valley",
  },
];
