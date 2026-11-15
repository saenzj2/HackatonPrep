import { ApiError, NETWORK_ERROR } from "./client";

export interface ErrorText {
  title: string;
  body: string;
  /** True when picking one of the demo fields is the way out (offer them). */
  offerDemoFields: boolean;
}

// One text per API error code (backend/docs/errors.md). Never show raw server messages.
const TEXTS: Record<string, ErrorText> = {
  cache_miss: {
    title: "No data for this location yet",
    body: "This demo only has NASA and soil data preloaded for a few fields. Pick one of the demo fields below.",
    offerDemoFields: true,
  },
  out_of_region: {
    title: "This location is outside the pilot region",
    body: "The pilot covers Costa Rica. Enter a point inside it, or pick a demo field.",
    offerDemoFields: true,
  },
  validation_failed: {
    title: "Some values are not valid",
    body: "Check the highlighted fields and try again.",
    offerDemoFields: false,
  },
  unknown_crop: {
    title: "A selected crop is not supported",
    body: "Choose crops from the list and try again.",
    offerDemoFields: false,
  },
  invalid_priorities: {
    title: "Priorities need at least one value above zero",
    body: "Move at least one priority slider and try again.",
    offerDemoFields: false,
  },
  invalid_rotation: {
    title: "Your current rotation is incomplete",
    body: "Choose one crop for each season, or leave every season empty.",
    offerDemoFields: false,
  },
  source_unavailable: {
    title: "Climate or soil data are temporarily unavailable",
    body: "A data source did not answer. Try again in a moment.",
    offerDemoFields: false,
  },
  source_bad_data: {
    title: "The data for this location could not be used",
    body: "A data source returned values we could not check. Try another field.",
    offerDemoFields: true,
  },
  [NETWORK_ERROR]: {
    title: "We could not reach the server",
    body: "Check your connection and try again.",
    offerDemoFields: false,
  },
};

const FALLBACK: ErrorText = {
  title: "Something went wrong",
  body: "Try again in a moment. If it keeps happening, tell the team.",
  offerDemoFields: false,
};

export function errorText(error: unknown): ErrorText {
  if (error instanceof ApiError) return TEXTS[error.code] ?? FALLBACK;
  return FALLBACK;
}
