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
    id: "san-carlos",
    name: "San Carlos",
    lat: 11.0,
    lon: -84.6,
    description: "Northern lowlands",
  },
  {
    id: "alajuela",
    name: "Alajuela",
    lat: 10.0,
    lon: -84.2,
    description: "Central Valley",
  },
];
