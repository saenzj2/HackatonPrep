import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { DEMO_FIELDS, type DemoField } from "../demoFields";
import { useI18n } from "../i18n";

// Brand colors (styles.css): selected point in space navy, demo fields in agricultural green.
const NAVY = "#072c4a";
const GREEN = "#2e7d32";

interface Props {
  /** Pilot region [min_lon, min_lat, max_lon, max_lat] from GET /health, drawn as a dashed box. */
  bbox?: number[];
  selected: { lat: number; lon: number } | null;
  onPick: (lat: number, lon: number) => void;
  onPickDemo: (field: DemoField) => void;
}

/**
 * Click the map to choose a point; demo fields are green markers. Loaded lazily (Field.tsx).
 * Demo names show on hover (13 permanent labels overlap); only the selected field keeps its label.
 * Keyboard and screen-reader users have the demo buttons and the coordinate inputs instead.
 */
export default function FieldMap({ bbox, selected, onPick, onPickDemo }: Props) {
  const { tr } = useI18n();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const handlers = useRef({ onPick, onPickDemo });
  handlers.current = { onPick, onPickDemo };

  useEffect(() => {
    if (!container.current) return;
    // The view fits the pilot region from GET /health (mvp.yaml) once it arrives; never hardcoded.
    const m = L.map(container.current, { center: [0, 0], zoom: 2, scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(m);
    for (const field of DEMO_FIELDS) {
      L.circleMarker([field.lat, field.lon], {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        fillColor: GREEN,
        fillOpacity: 1,
      })
        .bindTooltip(field.name, { direction: "right", offset: [8, 0] })
        .on("click", (e) => {
          L.DomEvent.stopPropagation(e);
          handlers.current.onPickDemo(field);
        })
        .addTo(m);
    }
    m.on("click", (e: L.LeafletMouseEvent) => {
      handlers.current.onPick(Number(e.latlng.lat.toFixed(2)), Number(e.latlng.lng.toFixed(2)));
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current || !bbox || bbox.length !== 4) return;
    const [minLon, minLat, maxLon, maxLat] = bbox;
    const box = L.rectangle(
      [
        [minLat, minLon],
        [maxLat, maxLon],
      ],
      { color: NAVY, weight: 1.5, dashArray: "6 6", fill: false, interactive: false },
    ).addTo(map.current);
    map.current.fitBounds(box.getBounds(), { padding: [16, 16] });
    return () => {
      box.remove();
    };
  }, [bbox]);

  useEffect(() => {
    if (!map.current) return;
    marker.current?.remove();
    marker.current = null;
    if (!selected) return;
    marker.current = L.circleMarker([selected.lat, selected.lon], {
      radius: 10,
      color: "#ffffff",
      weight: 3,
      fillColor: NAVY,
      fillOpacity: 1,
      interactive: false,
    }).addTo(map.current);
    const demo = DEMO_FIELDS.find((f) => f.lat === selected.lat && f.lon === selected.lon);
    marker.current.bindTooltip(demo ? demo.name : `${selected.lat}, ${selected.lon}`, {
      permanent: true,
      direction: "right",
      offset: [10, 0],
      className: "field-map__selected",
    });
  }, [selected?.lat, selected?.lon]);

  return (
    <div
      ref={container}
      className="field-map"
      role="application"
      aria-label={tr(
        "Map of the pilot region. Click to choose your field; green markers are demo fields (hover for the name).",
        "Mapa de la región piloto. Haga clic para elegir su campo; los marcadores verdes son campos de demostración (pase el cursor para ver el nombre).",
      )}
    />
  );
}
