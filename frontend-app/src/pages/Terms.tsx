import { Link } from "react-router";
import { useI18n, type Bilingual } from "../i18n";

// Plain-language terms for a hackathon prototype. Draft for the team to review; not legal advice.
// Facts here must match the app: no accounts, the plan lives in the browser session, the language
// choice in localStorage, maps from OpenStreetMap, videos from YouTube (privacy-enhanced mode).

const LAST_UPDATED: Bilingual = { en: "November 15, 2026", es: "15 de noviembre de 2026" };

const SECTIONS: { id: string; title: Bilingual; paragraphs: Bilingual[] }[] = [
  {
    id: "use",
    title: { en: "1. What Terra Cosmos is", es: "1. Qué es Terra Cosmos" },
    paragraphs: [
      {
        en: "Terra Cosmos is a free prototype built for the 2026 NASA Space Apps Challenge. It compares crop rotations for a field using public Earth observation, soil and crop data. By using it you accept these terms.",
        es: "Terra Cosmos es un prototipo gratuito hecho para el NASA Space Apps Challenge 2026. Compara rotaciones de cultivos para un campo con datos públicos de observación de la Tierra, suelos y cultivos. Al usarlo, usted acepta estos términos.",
      },
    ],
  },
  {
    id: "advice",
    title: { en: "2. Not professional advice", es: "2. No es asesoría profesional" },
    paragraphs: [
      {
        en: "Results are rule-based estimates, not predictions of yield, income or soil change. They do not consider everything that matters on a farm, such as irrigation, slope, pests, labor or prices. Check any decision with your own experience and a local agronomist or extension officer before you plant.",
        es: "Los resultados son estimaciones basadas en reglas, no predicciones de cosecha, ingresos ni cambios en el suelo. No consideran todo lo que importa en una finca, como el riego, la pendiente, las plagas, la mano de obra o los precios. Revise cualquier decisión con su propia experiencia y con un agrónomo o técnico de extensión de la zona antes de sembrar.",
      },
    ],
  },
  {
    id: "data",
    title: { en: "3. Data and its limits", es: "3. Los datos y sus límites" },
    paragraphs: [
      {
        en: "Climate, rainfall and soil values come from satellites, models and maps that cover areas from about 250 m to 50 km. They are estimates for your area, not measurements of your field, and they can be wrong or out of date.",
        es: "Los valores de clima, lluvia y suelo vienen de satélites, modelos y mapas que cubren áreas de unos 250 m a 50 km. Son estimaciones para su zona, no mediciones de su campo, y pueden estar equivocados o desactualizados.",
      },
      {
        en: "Each source keeps its own license and terms: NASA and NOAA data are openly available; OpenLandMap soil maps are licensed CC BY-SA 4.0; crop requirements come from FAO EcoCrop under FAO's terms of use; map tiles are © OpenStreetMap contributors. The sources are listed on the About page. NASA, NOAA and FAO do not endorse this project.",
        es: "Cada fuente mantiene su propia licencia y condiciones: los datos de la NASA y la NOAA son abiertos; los mapas de suelos de OpenLandMap tienen licencia CC BY-SA 4.0; los requisitos de los cultivos vienen de FAO EcoCrop según sus condiciones de uso; los mapas base son © colaboradores de OpenStreetMap. Las fuentes están en la página Acerca de. La NASA, la NOAA y la FAO no respaldan este proyecto.",
      },
    ],
  },
  {
    id: "privacy",
    title: { en: "4. Privacy", es: "4. Privacidad" },
    paragraphs: [
      {
        en: "Terra Cosmos has no accounts and does not ask for your name, email or phone. To look up data, the coordinates of the point you choose are sent to our server. Your choices on each step are kept in your browser only for the current visit, and your language choice is remembered in your browser. You can clear both by clearing your browser data.",
        es: "Terra Cosmos no tiene cuentas y no le pide su nombre, correo ni teléfono. Para buscar los datos, las coordenadas del punto que elija se envían a nuestro servidor. Lo que elige en cada paso se guarda en su navegador solo durante la visita, y su idioma queda recordado en su navegador. Puede borrar ambos limpiando los datos de su navegador.",
      },
      {
        en: "Some parts load from other services, which receive your IP address as any website does: map tiles from OpenStreetMap, and the background videos from YouTube in privacy-enhanced mode (youtube-nocookie.com). Our hosting provider may keep standard technical logs.",
        es: "Algunas partes se cargan desde otros servicios, que reciben su dirección IP como cualquier sitio web: los mapas desde OpenStreetMap y los videos de fondo desde YouTube en modo de privacidad mejorada (youtube-nocookie.com). Nuestro proveedor de alojamiento puede guardar registros técnicos normales.",
      },
    ],
  },
  {
    id: "ai",
    title: { en: "5. AI-generated content", es: "5. Contenido hecho con IA" },
    paragraphs: [
      {
        en: "The logo, brand artwork and background videos were made with AI tools and are labeled. Glossary and practice-card texts were drafted with AI and reviewed by the team. No AI model produces the recommendations.",
        es: "El logo, la imagen de marca y los videos de fondo se hicieron con herramientas de IA y están rotulados. Los textos del glosario y de las tarjetas de prácticas se redactaron con IA y los revisó el equipo. Ningún modelo de IA produce las recomendaciones.",
      },
    ],
  },
  {
    id: "warranty",
    title: { en: "6. No warranty and limitation of liability", es: "6. Sin garantía y límite de responsabilidad" },
    paragraphs: [
      {
        en: "Terra Cosmos is provided “as is”, without warranties of any kind, and may change, stop working or be taken offline at any time. To the extent the law allows, the team is not responsible for losses or damages, including crop losses, that result from using it or relying on its results.",
        es: "Terra Cosmos se ofrece “tal como está”, sin garantías de ningún tipo, y puede cambiar, dejar de funcionar o salir de línea en cualquier momento. En la medida en que la ley lo permita, el equipo no es responsable de pérdidas o daños, incluidas pérdidas de cosechas, que resulten de usarlo o de confiar en sus resultados.",
      },
    ],
  },
  {
    id: "changes",
    title: { en: "7. Changes to these terms", es: "7. Cambios en estos términos" },
    paragraphs: [
      {
        en: "We may update these terms. The date at the top shows the latest version.",
        es: "Podemos actualizar estos términos. La fecha al inicio indica la versión más reciente.",
      },
    ],
  },
];

