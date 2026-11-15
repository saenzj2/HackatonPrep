import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, type Crop, type Priorities } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { NeedsField } from "../components/NeedsField";
import { Stepper } from "../components/Stepper";
import { capitalize, monthSpan } from "../format";
import { usePlan } from "../state/PlanContext";

const PRIORITY_INFO: { key: keyof Priorities; label: string; hint: string }[] = [
  { key: "water", label: "Water", hint: "Rainfall and soil moisture fit the crop" },
  { key: "soil", label: "Soil", hint: "Soil pH fits the crop" },
  { key: "climate", label: "Climate", hint: "Temperature, heat stress and frost risk" },
];

type CropsState = { kind: "loading" } | { kind: "ready"; crops: Crop[] } | { kind: "error"; error: unknown };

export function Plan() {
  const { plan, setCrops, setCurrentRotation, setPriorities } = usePlan();
  const navigate = useNavigate();
  const [crops, setCropsState] = useState<CropsState>({ kind: "loading" });
  const [formError, setFormError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setCropsState({ kind: "loading" });
    api
      .crops()
      .then((r) => active && setCropsState({ kind: "ready", crops: r.crops }))
      .catch((error: unknown) => active && setCropsState({ kind: "error", error }));
    return () => {
      active = false;
    };
  }, [attempt]);

  // Until the farmer moves a slider, show the MVP default weights (mvp.yaml) as the API applies
  // them: one cheap /recommendations call returns the weights it used.
  const [defaults, setDefaults] = useState<Priorities | null>(null);
  const fieldKey = plan.field ? `${plan.field.lat},${plan.field.lon}` : "";
  useEffect(() => {
    if (!plan.field || plan.priorities) return;
    let active = true;
    api
      .recommendations({ lat: plan.field.lat, lon: plan.field.lon, top_n: 1 })
      .then((r) => {
        if (!active) return;
        const p = r.priorities;
        setDefaults({ water: Math.round(p.water * 10), soil: Math.round(p.soil * 10), climate: Math.round(p.climate * 10) });
      })
      .catch(() => undefined); // sliders stay hidden; the request still uses the defaults
    return () => {
      active = false;
    };
  }, [fieldKey, plan.priorities === null]);

  if (!plan.field) return <NeedsField />;
  const field = plan.field;

  const allIds = crops.kind === "ready" ? crops.crops.map((c) => c.id) : [];
  const selected = plan.crops ?? allIds;
  const weights = plan.priorities ?? defaults;
  const total = weights ? weights.water + weights.soil + weights.climate : 0;

  function toggleCrop(id: string) {
    const next = selected.includes(id) ? selected.filter((c) => c !== id) : [...selected, id];
    // All crops selected = omit `crops` and let the API use the MVP list.
    setCrops(next.length === allIds.length ? null : allIds.filter((c) => next.includes(c)));
  }

  function setSeasonCrop(index: number, cropId: string) {
    const next = field.seasons.map((_, i) => plan.currentRotation[i] ?? "");
    next[index] = cropId;
    setCurrentRotation(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const filled = plan.currentRotation.filter(Boolean).length;
    if (selected.length === 0) return setFormError("Select at least one crop to consider.");
    if (filled > 0 && filled < field.seasons.length) {
      return setFormError("Choose a crop for every season of your current rotation, or leave all empty.");
    }
    if (weights && total === 0) return setFormError("Move at least one priority above zero.");
    setFormError(null);
    navigate("/results");
  }

  return (
    <div className="stack">
      <Stepper current="plan" />
      <h1>Crops and priorities</h1>
      <p className="lead">
        For <strong>{field.name}</strong>. <Link to="/field">Change field</Link>
      </p>

      {crops.kind === "loading" && <div className="skeleton" role="status" aria-label="Loading crops" />}
      {crops.kind === "error" && <ErrorNotice error={crops.error} onRetry={() => setAttempt((n) => n + 1)} />}

      {crops.kind === "ready" && (
        <form className="stack" onSubmit={submit} noValidate>
          <fieldset>
            <legend>What you grow now (optional)</legend>
            <p className="hint">
              One crop per season. We compare every option with it. Leave all empty if you have no current crop.
            </p>
            <div className="grid grid--2">
              {field.seasons.map((season, i) => (
                <div key={season.name}>
                  <label htmlFor={`season-${season.name}`}>
                    {capitalize(season.name)} <span className="hint">({monthSpan(season.months)})</span>
                  </label>
                  <select
                    id={`season-${season.name}`}
                    value={plan.currentRotation[i] ?? ""}
                    onChange={(e) => setSeasonCrop(i, e.target.value)}
                  >
                    <option value="">No crop / not sure</option>
                    {crops.crops.map((crop) => (
                      <option key={crop.id} value={crop.id}>
                        {crop.name}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>What matters most to you</legend>
            <p className="hint">
              Each slider sets how much that part counts in the ranking.
              {!plan.priorities && " Now showing the default weights."}
            </p>
            {!weights && <div className="skeleton" role="status" aria-label="Loading default weights" />}
            <div className="stack">
              {weights && PRIORITY_INFO.map(({ key, label, hint }) => {
                const share = total > 0 ? Math.round((weights[key] / total) * 100) : 0;
                return (
                  <div key={key}>
                    <label htmlFor={`priority-${key}`}>
                      {label}: {share}% <span className="hint">· {hint}</span>
                    </label>
                    <input
                      id={`priority-${key}`}
                      type="range"
                      min={0}
                      max={10}
                      step={1}
                      value={weights[key]}
                      aria-valuetext={`${share}% of the ranking`}
                      onChange={(e) => setPriorities({ ...weights, [key]: Number(e.target.value) })}
                    />
                  </div>
                );
              })}
            </div>
          </fieldset>

          <details className="panel" open={selected.length === 0}>
            <summary>
              Crops to compare:{" "}
              {selected.length === allIds.length
                ? "all available"
                : crops.crops
                    .filter((c) => selected.includes(c.id))
                    .map((c) => c.name)
                    .join(", ") || "none"}
            </summary>
            <fieldset className="fieldset--plain">
              <legend className="visually-hidden">Crops you can grow</legend>
              <p className="hint">Rotations are built only from the crops you select.</p>
              {crops.crops.map((crop) => (
                <label key={crop.id} className="check">
                  <input type="checkbox" checked={selected.includes(crop.id)} onChange={() => toggleCrop(crop.id)} />
                  {crop.name}
                  {crop.is_legume && <span className="tag">Legume</span>}
                  {crop.is_cover_crop && <span className="tag">Cover crop</span>}
                </label>
              ))}
            </fieldset>
          </details>

          {formError && (
            <p className="field-error" role="alert">
              {formError}
            </p>
          )}

          <div className="btn-row">
            <Link to="/field" className="btn btn--secondary">
              Back
            </Link>
            <button type="submit" className="btn">
              Compare rotations
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
