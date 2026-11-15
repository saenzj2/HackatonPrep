import type { Lang } from "./i18n";

const MONTHS: Record<Lang, string[]> = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  // Costa Rica writes "set" for setiembre (backend/app/domain/text.py).
  es: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"],
};

export const monthName = (month: number, lang: Lang = "en") => MONTHS[lang][month - 1] ?? String(month);

/** "May–Aug" for a season's consecutive months. */
export function monthSpan(months: number[], lang: Lang = "en"): string {
  if (months.length === 0) return "";
  const first = monthName(months[0], lang);
  const last = monthName(months[months.length - 1], lang);
  return months.length === 1 ? first : `${first}–${last}`;
}

const decimal = (value: number, lang: Lang, digits = 2) =>
  value.toLocaleString(lang === "es" ? "es-CR" : "en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

/** Scores are 0..1 suitability values, not probabilities: "0.91 of 1" / "0,91 de 1", never "91%". */
export const scoreOf1 = (score: number, lang: Lang = "en") =>
  lang === "es" ? `${decimal(score, lang)} de 1` : `${decimal(score, lang)} of 1`;

export const signed = (value: number, lang: Lang = "en") =>
  `${value >= 0 ? "+" : "−"}${decimal(Math.abs(value), lang)}`;

export const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

// USDA texture classes as the soil map reports them, in Spanish.
const TEXTURE_ES: Record<string, string> = {
  clay: "arcilloso",
  "silty clay": "arcillo limoso",
  "sandy clay": "arcillo arenoso",
  "clay loam": "franco arcilloso",
  "silty clay loam": "franco arcillo limoso",
  "sandy clay loam": "franco arcillo arenoso",
  loam: "franco",
  "silt loam": "franco limoso",
  "sandy loam": "franco arenoso",
  silt: "limoso",
  "loamy sand": "arenoso franco",
  sand: "arenoso",
};

export const textureName = (texture: string, lang: Lang = "en") =>
  lang === "es" ? (TEXTURE_ES[texture] ?? texture) : texture;
