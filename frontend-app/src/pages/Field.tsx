import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type Conditions, type SoilProfile } from "../api/client";
import { RainChart, TemperatureChart } from "../components/ClimateCharts";
import { ErrorNotice } from "../components/ErrorNotice";
import { Stepper } from "../components/Stepper";
import { DEMO_FIELDS, type DemoField } from "../demoFields";
import { capitalize, monthSpan, textureName } from "../format";
import { useI18n } from "../i18n";
import { organicMatterPct } from "../practices";
import { usePlan } from "../state/PlanContext";

// The map (Leaflet + tiles) loads only when this page opens.
const FieldMap = lazy(() => import("../components/FieldMap"));

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; conditions: Conditions; soil: SoilProfile | null }
  | { kind: "error"; error: unknown; lat: number; lon: number; name: string };

const SOURCE_LABELS: Record<string, { en: string; es: string }> = {
  nasa_power: { en: "NASA POWER (long-term monthly averages)", es: "NASA POWER (promedios mensuales de largo plazo)" },
  "openlandmap+nasa_smap": {
    en: "OpenLandMap soil map (pH) and NASA SMAP satellite (soil moisture)",
    es: "Mapa de suelos OpenLandMap (pH) y satélite NASA SMAP (humedad del suelo)",
  },
  ecocrop_subset: { en: "FAO EcoCrop crop requirements", es: "Requisitos de cultivos de FAO EcoCrop" },
};

type Tr = (en: string, es: string) => string;

function validate(text: string, limit: number, name: { en: string; es: string }, tr: Tr): string | null {
  if (text.trim() === "") return tr(`Enter a ${name.en}.`, `Escriba una ${name.es}.`);
  const value = Number(text);
  if (!Number.isFinite(value) || value < -limit || value > limit) {
    return tr(`Enter a ${name.en} between -${limit} and ${limit}.`, `Escriba una ${name.es} entre -${limit} y ${limit}.`);
  }
  return null;
}

