import type { Rotation } from "../api/client";
import { useCropName } from "../cropNames";
import { capitalize } from "../format";
import { useI18n, type Bilingual } from "../i18n";

// "Why your current rotation scores lower": puts the farmer's own choice next to the recommendation
// and shows what holds it back, using only what /recommendations already returns (season-level
// variable scores, the score breakdown and the rotation's risks).

/** Below this a variable is a real problem for the crop (same cut as suitability.MARGINAL_SCORE). */
const WEAK = 0.5;

const VARIABLE_LABELS: Record<string, Bilingual> = {
  temperature: { en: "Temperature", es: "Temperatura" },
  rainfall: { en: "Rain over the crop cycle", es: "Lluvia durante el ciclo" },
  soil_ph: { en: "Soil pH", es: "pH del suelo" },
  soil_moisture: { en: "Soil moisture", es: "Humedad del suelo" },
  heat: { en: "Heat stress", es: "Estrés por calor" },
  frost: { en: "Frost risk", es: "Riesgo de helada" },
};

const PARTS: { key: "climate" | "water" | "soil"; label: Bilingual }[] = [
  { key: "climate", label: { en: "Climate", es: "Clima" } },
  { key: "water", label: { en: "Water", es: "Agua" } },
  { key: "soil", label: { en: "Soil", es: "Suelo" } },
];

/** Generic "check locally" notes are on every rotation; they don't explain a difference. */
const isGeneric = (t: Bilingual) => t.en.startsWith("Local review");

export function WhyNotCurrent({ best, current }: { best: Rotation; current: Rotation }) {
  const { tr, pick, num } = useI18n();
  const cropName = useCropName();

  // Season-by-season weak spots, e.g. "Primera · Rice: Rain over the crop cycle 0.00".
  const weak = current.sequence.flatMap((step) =>
    Object.entries(step.variable_scores ?? {})
      .filter(([, v]) => v < WEAK)
      .map(([variable, v]) => ({
        key: `${step.season}-${variable}`,
        where: `${capitalize(step.season)} · ${cropName(step.crop_id, step.crop_name)}`,
        what: VARIABLE_LABELS[variable] ? pick(VARIABLE_LABELS[variable]) : variable,
        value: v,
      })),
  );
  const lowerParts = PARTS.filter(({ key }) => {
    const b = best.breakdown[key];
    const c = current.breakdown[key];
    return b != null && c != null && b > c;
  });
  const reasons = current.risks.filter((r) => !isGeneric(r));
  const delta = best.score - current.score;

  return (
    <section className="panel why-current stack" aria-labelledby="why-current-title">
      <div>
        <span className="eyebrow eyebrow--current">{tr("Your choice", "Su elección")}</span>
        <h2 id="why-current-title">{tr("Why your current rotation scores lower", "Por qué su rotación actual puntúa menos")}</h2>
        <p>
          {tr(
            `Your rotation scores ${num(current.score)} of 1, ${num(delta)} below the recommended one (${num(best.score)}).`,
            `Su rotación obtiene ${num(current.score)} de 1, ${num(delta)} menos que la recomendada (${num(best.score)}).`,
          )}{" "}
          {!current.viable &&
            tr(
              "At least one of its crops is outside what it tolerates in its season, so it is not recommended.",
              "Al menos uno de sus cultivos está fuera de lo que aguanta en su época, por eso no se recomienda.",
            )}
        </p>
      </div>

      {weak.length > 0 && (
        <div>
          <h3>{tr("What holds it back", "Lo que la frena")}</h3>
          <ul className="why-current__weak">
            {weak.map((w) => (
              <li key={w.key}>
                <span className="why-current__where">{w.where}</span>
                <span>
                  {w.what}: <strong>{num(w.value)}</strong> {tr("of 1", "de 1")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {reasons.length > 0 && (
        <div>
          <h3>{tr("The main reasons", "Las razones principales")}</h3>
          <ul className="list">
            {reasons.slice(0, 3).map((r) => (
              <li key={r.en}>{pick(r)}</li>
            ))}
          </ul>
          {reasons.length > 3 && (
            <details className="more">
              <summary>{tr(`${reasons.length - 3} more`, `${reasons.length - 3} más`)}</summary>
              <ul className="list small more__body">
                {reasons.slice(3).map((r) => (
                  <li key={r.en}>{pick(r)}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {lowerParts.length > 0 && (
        <div>
          <h3>{tr("Where the recommended rotation does better", "Dónde le va mejor a la recomendada")}</h3>
          <ul className="why-current__parts">
            {lowerParts.map(({ key, label }) => (
              <li key={key}>
                {pick(label)}: <strong>{num(best.breakdown[key] ?? 0)}</strong> {tr("vs", "frente a")} {num(current.breakdown[key] ?? 0)}
              </li>
            ))}
            {best.benefits.length > current.benefits.length && (
              <li>
                {tr("Benefits", "Beneficios")}: <strong>{best.benefits.length}</strong> {tr("vs", "frente a")} {current.benefits.length}
              </li>
            )}
          </ul>
        </div>
      )}
    </section>
  );
}
