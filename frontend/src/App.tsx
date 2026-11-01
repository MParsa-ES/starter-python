import { useCallback, useEffect, useState } from "react";
import "./App.css";

// آدرس بک‌اند از متغیر محیطی Vite خوانده می‌شود (فایل .env.local)؛ در کد ثابت نیست.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8084";

type HealthResponse = { status: string; service: string };
type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse; httpStatus: number; ms: number }
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
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
            : "خطای ناشناخته (بک‌اند بالا است؟ CORS؟)",
      });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <main className="card" dir="rtl">
      <h1>LabBank · S4-RSK</h1>
      <p className="sub">سرویس ریسک و تقلب — بررسی سلامت بک‌اند</p>

      <div className="row">
        <span>آدرس</span>
        <code dir="ltr">GET {API_BASE_URL}/health</code>
      </div>

      {state.kind === "loading" && <p className="badge wait">در حال بررسی…</p>}

      {state.kind === "ok" && (
        <>
          <p className="badge ok">بک‌اند در دسترس است ✔</p>
          <div className="row">
            <span>وضعیت HTTP</span>
            <code dir="ltr">{state.httpStatus}</code>
          </div>
          <div className="row">
            <span>زمان پاسخ</span>
            <code dir="ltr">{state.ms} ms</code>
          </div>
          <pre dir="ltr">{JSON.stringify(state.data, null, 2)}</pre>
        </>
      )}

      {state.kind === "error" && (
        <p className="badge err">خطا: {state.message}</p>
      )}

      <button onClick={() => void check()}>بررسی دوباره</button>
    </main>
  );
}

// مسیریابی ساده بدون کتابخانه: صفحه‌ی اصلی روی /health است و "/" به آن منتقل می‌شود.
export default function App() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path === "/") {
    window.history.replaceState(null, "", "/health");
    return <HealthPage />;
  }
  if (path === "/health") return <HealthPage />;
  return (
    <main className="card" dir="rtl">
      <h1>۴۰۴</h1>
      <p className="sub">این آدرس وجود ندارد. <a href="/health">رفتن به /health</a></p>
    </main>
  );
}
