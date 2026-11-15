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
  // Added 2026-11-15 (decisions.md): one or more points per region, all in the committed cache,
  // each in its own NASA POWER climate cell (~50 km), so no two share the same climate.
  { id: "upala", name: "Upala", lat: 10.9, lon: -85.0, description: "Northern zone" },
  { id: "sarapiqui", name: "Sarapiquí", lat: 10.4, lon: -84.0, description: "Northern zone" },
  { id: "liberia", name: "Liberia", lat: 10.6, lon: -85.4, description: "North Pacific" },
  { id: "nicoya", name: "Nicoya", lat: 10.1, lon: -85.4, description: "North Pacific" },
  { id: "parrita", name: "Parrita", lat: 9.6, lon: -84.3, description: "Central Pacific" },
  { id: "cartago", name: "Cartago", lat: 9.9, lon: -83.9, description: "Central Valley" },
  { id: "matina", name: "Matina", lat: 10.1, lon: -83.3, description: "Caribbean" },
  { id: "bribri", name: "Bribri", lat: 9.6, lon: -82.7, description: "South Caribbean" },
  { id: "perez-zeledon", name: "Pérez Zeledón", lat: 9.4, lon: -83.7, description: "South Pacific" },
  { id: "buenos-aires", name: "Buenos Aires", lat: 9.2, lon: -83.3, description: "South Pacific" },
  { id: "ciudad-neily", name: "Ciudad Neily", lat: 8.6, lon: -82.9, description: "South Pacific" },
];

/**
 * One-click demo from Home: a demo field plus a common smallholder starting point (the same crop
 * every season) so the results show a comparison with "what you grow now". Crop ids must be in
 * GET /crops (mvp.yaml).
 */
export const DEMO_SCENARIO = {
  fieldId: "alajuela",
  currentCrop: "maize",
} as const;
