import { useEffect, useState } from "react";
import { useLocation } from "react-router";
// Bundled at build time from the backend's data folder (the Dockerfile copies it into the Node stage).
// Swap for a GET /glossary call if the team adds that endpoint.
import glossary from "../../../backend/data/glossary.json";
import { useI18n, type Bilingual } from "../i18n";

interface Term {
  term_id: string;
  category: string;
  term: Bilingual;
  tooltip: Bilingual;
  why_it_matters: Bilingual;
  /** "planned" = a feature not built yet; hidden here (glossary.json meta.note). */
  status?: string;
}

const CATEGORIES = glossary.meta.categories as Record<string, Bilingual>;
const TERMS = (glossary.terms as Term[]).filter((t) => t.status !== "planned");

// "How we used AI" rows (keep in sync with README.md "Use of AI tools").
const AI_ROWS: { what: Bilingual; tool: Bilingual; label: Bilingual; mark?: Bilingual }[] = [
  {
    what: { en: "Background video clips", es: "Videos de fondo" },
    tool: { en: "Veo (Google)", es: "Veo (Google)" },
    mark: { en: "AI generated video", es: "Video hecho con IA" },
    label: { en: "on screen", es: "en pantalla" },
  },
  {
    what: { en: "Logo and brand artwork", es: "Logo e imagen de marca" },
    tool: { en: "AI image generator", es: "Generador de imágenes con IA" },
    mark: { en: "AI generated", es: "Hecho con IA" },
    label: { en: "in the footer", es: "en el pie de página" },
  },
  {
    what: { en: "Glossary and practice-card texts", es: "Textos del glosario y de las tarjetas de prácticas" },
    tool: { en: "Claude (Anthropic)", es: "Claude (Anthropic)" },
    label: { en: "Note under each section; reviewed by the team", es: "Nota en cada sección; revisados por el equipo" },
  },
  {
    what: { en: "Presentation video end card", es: "Tarjeta final del video de presentación" },
    tool: { en: "Claude (Anthropic)", es: "Claude (Anthropic)" },
    label: { en: "Labeled in the video", es: "Rotulada en el video" },
  },
  {
    what: { en: "Code, tests and documentation; project backlog", es: "Código, pruebas y documentación; lista de tareas del proyecto" },
    tool: { en: "Claude Code (Anthropic), OpenAI Codex", es: "Claude Code (Anthropic), OpenAI Codex" },
    label: {
      en: "Every change reviewed by the team in pull requests with automated checks",
      es: "Cada cambio lo revisó el equipo en pull requests con pruebas automáticas",
    },
  },
];

