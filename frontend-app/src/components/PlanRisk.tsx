import { useEffect, useState } from "react";
import {
  api,
  type EnsoPhase,
  type PlanRiskPlanting,
  type PlanRiskResponse,
  type RiskCause,
  type Rotation,
} from "../api/client";
import { useCropName } from "../cropNames";
import { capitalize, monthName } from "../format";
import { useI18n, type Bilingual, type Lang } from "../i18n";
import { ErrorNotice } from "./ErrorNotice";

// "Would this plan have worked in past years?" Each crop of the recommended rotation is replayed
// against every season from 2000 on (POST /plan-risk: NASA GPM IMERG rain, MERRA-2 temperature and
// soil wetness, NOAA El Niño index). This is the "changing conditions" part of the tool.

const CAUSE_LABELS: Record<RiskCause, Bilingual> = {
  late_dry_start: { en: "Dry start after sowing", es: "Arranque seco después de sembrar" },
  flowering_dry_spell: { en: "Dry spell at flowering", es: "Veranillo en la floración" },
  cycle_rain_low: { en: "Too little rain over the cycle", es: "Poca lluvia durante el ciclo" },
  cycle_rain_high: { en: "Too much rain over the cycle", es: "Demasiada lluvia durante el ciclo" },
  harvest_wet: { en: "Rain at harvest", es: "Lluvia en la cosecha" },
  flowering_heat: { en: "Heat at flowering", es: "Calor en la floración" },
};

const ENSO_LABELS: Record<EnsoPhase, Bilingual> = {
  el_nino: { en: "El Niño", es: "El Niño" },
  la_nina: { en: "La Niña", es: "La Niña" },
  neutral: { en: "a normal year", es: "un año normal" },
};

const OUTCOME = {
  ok: { label: { en: "no problem", es: "sin problema" }, symbol: "✓" },
  stress: { label: { en: "stress", es: "estrés" }, symbol: "!" },
  fail: { label: { en: "failed", es: "perdido" }, symbol: "✕" },
} as const;

interface Sowing {
  month: number;
  day: number;
}

/** Sowing date choices for a season: the 1st and the 15th of each of its months. */
const sowingOptions = (months: number[]): Sowing[] =>
  months.flatMap((month) => [
    { month, day: 1 },
    { month, day: 15 },
  ]);

const dateLabel = (s: Sowing, lang: Lang) => (lang === "es" ? `${s.day} ${monthName(s.month, lang)}` : `${monthName(s.month, lang)} ${s.day}`);
const mmdd = (text: string, lang: Lang) => {
  const [m, d] = text.split("-").map(Number);
  return dateLabel({ month: m, day: d }, lang);
};

type Status = { kind: "loading" } | { kind: "ready"; data: PlanRiskResponse } | { kind: "error"; error: unknown };

export function PlanRisk({ lat, lon, rotation }: { lat: number; lon: number; rotation: Rotation }) {
  const { tr, pick, lang } = useI18n();
  const cropName = useCropName();
  // Default sowing: the 15th of each season's first month (e.g. May 15 for primera).
  const [sowings, setSowings] = useState<Sowing[]>(() =>
    rotation.sequence.map((s) => ({ month: s.months[0], day: 15 })),
  );
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify({ lat, lon, crops: rotation.sequence.map((s) => s.crop_id), sowings });

  useEffect(() => {
    let active = true;
    setStatus({ kind: "loading" });
    api
      .planRisk({
        lat,
        lon,
        plantings: rotation.sequence.map((s, i) => ({
          crop: s.crop_id,
          sowing_month: sowings[i].month,
          sowing_day: sowings[i].day,
        })),
      })
      .then((data) => active && setStatus({ kind: "ready", data }))
      .catch((error: unknown) => active && setStatus({ kind: "error", error }));
    return () => {
      active = false;
    };
  }, [key, attempt]);

  return (
    <section className="panel risk stack" aria-labelledby="risk-title">
      <div>
        <span className="eyebrow">{tr("Changing conditions", "Condiciones cambiantes")}</span>
        <h2 id="risk-title">{tr("Would this rotation have worked in past years?", "¿Le habría funcionado esta rotación en años anteriores?")}</h2>
        <p className="muted">
          {tr(
            "We replayed each sowing against every season since 2000, using NASA satellite rain and daily weather.",
            "Probamos cada siembra contra todas las temporadas desde el 2000, con la lluvia por satélite y el clima diario de la NASA.",
          )}
        </p>
      </div>

      {status.kind === "ready" && status.data.enso_now && <EnsoNow now={status.data.enso_now} />}

      <div className="grid grid--2">
        {rotation.sequence.map((step, i) => {
          const planting = status.kind === "ready" ? status.data.plantings[i] : undefined;
          const name = cropName(step.crop_id, step.crop_name);
          return (
            <article key={step.season} className="risk__planting">
              <header className="risk__head">
                <h3>
                  {name} <span className="muted small">· {capitalize(step.season)}</span>
                </h3>
                <label className="risk__date">
                  <span className="visually-hidden">{tr(`Sowing date for ${name}`, `Fecha de siembra de ${name}`)}</span>
                  {tr("Sown", "Siembra")}{" "}
                  <select
                    value={`${sowings[i].month}-${sowings[i].day}`}
                    onChange={(e) => {
                      const [month, day] = e.target.value.split("-").map(Number);
                      setSowings((prev) => prev.map((s, j) => (j === i ? { month, day } : s)));
                    }}
                  >
                    {sowingOptions(step.months).map((o) => (
                      <option key={`${o.month}-${o.day}`} value={`${o.month}-${o.day}`}>
                        {dateLabel(o, lang)}
                      </option>
                    ))}
                  </select>
                </label>
              </header>
              {status.kind === "loading" && <div className="skeleton" role="status" aria-label={tr("Checking past years", "Revisando años anteriores")} />}
              {planting && <PlantingResult planting={planting} />}
            </article>
          );
        })}
      </div>

      {status.kind === "error" && <ErrorNotice error={status.error} onRetry={() => setAttempt((n) => n + 1)} />}

      {status.kind === "ready" && (
        <details className="more">
          <summary>{tr("About this check", "Sobre esta revisión")}</summary>
          <ul className="list small more__body">
            {status.data.data_gaps.map((g) => (
              <li key={g.en}>{pick(g)}</li>
            ))}
          </ul>
          <p className="muted small">
            {tr("Sources", "Fuentes")}: {status.data.data_sources.join(" · ")}.{" "}
            {tr("Seasons", "Temporadas")} {status.data.years_evaluated.first}–{status.data.years_evaluated.last}.
          </p>
        </details>
      )}
    </section>
  );
}

