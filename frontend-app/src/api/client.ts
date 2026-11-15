// One place for every API call. URLs are relative: same origin in production, Vite proxy in dev.
// Types mirror backend/docs/api-contract.yaml; keep them in sync when the contract changes.

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

/** Envelope of every API error (backend/docs/errors.md). */
interface ErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}

/** Show users a text chosen from `code`, never `message` (English, meant for developers). */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId?: string;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.status = status;
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
};
