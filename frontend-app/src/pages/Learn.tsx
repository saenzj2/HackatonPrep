import { useState } from "react";
// Bundled at build time from the backend's data folder (the Dockerfile copies it into the Node stage).
// Swap for a GET /glossary call if the team adds that endpoint.
import glossary from "../../../backend/data/glossary.json";

interface Term {
  term_id: string;
  category: string;
  term: { en: string };
  tooltip: { en: string };
  why_it_matters: { en: string };
}

const CATEGORIES = glossary.meta.categories as Record<string, { en: string }>;
const TERMS = (glossary.terms as Term[]).slice().sort((a, b) => a.term.en.localeCompare(b.term.en));

export function Learn() {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const matches = TERMS.filter(
    (t) => !q || t.term.en.toLowerCase().includes(q) || t.tooltip.en.toLowerCase().includes(q),
  );

  return (
    <div className="stack">
      <h1>Learn</h1>

      <section className="panel stack" aria-labelledby="scores">
        <h2 id="scores">How the scores work</h2>
        <p>
          Each crop gets a score from 0 to 1 for each season: how well the season's climate, water and soil
          fit what the crop needs. A rotation's score is the average over its seasons, adjusted by rotation
          rules.
        </p>
        <ul className="list">
          <li>
            <strong>Climate:</strong> average temperature, heat stress and frost risk, from NASA POWER.
          </li>
          <li>
            <strong>Water:</strong> rainfall over the crop's cycle (NASA POWER) and soil moisture (NASA SMAP
            satellite).
          </li>
          <li>
            <strong>Soil:</strong> soil pH from the OpenLandMap soil map.
          </li>
          <li>
            <strong>Rotation rules:</strong> a bonus when a legume follows another crop; penalties for
            repeating a crop, two crops of the same family, two heavy nitrogen feeders in a row, or breaking
            the soil fungi that some crops depend on.
          </li>
          <li>
            <strong>Your priorities</strong> set how much climate, water and soil count.
          </li>
        </ul>
        <p className="muted small">
          Crop requirements come from FAO EcoCrop. Irrigation, slope and erosion, pests beyond crop family,
          labour and market prices are not scored. Check them with a local agronomist or extension officer.
        </p>
      </section>

      <section className="panel stack" aria-labelledby="glossary">
        <h2 id="glossary">Glossary</h2>
        <div>
          <label htmlFor="glossary-search">Search a term</label>
          <input
            id="glossary-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {matches.length === 0 && <p className="muted">No term matches “{query}”.</p>}
        {Object.entries(CATEGORIES).map(([id, name]) => {
          const terms = matches.filter((t) => t.category === id);
          if (terms.length === 0) return null;
          return (
            <div key={id}>
              <h3>{name.en}</h3>
              {terms.map((t) => (
                <details key={t.term_id}>
                  <summary>{t.term.en}</summary>
                  <p>{t.tooltip.en}</p>
                  <p className="muted small">{t.why_it_matters.en}</p>
                </details>
              ))}
            </div>
          );
        })}
      </section>
    </div>
  );
}
