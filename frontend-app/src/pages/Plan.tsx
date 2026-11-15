import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, type Crop, type Priorities } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { NeedsField } from "../components/NeedsField";
import { Stepper } from "../components/Stepper";
import { capitalize, monthSpan } from "../format";
import { useI18n, type Bilingual } from "../i18n";
import { usePlan } from "../state/PlanContext";

const PRIORITY_INFO: { key: keyof Priorities; label: Bilingual; hint: Bilingual }[] = [
  {
    key: "water",
    label: { en: "Water", es: "Agua" },
    hint: { en: "Rainfall and soil moisture fit the crop", es: "La lluvia y la humedad del suelo le sirven al cultivo" },
  },
  { key: "soil", label: { en: "Soil", es: "Suelo" }, hint: { en: "Soil pH fits the crop", es: "El pH del suelo le sirve al cultivo" } },
  {
    key: "climate",
    label: { en: "Climate", es: "Clima" },
    hint: { en: "Temperature, heat stress and frost risk", es: "Temperatura, estrés por calor y riesgo de helada" },
  },
];

type CropsState = { kind: "loading" } | { kind: "ready"; crops: Crop[] } | { kind: "error"; error: unknown };

export function Plan() {
  const { tr, pick, lang } = useI18n();
  const { plan, setCrops, setCurrentRotation, setPriorities } = usePlan();
  const navigate = useNavigate();
  const [crops, setCropsState] = useState<CropsState>({ kind: "loading" });
  const [formError, setFormError] = useState<Bilingual | null>(null);
  const [attempt, setAttempt] = useState(0);
  const cropName = (c: Crop) => (lang === "es" && c.name_es ? c.name_es : c.name);

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
    if (selected.length === 0) {
      return setFormError({ en: "Select at least one crop to consider.", es: "Elija al menos un cultivo para comparar." });
    }
    if (filled > 0 && filled < field.seasons.length) {
      return setFormError({
        en: "Choose a crop for every season of your current rotation, or leave all empty.",
        es: "Elija un cultivo para cada época de su rotación actual, o deje todas vacías.",
      });
    }
    if (weights && total === 0) {
      return setFormError({ en: "Move at least one priority above zero.", es: "Suba al menos una prioridad por encima de cero." });
    }
    setFormError(null);
    navigate("/results");
  }

  return (
    <div className="stack">
      <Stepper current="plan" />
      <h1>{tr("Crops and priorities", "Cultivos y prioridades")}</h1>
      <p className="lead">
        {tr("For", "Para")} <strong>{field.name}</strong>. <Link to="/field">{tr("Change field", "Cambiar de campo")}</Link>
      </p>

      {crops.kind === "loading" && <div className="skeleton" role="status" aria-label={tr("Loading crops", "Cargando cultivos")} />}
      {crops.kind === "error" && <ErrorNotice error={crops.error} onRetry={() => setAttempt((n) => n + 1)} />}

      {crops.kind === "ready" && (
        <form className="stack" onSubmit={submit} noValidate>
          <fieldset>
            <legend>{tr("What you grow now (optional)", "Lo que siembra hoy (opcional)")}</legend>
            <p className="hint">
              {tr(
                "One crop per season. We compare every option with it. Leave all empty if you have no current crop.",
                "Un cultivo por época. Comparamos cada opción con esto. Deje todo vacío si hoy no siembra nada.",
              )}
            </p>
            <div className="grid grid--2">
              {field.seasons.map((season, i) => (
                <div key={season.name}>
                  <label htmlFor={`season-${season.name}`}>
                    {capitalize(season.name)} <span className="hint">({monthSpan(season.months, lang)})</span>
                  </label>
                  <select
                    id={`season-${season.name}`}
                    value={plan.currentRotation[i] ?? ""}
                    onChange={(e) => setSeasonCrop(i, e.target.value)}
                  >
                    <option value="">{tr("No crop / not sure", "Ningún cultivo / no sé")}</option>
                    {crops.crops.map((crop) => (
                      <option key={crop.id} value={crop.id}>
                        {cropName(crop)}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>{tr("What matters most to you", "Lo que más le importa")}</legend>
            <p className="hint">
              {tr("Each slider sets how much that part counts in the ranking.", "Cada control define cuánto pesa esa parte en el orden.")}
              {!plan.priorities && tr(" Now showing the default weights.", " Ahora se muestran los pesos por defecto.")}
            </p>
            {!weights && <div className="skeleton" role="status" aria-label={tr("Loading default weights", "Cargando pesos por defecto")} />}
            <div className="stack">
              {weights &&
                PRIORITY_INFO.map(({ key, label, hint }) => {
                  const share = total > 0 ? Math.round((weights[key] / total) * 100) : 0;
                  return (
                    <div key={key}>
                      <label htmlFor={`priority-${key}`}>
                        {pick(label)}: {share} % <span className="hint">· {pick(hint)}</span>
                      </label>
                      <input
                        id={`priority-${key}`}
                        type="range"
                        min={0}
                        max={10}
                        step={1}
                        value={weights[key]}
                        aria-valuetext={tr(`${share}% of the ranking`, `${share} % del orden`)}
                        onChange={(e) => setPriorities({ ...weights, [key]: Number(e.target.value) })}
                      />
                    </div>
                  );
                })}
            </div>
          </fieldset>

          <details className="panel" open={selected.length === 0}>
            <summary>
              {tr("Crops to compare", "Cultivos para comparar")}:{" "}
              {selected.length === allIds.length
                ? tr("all available", "todos los disponibles")
                : crops.crops
                    .filter((c) => selected.includes(c.id))
                    .map(cropName)
                    .join(", ") || tr("none", "ninguno")}
            </summary>
            <fieldset className="fieldset--plain">
              <legend className="visually-hidden">{tr("Crops you can grow", "Cultivos que puede sembrar")}</legend>
              <p className="hint">
                {tr("Rotations are built only from the crops you select.", "Las rotaciones se arman solo con los cultivos que elija.")}
              </p>
              {crops.crops.map((crop) => (
                <label key={crop.id} className="check">
                  <input type="checkbox" checked={selected.includes(crop.id)} onChange={() => toggleCrop(crop.id)} />
                  {cropName(crop)}
                  {crop.is_legume && <span className="tag">{tr("Legume", "Leguminosa")}</span>}
                  {crop.is_cover_crop && <span className="tag">{tr("Cover crop", "Cultivo de cobertura")}</span>}
                </label>
              ))}
            </fieldset>
          </details>

          {formError && (
            <p className="field-error" role="alert">
              {pick(formError)}
            </p>
          )}

          <div className="btn-row">
            <Link to="/field" className="btn btn--secondary">
              {tr("Back", "Atrás")}
            </Link>
            <button type="submit" className="btn">
              {tr("Compare rotations", "Comparar rotaciones")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
