import { useState, type FormEvent } from "react";
import { api } from "./api/client";
import type { components } from "./api/schema";
import { ProblemDetails } from "./ProblemDetails";
import type { ProblemDetailsBody } from "./problem";

type Explanation = components["schemas"]["DecisionExplanation"];

export function ExplanationsPage() {
  const [token, setToken] = useState("");
  const [decisionId, setDecisionId] = useState("");
  const [loadedId, setLoadedId] = useState("");
  const [items, setItems] = useState<Explanation[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [problem, setProblem] = useState<ProblemDetailsBody | null>(null);
  const [message, setMessage] = useState("");

  async function load(id: string, next?: string) {
    setProblem(null); setMessage("");
    try {
      const { data, error, response } = await api.GET("/risk-assessments/{decision_id}/reasons", {
        headers: { Authorization: `Bearer ${token}` },
        params: { path: { decision_id: id }, query: { limit: 50, ...(next ? { cursor: next } : {}) } },
      });
      if (error || !data) {
        const body = error as Partial<ProblemDetailsBody> | undefined;
        setProblem({ title: body?.title ?? "Could not retrieve reasons", status: response.status, ...body });
        return;
      }
      setLoadedId(id); setItems(previous => next ? [...(previous ?? []), ...data.items] : data.items);
      setCursor(data.next_cursor);
    } catch { setMessage("Could not connect to the server."); }
  }

  function submit(event: FormEvent) {
    event.preventDefault(); setItems(null); setCursor(null);
    void load(decisionId.trim());
  }

  return <main className="card rules-card" dir="ltr">
    <h1>Risk decision reasons</h1><p className="sub">View recorded reasons for a decision ID</p>
    <p><a href="/rules">Rule management</a> · <a href="/health">Service health</a></p>
    <form onSubmit={submit}>
      <label>Access token <input type="password" autoComplete="off" value={token} onChange={event => { setToken(event.target.value); setItems(null); setCursor(null); }} /></label>
      <label>Decision ID <input dir="ltr" required value={decisionId} onChange={event => setDecisionId(event.target.value)} /></label>
      <button type="submit" disabled={!token}>Load reasons</button>
    </form>
    {problem && <ProblemDetails problem={problem} />}{message && <p role="status">{message}</p>}
    {items && items.length === 0 && <p>No reasons have been recorded.</p>}
    {items?.map((item, index) => <section className="rule-item" key={`${item.code}-${index}`}>
      <h2 dir="ltr">{item.code}</h2><p dir="ltr">{item.message}</p>
      {item.rule_id && <p>Rule ID: <code dir="ltr">{item.rule_id}</code></p>}
      {item.rule_revision != null && <p>Rule revision: {item.rule_revision}</p>}
    </section>)}
    {cursor && <button type="button" onClick={() => void load(loadedId, cursor)}>More reasons</button>}
  </main>;
}
