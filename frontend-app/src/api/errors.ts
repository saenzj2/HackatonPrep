import type { Bilingual } from "../i18n";
import { ApiError, NETWORK_ERROR } from "./client";

export interface ErrorText {
  title: Bilingual;
  body: Bilingual;
  /** True when picking one of the demo fields is the way out (offer them). */
  offerDemoFields: boolean;
}

// One text per API error code (backend/docs/errors.md), in English and Spanish. Never show raw
// server messages.
const TEXTS: Record<string, ErrorText> = {
  cache_miss: {
    title: { en: "No data for this location yet", es: "Todavía no hay datos para este lugar" },
    body: {
      en: "This demo only has NASA and soil data preloaded for a few fields. Pick one of the demo fields below.",
      es: "Esta demostración solo tiene datos de la NASA y del suelo para algunos campos. Elija uno de los campos de demostración.",
    },
    offerDemoFields: true,
  },
  out_of_region: {
    title: { en: "This location is outside the pilot region", es: "Este lugar está fuera de la región piloto" },
    body: {
      en: "Choose a point inside the dashed box on the map, or pick a demo field.",
      es: "Elija un punto dentro del recuadro punteado del mapa, o un campo de demostración.",
    },
    offerDemoFields: true,
  },
  validation_failed: {
    title: { en: "Some values are not valid", es: "Algunos valores no son válidos" },
    body: { en: "Check what you entered and try again.", es: "Revise lo que escribió e intente de nuevo." },
    offerDemoFields: false,
  },
  unknown_crop: {
    title: { en: "A selected crop is not supported", es: "Uno de los cultivos elegidos no está disponible" },
    body: { en: "Choose crops from the list and try again.", es: "Elija cultivos de la lista e intente de nuevo." },
    offerDemoFields: false,
  },
  invalid_priorities: {
    title: { en: "Priorities need at least one value above zero", es: "Al menos una prioridad debe ser mayor que cero" },
    body: { en: "Move at least one priority slider and try again.", es: "Mueva al menos un control de prioridad e intente de nuevo." },
    offerDemoFields: false,
  },
  invalid_rotation: {
    title: { en: "Your current rotation is incomplete", es: "Su rotación actual está incompleta" },
    body: {
      en: "Choose one crop for each season, or leave every season empty.",
      es: "Elija un cultivo para cada época, o deje todas las épocas vacías.",
    },
    offerDemoFields: false,
  },
  source_unavailable: {
    title: { en: "Climate or soil data are temporarily unavailable", es: "Los datos de clima o suelo no están disponibles por ahora" },
    body: { en: "A data source did not answer. Try again in a moment.", es: "Una fuente de datos no respondió. Intente de nuevo en un momento." },
    offerDemoFields: false,
  },
  source_bad_data: {
    title: { en: "The data for this location could not be used", es: "No se pudieron usar los datos de este lugar" },
    body: {
      en: "A data source returned values we could not check. Try another field.",
      es: "Una fuente de datos devolvió valores que no pudimos verificar. Pruebe con otro campo.",
    },
    offerDemoFields: true,
  },
  [NETWORK_ERROR]: {
    title: { en: "We could not reach the server", es: "No pudimos conectar con el servidor" },
    body: { en: "Check your connection and try again.", es: "Revise su conexión e intente de nuevo." },
    offerDemoFields: false,
  },
};

const FALLBACK: ErrorText = {
  title: { en: "Something went wrong", es: "Algo salió mal" },
  body: {
    en: "Try again in a moment. If it keeps happening, tell the team.",
    es: "Intente de nuevo en un momento. Si sigue pasando, avísele al equipo.",
  },
  offerDemoFields: false,
};

export function errorText(error: unknown): ErrorText {
  if (error instanceof ApiError) return TEXTS[error.code] ?? FALLBACK;
  return FALLBACK;
}
