import { useEffect, useState } from "react";
import { api, type PermanentCropFit, type PermanentCropsResponse, type Suitability } from "../api/client";
import { monthName } from "../format";
import { ErrorNotice } from "./ErrorNotice";

// Permanent crops (GET /permanent-crops): cacao, coffee, pineapple and banana stay in the field for
// years, so they are a separate decision from the rotation above. Each is scored once on the whole
// year at the point; the score is the most limiting variable, so the farmer's priorities don't move it.

const SUITABILITY: Record<Suitability, string> = {
  good: "Good fit",
  fair: "Fair fit, with limits",
  poor: "Poor fit",
  unsuitable: "Not suited",
};

const VARIABLE_LABELS: Record<string, string> = {
  temperature: "Average temperature",
  rainfall: "Rain over the year",
  heat: "Heat (hottest month)",
  frost: "Frost (coldest nights)",
  soil_ph: "Soil pH",
};

type Status = { kind: "loading" } | { kind: "ready"; data: PermanentCropsResponse } | { kind: "error"; error: unknown };

const number = (value: number) => Math.round(value).toLocaleString("en-US");

export function PermanentCrops({ lat, lon }: { lat: number; lon: number }) {
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setStatus({ kind: "loading" });
    api
      .permanentCrops(lat, lon)
      .then((data) => active && setStatus({ kind: "ready", data }))
      .catch((error: unknown) => active && setStatus({ kind: "error", error }));
    return () => {
      active = false;
    };
  }, [lat, lon, attempt]);

  return (
    <section className="panel perennial stack" aria-labelledby="perennial-title">
      <div>
        <span className="eyebrow">Plant once, harvest for years</span>
        <h2 id="perennial-title">Permanent crops for this place</h2>
        <p className="muted">
          Cacao, coffee, pineapple and banana stay in the field for years, so they are not part of the rotation.
          Each one is checked against this place's whole year.
        </p>
      </div>

      {status.kind === "loading" && <div className="skeleton skeleton--tall" role="status" aria-label="Checking permanent crops" />}
      {status.kind === "error" && <ErrorNotice error={status.error} onRetry={() => setAttempt((n) => n + 1)} />}
      {status.kind === "ready" && <PermanentCropsView data={status.data} />}
    </section>
  );
}

function PermanentCropsView({ data }: { data: PermanentCropsResponse }) {
  const year = data.year_climate;
  const dry = year.dry_months;
  return (
    <>
      <ul className="perennial__year" aria-label="This place's year">
        <li>
          <strong>{number(year.annual_rainfall_mm)} mm</strong> rain a year
        </li>
        <li>
          <strong>{year.temperature_c.toFixed(1)} °C</strong> average
        </li>
        <li>
          <strong>{year.hottest_month_max_c.toFixed(1)} °C</strong> hottest-month days
        </li>
        <li>
          <strong>{dry.length === 0 ? "No" : dry.length}</strong> dry month{dry.length === 1 ? "" : "s"}
          {dry.length > 0 && <span className="muted"> ({dry.map(monthName).join(", ")})</span>}
        </li>
      </ul>

      <div className="grid grid--2">
        {data.crops.map((crop) => (
          <CropCard key={crop.crop_id} crop={crop} />
        ))}
      </div>

      <details className="more">
        <summary>About this check</summary>
        <ul className="list small more__body">
          {data.data_gaps.map((g) => (
            <li key={g.en}>{g.en}</li>
          ))}
        </ul>
        <p className="muted small">
          Sources: crop ranges from FAO EcoCrop · climate {data.data_sources.climate} · soil {data.data_sources.soil}.
        </p>
      </details>
    </>
  );
}

function CropCard({ crop }: { crop: PermanentCropFit }) {
  const weakest = Object.entries(crop.variable_scores).sort((a, b) => a[1] - b[1])[0];
  return (
    <article className={`perennial__crop perennial__crop--${crop.suitability}`}>
      <header className="risk__head">
        <h3>
          {crop.crop_name.en} <span className="muted small">· {crop.scientific_name}</span>
        </h3>
        <span className={`risk__badge perennial__badge--${crop.suitability}`}>{SUITABILITY[crop.suitability]}</span>
      </header>

      <div className="bar">
        <span>Score</span>
        <span className="bar__track" aria-hidden="true">
          <span className={`bar__fill perennial__fill--${crop.suitability}`} style={{ width: `${crop.score * 100}%` }} />
        </span>
        <span>{crop.score.toFixed(2)}</span>
      </div>
      {weakest && weakest[1] < 1 && (
        <p className="small muted">
          Limited by: {VARIABLE_LABELS[weakest[0]] ?? weakest[0]} ({weakest[1].toFixed(2)})
        </p>
      )}

      {crop.risks.length > 0 && (
        <ul className="list small">
          {crop.risks.map((r) => (
            <li key={r.en}>{r.en}</li>
          ))}
        </ul>
      )}
      {crop.benefits.map((b) => (
        <p key={b.en} className="small">
          {b.en}
        </p>
      ))}
      {crop.max_altitude_m != null && (
        <p className="small muted">Grown up to {number(crop.max_altitude_m)} m. Check your farm's altitude.</p>
      )}
    </article>
  );
}
