const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const monthName = (month: number) => MONTHS[month - 1] ?? String(month);

/** "May–Aug" for a season's consecutive months. */
export function monthSpan(months: number[]): string {
  if (months.length === 0) return "";
  const first = monthName(months[0]);
  const last = monthName(months[months.length - 1]);
  return months.length === 1 ? first : `${first}–${last}`;
}

/** Scores are 0..1 suitability values, not probabilities: "0.91 of 1", never "91%". */
export const scoreOf1 = (score: number) => `${score.toFixed(2)} of 1`;

export const signed = (value: number) => `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;

export const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
