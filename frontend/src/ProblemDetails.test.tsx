import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProblemDetails } from "./ProblemDetails";
import { readProblem } from "./problem";

describe("ProblemDetails (component)", () => {
  it("همه‌ی فیلدهای RFC 9457 را نمایش می‌دهد", () => {
    render(
      <ProblemDetails
        problem={{
          title: "Database dependency unavailable",
          status: 503,
          code: "SERVICE_UNAVAILABLE",
          detail: "PostgreSQL connection check failed.",
          correlation_id: "abc-123",
        }}
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Database dependency unavailable")).toBeInTheDocument();
    expect(screen.getByText("503")).toBeInTheDocument();
    expect(screen.getByText("SERVICE_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("abc-123")).toBeInTheDocument();
  });

  it("فیلدهای اختیاری نباشند، خطا نمی‌دهد و فقط عنوان و وضعیت را نشان می‌دهد", () => {
    render(<ProblemDetails problem={{ title: "Resource not found", status: 404 }} />);
    expect(screen.getByText("Resource not found")).toBeInTheDocument();
    expect(screen.queryByText("کد خطا")).not.toBeInTheDocument();
  });
});

describe("readProblem", () => {
  it("بدنه‌ی problem+json را می‌خواند", async () => {
    const res = new Response(JSON.stringify({ title: "Forbidden", status: 403 }), {
      status: 403,
      headers: { "Content-Type": "application/problem+json" },
    });
    expect(await readProblem(res)).toMatchObject({ title: "Forbidden", status: 403 });
  });

  it("برای پاسخ غیر problem+json مقدار null برمی‌گرداند", async () => {
    const res = new Response("oops", { status: 500, headers: { "Content-Type": "text/plain" } });
    expect(await readProblem(res)).toBeNull();
  });
});
