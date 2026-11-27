import { useRef, useState, type FormEvent } from "react";
import { api } from "./api/client";
import type { components } from "./api/schema";
import { ProblemDetails } from "./ProblemDetails";
import type { ProblemDetailsBody } from "./problem";

type Rule = components["schemas"]["RiskRule"];
type Revision = components["schemas"]["RuleRevision"];

function unsafeNumbers(value: unknown): boolean {
  if (typeof value === "number") return !Number.isSafeInteger(value);
  if (value && typeof value === "object") return Object.values(value).some(unsafeNumbers);
  return false;
}

export function RulesPage() {
  const [token, setToken] = useState("");
  const [rules, setRules] = useState<Rule[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<Revision[]>([]);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [historyRule, setHistoryRule] = useState<string | null>(null);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [name, setName] = useState("");
  const [type, setType] = useState<Rule["type"]>("AMOUNT_LIMIT");
  const [parameters, setParameters] = useState('{"max_amount": 100}');
  const [enabled, setEnabled] = useState(false);
  const [effectiveAt, setEffectiveAt] = useState("");
  const [problem, setProblem] = useState<ProblemDetailsBody | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const pendingCreate = useRef<{ body: string; key: string } | null>(null);
  const headers = { Authorization: `Bearer ${token}` };

  function fail(error: unknown, status: number) {
    const body = error as Partial<ProblemDetailsBody> | undefined;
    setProblem({ title: body?.title ?? "Server communication error", status, ...body });
  }

  async function loadRules(next?: string) {
    setProblem(null);
    try {
      const { data, error, response } = await api.GET("/risk-rules", {
        headers, params: { query: { limit: 50, ...(next ? { cursor: next } : {}) } },
      });
      if (error || !data) return fail(error, response.status);
      setRules(previous => next ? [...previous, ...data.items] : data.items);
      setCursor(data.next_cursor);
    } catch { setMessage("Could not connect to the server."); }
  }

  async function loadHistory(ruleId: string, next?: string) {
    setProblem(null);
    try {
      const { data, error, response } = await api.GET("/risk-rules/{rule_id}/audit", {
        headers, params: { path: { rule_id: ruleId }, query: { limit: 50, ...(next ? { cursor: next } : {}) } },
      });
      if (error || !data) return fail(error, response.status);
      setHistoryRule(ruleId);
      setHistory(previous => next ? [...previous, ...data.items] : data.items);
      setHistoryCursor(data.next_cursor);
    } catch { setMessage("Could not connect to the server."); }
  }

  function edit(rule: Rule) {
    if (unsafeNumbers(rule.parameters)) {
      setMessage("Numbers outside the browser's safe integer range cannot be edited here; use the API.");
      return;
    }
    setEditing(rule); setName(rule.name); setType(rule.type);
    setParameters(JSON.stringify(rule.parameters, null, 2)); setEnabled(rule.enabled);
    setEffectiveAt(rule.effective_at); setMessage("");
  }

  function reset() {
    setEditing(null); setName(""); setType("AMOUNT_LIMIT"); setParameters('{"max_amount": 100}');
    setEnabled(false); setEffectiveAt("");
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setProblem(null); setMessage("");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(parameters);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" || unsafeNumbers(parsed)) throw new Error();
      if (effectiveAt && (!/(Z|[+-]\d{2}:\d{2})$/i.test(effectiveAt) || Number.isNaN(Date.parse(effectiveAt)))) throw new Error();
    } catch { setMessage("Parameters must be a JSON object with safe integers and a valid time."); return; }
    const fields = { name, parameters: parsed, enabled, ...(effectiveAt ? { effective_at: new Date(effectiveAt).toISOString() } : {}) };
    setBusy(true);
    try {
      const createBody = { ...fields, type };
      const signature = JSON.stringify(createBody);
      if (!editing && pendingCreate.current?.body !== signature) {
        pendingCreate.current = { body: signature, key: crypto.randomUUID() };
      }
      const result = editing
        ? await api.PATCH("/risk-rules/{rule_id}", { headers, params: { path: { rule_id: editing.id } }, body: { ...fields, expected_revision: editing.revision } })
        : await api.POST("/risk-rules", { headers: { ...headers, "Idempotency-Key": pendingCreate.current!.key }, body: createBody });
      if (result.error || !result.data) return fail(result.error, result.response.status);
      pendingCreate.current = null;
      reset(); setMessage("Rule saved."); await loadRules();
    } catch { setMessage("Could not connect to the server; check the rule list before retrying."); }
    finally { setBusy(false); }
  }

  return <main className="card rules-card" dir="ltr">
    <h1>Risk rule management</h1><p className="sub">Create, edit, and review rule history</p>
    <p><a href="/health">Service health</a> · <a href="/explanations">Decision reasons</a></p>
    <label>Manager token <input type="password" value={token} onChange={event => { setToken(event.target.value); setRules([]); setCursor(null); setHistory([]); setHistoryRule(null); pendingCreate.current = null; reset(); }} autoComplete="off" /></label>
    <button type="button" disabled={!token} onClick={() => void loadRules()}>Load rules</button>
    {problem && <ProblemDetails problem={problem} />}{message && <p role="status">{message}</p>}
    <form onSubmit={event => void save(event)}>
      <h2>{editing ? `Edit revision ${editing.revision}` : "New rule"}</h2>
      <label>Name <input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
      <label>Type <select disabled={!!editing} value={type} onChange={event => setType(event.target.value as Rule["type"])}><option value="AMOUNT_LIMIT">Amount limit</option><option value="BLOCKLIST">Blocklist</option></select></label>
      <label>Parameters (JSON) <textarea value={parameters} onChange={event => setParameters(event.target.value)} /></label>
      <label>Effective time (ISO 8601 with time zone) <input dir="ltr" placeholder="2026-11-26T12:00:00Z" value={effectiveAt} onChange={event => setEffectiveAt(event.target.value)} /></label>
      <label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} /> Enabled</label>
      <button disabled={!token || busy} type="submit">Save</button>{editing && <button type="button" onClick={reset}>Cancel</button>}
    </form>
    <h2>Rules</h2>{rules.map(rule => <section className="rule-item" key={rule.id}>
      <h2>{rule.name}</h2><p>{rule.type} · Revision {rule.revision} · {rule.enabled ? "Enabled" : "Disabled"}</p>
      <p dir="ltr">{rule.effective_at}</p><pre>{JSON.stringify(rule.parameters, null, 2)}</pre>
      <button type="button" onClick={() => edit(rule)}>Edit</button><button type="button" onClick={() => void loadHistory(rule.id)}>History</button>
      {historyRule === rule.id && <div><h3>History</h3>{history.map(item => <section key={item.revision}><p>Revision {item.revision} · {item.actor} · {item.changed_at}</p><pre>{JSON.stringify({ before: item.before, after: item.after }, null, 2)}</pre></section>)}{historyCursor && <button type="button" onClick={() => void loadHistory(rule.id, historyCursor)}>More history</button>}</div>}
    </section>)}{cursor && <button type="button" onClick={() => void loadRules(cursor)}>More rules</button>}
  </main>;
}
