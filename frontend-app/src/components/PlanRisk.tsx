import { useEffect, useState } from "react";
import {
  api,
  type EnsoPhase,
  type PlanRiskPlanting,
  type PlanRiskResponse,
  type RiskCause,
  type Rotation,
} from "../api/client";
import { capitalize, monthName } from "../format";
import { ErrorNotice } from "./ErrorNotice";

// "Would this plan have worked in past years?" Each crop of the recommended rotation is replayed
// against every season from 2000 on (POST /plan-risk: NASA GPM IMERG rain, MERRA-2 temperature and
// soil wetness, NOAA El Niño index). This is the "changing conditions" part of the tool.

const CAUSE_LABELS: Record<RiskCause, string> = {
  late_dry_start: "Dry start after sowing",
  flowering_dry_spell: "Dry spell at flowering",
  cycle_rain_low: "Too little rain over the cycle",
  cycle_rain_high: "Too much rain over the cycle",
  harvest_wet: "Rain at harvest",
  flowering_heat: "Heat at flowering",
};

const ENSO_LABELS: Record<EnsoPhase, string> = {
  el_nino: "El Niño",
  la_nina: "La Niña",
  neutral: "a normal year",
};

const OUTCOME = {
  ok: { label: "no problem", symbol: "✓" },
  stress: { label: "stress", symbol: "!" },
  fail: { label: "failed", symbol: "✕" },
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

const dateLabel = (s: Sowing) => `${monthName(s.month)} ${s.day}`;
const mmdd = (text: string) => {
  const [m, d] = text.split("-").map(Number);
  return `${monthName(m)} ${d}`;
};

type Status = { kind: "loading" } | { kind: "ready"; data: PlanRiskResponse } | { kind: "error"; error: unknown };

export function PlanRisk({ lat, lon, rotation }: { lat: number; lon: number; rotation: Rotation }) {
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
        <span className="eyebrow">Changing conditions</span>
        <h2 id="risk-title">Would this rotation have worked in past years?</h2>
        <p className="muted">
          We replayed each sowing against every season since 2000, using NASA satellite rain and daily weather.
        </p>
      </div>

      {status.kind === "ready" && status.data.enso_now && <EnsoNow now={status.data.enso_now} />}

      <div className="grid grid--2">
        {rotation.sequence.map((step, i) => {
          const planting = status.kind === "ready" ? status.data.plantings[i] : undefined;
          return (
            <article key={step.season} className="risk__planting">
              <header className="risk__head">
                <h3>
                  {step.crop_name} <span className="muted small">· {capitalize(step.season)}</span>
                </h3>
                <label className="risk__date">
                  <span className="visually-hidden">Sowing date for {step.crop_name}</span>
                  Sown{" "}
                  <select
                    value={`${sowings[i].month}-${sowings[i].day}`}
                    onChange={(e) => {
                      const [month, day] = e.target.value.split("-").map(Number);
                      setSowings((prev) => prev.map((s, j) => (j === i ? { month, day } : s)));
                    }}
                  >
                    {sowingOptions(step.months).map((o) => (
                      <option key={`${o.month}-${o.day}`} value={`${o.month}-${o.day}`}>
                        {dateLabel(o)}
                      </option>
                    ))}
                  </select>
                </label>
              </header>
              {status.kind === "loading" && <div className="skeleton" role="status" aria-label="Checking past years" />}
              {planting && <PlantingResult planting={planting} />}
            </article>
          );
        })}
      </div>

      {status.kind === "error" && <ErrorNotice error={status.error} onRetry={() => setAttempt((n) => n + 1)} />}

      {status.kind === "ready" && (
        <details className="more">
          <summary>About this check</summary>
          <ul className="list small more__body">
            {status.data.data_gaps.map((g) => (
              <li key={g.en}>{g.en}</li>
            ))}
          </ul>
          <p className="muted small">
            Sources: {status.data.data_sources.join(" · ")}. Seasons {status.data.years_evaluated.first}–
            {status.data.years_evaluated.last}.
          </p>
        </details>
      )}
    </section>
  );
}

function EnsoNow({ now }: { now: NonNullable<PlanRiskResponse["enso_now"]> }) {
  const phase = now.phase === "neutral" ? "Neutral conditions (no El Niño or La Niña)" : `${ENSO_LABELS[now.phase]} now`;
  return (
    <p className={`enso enso--${now.phase}`}>
      <strong>{phase}</strong> · ocean index {now.oni > 0 ? "+" : ""}
      {now.oni.toFixed(1)} °C ({now.season}). It describes the ocean today, not a forecast for your season.
    </p>
  );
}

function PlantingResult({ planting }: { planting: PlanRiskPlanting }) {
  const evaluated = planting.years.length;
  const stressed = planting.years.filter((y) => y.outcome === "stress").length;
  return (
    <div className="stack fade-in">
      <p className="risk__headline">
        <span className={`risk__badge risk__badge--${planting.failed_years > 0 ? "fail" : stressed > 0 ? "stress" : "ok"}`}>
          {planting.failed_years} of {evaluated} years failed
        </span>
        <span className="muted small">
          Sow {mmdd(planting.sowing_date)} → harvest {mmdd(planting.harvest_date)}
        </span>
      </p>
      <p>{planting.summary.en}</p>

      <YearStrip planting={planting} />

      {planting.causes.length > 0 && (
        <details className="more">
          <summary>What went wrong and what to do</summary>
          <div className="more__body stack">
            {planting.causes.map((c) => (
              <div key={c.cause}>
                <h4>
                  {CAUSE_LABELS[c.cause]}{" "}
                  <span className={`tag${c.severity === "fail" ? " tag--warn" : ""}`}>
                    {c.count} year{c.count === 1 ? "" : "s"} · {c.severity === "fail" ? "failed" : "stress"}
                  </span>
                </h4>
                <p className="small">{c.explanation.en}</p>
                <ul className="list small">
                  {c.actions.map((a) => (
                    <li key={a.en}>{a.en}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </details>
      )}

      {planting.alternatives.length > 0 && (
        <div className="risk__alts">
          <h4>Safer options</h4>
          <ul className="list small">
            {planting.alternatives.map((a) => (
              <li key={`${a.kind}-${a.crop_id}-${a.sowing_date}`}>{a.label.en}</li>
            ))}
          </ul>
        </div>
      )}

      {planting.enso_split && <p className="muted small">{planting.enso_split.note.en}</p>}
    </div>
  );
}

/** One cell per past season: color and symbol (never color alone), details on hover and for screen readers. */
function YearStrip({ planting }: { planting: PlanRiskPlanting }) {
  return (
    <div>
      <ol className="years" aria-label={`Outcome per sowing year for ${planting.crop_name.en}`}>
        {planting.years.map((y) => {
          const causes = y.causes.map((c) => CAUSE_LABELS[c].toLowerCase()).join(", ");
          const text = `${y.year}: ${OUTCOME[y.outcome].label}${causes ? ` (${causes})` : ""}${y.enso ? `, ${ENSO_LABELS[y.enso]}` : ""}`;
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
        <span className="years__cell years__cell--ok">✓</span> no problem
        <span className="years__cell years__cell--stress">!</span> stress
        <span className="years__cell years__cell--fail">✕</span> failed
      </p>
    </div>
  );
}
