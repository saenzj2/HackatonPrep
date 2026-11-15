// Crop names in the visitor's language. GET /crops has `name` (English) and `name_es`; rotation steps
// only carry the English name, so screens look the Spanish one up here by crop id.
import { useEffect, useState } from "react";
import { api } from "./api/client";
import { useI18n } from "./i18n";

type Names = Map<string, { en: string; es?: string }>;

let cache: Promise<Names> | null = null;
const load = (): Promise<Names> =>
  (cache ??= api
    .crops()
    .then((r) => new Map(r.crops.map((c) => [c.id, { en: c.name, es: c.name_es }])))
    .catch(() => {
      cache = null; // try again next time
      return new Map();
    }));

/** cropName(id, englishFallback) in the current language. */
export function useCropName(): (id: string, fallback: string) => string {
  const { lang } = useI18n();
  const [names, setNames] = useState<Names>(new Map());
  useEffect(() => {
    let active = true;
    void load().then((n) => active && setNames(n));
    return () => {
      active = false;
    };
  }, []);
  return (id, fallback) => (lang === "es" ? (names.get(id)?.es ?? fallback) : (names.get(id)?.en ?? fallback));
}
