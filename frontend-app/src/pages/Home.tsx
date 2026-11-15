import { Link } from "react-router";

export function Home() {
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
