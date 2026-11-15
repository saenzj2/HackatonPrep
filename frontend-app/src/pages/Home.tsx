import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { DEMO_FIELDS, DEMO_SCENARIO } from "../demoFields";
import { usePlan } from "../state/PlanContext";

export function Home() {
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
        <p className="tagline">Earth insights from space for more productive, resilient, and sustainable agriculture.</p>
        <h1>Identify the best crops for your field</h1>
        <p className="lead">
          See how each rotation fits your field's climate, water and soil, using NASA Earth
          observation data, crop requirements and the priorities you choose.
        </p>
        <div className="btn-row">
          <Link to="/field" className="btn">
            Start with my field
          </Link>
          <button type="button" className="btn btn--demo" onClick={() => void tryDemo()} disabled={loading}>
            {loading ? "Loading demo…" : "Try a demo"}
          </button>
          <Link to="/learn" className="btn btn--secondary">
            How it works
          </Link>
        </div>
      </section>

      <section aria-labelledby="how">
        <h2 id="how">How it works</h2>
        <ol className="grid grid--3 list" style={{ listStyle: "none", padding: 0 }}>
          <li className="panel">
            <h3>1. Choose your field</h3>
            <p>We look up long-term climate from NASA POWER, soil moisture from NASA SMAP and soil pH.</p>
          </li>
          <li className="panel">
            <h3>2. Tell us what matters</h3>
            <p>Pick the crops you can grow, what you grow now, and how much water, soil and climate matter to you.</p>
          </li>
          <li className="panel">
            <h3>3. Compare rotations</h3>
            <p>See ranked rotations with the reasons, the risks and what the data cannot tell.</p>
          </li>
        </ol>
      </section>

      <p className="notice notice--info small">
        Results are rule-based estimates to support your decision. They do not replace the advice of a
        local agronomist or extension officer.
      </p>
    </div>
  );
}
