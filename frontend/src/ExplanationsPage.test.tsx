import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api/client";
import { ExplanationsPage } from "./ExplanationsPage";

vi.mock("./api/client", () => ({ api: { GET: vi.fn() } }));

describe("decision explanations", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows recorded reasons and follows the next cursor", async () => {
    vi.mocked(api.GET)
      .mockResolvedValueOnce({ data: { items: [{ code: "MATCH", message: "Rule matched", rule_id: "rule-id", rule_revision: 2 }], next_cursor: "next" }, response: new Response() } as never)
      .mockResolvedValueOnce({ data: { items: [{ code: "SECOND", message: "Second reason", rule_id: null, rule_revision: null }], next_cursor: null }, response: new Response() } as never);
    render(<ExplanationsPage />);
    fireEvent.change(screen.getByLabelText("توکن دسترسی"), { target: { value: "token" } });
    fireEvent.change(screen.getByLabelText("شناسهٔ تصمیم"), { target: { value: "decision-id" } });
    fireEvent.click(screen.getByText("دریافت دلایل"));
    expect(await screen.findByText("Rule matched")).toBeInTheDocument();
    expect(screen.getByText(/نسخهٔ قانون: 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("دلایل بیشتر"));
    expect(await screen.findByText("Second reason")).toBeInTheDocument();
    await waitFor(() => expect(api.GET).toHaveBeenLastCalledWith("/risk-assessments/{decision_id}/reasons", expect.objectContaining({
      params: { path: { decision_id: "decision-id" }, query: { limit: 50, cursor: "next" } },
    })));
  });

  it("displays an API error", async () => {
    vi.mocked(api.GET).mockResolvedValue({ error: { title: "Not found", status: 404 }, response: new Response(null, { status: 404 }) } as never);
    render(<ExplanationsPage />);
    fireEvent.change(screen.getByLabelText("توکن دسترسی"), { target: { value: "token" } });
    fireEvent.change(screen.getByLabelText("شناسهٔ تصمیم"), { target: { value: "missing" } });
    fireEvent.click(screen.getByText("دریافت دلایل"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Not found");
  });
});
