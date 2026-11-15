import { useEffect, useState } from "react";
import { useLocation } from "react-router";
// Bundled at build time from the backend's data folder (the Dockerfile copies it into the Node stage).
// Swap for a GET /glossary call if the team adds that endpoint.
import glossary from "../../../backend/data/glossary.json";

interface Term {
  term_id: string;
  category: string;
  term: { en: string };
  tooltip: { en: string };
  why_it_matters: { en: string };
  /** "planned" = a feature not built yet; hidden here (glossary.json meta.note). */
  status?: string;
}

const CATEGORIES = glossary.meta.categories as Record<string, { en: string }>;
const TERMS = (glossary.terms as Term[])
  .filter((t) => t.status !== "planned")
  .sort((a, b) => a.term.en.localeCompare(b.term.en));

export function Learn() {
  const [query, setQuery] = useState("");
  const location = useLocation();

  // The footer link opens this page at the AI section. Wait a moment: the route fade scrolls to the
  // top after this page's own effects run. (A timeout, not requestAnimationFrame, which background
  // tabs pause.)
  useEffect(() => {
    if ((location.state as { section?: string } | null)?.section !== "ai-use") return;
    const id = window.setTimeout(() => document.getElementById("ai-use")?.scrollIntoView({ block: "start" }), 50);
    return () => window.clearTimeout(id);
  }, [location.state]);
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
            <strong>Rotation rules:</strong> a bonus when a legume follows a crop that is not a legume; penalties for
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
        <p className="muted small">Definitions drafted with AI (Claude) and reviewed by the team.</p>
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

      <section className="panel stack" id="ai-use" aria-labelledby="ai-use-title">
        <h2 id="ai-use-title">How we used AI</h2>
        <p>
          AI tools helped us build this project. The recommendations do not come from an AI model: every
          score comes from our own code, public crop data (FAO EcoCrop) and NASA Earth observations.
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">What</th>
                <th scope="col">AI tool</th>
                <th scope="col">How it is labeled</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Background video clips</th>
                <td>Veo (Google)</td>
                <td>
                  <span className="ai-mark">AI generated video</span> on screen
                </td>
              </tr>
              <tr>
                <th scope="row">Logo and brand artwork</th>
                <td>AI image generator</td>
                <td>
                  <span className="ai-mark">AI generated</span> in the footer
                </td>
              </tr>
              <tr>
                <th scope="row">Glossary and practice-card texts</th>
                <td>Claude (Anthropic)</td>
                <td>Note under each section; reviewed by the team</td>
              </tr>
              <tr>
                <th scope="row">Presentation video end card</th>
                <td>Claude (Anthropic)</td>
                <td>Labeled in the video</td>
              </tr>
              <tr>
                <th scope="row">Code, tests and documentation; project backlog</th>
                <td>Claude Code (Anthropic), OpenAI Codex</td>
                <td>Every change reviewed by the team in pull requests with automated checks</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
