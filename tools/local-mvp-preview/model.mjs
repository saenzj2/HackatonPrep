// Display extent from docs/pilot-baseline, not an analytical raster transform.
export const bounds = [-84.64, 10.97, -84.56, 11.03];
export function normalize(values) {
  const total = values.reduce((sum, value) => sum + value, 0);
  return total ? values.map(value => value / total) : values.map(() => 0);
}
export function constrain(rect) {
  const w = Math.max(0, Math.min(100, rect.w));
  const h = Math.max(0, Math.min(100, rect.h));
  return {x: Math.max(0, Math.min(100 - w, rect.x)), y: Math.max(0, Math.min(100 - h, rect.y)), w, h};
}
export function selectionBounds(rect) {
  const [west, south, east, north] = bounds;
  const lon = x => west + x / 100 * (east - west);
  const lat = y => north - y / 100 * (north - south);
  return [lon(rect.x), lat(rect.y + rect.h), lon(rect.x + rect.w), lat(rect.y)];
}
