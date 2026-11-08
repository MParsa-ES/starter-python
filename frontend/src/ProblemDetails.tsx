// کامپوننت نمایش خطای RFC 9457؛ نوع و تابع خواندن پاسخ در problem.ts است.
import type { ProblemDetailsBody } from "./problem";

export function ProblemDetails({ problem }: { problem: ProblemDetailsBody }) {
  return (
    <section role="alert" className="badge err" aria-label="problem-details">
      <h2>{problem.title}</h2>
      <div className="row">
        <span>وضعیت</span>
        <code dir="ltr">{problem.status}</code>
      </div>
      {problem.code && (
        <div className="row">
          <span>کد خطا</span>
          <code dir="ltr">{problem.code}</code>
        </div>
      )}
      {problem.detail && <p dir="ltr">{problem.detail}</p>}
      {problem.correlation_id && (
        <div className="row">
          <span>شناسه‌ی پیگیری</span>
          <code dir="ltr">{problem.correlation_id}</code>
        </div>
      )}
    </section>
  );
}
