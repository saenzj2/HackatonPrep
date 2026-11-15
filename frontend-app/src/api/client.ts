// One place for every API call. URLs are relative: same origin in production, Vite proxy in dev.
// Types mirror backend/docs/api-contract.yaml; keep them in sync when the contract changes.

/** Farmer-facing text in both languages. The UI shows `en`. */
export interface Text {
  en: string;
  es: string;
}

export interface Region {
  name: string;
  bbox?: number[];
}

export interface HealthResponse {
  status: string;
  version: string;
  data_mode: string;
  region: Region;
}

export interface Crop {
  id: string;
  name: string;
  family: string;
  is_legume: boolean;
  is_cover_crop: boolean;
  cycle_days: number;
}

export interface CropsResponse {
  crops: Crop[];
}

export interface Season {
  name: string;
  months: number[];
}

export interface MonthlyClimate {
  month: number;
  temperature_c: number;
  rainfall_mm: number;
  temperature_max_c: number;
  temperature_min_c: number;
}

export interface SeasonSummary extends Season {
  temperature_c: number;
  rainfall_mm_per_month: number;
  temperature_max_c: number;
  temperature_min_c: number;
}

export interface Soil {
  ph?: number | null;
  moisture_m3m3?: number | null;
  texture_class?: string | null;
}

export interface DataSources {
  climate: string;
  soil: string;
  crops: string;
}

export interface Conditions {
  location: { lat: number; lon: number };
  monthly: MonthlyClimate[];
  seasons: SeasonSummary[];
  soil: Soil;
  data_sources: DataSources;
}

export interface Priorities {
  water: number;
  soil: number;
  climate: number;
}

export interface RotationStep {
  season: string;
  months: number[];
  crop_id: string;
  crop_name: string;
  score: number;
}

export interface Rotation {
  rank: number;
  sequence: RotationStep[];
  score: number;
  viable: boolean;
  breakdown: { climate: number | null; water: number | null; soil: number | null };
  explanation: Text;
  is_current: boolean;
  score_delta_vs_current: number | null;
  benefits: Text[];
  risks: Text[];
  data_gaps: Text[];
  evidence: Text[];
}

export interface RecommendationRequest {
  lat: number;
  lon: number;
  crops?: string[];
  priorities?: Priorities;
  top_n?: number;
  current_rotation?: string[];
}

export interface RecommendationResponse {
  location: { lat: number; lon: number };
  region: Region;
  priorities: Priorities;
  conditions: Conditions;
  rotations: Rotation[];
  current_rotation: Rotation | null;
  method_version: string;
  generated_at: string;
}

/** Envelope of every API error (backend/docs/errors.md). */
interface ErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

/** Show users a text chosen from `code` (api/errors.ts); `message` is for logs. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: Record<string, unknown>;
  readonly requestId?: string;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

/** Code used when the server cannot be reached or answers without the error envelope. */
export const NETWORK_ERROR = "network_error";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, { code: NETWORK_ERROR, message: `Cannot reach ${path}` });
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const body = (data as { error?: ErrorBody } | null)?.error;
    throw new ApiError(
      response.status,
      body ?? { code: NETWORK_ERROR, message: `HTTP ${response.status} from ${path}` },
    );
  }
  return data as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  crops: () => request<CropsResponse>("/crops"),
  conditions: (lat: number, lon: number) =>
    request<Conditions>(`/conditions?${new URLSearchParams({ lat: String(lat), lon: String(lon) })}`),
  recommendations: (body: RecommendationRequest) =>
    request<RecommendationResponse>("/recommendations", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
