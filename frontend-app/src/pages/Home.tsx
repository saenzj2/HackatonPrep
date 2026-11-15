import { useEffect, useState } from "react";
import { api, ApiError, type HealthResponse } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthResponse }
  | { kind: "error"; code: string };

// Placeholder start page: proves the build, the /app/ base and the API connection work.
export function Home() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    api
      .health()
      .then((health) => active && setState({ kind: "ready", health }))
      .catch((error: unknown) => {
        const code = error instanceof ApiError ? error.code : "unknown";
        if (active) setState({ kind: "error", code });
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h1>Compare crop rotation options</h1>
      <p className="muted">
        NASA Earth observation, soil and crop data to choose more resilient rotations.
      </p>
      <p role="status" className="status">
        {state.kind === "loading" && "Connecting to the API…"}
        {state.kind === "ready" &&
          `API connected · region ${state.health.region.name} · data ${state.health.data_mode}`}
        {state.kind === "error" && "We could not reach the server. Please try again in a moment."}
      </p>
    </section>
  );
}
