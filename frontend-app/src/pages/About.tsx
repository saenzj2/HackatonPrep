import { Link } from "react-router";
import { useI18n, type Bilingual } from "../i18n";

const SOURCES: { name: string; url: string; what: Bilingual }[] = [
  {
    name: "NASA POWER",
    url: "https://power.larc.nasa.gov/",
    what: { en: "Long-term monthly climate and daily weather", es: "Clima mensual de largo plazo y clima diario" },
  },
  {
    name: "NASA SMAP",
    url: "https://smap.jpl.nasa.gov/",
    what: { en: "Soil moisture from satellite", es: "Humedad del suelo por satélite" },
  },
  {
    name: "NASA GPM IMERG",
    url: "https://gpm.nasa.gov/data/imerg",
    what: { en: "Daily rainfall from satellites (past-weather check)", es: "Lluvia diaria por satélite (revisión con años anteriores)" },
  },
  {
    name: "NASA MERRA-2",
    url: "https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/",
    what: { en: "Daily temperature and soil wetness (past-weather check)", es: "Temperatura y humedad diarias del suelo (revisión con años anteriores)" },
  },
  {
    name: "NOAA CPC",
    url: "https://www.cpc.ncep.noaa.gov/",
    what: { en: "El Niño / La Niña ocean index", es: "Índice del océano de El Niño / La Niña" },
  },
  {
    name: "OpenLandMap",
    url: "https://openlandmap.org/",
    what: { en: "Soil maps: pH, organic carbon, texture (250 m)", es: "Mapas de suelos: pH, carbono orgánico, textura (250 m)" },
  },
  {
    name: "FAO EcoCrop",
    url: "https://gaez.fao.org/pages/ecocrop",
    what: { en: "What each crop needs: temperature, rain, soil pH", es: "Lo que necesita cada cultivo: temperatura, lluvia, pH del suelo" },
  },
  {
    name: "OpenStreetMap",
    url: "https://www.openstreetmap.org/copyright",
    what: { en: "Base map", es: "Mapa base" },
  },
];

export function About() {
  const { tr, pick } = useI18n();
  return (
    <div className="stack prose">
      <h1>{tr("About Terra Cosmos", "Acerca de Terra Cosmos")}</h1>
      <p className="lead">
        {tr(
          "Terra Cosmos helps smallholder farmers choose crop rotations that protect their soil and cope with a changing climate, using NASA Earth observation data.",
          "Terra Cosmos ayuda a pequeños productores a elegir rotaciones de cultivos que protejan su suelo y resistan un clima cambiante, con datos de observación de la Tierra de la NASA.",
        )}
      </p>

      <section className="panel stack" aria-labelledby="about-what">
        <h2 id="about-what">{tr("What it does", "Qué hace")}</h2>
        <p>
          {tr(
            "You choose your field on the map, the crops you can grow, what you grow now and what matters most to you: water, soil or climate. The tool ranks two-season rotations for that field, explains each one, compares it with your current rotation and replays every sowing against the weather of past seasons since 2000.",
            "Usted elige su campo en el mapa, los cultivos que puede sembrar, lo que siembra hoy y lo que más le importa: el agua, el suelo o el clima. La herramienta ordena rotaciones de dos épocas para ese campo, explica cada una, la compara con su rotación actual y prueba cada siembra contra el clima de las temporadas pasadas desde el 2000.",
          )}
        </p>
        <p>
          {tr(
            "Every score is a rule-based estimate that shows its data and its limits. It supports your decision; it does not replace your experience or the advice of a local agronomist.",
            "Cada puntaje es una estimación basada en reglas que muestra sus datos y sus límites. Apoya su decisión; no reemplaza su experiencia ni el consejo de un agrónomo de la zona.",
          )}
        </p>
        <p>
          <Link to="/learn">{tr("How the scores work", "Cómo funcionan los puntajes")}</Link>
        </p>
      </section>

      <section className="panel stack" aria-labelledby="about-challenge">
        <h2 id="about-challenge">{tr("The challenge", "El reto")}</h2>
        <p>
          {tr(
            "Terra Cosmos was built by the team Guardians of the Harvest for the 2026 NASA Space Apps Challenge, “Field Shift: Adapting Farms with NASA Data”: a decision-support tool that uses NASA Earth observations with local soil information, crop characteristics and farmer priorities to explore rotation strategies that strengthen soil health and adapt farms to changing conditions.",
            "Terra Cosmos lo construyó el equipo Guardians of the Harvest para el NASA Space Apps Challenge 2026, “Field Shift: Adapting Farms with NASA Data”: una herramienta de apoyo a decisiones que usa observaciones de la Tierra de la NASA junto con información local del suelo, características de los cultivos y las prioridades del agricultor, para explorar rotaciones que fortalezcan la salud del suelo y adapten las fincas a condiciones cambiantes.",
          )}
        </p>
        <p className="muted small">
          {tr(
            "The pilot region is Costa Rica. This is a hackathon prototype: the demo works with preloaded data for a few fields.",
            "La región piloto es Costa Rica. Es un prototipo de hackatón: la demostración funciona con datos precargados de algunos campos.",
          )}
        </p>
      </section>

      <section className="panel stack" aria-labelledby="about-data">
        <h2 id="about-data">{tr("Data sources", "Fuentes de datos")}</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">{tr("Source", "Fuente")}</th>
                <th scope="col">{tr("Used for", "Para qué se usa")}</th>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map((s) => (
                <tr key={s.name}>
                  <th scope="row">
                    <a href={s.url} target="_blank" rel="noopener noreferrer">
                      {s.name}
                      <span className="visually-hidden">{tr(" (opens in a new tab)", " (se abre en otra pestaña)")}</span>
                    </a>
                  </th>
                  <td>{pick(s.what)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          {tr(
            "NASA does not endorse this project. Terra Cosmos uses NASA's openly available data.",
            "La NASA no respalda este proyecto. Terra Cosmos usa datos abiertos de la NASA.",
          )}
        </p>
      </section>

      <section className="panel stack" aria-labelledby="about-more">
        <h2 id="about-more">{tr("More", "Más información")}</h2>
        <ul className="list">
          <li>
            <Link to="/learn" state={{ section: "ai-use" }}>
              {tr("How we used AI", "Cómo usamos IA")}
            </Link>
          </li>
          <li>
            <Link to="/terms">{tr("Terms and Conditions", "Términos y condiciones")}</Link>
          </li>
          <li>
            <a href="/docs">{tr("API documentation", "Documentación de la API")}</a>
          </li>
        </ul>
      </section>
    </div>
  );
}
