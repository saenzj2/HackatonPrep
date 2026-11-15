import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type RecommendationRequest, type RecommendationResponse, type Rotation } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { NeedsField } from "../components/NeedsField";
import { Stepper } from "../components/Stepper";
import { capitalize, monthSpan, scoreOf1, signed } from "../format";
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
    priorities: plan.priorities,
    top_n: TOP_N,
    ...(plan.crops ? { crops: plan.crops } : {}),
    ...(rotation.length > 0 && rotation.every(Boolean) ? { current_rotation: rotation } : {}),
  };
}

/** The API's one-line explanation, without the trailing "Score 0.91 of 1." (shown separately). */
const summaryOf = (r: Rotation) => r.explanation.en.replace(/\s*Score [\d.]+ of 1\.?\s*$/, "");

export function Results() {
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
        <h1>Best rotation for {plan.field.name}</h1>
        <div className="btn-row">
          <Link to="/plan" className="btn btn--secondary btn--small">
            Change priorities
          </Link>
          <Link to="/field" className="btn btn--secondary btn--small">
            Edit field
          </Link>
        </div>
      </div>

      <div aria-live="polite">
        {status.kind === "loading" && (
          <div className="stack" role="status" aria-label="Comparing rotations">
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
  const [best, ...others] = data.rotations;
  const current = data.current_rotation;
  const total = data.priorities.water + data.priorities.soil + data.priorities.climate || 1;
  const pct = (v: number) => `${Math.round((v / total) * 100)}%`;

  if (!best) {
    return (
      <div className="notice">
        <h2>No rotation found</h2>
        <p>Try selecting more crops or changing your priorities.</p>
      </div>
    );
  }

  const bestIsCurrent = best.is_current;
  return (
    <div className="stack fade-in">
      <article className="panel best">
        <div className="best__head">
          <span className="eyebrow">Recommended</span>
          <Sequence rotation={best} large />
        </div>

        <div className="best__body">
          <div className="best__score">
            <span className="score score--xl">{scoreOf1(best.score)}</span>
            <span className="tag">Rule-based estimate</span>
            {!best.viable && <span className="tag tag--warn">Poor fit</span>}
          </div>
          <p className="best__summary">{summaryOf(best)}</p>
          <Counts rotation={best} />
        </div>

        {current && !bestIsCurrent && <VsCurrent best={best} current={current} />}
        {bestIsCurrent && (
          <p className="notice notice--info small">Your current rotation is already the best fit among these crops.</p>
        )}

        <Breakdown rotation={best} />
        <Details rotation={best} />
      </article>

      {others.length > 0 && (
        <details className="panel others">
          <summary>
            {others.length} other option{others.length > 1 ? "s" : ""}
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
        Scores run from 0 to 1: how well each rotation fits this field's climate, water and soil, plus
        rotation rules. They are rule-based estimates, not yield predictions. Weights: water{" "}
        {pct(data.priorities.water)}, soil {pct(data.priorities.soil)}, climate {pct(data.priorities.climate)}.
        Method {data.method_version}.
      </p>
    </div>
  );
}

function Sequence({ rotation, large = false }: { rotation: Rotation; large?: boolean }) {
  return (
    <ol className={`sequence${large ? " sequence--large" : ""}`} aria-label="Crop per season">
      {rotation.sequence.map((step, i) => (
        <li key={step.season}>
          {i > 0 && (
            <span className="sequence__arrow" aria-hidden="true">
              →
            </span>
          )}
          <span className="sequence__step">
            <span className="season">
              {capitalize(step.season)} · {monthSpan(step.months)}
            </span>
            {step.crop_name}
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
  const b = rotation.benefits.length;
  const r = rotation.risks.length;
  return (
    <p className="counts">
      <span>
        <CheckIcon /> {b} benefit{b === 1 ? "" : "s"}
      </span>
      <span>
        <WarnIcon /> {r} thing{r === 1 ? "" : "s"} to watch
      </span>
    </p>
  );
}

function VsCurrent({ best, current }: { best: Rotation; current: Rotation }) {
  const delta = best.score_delta_vs_current;
  return (
    <div className="vs" aria-label="Compared with your current rotation">
      <div className="vs__row">
        <span className="vs__label">Recommended</span>
        <span className="bar__track" aria-hidden="true">
          <span className="bar__fill bar__fill--soil" style={{ width: `${best.score * 100}%` }} />
        </span>
        <span className="vs__value">{best.score.toFixed(2)}</span>
      </div>
      <div className="vs__row">
        <span className="vs__label">
          Your current: {current.sequence.map((s) => s.crop_name).join(" → ")}
        </span>
        <span className="bar__track" aria-hidden="true">
          <span className="bar__fill bar__fill--muted" style={{ width: `${current.score * 100}%` }} />
        </span>
        <span className="vs__value">{current.score.toFixed(2)}</span>
      </div>
      {delta != null && (
        <p className="small">
          <strong>{signed(delta)}</strong> better than what you grow now.
        </p>
      )}
    </div>
  );
}

function Breakdown({ rotation }: { rotation: Rotation }) {
  return (
    <div className="breakdown" aria-label="Score by part">
      <Bar label="Climate" value={rotation.breakdown.climate} kind="climate" />
      <Bar label="Water" value={rotation.breakdown.water} kind="water" />
      <Bar label="Soil" value={rotation.breakdown.soil} kind="soil" />
    </div>
  );
}

function Details({ rotation }: { rotation: Rotation }) {
  return (
    <details className="more">
      <summary>See details</summary>
      <div className="grid grid--2 more__body">
        {rotation.benefits.length > 0 && (
          <div>
            <h4>
              <CheckIcon /> Benefits
            </h4>
            <ul className="list">
              {rotation.benefits.map((b) => (
                <li key={b.en}>{b.en}</li>
              ))}
            </ul>
          </div>
        )}
        {rotation.risks.length > 0 && (
          <div>
            <h4>
              <WarnIcon /> Watch out
            </h4>
            <ul className="list">
              {rotation.risks.map((r) => (
                <li key={r.en}>{r.en}</li>
              ))}
            </ul>
          </div>
        )}
        {rotation.evidence.length > 0 && (
          <div>
            <h4>Data behind this score</h4>
            <ul className="list small">
              {rotation.evidence.map((e) => (
                <li key={e.en}>{e.en}</li>
              ))}
            </ul>
          </div>
        )}
        {rotation.data_gaps.length > 0 && (
          <div>
            <h4>What the data cannot tell</h4>
            <ul className="list small">
              {rotation.data_gaps.map((g) => (
                <li key={g.en}>{g.en}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}

function OptionRow({ rotation, hasCurrent }: { rotation: Rotation; hasCurrent: boolean }) {
  return (
    <div className="option">
      <div className="option__head">
        <Sequence rotation={rotation} />
        <span className="score">{scoreOf1(rotation.score)}</span>
      </div>
      <p className="small">{summaryOf(rotation)}</p>
      <div className="option__meta">
        <Counts rotation={rotation} />
        {hasCurrent && rotation.score_delta_vs_current != null && !rotation.is_current && (
          <span className="small muted">{signed(rotation.score_delta_vs_current)} vs your current rotation</span>
        )}
        {rotation.is_current && <span className="tag">Your current rotation</span>}
      </div>
      <Breakdown rotation={rotation} />
      <Details rotation={rotation} />
    </div>
  );
}

function Bar({ label, value, kind }: { label: string; value: number | null; kind: "climate" | "water" | "soil" }) {
  return (
    <div className="bar">
      <span>{label}</span>
      <span className="bar__track" aria-hidden="true">
        {value != null && <span className={`bar__fill bar__fill--${kind}`} style={{ width: `${value * 100}%` }} />}
      </span>
      <span>{value != null ? value.toFixed(2) : "Not scored"}</span>
    </div>
  );
}
