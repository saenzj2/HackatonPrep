import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { DEMO_FIELDS, DEMO_SCENARIO } from "../demoFields";
import { useI18n } from "../i18n";
import { usePlan } from "../state/PlanContext";

export function Home() {
  const { tr } = useI18n();
  const navigate = useNavigate();
  const { setField, setCrops, setCurrentRotation, setPriorities } = usePlan();
  const [loading, setLoading] = useState(false);

  // Fills the plan with a demo field and current rotation, then opens the results in one click.
  async function tryDemo() {
    const field = DEMO_FIELDS.find((f) => f.id === DEMO_SCENARIO.fieldId) ?? DEMO_FIELDS[0];
    setLoading(true);
    try {
      const conditions = await api.conditions(field.lat, field.lon);
      const seasons = conditions.seasons.map(({ name, months }) => ({ name, months }));
      setField({ lat: field.lat, lon: field.lon, name: field.name, seasons });
      setCrops(null);
      setPriorities(null);
      setCurrentRotation(seasons.map(() => DEMO_SCENARIO.currentCrop));
      navigate("/results");
    } catch {
      navigate("/field"); // the field step explains the problem and offers the demo fields
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <section className="hero">
        <p className="tagline">
          {tr(
            "Earth insights from space for more productive, resilient, and sustainable agriculture.",
            "Datos de la Tierra desde el espacio para una agricultura más productiva, resistente y sostenible.",
          )}
        </p>
        <h1>{tr("Identify the best crops for your field", "Identifique los mejores cultivos para su campo")}</h1>
        <p className="lead">
          {tr(
            "See how each rotation fits your field's climate, water and soil, using NASA Earth observation data, crop requirements and the priorities you choose.",
            "Vea qué tan bien se adapta cada rotación al clima, el agua y el suelo de su campo, con datos de observación de la Tierra de la NASA, los requisitos de cada cultivo y las prioridades que usted elija.",
          )}
        </p>
        <div className="btn-row">
          <Link to="/field" className="btn">
            {tr("Start with my field", "Empezar con mi campo")}
          </Link>
          <button type="button" className="btn btn--demo" onClick={() => void tryDemo()} disabled={loading}>
            {loading ? tr("Loading demo…", "Cargando demostración…") : tr("Try a demo", "Ver una demostración")}
          </button>
          <Link to="/learn" className="btn btn--secondary">
            {tr("How it works", "Cómo funciona")}
          </Link>
        </div>
      </section>

      <section aria-labelledby="how">
        <h2 id="how">{tr("How it works", "Cómo funciona")}</h2>
        <ol className="grid grid--3 list" style={{ listStyle: "none", padding: 0 }}>
          <li className="panel">
            <h3>{tr("1. Choose your field", "1. Elija su campo")}</h3>
            <p>
              {tr(
                "We look up long-term climate from NASA POWER, soil moisture from NASA SMAP and soil pH.",
                "Buscamos el clima de largo plazo en NASA POWER, la humedad del suelo en NASA SMAP y el pH del suelo.",
              )}
            </p>
          </li>
          <li className="panel">
            <h3>{tr("2. Tell us what matters", "2. Díganos qué le importa")}</h3>
            <p>
              {tr(
                "Pick the crops you can grow, what you grow now, and how much water, soil and climate matter to you.",
                "Elija los cultivos que puede sembrar, lo que siembra hoy y cuánto le importan el agua, el suelo y el clima.",
              )}
            </p>
          </li>
          <li className="panel">
            <h3>{tr("3. Compare rotations", "3. Compare rotaciones")}</h3>
            <p>
              {tr(
                "See ranked rotations with the reasons, the risks and what the data cannot tell.",
                "Vea las rotaciones ordenadas, con sus razones, sus riesgos y lo que los datos no pueden decir.",
              )}
            </p>
          </li>
        </ol>
      </section>

      <p className="notice notice--info small">
        {tr(
          "Results are rule-based estimates to support your decision. They do not replace the advice of a local agronomist or extension officer.",
          "Los resultados son estimaciones basadas en reglas para apoyar su decisión. No reemplazan el consejo de un agrónomo o técnico de extensión de la zona.",
        )}
      </p>
    </div>
  );
}
