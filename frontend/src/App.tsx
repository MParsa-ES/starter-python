import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { ProblemDetails } from "./ProblemDetails";
import { readProblem, type ProblemDetailsBody } from "./problem";
import { RulesPage } from "./RulesPage";

// Read the backend address from the Vite environment configuration.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8084";

type HealthResponse = { status: string; service: string };
type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse; httpStatus: number; ms: number }
  | { kind: "problem"; problem: ProblemDetailsBody }
  | { kind: "error"; message: string };

function HealthPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const check = useCallback(async () => {
    setState({ kind: "loading" });
    const started = performance.now();
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const problem = await readProblem(res);
        if (problem) {
          setState({ kind: "problem", problem });
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as HealthResponse;
      setState({
        kind: "ok",
        data,
        httpStatus: res.status,
        ms: Math.round(performance.now() - started),
      });
    } catch (err) {
      setState({
        kind: "error",
        message:
          err instanceof Error
            ? err.message
            : "Unknown error (is the backend running and CORS configured?)",
      });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <main className="card" dir="ltr">
      <h1>LabBank · S4-RSK</h1>
      <p className="sub">Risk and fraud service — backend health</p>

      <div className="row">
        <span>Address</span>
        <code dir="ltr">GET {API_BASE_URL}/health</code>
      </div>

      {state.kind === "loading" && <p className="badge wait">Checking…</p>}

      {state.kind === "ok" && (
        <>
          <p className="badge ok">Backend is available ✔</p>
          <div className="row">
            <span>HTTP status</span>
            <code dir="ltr">{state.httpStatus}</code>
          </div>
          <div className="row">
            <span>Response time</span>
            <code dir="ltr">{state.ms} ms</code>
          </div>
          <pre dir="ltr">{JSON.stringify(state.data, null, 2)}</pre>
        </>
      )}

      {state.kind === "problem" && <ProblemDetails problem={state.problem} />}

      {state.kind === "error" && (
        <p className="badge err">Error: {state.message}</p>
      )}

      <button onClick={() => void check()}>Check again</button>
    </main>
  );
}

// Route the root path to the health page without a routing library.
export default function App() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/") {
    window.history.replaceState(null, "", "/health");
    return <HealthPage />;
  }
  if (path === "/health") return <HealthPage />;
  if (path === "/rules") return <RulesPage />;
  return (
    <main className="card" dir="ltr">
      <h1>404</h1>
      <p className="sub">This page does not exist. <a href="/health">Go to /health</a></p>
    </main>
  );
}
