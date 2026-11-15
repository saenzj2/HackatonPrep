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
      <h1>Rotations for {plan.field.name}</h1>
      <div className="btn-row">
        <Link to="/plan" className="btn btn--secondary">
          Change priorities
        </Link>
        <Link to="/field" className="btn btn--secondary">
          Edit field
        </Link>
      </div>

      <div aria-live="polite">
        {status.kind === "loading" && (
          <div className="grid grid--3" role="status" aria-label="Comparing rotations">
            <div className="skeleton" />
            <div className="skeleton" />
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
        {status.kind === "ready" && <ResultsList data={status.data} />}
      </div>
    </div>
  );
}

function ResultsList({ data }: { data: RecommendationResponse }) {
  const current = data.current_rotation;
  const total = data.priorities.water + data.priorities.soil + data.priorities.climate || 1;
  const pct = (v: number) => `${Math.round((v / total) * 100)}%`;

  return (
    <div className="stack">
      <p className="notice notice--info small">
        Scores run from 0 to 1 and show how well each rotation fits this field's climate, water and soil,
        plus rotation rules. They are rule-based estimates, not yield predictions. Weights used: water{" "}
        {pct(data.priorities.water)}, soil {pct(data.priorities.soil)}, climate {pct(data.priorities.climate)}.
      </p>

      {data.rotations.length === 0 ? (
        <div className="notice">
          <h2>No rotation found</h2>
          <p>Try selecting more crops or changing your priorities.</p>
        </div>
      ) : (
        <div className="grid grid--3">
          {data.rotations.map((rotation) => (
            <RotationCard key={rotation.rank} rotation={rotation} hasCurrent={current !== null} />
          ))}
        </div>
      )}

      {current && !data.rotations.some((r) => r.is_current) && (
        <section aria-labelledby="current">
          <h2 id="current">Your current rotation</h2>
          <div className="grid grid--3">
            <RotationCard rotation={current} hasCurrent />
          </div>
        </section>
      )}

      <p className="muted small">
        Method {data.method_version} · generated{" "}
        {new Date(data.generated_at).toLocaleDateString("en", { dateStyle: "medium" })}
      </p>
    </div>
  );
}

function RotationCard({ rotation, hasCurrent }: { rotation: Rotation; hasCurrent: boolean }) {
  const title = rotation.is_current ? "Your current rotation" : `Option ${rotation.rank}`;
  return (
    <article className={`panel rotation-card${rotation.is_current ? " rotation-card--current" : ""}`}>
      <header>
        <h3>{title}</h3>
        <ol className="sequence" aria-label="Crop per season">
          {rotation.sequence.map((step) => (
            <li key={step.season}>
              <span className="season">
                {capitalize(step.season)} · {monthSpan(step.months)}
              </span>
              {step.crop_name}
            </li>
          ))}
        </ol>
      </header>

      <div>
        <span className="score">{scoreOf1(rotation.score)}</span>{" "}
        <span className="tag">Rule-based estimate</span>
        {!rotation.viable && <span className="tag tag--warn">Poor fit</span>}
        {hasCurrent && rotation.score_delta_vs_current != null && !rotation.is_current && (
          <p className="small muted">{signed(rotation.score_delta_vs_current)} vs your current rotation</p>
        )}
      </div>

      <div aria-label="Score by part">
        <Bar label="Climate" value={rotation.breakdown.climate} kind="climate" />
        <Bar label="Water" value={rotation.breakdown.water} kind="water" />
        <Bar label="Soil" value={rotation.breakdown.soil} kind="soil" />
      </div>

      <p>{rotation.explanation.en}</p>

      {rotation.benefits.length > 0 && (
        <div>
          <h4>Benefits</h4>
          <ul className="list">
            {rotation.benefits.map((b) => (
              <li key={b.en}>{b.en}</li>
            ))}
          </ul>
        </div>
      )}

      {rotation.risks.length > 0 && (
        <div>
          <h4>Watch out</h4>
          <ul className="list">
            {rotation.risks.map((r) => (
              <li key={r.en}>{r.en}</li>
            ))}
          </ul>
        </div>
      )}

      {rotation.evidence.length > 0 && (
        <details>
          <summary>Data behind this score</summary>
          <ul className="list small">
            {rotation.evidence.map((e) => (
              <li key={e.en}>{e.en}</li>
            ))}
          </ul>
        </details>
      )}

      {rotation.data_gaps.length > 0 && (
        <details>
          <summary>What the data cannot tell</summary>
          <ul className="list small">
            {rotation.data_gaps.map((g) => (
              <li key={g.en}>{g.en}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function Bar({ label, value, kind }: { label: string; value: number | null; kind: "climate" | "water" | "soil" }) {
  return (
    <div className="bar">
      <span>{label}</span>
      <span className="bar__track" aria-hidden="true">
        {value != null && (
          <span className={`bar__fill bar__fill--${kind}`} style={{ width: `${value * 100}%`, display: "block" }} />
        )}
      </span>
      <span>{value != null ? value.toFixed(2) : "Not scored"}</span>
    </div>
  );
}
