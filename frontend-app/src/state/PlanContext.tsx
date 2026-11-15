import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Priorities, Season } from "../api/client";

/** The field the farmer chose. Saved only after /conditions answered for it. */
export interface Field {
  lat: number;
  lon: number;
  name: string;
  seasons: Season[];
}

/** Everything POST /recommendations needs, kept while moving between steps. */
export interface PlanState {
  field: Field | null;
  /** null = all MVP crops (the request omits `crops`). */
  crops: string[] | null;
  /** One crop id per season, "" = not set. All empty = no current rotation. */
  currentRotation: string[];
  /** Slider values 0..10 (the API normalizes them to sum 1); null = the MVP default weights
   * from mvp.yaml, so the request omits `priorities` until the farmer moves a slider. */
  priorities: Priorities | null;
}

const INITIAL: PlanState = {
  field: null,
  crops: null,
  currentRotation: [],
  priorities: null,
};

const STORAGE_KEY = "guardians-plan-v1";

function load(): PlanState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? { ...INITIAL, ...(JSON.parse(raw) as Partial<PlanState>) } : INITIAL;
  } catch {
    return INITIAL;
  }
}

interface PlanContextValue {
  plan: PlanState;
  setField: (field: Field) => void;
  setCrops: (crops: string[] | null) => void;
  setCurrentRotation: (rotation: string[]) => void;
  setPriorities: (priorities: Priorities) => void;
}

const PlanContext = createContext<PlanContextValue | null>(null);

export function PlanProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<PlanState>(load);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(plan));
    } catch {
      // Private mode or blocked storage: the plan still works for this visit.
    }
  }, [plan]);

  const value: PlanContextValue = {
    plan,
    // A different field can have other seasons, so its current rotation starts over.
    setField: (field) =>
      setPlan((p) => {
        const same =
          p.field?.lat === field.lat &&
          p.field?.lon === field.lon &&
          p.currentRotation.length === field.seasons.length;
        return {
          ...p,
          field,
          currentRotation: same ? p.currentRotation : field.seasons.map(() => ""),
        };
      }),
    setCrops: (crops) => setPlan((p) => ({ ...p, crops })),
    setCurrentRotation: (currentRotation) => setPlan((p) => ({ ...p, currentRotation })),
    setPriorities: (priorities) => setPlan((p) => ({ ...p, priorities })),
  };

  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>;
}

export function usePlan(): PlanContextValue {
  const value = useContext(PlanContext);
  if (!value) throw new Error("usePlan must be used inside PlanProvider");
  return value;
}
