const STEPS = [
  { id: "field", label: "1. My field" },
  { id: "plan", label: "2. Crops and priorities" },
  { id: "results", label: "3. Rotations" },
] as const;

export function Stepper({ current }: { current: (typeof STEPS)[number]["id"] }) {
  return (
    <ol className="stepper" aria-label="Steps">
      {STEPS.map((step) => (
        <li key={step.id} aria-current={step.id === current ? "step" : undefined}>
          {step.label}
        </li>
      ))}
    </ol>
  );
}
