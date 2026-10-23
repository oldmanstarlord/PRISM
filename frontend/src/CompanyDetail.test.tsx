import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import CompanyDetail from "./CompanyDetail";

afterEach(() => vi.restoreAllMocks());

describe("CompanyDetail", () => {
  it("explains the direction and renders the exact peer comparison", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => url.includes("/gnn/") ? {
        run: { status: "unavailable", production_eligible: false },
        symbol: "TEST", latest: null, history: [],
      } : ({
        run: { signal_date: "2026-10-01" },
        company: { symbol: "TEST", name: "Test Ltd.", industry: "Banks" },
        scores: [{
          horizon: 20, divergence_value: -2.5, residual_value: -0.1,
          industry_percentile: 10, interpretation: "strong", alpha: 0,
          beta: 1, residual_volatility: 0.02, observations_used: 60,
          lookback_start: "2026-07-01", lookback_end: "2026-09-30",
        }],
        comparison: {
          basis: "leave-one-out median", indexed_to: 100, peer_count: 4,
          peer_symbols: ["A", "B", "C", "D"], omitted_earlier_paired_observations: 0,
          points: [
            { trade_date: "2026-09-01", stock_index: 100, benchmark_index: 100 },
            { trade_date: "2026-10-01", stock_index: 95, benchmark_index: 102 },
          ],
        },
        limitations: [],
      }),
    })));
    render(
      <MemoryRouter initialEntries={["/companies/TEST"]}>
        <Routes><Route path="/companies/:symbol" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "TEST" })).toBeInTheDocument();
    expect(screen.getByText("negative residual versus peer model")).toBeInTheDocument();
    expect(screen.getByText(/20-day actual performance/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /TEST indexed performance/i })).toBeInTheDocument();
    expect(screen.getByText(/TEST was excluded from its own comparison/i)).toBeInTheDocument();
    expect(await screen.findByText("No GNN history is available for TEST.")).toBeVisible();
  });
});
