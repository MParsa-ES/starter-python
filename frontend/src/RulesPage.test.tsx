import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RulesPage } from "./RulesPage";
import { api } from "./api/client";

vi.mock("./api/client", () => ({ api: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn() } }));

const rule = { id: "rule-1", name: "Limit", type: "AMOUNT_LIMIT", parameters: { max_amount: 100 }, enabled: true, effective_at: "2026-01-01T00:00:00Z", revision: 1, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };

describe("rule management", () => {
  beforeEach(() => vi.resetAllMocks());

  it("loads rules and updates the selected revision", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: { items: [rule], next_cursor: null }, response: new Response() } as never);
    vi.mocked(api.PATCH).mockResolvedValue({ data: { ...rule, revision: 2 }, response: new Response() } as never);
    render(<RulesPage />);
    fireEvent.change(screen.getByLabelText("توکن مدیر"), { target: { value: "token" } });
    fireEvent.click(screen.getByText("دریافت قوانین"));
    fireEvent.click(await screen.findByText("ویرایش"));
    fireEvent.change(screen.getByLabelText("نام"), { target: { value: "Updated" } });
    fireEvent.click(screen.getByText("ذخیره"));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledWith("/risk-rules/{rule_id}", expect.objectContaining({
      body: expect.objectContaining({ name: "Updated", expected_revision: 1 }),
      headers: { Authorization: "Bearer token" },
    })));
    expect(await screen.findByText("قانون ذخیره شد.")).toBeInTheDocument();
  });

  it("rejects invalid JSON without submitting", () => {
    render(<RulesPage />);
    fireEvent.change(screen.getByLabelText("توکن مدیر"), { target: { value: "token" } });
    fireEvent.change(screen.getByLabelText("نام"), { target: { value: "Limit" } });
    fireEvent.change(screen.getByLabelText("پارامترها (JSON)"), { target: { value: "[]" } });
    fireEvent.click(screen.getByText("ذخیره"));
    expect(screen.getByRole("status")).toHaveTextContent("JSON");
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("shows server authorization errors", async () => {
    vi.mocked(api.GET).mockResolvedValue({ error: { title: "Forbidden", status: 403 }, response: new Response(null, { status: 403 }) } as never);
    render(<RulesPage />);
    fireEvent.change(screen.getByLabelText("توکن مدیر"), { target: { value: "token" } });
    fireEvent.click(screen.getByText("دریافت قوانین"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
  });
});
