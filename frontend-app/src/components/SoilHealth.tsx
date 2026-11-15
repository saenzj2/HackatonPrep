import { useEffect, useState } from "react";
import { api, type CropDetails, type Rotation, type Season, type SoilProfile } from "../api/client";
import { useI18n } from "../i18n";
import { fieldFacts, matchPractices, nitrogenInsight, PRACTICES_DISCLAIMER } from "../practices";

interface Props {
  lat: number;
  lon: number;
  seasons: Season[];
  recommended: Rotation;
  current: Rotation | null;
}

type Loaded = { soil: SoilProfile | null; crops: Map<string, CropDetails> };

/** Soil health for the recommended rotation: organic carbon, nitrogen and practice cards that fit. */
export function SoilHealth({ lat, lon, seasons, recommended, current }: Props) {
  const { tr, pick, lang } = useI18n();
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const list = (l: { en: string[]; es?: string[] }) => (lang === "es" && l.es ? l.es : l.en);

  useEffect(() => {
    let active = true;
    Promise.all([api.soil(lat, lon).catch(() => null), api.crops().catch(() => ({ crops: [] }))]).then(
      ([soil, crops]) => {
        if (active) setLoaded({ soil, crops: new Map(crops.crops.map((c) => [c.id, c])) });
      },
    );
    return () => {
      active = false;
    };
  }, [lat, lon]);

  if (!loaded) return <div className="skeleton" role="status" aria-label={tr("Loading soil health", "Cargando la salud del suelo")} />;

  const facts = fieldFacts(loaded.soil, seasons);
  const recIds = recommended.sequence.map((s) => s.crop_id);
  const insight = nitrogenInsight(facts, recIds, loaded.crops);
  const practices = matchPractices({
    facts,
    recommended: recIds,
    current: current ? current.sequence.map((s) => s.crop_id) : null,
    crops: loaded.crops,
  });

  return (
    <section className="panel soil stack fade-in" aria-labelledby="soil-title">
      <div>
        <span className="eyebrow">{tr("Soil health", "Salud del suelo")}</span>
        <h2 id="soil-title">{tr("Organic matter and nitrogen", "Materia orgánica y nitrógeno")}</h2>
        <p>{pick(insight)}</p>
      </div>

      {practices.length > 0 && (
        <div className="stack">
          <h3>{tr("Practices that could help this field", "Prácticas que podrían ayudar a este campo")}</h3>
          <div className="grid grid--3">
            {practices.map(({ card, reasons }) => (
              <article key={card.practice_id} className="practice">
                <h4>{pick(card.name)}</h4>
                <p className="small">{pick(card.summary)}</p>
                <p className="small">
                  <strong>{tr("Why here:", "Por qué aquí:")}</strong> {reasons.map(pick).join("; ")}.
                </p>
                <details className="more">
                  <summary>{tr("How to start", "Cómo empezar")}</summary>
                  <div className="more__body stack">
                    <ul className="list small">
                      {list(card.how_to_start).map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                    <p className="small">
                      <strong>{tr("Benefits:", "Beneficios:")}</strong> {list(card.benefits).join("; ")}.
                    </p>
                    <p className="small">
                      <strong>{tr("Check locally:", "Revise localmente:")}</strong> {list(card.cautions_local_review).join(" ")}
                    </p>
                    <p className="muted small">{pick(card.evidence_note)}</p>
                  </div>
                </details>
              </article>
            ))}
          </div>
        </div>
      )}

      <p className="muted small">
        {pick(PRACTICES_DISCLAIMER)}{" "}
        {tr(
          "Card texts drafted with AI (Claude) and reviewed by the team. Organic carbon is a soil-map estimate (OpenLandMap, 250 m), not a soil test.",
          "Textos de las tarjetas redactados con IA (Claude) y revisados por el equipo. El carbono orgánico es una estimación del mapa de suelos (OpenLandMap, 250 m), no un análisis de suelo.",
        )}
      </p>
    </section>
  );
}
