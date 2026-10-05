import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import StockDetailPage from "./StockDetailPage";

afterEach(() => vi.restoreAllMocks());

describe("StockDetailPage", () => {
  it("renders risk gauges, ExplainPanel, and unknown components dynamically without errors (D2, D5)", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/risk/history")) {
          return Promise.resolve({
            ok: true,
            json: async () => [
              {
                as_of_date: "2026-01-15",
                total_score: 58.2,
                confidence: 82.0,
                data_coverage: 0.85,
              },
            ],
          });
        }

        return Promise.resolve({
          ok: true,
          json: async () => ({
            subject: "stock:INFY",
            symbol: "INFY",
            company_name: "Infosys Ltd.",
            industry: "Information Technology",
            effective_time: "2026-01-15",
            method: "prism_multidimensional_risk_synthesis",
            version: "1.0.0",
            method_version: "risk-scorer-1.0.0",
            input_fingerprint: "inp-fp-test",
            config_fingerprint: "cfg-fp-test",
            units: "points_0_to_100",
            total_score: 58.2,
            confidence: {
              score: 82.0,
              factors: { data_coverage: { value: 0.85, weight: 1.0, cap_applied: null } },
            },
            data_sufficiency: "sufficient",
            data_coverage: 0.85,
            dimension_scores: {
              market: { score: 62.0, weight: 25.0, status: "ok" },
              unknown_dim: { score: 45.0, weight: 10.0, status: "ok" },
            },
            component_contributions: [
              {
                component_id: "unknown_quantum_factor",
                dimension: "unknown_dim",
                name: "Quantum Audit Metric",
                contribution: 12.5,
                text: "Quantum Audit Metric is elevated at 75th percentile, contributing +12.5 pts to Unknown_dim risk.",
              },
            ],
            // Generic array including a brand new, unknown component key (D2, D5)
            components: [
              {
                component_id: "ewma_volatility",
                name: "EWMA Realised Volatility",
                dimension: "market",
                direction: "higher_is_riskier",
                raw_value: 0.28,
                percentile_rank: 62.0,
                points: 62.0,
                status: "ok",
                status_label: "Ok",
                data_as_of: "2026-01-15",
                data_age_days: 0,
                evidence_ref: {},
              },
              {
                component_id: "unknown_quantum_factor",
                name: "Quantum Audit Metric",
                dimension: "unknown_dim",
                direction: "higher_is_riskier",
                raw_value: 75.0,
                percentile_rank: 75.0,
                points: 75.0,
                status: "ok",
                status_label: "Ok",
                data_as_of: "2026-01-15",
                data_age_days: 0,
                evidence_ref: { custom_source: "quantum_node" },
              },
              {
                component_id: "inactive_future_component",
                name: "Future Sentiment Index",
                dimension: "events",
                direction: "higher_is_riskier",
                raw_value: null,
                percentile_rank: null,
                points: null,
                status: "inactive",
                status_label: "Not yet available",
                data_as_of: null,
                data_age_days: null,
                evidence_ref: {},
              },
            ],
            limitations: ["No look-ahead anywhere."],
            computed_at: "2026-01-15T18:00:00Z",
          }),
        });
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/stocks/INFY"]}>
          <Routes>
            <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByRole("heading", { name: "INFY" })).toBeInTheDocument();
    expect(screen.getByText("58.2")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();

    // Verify unknown component rendered dynamically in breakdown
    expect(screen.getByText("Quantum Audit Metric")).toBeInTheDocument();
    expect(screen.getByText(/Quantum Audit Metric is elevated/i)).toBeInTheDocument();

    // Verify inactive/missing component rendered as not yet available
    expect(screen.getByText("Future Sentiment Index")).toBeInTheDocument();
    expect(screen.getByText(/Not yet available in current data release/i)).toBeInTheDocument();

    // Verify link to Layer 1 Peer Divergence
    expect(screen.getByRole("link", { name: /Layer 1 Peer Divergence/i })).toHaveAttribute(
      "href",
      "/companies/INFY"
    );
  });
});
