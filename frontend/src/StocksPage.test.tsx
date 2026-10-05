import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import StocksPage from "./StocksPage";

afterEach(() => vi.restoreAllMocks());

describe("StocksPage", () => {
  it("renders screener table with multi-dimensional risk scores and reasons", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          run_id: "run-123",
          as_of_date: "2026-01-15",
          config_version: "1.0.0",
          total_items: 2,
          page: 1,
          page_size: 25,
          items: [
            {
              security_id: "sec-1",
              symbol: "RELIANCE",
              company_name: "Reliance Industries Ltd.",
              industry: "Oil & Gas",
              total_score: 65.4,
              confidence: 88.0,
              data_coverage: 0.85,
              dimension_scores: { market: { score: 65.4, weight: 25.0, status: "ok" } },
              top_reason: {
                component_id: "ewma_volatility",
                dimension: "market",
                name: "EWMA Realised Volatility",
                contribution: 16.4,
                text: "EWMA Realised Volatility is elevated at the 82th percentile, contributing +16.4 pts to Market risk.",
              },
              limitations: [],
              computed_at: "2026-01-15T18:00:00Z",
            },
            {
              security_id: "sec-2",
              symbol: "TCS",
              company_name: "Tata Consultancy Services Ltd.",
              industry: "Information Technology",
              total_score: 32.1,
              confidence: 94.0,
              data_coverage: 1.0,
              dimension_scores: { market: { score: 32.1, weight: 25.0, status: "ok" } },
              top_reason: null,
              limitations: [],
              computed_at: "2026-01-15T18:00:00Z",
            },
          ],
        }),
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/stocks"]}>
          <Routes>
            <Route path="/stocks" element={<StocksPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(
      await screen.findByRole("heading", { name: /Multi-Dimensional Stock Risk Screener/i })
    ).toBeInTheDocument();
    expect(screen.getByText("RELIANCE")).toBeInTheDocument();
    expect(screen.getByText("TCS")).toBeInTheDocument();
    expect(screen.getByText("65.4")).toBeInTheDocument();
    expect(screen.getByText("32.1")).toBeInTheDocument();
    expect(
      screen.getByText(/EWMA Realised Volatility is elevated/i)
    ).toBeInTheDocument();
  });
});
