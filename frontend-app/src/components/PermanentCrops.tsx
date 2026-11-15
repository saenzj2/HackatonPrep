import { useEffect, useState } from "react";
import { api, type PermanentCropFit, type PermanentCropsResponse, type Suitability } from "../api/client";
import { monthName } from "../format";
import { useI18n } from "../i18n";
import { ErrorNotice } from "./ErrorNotice";

// Permanent crops (GET /permanent-crops): cacao, coffee, pineapple and banana stay in the field for
// years, so they are a separate decision from the rotation above. Each is scored once on the whole
// year at the point; the score is the most limiting variable, so the farmer's priorities don't move it.

const SUITABILITY: Record<Suitability, [string, string]> = {
  good: ["Good fit", "Se adapta bien"],
  fair: ["Fair fit, with limits", "Se adapta, con limitaciones"],
  poor: ["Poor fit", "Se adapta poco"],
  unsuitable: ["Not suited", "No se adapta"],
};

const VARIABLE_LABELS: Record<string, [string, string]> = {
  temperature: ["Average temperature", "Temperatura promedio"],
  rainfall: ["Rain over the year", "Lluvia del año"],
  heat: ["Heat (hottest month)", "Calor (mes más caliente)"],
  frost: ["Frost (coldest nights)", "Helada (noches más frías)"],
  soil_ph: ["Soil pH", "pH del suelo"],
};

type Status = { kind: "loading" } | { kind: "ready"; data: PermanentCropsResponse } | { kind: "error"; error: unknown };

export function PermanentCrops({ lat, lon }: { lat: number; lon: number }) {
  const { tr } = useI18n();
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
        <span className="eyebrow">{tr("Plant once, harvest for years", "Se siembra una vez, se cosecha por años")}</span>
        <h2 id="perennial-title">{tr("Permanent crops for this place", "Cultivos permanentes para este lugar")}</h2>
        <p className="muted">
          {tr(
            "Cacao, coffee, pineapple and banana stay in the field for years, so they are not part of the rotation. Each one is checked against this place's whole year.",
            "El cacao, el café, la piña y el banano se quedan en la finca por años, así que no son parte de la rotación. Cada uno se revisa con el año completo de este lugar.",
          )}
        </p>
      </div>

      {status.kind === "loading" && (
        <div
          className="skeleton skeleton--tall"
          role="status"
          aria-label={tr("Checking permanent crops", "Revisando cultivos permanentes")}
        />
      )}
      {status.kind === "error" && <ErrorNotice error={status.error} onRetry={() => setAttempt((n) => n + 1)} />}
      {status.kind === "ready" && <PermanentCropsView data={status.data} />}
    </section>
  );
}

function PermanentCropsView({ data }: { data: PermanentCropsResponse }) {
  const { tr, pick, num, lang } = useI18n();
  const year = data.year_climate;
  const dry = year.dry_months;
  const dryCount = dry.length;
  return (
    <>
      <ul className="perennial__year" aria-label={tr("This place's year", "El año de este lugar")}>
        <li>
          <strong>{num(year.annual_rainfall_mm, 0)} mm</strong> {tr("rain a year", "de lluvia al año")}
        </li>
        <li>
          <strong>{num(year.temperature_c, 1)} °C</strong> {tr("average", "de promedio")}
        </li>
        <li>
          <strong>{num(year.hottest_month_max_c, 1)} °C</strong>{" "}
          {tr("hottest-month days", "en los días del mes más caliente")}
        </li>
        <li>
          <strong>{dryCount === 0 ? tr("No", "Ningún") : dryCount}</strong>{" "}
          {dryCount === 1 ? tr("dry month", "mes seco") : dryCount === 0 ? tr("dry months", "mes seco") : tr("dry months", "meses secos")}
          {dryCount > 0 && <span className="muted"> ({dry.map((m) => monthName(m, lang)).join(", ")})</span>}
        </li>
      </ul>

      <div className="grid grid--2">
        {data.crops.map((crop) => (
          <CropCard key={crop.crop_id} crop={crop} />
        ))}
      </div>

      <details className="more">
        <summary>{tr("About this check", "Sobre esta revisión")}</summary>
        <ul className="list small more__body">
          {data.data_gaps.map((g) => (
            <li key={g.en}>{pick(g)}</li>
          ))}
        </ul>
        <p className="muted small">
          {tr("Sources: crop ranges from FAO EcoCrop", "Fuentes: rangos de los cultivos de FAO EcoCrop")} ·{" "}
          {tr("climate", "clima")} {data.data_sources.climate} · {tr("soil", "suelo")} {data.data_sources.soil}.
        </p>
      </details>
    </>
  );
}

function CropCard({ crop }: { crop: PermanentCropFit }) {
  const { tr, pick, num } = useI18n();
  const weakest = Object.entries(crop.variable_scores).sort((a, b) => a[1] - b[1])[0];
  const [suitEn, suitEs] = SUITABILITY[crop.suitability];
  const weakLabel = weakest && VARIABLE_LABELS[weakest[0]];
  return (
    <article className={`perennial__crop perennial__crop--${crop.suitability}`}>
      <header className="risk__head">
        <h3>
          {pick(crop.crop_name)} <span className="muted small">· {crop.scientific_name}</span>
        </h3>
        <span className={`risk__badge perennial__badge--${crop.suitability}`}>{tr(suitEn, suitEs)}</span>
      </header>

      <div className="bar">
        <span>{tr("Score", "Puntaje")}</span>
        <span className="bar__track" aria-hidden="true">
          <span className={`bar__fill perennial__fill--${crop.suitability}`} style={{ width: `${crop.score * 100}%` }} />
        </span>
        <span>{num(crop.score)}</span>
      </div>
      {weakest && weakest[1] < 1 && (
        <p className="small muted">
          {tr("Limited by", "Lo limita")}: {weakLabel ? tr(weakLabel[0], weakLabel[1]) : weakest[0]} ({num(weakest[1])})
        </p>
      )}

      {crop.risks.length > 0 && (
        <ul className="list small">
          {crop.risks.map((r) => (
            <li key={r.en}>{pick(r)}</li>
          ))}
        </ul>
      )}
      {crop.benefits.map((b) => (
        <p key={b.en} className="small">
          {pick(b)}
        </p>
      ))}
      {crop.max_altitude_m != null && (
        <p className="small muted">
          {tr(
            `Grown up to ${num(crop.max_altitude_m, 0)} m. Check your farm's altitude.`,
            `Se siembra hasta ${num(crop.max_altitude_m, 0)} m. Revise la altura de su finca.`,
          )}
        </p>
      )}
    </article>
  );
}
