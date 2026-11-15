import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type RecommendationRequest, type RecommendationResponse, type Rotation } from "../api/client";
import { CompareTable } from "../components/CompareTable";
import { ErrorNotice } from "../components/ErrorNotice";
import { NeedsField } from "../components/NeedsField";
import { PlanRisk } from "../components/PlanRisk";
import { SoilHealth } from "../components/SoilHealth";
import { Stepper } from "../components/Stepper";
import { WhyNotCurrent } from "../components/WhyNotCurrent";
import { useCropName } from "../cropNames";
import { capitalize, monthSpan, scoreOf1, signed } from "../format";
import { useI18n, type Bilingual } from "../i18n";
import { usePlan, type PlanState } from "../state/PlanContext";

const TOP_N = 3; // requirements: show up to three candidate rotations

type Status =
  | { kind: "loading" }
  | { kind: "ready"; data: RecommendationResponse }
  | { kind: "error"; error: unknown };

function toRequest(plan: PlanState): RecommendationRequest | null {
  if (!plan.field) return null;
  const rotation = plan.currentRotation;
  return {
    lat: plan.field.lat,
    lon: plan.field.lon,
    ...(plan.priorities ? { priorities: plan.priorities } : {}),
    top_n: TOP_N,
    ...(plan.crops ? { crops: plan.crops } : {}),
    ...(rotation.length > 0 && rotation.every(Boolean) ? { current_rotation: rotation } : {}),
  };
}

/**
 * The API's one-line explanation, without the trailing "Score 0.91 of 1." / "Puntaje 0,91 de 1."
 * (shown separately). Matches the wording built in backend/app/domain/ranking.py; if that wording
 * changes, the regex simply stops matching and the full explanation is shown.
 */
const stripScore = (text: string) => text.replace(/\s*(Score [\d.]+ of 1|Puntaje [\d,]+ de 1)\.?\s*$/, "");

/** Crop names of a rotation in the visitor's language. */
function useSequenceNames() {
  const cropName = useCropName();
  return (r: Rotation) => r.sequence.map((s) => cropName(s.crop_id, s.crop_name));
}

export function Results() {
  const { tr } = useI18n();
  const { plan } = usePlan();
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const request = toRequest(plan);
  const requestKey = JSON.stringify(request);

  // Fetched fresh from the current inputs, so a changed field or crop never shows stale results.
  useEffect(() => {
    if (!request) return;
    let active = true;
    setStatus({ kind: "loading" });
    api
      .recommendations(request)
      .then((data) => active && setStatus({ kind: "ready", data }))
      .catch((error: unknown) => active && setStatus({ kind: "error", error }));
    return () => {
      active = false;
    };
  }, [requestKey, attempt]); // requestKey changes whenever any input changes

  if (!plan.field) return <NeedsField />;

  return (
    <div className="stack">
      <Stepper current="results" />
      <div className="section-head">
        <h1>
          {tr("Best rotation for", "Mejor rotación para")} {plan.field.name}
        </h1>
        <div className="btn-row">
          <Link to="/plan" className="btn btn--secondary btn--small">
            {tr("Change priorities", "Cambiar prioridades")}
          </Link>
          <Link to="/field" className="btn btn--secondary btn--small">
            {tr("Edit field", "Editar campo")}
          </Link>
        </div>
      </div>

      <div aria-live="polite">
        {status.kind === "loading" && (
          <div className="stack" role="status" aria-label={tr("Comparing rotations", "Comparando rotaciones")}>
            <div className="skeleton skeleton--tall" />
            <div className="skeleton" />
          </div>
        )}
        {status.kind === "error" && (
          <ErrorNotice
            error={status.error}
            onRetry={() => setAttempt((n) => n + 1)}
            onPickDemo={() => navigate("/field")}
          />
        )}
        {status.kind === "ready" && <ResultsView data={status.data} />}
      </div>
    </div>
  );
}

