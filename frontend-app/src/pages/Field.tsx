import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type Conditions } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { Stepper } from "../components/Stepper";
import { DEMO_FIELDS, type DemoField } from "../demoFields";
import { capitalize, monthSpan } from "../format";
import { usePlan } from "../state/PlanContext";

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

  // Coming back to this step: show the saved field's conditions again.
  useEffect(() => {
    if (plan.field) void lookUp(plan.field.lat, plan.field.lon, plan.field.name);
  }, []); // only on first render

  async function lookUp(latValue: number, lonValue: number, name: string) {
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

  function pickDemo(field: DemoField) {
    setLat(String(field.lat));
    setLon(String(field.lon));
    setErrors({});
    void lookUp(field.lat, field.lon, field.name);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = {
      lat: validate(lat, 90, "latitude") ?? undefined,
      lon: validate(lon, 180, "longitude") ?? undefined,
    };
    setErrors(next);
    if (next.lat) return document.getElementById("lat")?.focus();
    if (next.lon) return document.getElementById("lon")?.focus();
    void lookUp(Number(lat), Number(lon), `Field at ${Number(lat)}, ${Number(lon)}`);
  }

  return (
    <div className="stack">
      <Stepper current="field" />
      <h1>My field</h1>
      <p className="lead">Choose where your field is. We use one point to look up climate and soil.</p>

      <section className="panel" aria-labelledby="demo">
        <h2 id="demo">Demo fields</h2>
        <p className="muted small">These fields have NASA and soil data preloaded for the demo.</p>
        <div className="btn-row">
          {DEMO_FIELDS.map((field) => (
            <button
              key={field.id}
              type="button"
              className="btn btn--secondary"
              onClick={() => pickDemo(field)}
              aria-pressed={plan.field?.lat === field.lat && plan.field?.lon === field.lon}
            >
              {field.name} · {field.description}
            </button>
          ))}
        </div>
      </section>

      <form className="panel stack" onSubmit={submit} noValidate aria-labelledby="coords">
        <h2 id="coords">Or enter coordinates</h2>
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
        <div className="btn-row">
          <button type="submit" className="btn" disabled={status.kind === "loading"}>
            Look up this field
          </button>
        </div>
      </form>

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
  const { soil, seasons, data_sources } = conditions;
  return (
    <section className="stack" aria-labelledby="conditions">
      <h2 id="conditions">
        Your field at {conditions.location.lat}, {conditions.location.lon}
      </h2>

      <div className="panel">
        <h3>Growing seasons</h3>
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
      </div>

      <div className="grid grid--3">
        <div className="panel">
          <h3>Soil pH</h3>
          <p className="stat stat--green">{soil.ph != null ? soil.ph.toFixed(1) : "Not available"}</p>
          <p className="muted small">Estimate from the OpenLandMap soil map, not a soil test.</p>
        </div>
        <div className="panel">
          <h3>Soil moisture</h3>
          <p className="stat">
            {soil.moisture_m3m3 != null ? `${soil.moisture_m3m3.toFixed(2)} m³/m³` : "Not available"}
          </p>
          <p className="muted small">Yearly average from NASA SMAP satellite data (~9 km area).</p>
        </div>
        <div className="panel">
          <h3>Soil texture</h3>
          <p className="stat stat--green">
            {soil.texture_class ? capitalize(soil.texture_class) : "Not available"}
          </p>
          <p className="muted small">From the soil map; it can differ from your field.</p>
        </div>
      </div>

      <p className="small muted">
        Sources: {Object.values(data_sources).map((s) => SOURCE_LABELS[s] ?? s).join(" · ")}
      </p>

      <div className="btn-row">
        <Link to="/plan" className="btn">
          Next: crops and priorities
        </Link>
      </div>
    </section>
  );
}
