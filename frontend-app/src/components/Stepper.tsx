import { useI18n } from "../i18n";

const STEPS = [
  { id: "field", en: "1. My field", es: "1. Mi campo" },
  { id: "plan", en: "2. Crops and priorities", es: "2. Cultivos y prioridades" },
  { id: "results", en: "3. Rotations", es: "3. Rotaciones" },
] as const;

export function Stepper({ current }: { current: (typeof STEPS)[number]["id"] }) {
  const { tr } = useI18n();
  return (
    <ol className="stepper" aria-label={tr("Steps", "Pasos")}>
      {STEPS.map((step) => (
        <li key={step.id} aria-current={step.id === current ? "step" : undefined}>
          {tr(step.en, step.es)}
        </li>
      ))}
    </ol>
  );
}
