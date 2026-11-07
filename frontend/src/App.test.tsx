import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function mockFetch(res: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));
}

describe("App / HealthPage (component)", () => {
  beforeEach(() => window.history.pushState(null, "", "/health"));
  afterEach(() => vi.unstubAllGlobals());

  it("وقتی /health موفق است وضعیت سالم را نشان می‌دهد", async () => {
    mockFetch(
      new Response(JSON.stringify({ status: "UP", service: "s4-rsk" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<App />);
    expect(await screen.findByText(/بک‌اند در دسترس است/)).toBeInTheDocument();
    expect(screen.getByText(/"status": "UP"/)).toBeInTheDocument();
  });

  it("وقتی بک‌اند خطای Problem Details برمی‌گرداند آن را نمایش می‌دهد", async () => {
    mockFetch(
      new Response(
        JSON.stringify({
          type: "https://errors.labbank.example/service-unavailable",
          title: "Database dependency unavailable",
          status: 503,
          code: "SERVICE_UNAVAILABLE",
          detail: "PostgreSQL connection check failed.",
          correlation_id: "cid-42",
        }),
        { status: 503, headers: { "Content-Type": "application/problem+json" } },
      ),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database dependency unavailable");
    expect(screen.getByText("SERVICE_UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("cid-42")).toBeInTheDocument();
  });

  it("وقتی شبکه قطع است پیام خطای ساده نشان می‌دهد", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Failed to fetch")));
    render(<App />);
    expect(await screen.findByText(/Failed to fetch/)).toBeInTheDocument();
  });
});