export function Learn() {
  const { tr, pick, lang } = useI18n();
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
  const matches = TERMS.filter((t) => !q || pick(t.term).toLowerCase().includes(q) || pick(t.tooltip).toLowerCase().includes(q)).sort(
    (a, b) => pick(a.term).localeCompare(pick(b.term), lang),
  );

  return (
    <div className="stack">
      <h1>{tr("Learn", "Aprenda")}</h1>

      <section className="panel stack" aria-labelledby="scores">
        <h2 id="scores">{tr("How the scores work", "Cómo funcionan los puntajes")}</h2>
        <p>
          {tr(
            "Each crop gets a score from 0 to 1 for each season: how well the season's climate, water and soil fit what the crop needs. A rotation's score is the average over its seasons, adjusted by rotation rules.",
            "Cada cultivo recibe un puntaje de 0 a 1 en cada época: qué tan bien el clima, el agua y el suelo de la época le sirven al cultivo. El puntaje de una rotación es el promedio de sus épocas, ajustado por las reglas de rotación.",
          )}
        </p>
        <ul className="list">
          <li>
            <strong>{tr("Climate:", "Clima:")}</strong>{" "}
            {tr("average temperature, heat stress and frost risk, from NASA POWER.", "temperatura promedio, estrés por calor y riesgo de helada, de NASA POWER.")}
          </li>
          <li>
            <strong>{tr("Water:", "Agua:")}</strong>{" "}
            {tr(
              "rainfall over the crop's cycle (NASA POWER) and soil moisture (NASA SMAP satellite).",
              "lluvia durante el ciclo del cultivo (NASA POWER) y humedad del suelo (satélite NASA SMAP).",
            )}
          </li>
          <li>
            <strong>{tr("Soil:", "Suelo:")}</strong> {tr("soil pH from the OpenLandMap soil map.", "pH del suelo del mapa OpenLandMap.")}
          </li>
          <li>
            <strong>{tr("Rotation rules:", "Reglas de rotación:")}</strong>{" "}
            {tr(
              "a bonus when a legume follows a crop that is not a legume; penalties for repeating a crop, two crops of the same family, two heavy nitrogen feeders in a row, or breaking the soil fungi that some crops depend on.",
              "una bonificación cuando una leguminosa sigue a un cultivo que no lo es; penalizaciones por repetir un cultivo, por dos cultivos de la misma familia, por dos cultivos que piden mucho nitrógeno seguidos, o por cortar los hongos del suelo de los que dependen algunos cultivos.",
            )}
          </li>
          <li>
            <strong>{tr("Your priorities", "Sus prioridades")}</strong>{" "}
            {tr("set how much climate, water and soil count.", "definen cuánto pesan el clima, el agua y el suelo.")}
          </li>
        </ul>
        <p className="muted small">
          {tr(
            "Crop requirements come from FAO EcoCrop. Irrigation, slope and erosion, pests beyond crop family, labor and market prices are not scored. Check them with a local agronomist or extension officer.",
            "Los requisitos de los cultivos vienen de FAO EcoCrop. No se evalúan el riego, la pendiente y la erosión, las plagas más allá de la familia del cultivo, la mano de obra ni los precios. Consúltelos con un agrónomo o técnico de extensión de la zona.",
          )}
        </p>
      </section>

      <section className="panel stack" aria-labelledby="glossary">
        <h2 id="glossary">{tr("Glossary", "Glosario")}</h2>
        <div>
          <label htmlFor="glossary-search">{tr("Search a term", "Buscar un término")}</label>
          <input id="glossary-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        {matches.length === 0 && (
          <p className="muted">{tr(`No term matches “${query}”.`, `Ningún término coincide con “${query}”.`)}</p>
        )}
        <p className="muted small">
          {tr("Definitions drafted with AI (Claude) and reviewed by the team.", "Definiciones redactadas con IA (Claude) y revisadas por el equipo.")}
        </p>
        {Object.entries(CATEGORIES).map(([id, name]) => {
          const terms = matches.filter((t) => t.category === id);
          if (terms.length === 0) return null;
          return (
            <div key={id}>
              <h3>{pick(name)}</h3>
              {terms.map((t) => (
                <details key={t.term_id}>
                  <summary>{pick(t.term)}</summary>
                  <p>{pick(t.tooltip)}</p>
                  <p className="muted small">{pick(t.why_it_matters)}</p>
                </details>
              ))}
            </div>
          );
        })}
      </section>

      <section className="panel stack" id="ai-use" aria-labelledby="ai-use-title">
        <h2 id="ai-use-title">{tr("How we used AI", "Cómo usamos IA")}</h2>
        <p>
          {tr(
            "AI tools helped us build this project. The recommendations do not come from an AI model: every score comes from our own code, public crop data (FAO EcoCrop) and NASA Earth observations.",
            "Herramientas de IA nos ayudaron a construir este proyecto. Las recomendaciones no salen de un modelo de IA: cada puntaje sale de nuestro propio código, de datos públicos de cultivos (FAO EcoCrop) y de observaciones de la Tierra de la NASA.",
          )}
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">{tr("What", "Qué")}</th>
                <th scope="col">{tr("AI tool", "Herramienta de IA")}</th>
                <th scope="col">{tr("How it is labeled", "Cómo se rotula")}</th>
              </tr>
            </thead>
            <tbody>
              {AI_ROWS.map((row) => (
                <tr key={row.what.en}>
                  <th scope="row">{pick(row.what)}</th>
                  <td>{pick(row.tool)}</td>
                  <td>
                    {row.mark && <span className="ai-mark">{pick(row.mark)}</span>} {pick(row.label)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