function EnsoNow({ now }: { now: NonNullable<PlanRiskResponse["enso_now"]> }) {
  const { tr, pick, num } = useI18n();
  const phase =
    now.phase === "neutral"
      ? tr("Neutral conditions (no El Niño or La Niña)", "Condiciones neutras (ni El Niño ni La Niña)")
      : tr(`${pick(ENSO_LABELS[now.phase])} now`, `${pick(ENSO_LABELS[now.phase])} en este momento`);
  return (
    <p className={`enso enso--${now.phase}`}>
      <strong>{phase}</strong> · {tr("ocean index", "índice del océano")} {now.oni > 0 ? "+" : ""}
      {num(now.oni, 1)} °C ({now.season}).{" "}
      {tr(
        "It describes the ocean today, not a forecast for your season.",
        "Describe el océano hoy; no es un pronóstico para su temporada.",
      )}
    </p>
  );
}

function PlantingResult({ planting }: { planting: PlanRiskPlanting }) {
  const { tr, pick, lang } = useI18n();
  const evaluated = planting.years.length;
  const stressed = planting.years.filter((y) => y.outcome === "stress").length;
  return (
    <div className="stack fade-in">
      <p className="risk__headline">
        <span className={`risk__badge risk__badge--${planting.failed_years > 0 ? "fail" : stressed > 0 ? "stress" : "ok"}`}>
          {tr(`${planting.failed_years} of ${evaluated} years failed`, `${planting.failed_years} de ${evaluated} años perdidos`)}
        </span>
        <span className="muted small">
          {tr("Sow", "Siembra")} {mmdd(planting.sowing_date, lang)} → {tr("harvest", "cosecha")} {mmdd(planting.harvest_date, lang)}
        </span>
      </p>
      <p>{pick(planting.summary)}</p>

      <YearStrip planting={planting} />

      {planting.causes.length > 0 && (
        <details className="more">
          <summary>{tr("What went wrong and what to do", "Qué salió mal y qué hacer")}</summary>
          <div className="more__body stack">
            {planting.causes.map((c) => (
              <div key={c.cause}>
                <h4>
                  {pick(CAUSE_LABELS[c.cause])}{" "}
                  <span className={`tag${c.severity === "fail" ? " tag--warn" : ""}`}>
                    {c.count === 1 ? tr("1 year", "1 año") : tr(`${c.count} years`, `${c.count} años`)} ·{" "}
                    {c.severity === "fail" ? tr("failed", "perdido") : tr("stress", "estrés")}
                  </span>
                </h4>
                <p className="small">{pick(c.explanation)}</p>
                <ul className="list small">
                  {c.actions.map((a) => (
                    <li key={a.en}>{pick(a)}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </details>
      )}

      {planting.alternatives.length > 0 && (
        <div className="risk__alts">
          <h4>{tr("Safer options", "Opciones más seguras")}</h4>
          <ul className="list small">
            {planting.alternatives.map((a) => (
              <li key={`${a.kind}-${a.crop_id}-${a.sowing_date}`}>{pick(a.label)}</li>
            ))}
          </ul>
        </div>
      )}

      {planting.enso_split && <p className="muted small">{pick(planting.enso_split.note)}</p>}
    </div>
  );
}

/** One cell per past season: color and symbol (never color alone), details on hover and for screen readers. */
function YearStrip({ planting }: { planting: PlanRiskPlanting }) {
  const { tr, pick } = useI18n();
  return (
    <div>
      <ol className="years" aria-label={tr(`Outcome per sowing year for ${pick(planting.crop_name)}`, `Resultado por año de siembra de ${pick(planting.crop_name)}`)}>
        {planting.years.map((y) => {
          const causes = y.causes.map((c) => pick(CAUSE_LABELS[c]).toLowerCase()).join(", ");
          const text = `${y.year}: ${pick(OUTCOME[y.outcome].label)}${causes ? ` (${causes})` : ""}${y.enso ? `, ${pick(ENSO_LABELS[y.enso])}` : ""}`;
          return (
            <li key={y.year} className={`years__cell years__cell--${y.outcome}`} title={text} aria-label={text}>
              <span aria-hidden="true">{OUTCOME[y.outcome].symbol}</span>
            </li>
          );
        })}
      </ol>
      <p className="years__axis small muted" aria-hidden="true">
        <span>{planting.years[0]?.year}</span>
        <span>{planting.years[planting.years.length - 1]?.year}</span>
      </p>
      <p className="years__legend small">
        <span className="years__cell years__cell--ok">✓</span> {pick(OUTCOME.ok.label)}
        <span className="years__cell years__cell--stress">!</span> {pick(OUTCOME.stress.label)}
        <span className="years__cell years__cell--fail">✕</span> {pick(OUTCOME.fail.label)}
      </p>
    </div>
  );
}