function ResultsView({ data }: { data: RecommendationResponse }) {
  const { tr, pick, lang } = useI18n();
  const [best, ...others] = data.rotations;
  const current = data.current_rotation;
  const total = data.priorities.water + data.priorities.soil + data.priorities.climate || 1;
  const pct = (v: number) => `${Math.round((v / total) * 100)} %`;

  if (!best) {
    return (
      <div className="notice">
        <h2>{tr("No rotation found", "No se encontró ninguna rotación")}</h2>
        <p>{tr("Try selecting more crops or changing your priorities.", "Pruebe con más cultivos o cambie sus prioridades.")}</p>
      </div>
    );
  }

  const bestIsCurrent = best.is_current;
  return (
    <div className="stack fade-in">
      <article className="panel best">
        <div className="best__head">
          <span className="eyebrow">{tr("Recommended", "Recomendada")}</span>
          <Sequence rotation={best} large />
        </div>

        <div className="best__body">
          <div className="best__score">
            <span className="score score--xl">{scoreOf1(best.score, lang)}</span>
            <span className="tag">{tr("Rule-based estimate", "Estimación basada en reglas")}</span>
            {!best.viable && <span className="tag tag--warn">{tr("Poor fit", "Poco adecuada")}</span>}
          </div>
          <p className="best__summary">{stripScore(pick(best.explanation))}</p>
          <Counts rotation={best} />
        </div>

        {current && !bestIsCurrent && <VsCurrent best={best} current={current} />}
        {bestIsCurrent && (
          <p className="notice notice--info small">
            {tr(
              "Your current rotation is already the best fit among these crops.",
              "Su rotación actual ya es la que mejor se adapta entre estos cultivos.",
            )}
          </p>
        )}

        <Breakdown rotation={best} />
        <Details rotation={best} />
      </article>

      {current && !bestIsCurrent && <WhyNotCurrent best={best} current={current} />}

      <CompareTable lat={data.location.lat} lon={data.location.lon} rotations={data.rotations} current={current} />

      <PlanRisk
        key={best.sequence.map((s) => s.crop_id).join("-")}
        lat={data.location.lat}
        lon={data.location.lon}
        rotation={best}
      />

      <SoilHealth
        lat={data.location.lat}
        lon={data.location.lon}
        seasons={data.conditions.seasons}
        recommended={best}
        current={current}
      />

      {others.length > 0 && (
        <details className="panel others">
          <summary>
            {others.length === 1 ? tr("1 other option", "1 opción más") : tr(`${others.length} other options`, `${others.length} opciones más`)}
          </summary>
          <ul className="option-list">
            {others.map((r) => (
              <li key={r.rank}>
                <OptionRow rotation={r} hasCurrent={current !== null} />
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="muted small">
        {tr(
          `Scores run from 0 to 1: how well each rotation fits this field's climate, water and soil, plus rotation rules. They are rule-based estimates, not yield predictions. Weights: water ${pct(data.priorities.water)}, soil ${pct(data.priorities.soil)}, climate ${pct(data.priorities.climate)}. Method ${data.method_version}.`,
          `Los puntajes van de 0 a 1: qué tan bien se adapta cada rotación al clima, el agua y el suelo de este campo, más las reglas de rotación. Son estimaciones basadas en reglas, no predicciones de cosecha. Pesos: agua ${pct(data.priorities.water)}, suelo ${pct(data.priorities.soil)}, clima ${pct(data.priorities.climate)}. Método ${data.method_version}.`,
        )}
      </p>
    </div>
  );
}

function Sequence({ rotation, large = false }: { rotation: Rotation; large?: boolean }) {
  const { tr, lang } = useI18n();
  const names = useSequenceNames()(rotation);
  return (
    <ol className={`sequence${large ? " sequence--large" : ""}`} aria-label={tr("Crop per season", "Cultivo por época")}>
      {rotation.sequence.map((step, i) => (
        <li key={step.season}>
          {i > 0 && (
            <span className="sequence__arrow" aria-hidden="true">
              →
            </span>
          )}
          <span className="sequence__step">
            <span className="season">
              {capitalize(step.season)} · {monthSpan(step.months, lang)}
            </span>
            {names[i]}
          </span>
        </li>
      ))}
    </ol>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" className="icon icon--good">
      <circle cx="8" cy="8" r="8" />
      <path d="M4.5 8.3l2.2 2.2 4.8-4.8" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function WarnIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" className="icon icon--warn">
      <path d="M8 1l7.5 13.5h-15z" />
      <path d="M8 6v4" stroke="#0f1f2d" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="8" cy="12.3" r="1" fill="#0f1f2d" />
    </svg>
  );
}

function Counts({ rotation }: { rotation: Rotation }) {
  const { tr } = useI18n();
  const b = rotation.benefits.length;
  const r = rotation.risks.length;
  return (
    <p className="counts">
      <span>
        <CheckIcon /> {b === 1 ? tr("1 benefit", "1 beneficio") : tr(`${b} benefits`, `${b} beneficios`)}
      </span>
      <span>
        <WarnIcon /> {r === 1 ? tr("1 thing to watch", "1 aspecto a vigilar") : tr(`${r} things to watch`, `${r} aspectos a vigilar`)}
      </span>
    </p>
  );
}

function VsCurrent({ best, current }: { best: Rotation; current: Rotation }) {
  const { tr, num, lang } = useI18n();
  const names = useSequenceNames();
  const delta = best.score_delta_vs_current;
  return (
    <div className="vs" aria-label={tr("Compared with your current rotation", "Comparada con su rotación actual")}>
      <div className="vs__row">
        <span className="vs__label">{tr("Recommended", "Recomendada")}</span>
        <span className="bar__track" aria-hidden="true">
          <span className="bar__fill bar__fill--soil" style={{ width: `${best.score * 100}%` }} />
        </span>
        <span className="vs__value">{num(best.score)}</span>
      </div>
      <div className="vs__row">
        <span className="vs__label">
          {tr("Your current", "Su rotación actual")}: {names(current).join(" → ")}
        </span>
        <span className="bar__track" aria-hidden="true">
          <span className="bar__fill bar__fill--muted" style={{ width: `${current.score * 100}%` }} />
        </span>
        <span className="vs__value">{num(current.score)}</span>
      </div>
      {delta != null && (
        <p className="small">
          <strong>{signed(delta, lang)}</strong> {tr("better than what you grow now.", "mejor que lo que siembra hoy.")}
        </p>
      )}
    </div>
  );
}

function Breakdown({ rotation }: { rotation: Rotation }) {
  const { tr } = useI18n();
  return (
    <div className="breakdown" aria-label={tr("Score by part", "Puntaje por parte")}>
      <Bar label={tr("Climate", "Clima")} value={rotation.breakdown.climate} kind="climate" />
      <Bar label={tr("Water", "Agua")} value={rotation.breakdown.water} kind="water" />
      <Bar label={tr("Soil", "Suelo")} value={rotation.breakdown.soil} kind="soil" />
    </div>
  );
}

function TextList({ items, small = false }: { items: Bilingual[]; small?: boolean }) {
  const { pick } = useI18n();
  return (
    <ul className={`list${small ? " small" : ""}`}>
      {items.map((t) => (
        <li key={t.en}>{pick(t)}</li>
      ))}
    </ul>
  );
}

function Details({ rotation }: { rotation: Rotation }) {
  const { tr } = useI18n();
  return (
    <details className="more">
      <summary>{tr("See details", "Ver detalles")}</summary>
      <div className="grid grid--2 more__body">
        {rotation.benefits.length > 0 && (
          <div>
            <h4>
              <CheckIcon /> {tr("Benefits", "Beneficios")}
            </h4>
            <TextList items={rotation.benefits} />
          </div>
        )}
        {rotation.risks.length > 0 && (
          <div>
            <h4>
              <WarnIcon /> {tr("Watch out", "Atención")}
            </h4>
            <TextList items={rotation.risks} />
          </div>
        )}
        {rotation.evidence.length > 0 && (
          <div>
            <h4>{tr("Data behind this score", "Datos detrás de este puntaje")}</h4>
            <TextList items={rotation.evidence} small />
          </div>
        )}
        {rotation.data_gaps.length > 0 && (
          <div>
            <h4>{tr("What the data cannot tell", "Lo que los datos no pueden decir")}</h4>
            <TextList items={rotation.data_gaps} small />
          </div>
        )}
      </div>
    </details>
  );
}

function OptionRow({ rotation, hasCurrent }: { rotation: Rotation; hasCurrent: boolean }) {
  const { tr, pick, lang } = useI18n();
  return (
    <div className="option">
      <div className="option__head">
        <Sequence rotation={rotation} />
        <span className="score">{scoreOf1(rotation.score, lang)}</span>
      </div>
      <p className="small">{stripScore(pick(rotation.explanation))}</p>
      <div className="option__meta">
        <Counts rotation={rotation} />
        {hasCurrent && rotation.score_delta_vs_current != null && !rotation.is_current && (
          <span className="small muted">
            {signed(rotation.score_delta_vs_current, lang)} {tr("vs your current rotation", "frente a su rotación actual")}
          </span>
        )}
        {rotation.is_current && <span className="tag">{tr("Your current rotation", "Su rotación actual")}</span>}
      </div>
      <Breakdown rotation={rotation} />
      <Details rotation={rotation} />
    </div>
  );
}

function Bar({ label, value, kind }: { label: string; value: number | null; kind: "climate" | "water" | "soil" }) {
  const { tr, num } = useI18n();
  return (
    <div className="bar">
      <span>{label}</span>
      <span className="bar__track" aria-hidden="true">
        {value != null && <span className={`bar__fill bar__fill--${kind}`} style={{ width: `${value * 100}%` }} />}
      </span>
      <span>{value != null ? num(value) : tr("Not scored", "Sin puntaje")}</span>
    </div>
  );
}
