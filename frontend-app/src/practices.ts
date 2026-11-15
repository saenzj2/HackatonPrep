// Picks regenerative practice cards for a field and rotation.
// The cards and their rules live in backend/data/regenerative_practices.json (bundled at build time,
// like the glossary). Each card lists rules on data-model attributes; this file evaluates ONLY the
// rules whose data the app has today, and says which ones matched. Rules that need a soil test,
// slope, extreme-rain days or dry spells are skipped until that data reaches the front end.
// Thresholds come from the JSON (team starting values that need agronomic review).
// Every sentence built here is returned in English and Spanish ({ en, es }).
import data from "../../backend/data/regenerative_practices.json";
import type { CropDetails, Season, SoilProfile } from "./api/client";
import { monthName, textureName } from "./format";
import type { Bilingual } from "./i18n";

interface Rule {
  attribute: string;
  operator: string;
  value: unknown;
}

type Lists = { en: string[]; es?: string[] };

export interface PracticeCard {
  practice_id: string;
  name: Bilingual;
  summary: Bilingual;
  how_to_start: Lists;
  benefits: Lists;
  cautions_local_review: Lists;
  evidence_note: Bilingual;
  applies_when: { rules: Rule[] };
}

export interface MatchedPractice {
  card: PracticeCard;
  reasons: Bilingual[];
}

const CARDS = (data as { practices: PracticeCard[] }).practices;
/** "Low organic matter" threshold (%) as the cards define it (soil_test.organic_matter_pct rule). */
export const LOW_ORGANIC_MATTER_PCT = Number(
  CARDS.flatMap((c) => c.applies_when.rules).find((r) => r.attribute === "soil_test.organic_matter_pct")
    ?.value ?? Number.NaN,
);

export const PRACTICES_DISCLAIMER = (data as { meta: { disclaimer: Bilingual } }).meta.disclaimer;

/**
 * Organic matter from organic carbon with the conventional van Bemmelen factor (1.724). An
 * approximation: the real ratio varies by soil, so results are labelled as estimates.
 */
export const organicMatterPct = (organicCarbonGKg: number) => (organicCarbonGKg * 1.724) / 10;