export function Terms() {
  const { tr, pick } = useI18n();
  return (
    <div className="stack prose">
      <h1>{tr("Terms and Conditions", "Términos y condiciones")}</h1>
      <p className="muted">
        {tr("Last updated", "Última actualización")}: {pick(LAST_UPDATED)}
      </p>

      <nav className="panel" aria-label={tr("Contents", "Contenido")}>
        <ol className="list toc">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#terms-${s.id}`}
                onClick={(e) => {
                  // Hash routes own the URL hash, so scroll in place instead of navigating.
                  e.preventDefault();
                  document.getElementById(`terms-${s.id}`)?.scrollIntoView({ block: "start" });
                }}
              >
                {pick(s.title).replace(/^\d+\.\s*/, "")}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {SECTIONS.map((s) => (
        <section key={s.id} id={`terms-${s.id}`} className="panel stack" aria-labelledby={`terms-${s.id}-title`}>
          <h2 id={`terms-${s.id}-title`}>{pick(s.title)}</h2>
          {s.paragraphs.map((p) => (
            <p key={p.en}>{pick(p)}</p>
          ))}
        </section>
      ))}

      <p className="muted small">
        {tr("See also:", "Vea también:")} <Link to="/about">{tr("About", "Acerca de")}</Link> ·{" "}
        <Link to="/learn" state={{ section: "ai-use" }}>
          {tr("How we used AI", "Cómo usamos IA")}
        </Link>
      </p>
    </div>
  );
}
