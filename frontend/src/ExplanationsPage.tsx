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
        setProblem({ title: body?.title ?? "خطا در دریافت دلایل", status: response.status, ...body });
        return;
      }
      setLoadedId(id); setItems(previous => next ? [...(previous ?? []), ...data.items] : data.items);
      setCursor(data.next_cursor);
    } catch { setMessage("ارتباط با سرور برقرار نشد."); }
  }

  function submit(event: FormEvent) {
    event.preventDefault(); setItems(null); setCursor(null);
    void load(decisionId.trim());
  }

  return <main className="card rules-card" dir="rtl">
    <h1>دلایل تصمیم ریسک</h1><p className="sub">مشاهدهٔ دلایل ثبت‌شده برای شناسهٔ تصمیم</p>
    <p><a href="/rules">مدیریت قوانین</a> · <a href="/health">وضعیت سرویس</a></p>
    <form onSubmit={submit}>
      <label>توکن دسترسی <input type="password" autoComplete="off" value={token} onChange={event => { setToken(event.target.value); setItems(null); setCursor(null); }} /></label>
      <label>شناسهٔ تصمیم <input dir="ltr" required value={decisionId} onChange={event => setDecisionId(event.target.value)} /></label>
      <button type="submit" disabled={!token}>دریافت دلایل</button>
    </form>
    {problem && <ProblemDetails problem={problem} />}{message && <p role="status">{message}</p>}
    {items && items.length === 0 && <p>دلیلی ثبت نشده است.</p>}
    {items?.map((item, index) => <section className="rule-item" key={`${item.code}-${index}`}>
      <h2 dir="ltr">{item.code}</h2><p dir="ltr">{item.message}</p>
      {item.rule_id && <p>شناسهٔ قانون: <code dir="ltr">{item.rule_id}</code></p>}
      {item.rule_revision != null && <p>نسخهٔ قانون: {item.rule_revision}</p>}
    </section>)}
    {cursor && <button type="button" onClick={() => void load(loadedId, cursor)}>دلایل بیشتر</button>}
  </main>;
}