export function Field() {
  const { tr, lang } = useI18n();
  const { plan, setField } = usePlan();
  const [lat, setLat] = useState(plan.field ? String(plan.field.lat) : "");
  const [lon, setLon] = useState(plan.field ? String(plan.field.lon) : "");
  const [errors, setErrors] = useState<{ lat?: string; lon?: string }>({});
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [point, setPoint] = useState(plan.field ? { lat: plan.field.lat, lon: plan.field.lon } : null);
  const [bbox, setBbox] = useState<number[] | undefined>();
  // Ignore answers that arrive after the page closed or after a newer lookup started.
  const latestLookup = useRef(0);
  useEffect(() => () => {
    latestLookup.current = -1;
  }, []);

  useEffect(() => {
    // Coming back to this step: show the saved field again.
    if (plan.field) void lookUp(plan.field.lat, plan.field.lon, plan.field.name);
    api
      .health()
      .then((h) => setBbox(h.region.bbox))
      .catch(() => undefined); // the region box is a hint only
  }, []); // only on first render

  async function lookUp(latValue: number, lonValue: number, name: string) {
    setPoint({ lat: latValue, lon: lonValue });
    setLat(String(latValue));
    setLon(String(lonValue));
    const id = ++latestLookup.current;
    setStatus({ kind: "loading" });
    try {
      // The soil profile adds organic carbon; it is optional, so its failure never blocks the step.
      const [conditions, soil] = await Promise.all([
        api.conditions(latValue, lonValue),
        api.soil(latValue, lonValue).catch(() => null),
      ]);
      if (id !== latestLookup.current) return;
      setField({
        lat: latValue,
        lon: lonValue,
        name,
        seasons: conditions.seasons.map(({ name: season, months }) => ({ name: season, months })),
      });
      setStatus({ kind: "ready", conditions, soil });
    } catch (error) {
      if (id !== latestLookup.current) return;
      setStatus({ kind: "error", error, lat: latValue, lon: lonValue, name });
    }
  }

  const pickDemo = (field: DemoField) => {
    setErrors({});
    void lookUp(field.lat, field.lon, field.name);
  };

  const pickPoint = (latValue: number, lonValue: number) => {
    setErrors({});
    void lookUp(latValue, lonValue, `${latValue}, ${lonValue}`); // reads the same in both languages
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = {
      lat: validate(lat, 90, { en: "latitude", es: "latitud" }, tr) ?? undefined,
      lon: validate(lon, 180, { en: "longitude", es: "longitud" }, tr) ?? undefined,
    };
    setErrors(next);
    if (next.lat) return document.getElementById("lat")?.focus();
    if (next.lon) return document.getElementById("lon")?.focus();
    pickPoint(Number(lat), Number(lon));
  }

  return (
    <div className="stack">
      <Stepper current="field" />
      <h1>{tr("Where is your field?", "¿Dónde está su campo?")}</h1>
      <p className="lead">
        {tr(
          "Click your field on the map. We use that point to look up climate and soil.",
          "Haga clic en su campo en el mapa. Con ese punto buscamos el clima y el suelo.",
        )}
      </p>

      <section className="panel stack" aria-label={tr("Choose your field", "Elija su campo")}>
        <Suspense fallback={<div className="skeleton field-map" role="status" aria-label={tr("Loading map", "Cargando el mapa")} />}>
          <FieldMap key={lang} bbox={bbox} selected={point} onPick={pickPoint} onPickDemo={pickDemo} />
        </Suspense>

        <div className="btn-row">
          <span className="muted small">{tr("Or use a demo field:", "O use un campo de demostración:")}</span>
          {DEMO_FIELDS.map((field) => (
            <button
              key={field.id}
              type="button"
              className="btn btn--secondary btn--small"
              onClick={() => pickDemo(field)}
              aria-pressed={plan.field?.lat === field.lat && plan.field?.lon === field.lon}
            >
              {field.name}
            </button>
          ))}
        </div>

        <details open={Boolean(errors.lat || errors.lon)}>
          <summary>{tr("Enter coordinates instead", "Escribir coordenadas")}</summary>
          <form className="stack" onSubmit={submit} noValidate>
            <div className="grid grid--2">
              <div>
                <label htmlFor="lat">
                  {tr("Latitude", "Latitud")} <span className="hint">{tr("(-90 to 90, e.g. 10.0)", "(-90 a 90, p. ej. 10.0)")}</span>
                </label>
                <input
                  id="lat"
                  type="number"
                  inputMode="decimal"
                  step="any"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  aria-invalid={errors.lat ? true : undefined}
                  aria-describedby={errors.lat ? "lat-error" : undefined}
                />
                {errors.lat && (
                  <p id="lat-error" className="field-error">
                    {errors.lat}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="lon">
                  {tr("Longitude", "Longitud")} <span className="hint">{tr("(-180 to 180, e.g. -84.2)", "(-180 a 180, p. ej. -84.2)")}</span>
                </label>
                <input
                  id="lon"
                  type="number"
                  inputMode="decimal"
                  step="any"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  aria-invalid={errors.lon ? true : undefined}
                  aria-describedby={errors.lon ? "lon-error" : undefined}
                />
                {errors.lon && (
                  <p id="lon-error" className="field-error">
                    {errors.lon}
                  </p>
                )}
              </div>
            </div>
            <div>
              <button type="submit" className="btn btn--secondary" disabled={status.kind === "loading"}>
                {tr("Look up these coordinates", "Buscar estas coordenadas")}
              </button>
            </div>
          </form>
        </details>
      </section>

      <div aria-live="polite">
        {status.kind === "loading" && (
          <div className="skeleton" role="status" aria-label={tr("Loading NASA and soil data", "Cargando datos de la NASA y del suelo")} />
        )}
        {status.kind === "error" && (
          <ErrorNotice
            error={status.error}
            onPickDemo={pickDemo}
            onRetry={() => void lookUp(status.lat, status.lon, status.name)}
          />
        )}
        {status.kind === "ready" && <ConditionsSummary conditions={status.conditions} profile={status.soil} />}
      </div>
    </div>
  );
}

function ConditionsSummary({ conditions, profile }: { conditions: Conditions; profile: SoilProfile | null }) {
  const { tr, lang, num } = useI18n();
  const { soil, seasons, monthly, data_sources } = conditions;
  const na = tr("Not available", "No disponible");
  const topsoil = profile?.layers.find((l) => l.depth_cm === 0) ?? profile?.layers[0];
  const carbon = topsoil?.organic_carbon_g_kg ?? null;
  const yearRain = monthly.reduce((sum, m) => sum + m.rainfall_mm, 0);
  return (
    <section className="stack fade-in" aria-labelledby="conditions">
      <div className="section-head">
        <h2 id="conditions">
          {tr("Your field at", "Su campo en")} {conditions.location.lat}, {conditions.location.lon}
        </h2>
        <Link to="/plan" className="btn">
          {tr("Next: crops and priorities", "Siguiente: cultivos y prioridades")}
        </Link>
      </div>

      <div className="grid grid--auto">
        <div className="panel stat-card">
          <span className="stat-card__label">{tr("Rain per year", "Lluvia al año")}</span>
          <span className="stat">{num(Math.round(yearRain), 0)} mm</span>
          <span className="muted small">{tr("NASA POWER average", "Promedio de NASA POWER")}</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">{tr("Soil moisture", "Humedad del suelo")}</span>
          <span className="stat">{soil.moisture_m3m3 != null ? `${num(soil.moisture_m3m3)} m³/m³` : na}</span>
          <span className="muted small">{tr("NASA SMAP satellite, ~9 km", "Satélite NASA SMAP, ~9 km")}</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">{tr("Soil pH", "pH del suelo")}</span>
          <span className="stat stat--green">{soil.ph != null ? num(soil.ph, 1) : na}</span>
          <span className="muted small">{tr("Soil map estimate, not a test", "Estimación del mapa, no un análisis")}</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">{tr("Organic carbon", "Carbono orgánico")}</span>
          <span className="stat stat--green">{carbon != null ? `${num(carbon, 0)} g/kg` : na}</span>
          <span className="muted small">
            {carbon != null
              ? tr(
                  `Topsoil, about ${num(organicMatterPct(carbon), 1)}% organic matter (soil map)`,
                  `Capa superficial, cerca de ${num(organicMatterPct(carbon), 1)} % de materia orgánica (mapa de suelos)`,
                )
              : tr("Soil map has no value here", "El mapa de suelos no tiene dato aquí")}
          </span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">{tr("Soil texture", "Textura del suelo")}</span>
          <span className="stat stat--green">{soil.texture_class ? capitalize(textureName(soil.texture_class, lang)) : na}</span>
          <span className="muted small">{tr("Soil map; can differ from your field", "Mapa de suelos; puede diferir de su campo")}</span>
        </div>
      </div>

      <div className="grid grid--2">
        <div className="panel">
          <RainChart monthly={monthly} seasons={seasons} />
        </div>
        <div className="panel">
          <TemperatureChart monthly={monthly} seasons={seasons} />
        </div>
      </div>

      <details className="panel">
        <summary>{tr("Season averages as a table", "Promedios por época en una tabla")}</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">{tr("Season", "Época")}</th>
                <th scope="col">{tr("Months", "Meses")}</th>
                <th scope="col">{tr("Average temp. (°C)", "Temp. promedio (°C)")}</th>
                <th scope="col">{tr("Hottest hours (°C)", "Horas más calientes (°C)")}</th>
                <th scope="col">{tr("Coolest nights (°C)", "Noches más frescas (°C)")}</th>
                <th scope="col">{tr("Rain per month (mm)", "Lluvia al mes (mm)")}</th>
              </tr>
            </thead>
            <tbody>
              {seasons.map((season) => (
                <tr key={season.name}>
                  <th scope="row">{capitalize(season.name)}</th>
                  <td>{monthSpan(season.months, lang)}</td>
                  <td>{num(season.temperature_c, 1)}</td>
                  <td>{num(season.temperature_max_c, 1)}</td>
                  <td>{num(season.temperature_min_c, 1)}</td>
                  <td>{Math.round(season.rainfall_mm_per_month)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          {tr(
            "Long-term averages from NASA POWER. Seasons are rainfed.",
            "Promedios de largo plazo de NASA POWER. Épocas de temporal (sin riego).",
          )}
        </p>
      </details>

      <p className="small muted">
        {tr("Sources", "Fuentes")}:{" "}
        {Object.values(data_sources)
          .map((s) => (SOURCE_LABELS[s] ? tr(SOURCE_LABELS[s].en, SOURCE_LABELS[s].es) : s))
          .join(" · ")}
      </p>
    </section>
  );
}