const n1 = (v: number) => ({ en: v.toFixed(1), es: v.toFixed(1).replace(".", ",") });
const cropEs = (c: CropDetails) => c.name_es ?? c.name;
const joinAnd = (names: string[], and: string) =>
  names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} ${and} ${names[names.length - 1]}`;

export interface FieldFacts {
  /** Topsoil (0 cm) organic carbon from the soil map, or null. */
  organicCarbonGKg: number | null;
  textureClass: string | null;
  /** Months outside every growing season (the dry season is fallow in v0). */
  bareMonths: number[];
}

export function fieldFacts(soil: SoilProfile | null, seasons: Season[]): FieldFacts {
  const top = soil?.layers.find((l) => l.depth_cm === 0) ?? soil?.layers[0];
  const grown = new Set(seasons.flatMap((s) => s.months));
  const bare = Array.from({ length: 12 }, (_, i) => i + 1).filter((m) => !grown.has(m));
  // Start the list at the first bare month after a grown one, so Dec–Apr reads Dec, Jan, …, Apr.
  const start = bare.findIndex((m) => grown.has(m === 1 ? 12 : m - 1));
  return {
    organicCarbonGKg: top?.organic_carbon_g_kg ?? null,
    textureClass: top?.texture_class ?? null,
    bareMonths: start > 0 ? [...bare.slice(start), ...bare.slice(0, start)] : bare,
  };
}

/** One crop id per season, in order; transitions are cyclic (the rotation repeats every year). */
function rotationFacts(ids: string[], crops: Map<string, CropDetails>) {
  const list = ids.map((id) => crops.get(id)).filter((c): c is CropDetails => Boolean(c));
  const sameFamily = list.some((c, i) => list.length > 1 && c.family === list[(i + 1) % list.length].family);
  return {
    list,
    distinct: new Set(ids).size,
    hasLegume: list.some((c) => c.is_legume),
    sameFamilyConsecutive: sameFamily,
  };
}

/**
 * Cards whose evaluable rules match, most reasons first (max 3). `current` is the farmer's rotation
 * (the JSON's "existing rotation" rules); `recommended` is the rotation the app suggests.
 */
export function matchPractices(opts: {
  facts: FieldFacts;
  recommended: string[];
  current: string[] | null;
  crops: Map<string, CropDetails>;
}): MatchedPractice[] {
  const { facts, crops } = opts;
  const rec = rotationFacts(opts.recommended, crops);
  const cur = opts.current ? rotationFacts(opts.current, crops) : null;
  const om = facts.organicCarbonGKg != null ? organicMatterPct(facts.organicCarbonGKg) : null;
  const first = facts.bareMonths[0];
  const last = facts.bareMonths[facts.bareMonths.length - 1];
  const bare: Bilingual | null =
    facts.bareMonths.length > 0
      ? {
          en: `the field has no crop from ${monthName(first, "en")} to ${monthName(last, "en")} (dry season)`,
          es: `el campo queda sin cultivo de ${monthName(first, "es")} a ${monthName(last, "es")} (época seca)`,
        }
      : null;

  const check = (rule: Rule): Bilingual | null => {
    switch (rule.attribute) {
      case "field_indicator_monthly.bare_field":
        return bare;
      case "soil_test.organic_matter_pct":
        return om != null && om < Number(rule.value)
          ? {
              en: `the soil map suggests about ${n1(om).en}% organic matter, below ${rule.value}%`,
              es: `el mapa de suelos indica cerca de ${n1(om).es} % de materia orgánica, menos de ${rule.value} %`,
            }
          : null;
      case "soil_test.texture_class": {
        const sandy = Array.isArray(rule.value) && facts.textureClass && rule.value.includes(facts.textureClass);
        return sandy && facts.textureClass
          ? {
              en: `the soil map shows ${facts.textureClass}, which holds little water`,
              es: `el mapa de suelos muestra un suelo ${textureName(facts.textureClass, "es")}, que retiene poca agua`,
            }
          : null;
      }
      case "crop.mycorrhizal_affinity": {
        const dependent = rec.list.filter((c) => c.mycorrhizal_affinity?.level === rule.value);
        if (!dependent.length) return null;
        const many = dependent.length > 1;
        return {
          en: `${joinAnd(dependent.map((c) => c.name), "and")} ${many ? "rely" : "relies"} on soil fungi`,
          es: `${joinAnd(dependent.map(cropEs), "y")} ${many ? "dependen" : "depende"} de los hongos del suelo`,
        };
      }
      case "rotation.has_nitrogen_fixing_crop":
        return cur && !cur.hasLegume
          ? { en: "what you grow now has no legume to add nitrogen", es: "lo que siembra hoy no tiene una leguminosa que aporte nitrógeno" }
          : null;
      case "rotation.same_family_consecutive":
        return cur?.sameFamilyConsecutive
          ? { en: "what you grow now repeats the same plant family", es: "lo que siembra hoy repite la misma familia de plantas" }
          : null;
      case "rotation.distinct_crops":
        return cur && cur.distinct < Number(rule.value)
          ? {
              en: `what you grow now has ${cur.distinct === 1 ? "a single crop" : `only ${cur.distinct} crops`}; this practice aims for at least ${rule.value}`,
              es: `lo que siembra hoy tiene ${cur.distinct === 1 ? "un solo cultivo" : `solo ${cur.distinct} cultivos`}; esta práctica busca al menos ${rule.value}`,
            }
          : null;
      default:
        return null; // needs data the app does not have yet (soil test, slope, rain extremes, dry spells)
    }
  };

  return CARDS.map((card) => {
    const seen = new Set<string>();
    const reasons = card.applies_when.rules
      .map(check)
      .filter((r): r is Bilingual => r !== null && !seen.has(r.en) && Boolean(seen.add(r.en)));
    return { card, reasons };
  })
    .filter((m) => m.reasons.length > 0)
    .sort((a, b) => b.reasons.length - a.reasons.length)
    .slice(0, 3);
}

/** One plain sentence on organic carbon and nitrogen for the recommended rotation. */
export function nitrogenInsight(facts: FieldFacts, recommended: string[], crops: Map<string, CropDetails>): Bilingual {
  const rec = rotationFacts(recommended, crops);
  const legume = rec.list.find((c) => c.is_legume);
  const heavy = rec.list.find((c) => c.nitrogen_demand?.level === "high");
  const en: string[] = [];
  const es: string[] = [];
  if (facts.organicCarbonGKg != null) {
    const om = organicMatterPct(facts.organicCarbonGKg);
    const carbon = facts.organicCarbonGKg.toFixed(0);
    const known = Number.isFinite(LOW_ORGANIC_MATTER_PCT);
    const low = om < LOW_ORGANIC_MATTER_PCT;
    en.push(
      `The soil map shows ${carbon} g/kg of organic carbon in the topsoil (about ${n1(om).en}% organic matter${known ? `, ${low ? "low" : "not low"}` : ""}).`,
    );
    es.push(
      `El mapa de suelos muestra ${carbon} g/kg de carbono orgánico en la capa superficial (cerca de ${n1(om).es} % de materia orgánica${known ? `, ${low ? "baja" : "no es baja"}` : ""}).`,
    );
  }
  if (legume) {
    const helps = heavy && heavy !== legume;
    en.push(
      `${legume.name} is a legume: it takes part of its nitrogen from the air${helps ? `, which helps the ${heavy.name.toLowerCase()} that follows it` : ""}.`,
    );
    es.push(
      `${cropEs(legume)} es una leguminosa: toma parte de su nitrógeno del aire${helps ? `, lo que ayuda al ${cropEs(heavy).toLowerCase()} que sigue` : ""}.`,
    );
  } else {
    en.push("This rotation has no legume, so all its nitrogen comes from the soil and fertilizer; adding a bean or cowpea season would help.");
    es.push("Esta rotación no tiene leguminosas, así que todo su nitrógeno sale del suelo y del abono; sumar una época de frijol o caupí ayudaría.");
  }
  return { en: en.join(" "), es: es.join(" ") };
}
