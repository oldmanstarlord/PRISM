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
        if (url.includes("/fundamentals")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "INFY",
              company_name: "Infosys Ltd.",
              industry: "Information Technology",
              as_of: "2026-01-15",
              data_age_days: 15,
              periods: [],
              metrics: [],
              limitations: [],
              source_note: "Official exchange financial results",
            }),
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

  it("automatically picks up new fundamental components in score breakdown and renders FundamentalsPanel (D2, D5, Step 7)", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/risk/history")) {
          return Promise.resolve({ ok: true, json: async () => [] });
        }
        if (url.includes("/fundamentals")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "TCS",
              company_name: "Tata Consultancy Services Ltd.",
              industry: "Information Technology",
              as_of: "2026-01-15",
              data_age_days: 45,
              periods: [
                {
                  id: "p1",
                  period_end: "2025-12-31",
                  period_type: "quarter",
                  basis: "consolidated",
                  published_at: "2026-01-10T18:00:00Z",
                  published_at_method: "actual",
                  version: 1,
                  revenue: 600000000000,
                  operating_profit: 150000000000,
                  pat: 120000000000,
                  interest_expense: 1000000000,
                  total_debt: 80000000000,
                  total_equity: 900000000000,
                  total_assets: 1400000000000,
                  cash_from_operations: 140000000000,
                },
              ],
              metrics: [
                {
                  metric_key: "debt_to_equity",
                  value: 0.09,
                  peer_percentile: 25.0,
                  peer_group: "Information Technology",
                  status: "computed",
                },
                {
                  metric_key: "interest_coverage",
                  value: 150.0,
                  peer_percentile: 90.0,
                  peer_group: "Information Technology",
                  status: "computed",
                },
                {
                  metric_key: "cash_flow_quality",
                  value: 1.17,
                  peer_percentile: 80.0,
                  peer_group: "Information Technology",
                  status: "computed",
                },
              ],
              limitations: [
                "Source: Yahoo Finance, unofficial, last ~4 to 5 quarters, publication dates estimated.",
              ],
              source_note: "Source: Yahoo Finance, unofficial, last ~4 to 5 quarters, publication dates estimated",
            }),
          });
        }

        // Return envelope with Step 7 fundamental components
        return Promise.resolve({
          ok: true,
          json: async () => ({
            subject: "stock:TCS",
            symbol: "TCS",
            company_name: "Tata Consultancy Services Ltd.",
            industry: "Information Technology",
            effective_time: "2026-01-15",
            method_version: "risk-scorer-1.0.0",
            total_score: 42.0,
            confidence: { score: 85.0 },
            data_coverage: 0.90,
            dimension_scores: {
              market: { score: 40.0, weight: 25.0 },
              fundamentals: { score: 35.0, weight: 20.0 },
            },
            components: [
              {
                component_id: "fund_leverage",
                name: "Financial Leverage",
                dimension: "fundamentals",
                direction: "higher_is_riskier",
                raw_value: 0.09,
                percentile_rank: 25.0,
                points: 25.0,
                status: "ok",
                data_as_of: "2025-12-31",
                data_age_days: 45,
                evidence_ref: { metric_key: "debt_to_equity" },
              },
              {
                component_id: "fund_coverage",
                name: "Solvency & Interest Coverage",
                dimension: "fundamentals",
                direction: "lower_is_riskier",
                raw_value: 150.0,
                percentile_rank: 10.0,
                points: 10.0,
                status: "ok",
                data_as_of: "2025-12-31",
                data_age_days: 45,
                evidence_ref: { metric_key: "interest_coverage" },
              },
              {
                component_id: "fund_cashflow_quality",
                name: "Cash Flow Quality (CFO / PAT)",
                dimension: "fundamentals",
                direction: "lower_is_riskier",
                raw_value: 1.17,
                percentile_rank: 20.0,
                points: 20.0,
                status: "ok",
                data_as_of: "2025-12-31",
                data_age_days: 45,
                evidence_ref: { metric_key: "cash_flow_quality" },
              },
            ],
            limitations: [],
            computed_at: "2026-01-15T18:00:00Z",
          }),
        });
      })
    );

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/stocks/TCS"]}>
          <Routes>
            <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Verify that the breakdown picked up all new fundamental components automatically (D2, D5)
    expect(await screen.findByText("Financial Leverage")).toBeInTheDocument();
    expect(screen.getByText("Solvency & Interest Coverage")).toBeInTheDocument();
    expect(screen.getAllByText(/Cash Flow Quality/i).length).toBeGreaterThan(0);

    // Verify FundamentalsPanel rendered
    expect(screen.getByText(/Fundamental Risk Analysis & Financial Disclosures/i)).toBeInTheDocument();
    expect(screen.getByText("2025-12-31")).toBeInTheDocument();
    expect(screen.getByText("Yahoo Unofficial")).toBeInTheDocument();
    expect(screen.getByText("25th pct")).toBeInTheDocument();
  });
});
