import { useEffect, useState } from "react";
import { api, type CropDetails, type Rotation, type Season, type SoilProfile } from "../api/client";
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
  const [loaded, setLoaded] = useState<Loaded | null>(null);

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

  if (!loaded) return <div className="skeleton" role="status" aria-label="Loading soil health" />;

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
        <span className="eyebrow">Soil health</span>
        <h2 id="soil-title">Organic matter and nitrogen</h2>
        {insight && <p>{insight}</p>}
      </div>

      {practices.length > 0 && (
        <div className="stack">
          <h3>Practices that could help this field</h3>
          <div className="grid grid--3">
            {practices.map(({ card, reasons }) => (
              <article key={card.practice_id} className="practice">
                <h4>{card.name.en}</h4>
                <p className="small">{card.summary.en}</p>
                <p className="small">
                  <strong>Why here:</strong> {reasons.join("; ")}.
                </p>
                <details className="more">
                  <summary>How to start</summary>
                  <div className="more__body stack">
                    <ul className="list small">
                      {card.how_to_start.en.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                    <p className="small">
                      <strong>Benefits:</strong> {card.benefits.en.join("; ")}.
                    </p>
                    <p className="small">
                      <strong>Check locally:</strong> {card.cautions_local_review.en.join(" ")}
                    </p>
                    <p className="muted small">{card.evidence_note.en}</p>
                  </div>
                </details>
              </article>
            ))}
          </div>
        </div>
      )}

      <p className="muted small">
        {PRACTICES_DISCLAIMER} Card texts drafted with AI (Claude) and reviewed by the team. Organic carbon
        is a soil-map estimate (OpenLandMap, 250 m), not a soil test.
      </p>
    </section>
  );
}
