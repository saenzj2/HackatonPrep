import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type Conditions } from "../api/client";
import { RainChart, TemperatureChart } from "../components/ClimateCharts";
import { ErrorNotice } from "../components/ErrorNotice";
import { Stepper } from "../components/Stepper";
import { DEMO_FIELDS, type DemoField } from "../demoFields";
import { capitalize, monthSpan } from "../format";
import { usePlan } from "../state/PlanContext";

// The map (Leaflet + tiles) loads only when this page opens.
const FieldMap = lazy(() => import("../components/FieldMap"));

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; conditions: Conditions }
  | { kind: "error"; error: unknown; lat: number; lon: number; name: string };

const SOURCE_LABELS: Record<string, string> = {
  nasa_power: "NASA POWER (long-term monthly averages)",
  "openlandmap+nasa_smap": "OpenLandMap soil map (pH) and NASA SMAP satellite (soil moisture)",
  ecocrop_subset: "FAO EcoCrop crop requirements",
};

function validate(text: string, limit: number, name: string): string | null {
  if (text.trim() === "") return `Enter a ${name}.`;
  const value = Number(text);
  if (!Number.isFinite(value) || value < -limit || value > limit) {
    return `Enter a ${name} between -${limit} and ${limit}.`;
  }
  return null;
}

export function Field() {
  const { plan, setField } = usePlan();
  const [lat, setLat] = useState(plan.field ? String(plan.field.lat) : "");
  const [lon, setLon] = useState(plan.field ? String(plan.field.lon) : "");
  const [errors, setErrors] = useState<{ lat?: string; lon?: string }>({});
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [point, setPoint] = useState(plan.field ? { lat: plan.field.lat, lon: plan.field.lon } : null);
  const [bbox, setBbox] = useState<number[] | undefined>();

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
    setStatus({ kind: "loading" });
    try {
      const conditions = await api.conditions(latValue, lonValue);
      setField({
        lat: latValue,
        lon: lonValue,
        name,
        seasons: conditions.seasons.map(({ name: season, months }) => ({ name: season, months })),
      });
      setStatus({ kind: "ready", conditions });
    } catch (error) {
      setStatus({ kind: "error", error, lat: latValue, lon: lonValue, name });
    }
  }

  const pickDemo = (field: DemoField) => {
    setErrors({});
    void lookUp(field.lat, field.lon, field.name);
  };

  const pickPoint = (latValue: number, lonValue: number) => {
    setErrors({});
    void lookUp(latValue, lonValue, `Field at ${latValue}, ${lonValue}`);
  };

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = {
      lat: validate(lat, 90, "latitude") ?? undefined,
      lon: validate(lon, 180, "longitude") ?? undefined,
    };
    setErrors(next);
    if (next.lat) return document.getElementById("lat")?.focus();
    if (next.lon) return document.getElementById("lon")?.focus();
    pickPoint(Number(lat), Number(lon));
  }

  return (
    <div className="stack">
      <Stepper current="field" />
      <h1>Where is your field?</h1>
      <p className="lead">Click your field on the map. We use that point to look up climate and soil.</p>

      <section className="panel stack" aria-label="Choose your field">
        <Suspense fallback={<div className="skeleton field-map" role="status" aria-label="Loading map" />}>
          <FieldMap bbox={bbox} selected={point} onPick={pickPoint} onPickDemo={pickDemo} />
        </Suspense>

        <div className="btn-row">
          <span className="muted small">Or use a demo field:</span>
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
          <summary>Enter coordinates instead</summary>
          <form className="stack" onSubmit={submit} noValidate>
            <div className="grid grid--2">
              <div>
                <label htmlFor="lat">
                  Latitude <span className="hint">(-90 to 90, e.g. 10.0)</span>
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
                  Longitude <span className="hint">(-180 to 180, e.g. -84.2)</span>
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
                Look up these coordinates
              </button>
            </div>
          </form>
        </details>
      </section>

      <div aria-live="polite">
        {status.kind === "loading" && (
          <div className="skeleton" role="status" aria-label="Loading NASA and soil data" />
        )}
        {status.kind === "error" && (
          <ErrorNotice
            error={status.error}
            onPickDemo={pickDemo}
            onRetry={() => void lookUp(status.lat, status.lon, status.name)}
          />
        )}
        {status.kind === "ready" && <ConditionsSummary conditions={status.conditions} />}
      </div>
    </div>
  );
}

function ConditionsSummary({ conditions }: { conditions: Conditions }) {
  const { soil, seasons, monthly, data_sources } = conditions;
  const yearRain = monthly.reduce((sum, m) => sum + m.rainfall_mm, 0);
  return (
    <section className="stack fade-in" aria-labelledby="conditions">
      <div className="section-head">
        <h2 id="conditions">
          Your field at {conditions.location.lat}, {conditions.location.lon}
        </h2>
        <Link to="/plan" className="btn">
          Next: crops and priorities
        </Link>
      </div>

      <div className="grid grid--4">
        <div className="panel stat-card">
          <span className="stat-card__label">Rain per year</span>
          <span className="stat">{Math.round(yearRain).toLocaleString("en")} mm</span>
          <span className="muted small">NASA POWER average</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">Soil moisture</span>
          <span className="stat">
            {soil.moisture_m3m3 != null ? `${soil.moisture_m3m3.toFixed(2)} m³/m³` : "Not available"}
          </span>
          <span className="muted small">NASA SMAP satellite, ~9 km</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">Soil pH</span>
          <span className="stat stat--green">{soil.ph != null ? soil.ph.toFixed(1) : "Not available"}</span>
          <span className="muted small">Soil map estimate, not a test</span>
        </div>
        <div className="panel stat-card">
          <span className="stat-card__label">Soil texture</span>
          <span className="stat stat--green">{soil.texture_class ? capitalize(soil.texture_class) : "Not available"}</span>
          <span className="muted small">Soil map; can differ from your field</span>
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
        <summary>Season averages as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Season</th>
                <th scope="col">Months</th>
                <th scope="col">Average temp. (°C)</th>
                <th scope="col">Hottest hours (°C)</th>
                <th scope="col">Coolest nights (°C)</th>
                <th scope="col">Rain per month (mm)</th>
              </tr>
            </thead>
            <tbody>
              {seasons.map((season) => (
                <tr key={season.name}>
                  <th scope="row">{capitalize(season.name)}</th>
                  <td>{monthSpan(season.months)}</td>
                  <td>{season.temperature_c.toFixed(1)}</td>
                  <td>{season.temperature_max_c.toFixed(1)}</td>
                  <td>{season.temperature_min_c.toFixed(1)}</td>
                  <td>{Math.round(season.rainfall_mm_per_month)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">Long-term averages from NASA POWER. Seasons are rainfed.</p>
      </details>

      <p className="small muted">
        Sources: {Object.values(data_sources).map((s) => SOURCE_LABELS[s] ?? s).join(" · ")}
      </p>
    </section>
  );
}
