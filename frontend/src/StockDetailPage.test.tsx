import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import StockDetailPage from "./StockDetailPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

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
        if (url.includes("/governance")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "INFY",
              security_id: "sec-infy-123",
              as_of: "2026-01-15",
              pledge: {
                quarter_end: "2025-12-31",
                pledge_level_pct: 0.0,
                pledge_change_pct: 0.0,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              promoter_holding: {
                promoter_pct: 14.8,
                promoter_change_pct: 0.0,
                status: "ok",
              },
              institutional_flow: {
                quarter_end: "2025-12-31",
                fii_pct: 34.2,
                dii_pct: 35.1,
                combined_pct: 69.3,
                institutional_change_pct: 0.5,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              insider_activity: {
                window_days: 180,
                window_start: "2025-07-19",
                window_end: "2026-01-15",
                buy_value_inr: 0,
                sell_value_inr: 0,
                net_sell_value_inr: 0,
                trade_count: 0,
                insider_sell_ratio: 0.0,
                status: "ok",
                limitations: [],
              },
              holding_table: [],
              recent_insider_trades: [],
              limitations: [],
              method_version: "governance_analysis_v1",
              config_key: "governance_analysis",
            }),
          });
        }

        if (url.includes("/macro")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "INFY",
              industry: "Information Technology",
              regime: "calm",
              regime_multiplier: 1.0,
              macro_score: 1.25,
              sensitivities: [],
              recent_shocks: {},
              limitations: [],
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
        if (url.includes("/governance")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "TCS",
              security_id: "sec-tcs-123",
              as_of: "2026-01-15",
              pledge: {
                quarter_end: "2025-12-31",
                pledge_level_pct: 0.0,
                pledge_change_pct: 0.0,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              promoter_holding: {
                promoter_pct: 72.3,
                promoter_change_pct: 0.0,
                status: "ok",
              },
              institutional_flow: {
                quarter_end: "2025-12-31",
                fii_pct: 12.5,
                dii_pct: 9.8,
                combined_pct: 22.3,
                institutional_change_pct: 0.2,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              insider_activity: {
                window_days: 180,
                window_start: "2025-07-19",
                window_end: "2026-01-15",
                buy_value_inr: 0,
                sell_value_inr: 0,
                net_sell_value_inr: 0,
                trade_count: 0,
                insider_sell_ratio: 0.0,
                status: "ok",
                limitations: [],
              },
              holding_table: [],
              recent_insider_trades: [],
              limitations: [],
              method_version: "governance_analysis_v1",
              config_key: "governance_analysis",
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

    // Verify FundamentalsPanel rendered (separate async fetch — use findByText to await panel data)
    expect(await screen.findByText("Yahoo Unofficial")).toBeInTheDocument();
    expect(screen.getByText("2025-12-31")).toBeInTheDocument();
    expect(screen.getByText("25th pct")).toBeInTheDocument();
  });

  it("automatically renders Step 8 GovernancePanel and picks up governance components (D2, D5, Step 8)", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/risk/history")) {
          return Promise.resolve({
            ok: true,
            json: async () => [],
          });
        }
        if (url.includes("/fundamentals")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "RELIANCE",
              company_name: "Reliance Industries Ltd.",
              industry: "Energy",
              as_of: "2026-01-15",
              periods: [],
              metrics: [],
              limitations: [],
              source_note: "Exchange results",
            }),
          });
        }
        if (url.includes("/governance")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              symbol: "RELIANCE",
              security_id: "sec-rel-123",
              as_of: "2026-01-15",
              pledge: {
                quarter_end: "2025-12-31",
                pledge_level_pct: 0.0,
                pledge_change_pct: 0.0,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              promoter_holding: {
                promoter_pct: 50.3,
                promoter_change_pct: 0.1,
                status: "ok",
              },
              institutional_flow: {
                quarter_end: "2025-12-31",
                fii_pct: 22.1,
                dii_pct: 16.4,
                combined_pct: 38.5,
                institutional_change_pct: 1.2,
                n_quarters_available: 4,
                status: "ok",
                limitations: [],
              },
              insider_activity: {
                window_days: 180,
                window_start: "2025-07-19",
                window_end: "2026-01-15",
                buy_value_inr: 25000000.0,
                sell_value_inr: 50000000.0,
                net_sell_value_inr: 25000000.0,
                trade_count: 8,
                insider_sell_ratio: 0.0001,
                status: "ok",
                limitations: [],
              },
              holding_table: [
                {
                  quarter_end: "2025-12-31",
                  promoter_pct: 50.3,
                  promoter_pledged_pct_of_promoter: 0.0,
                  fii_pct: 22.1,
                  dii_pct: 16.4,
                  public_pct: 11.2,
                  published_at: "2026-01-14T10:00:00Z",
                  source: "CSV_IMPORT",
                },
              ],
              recent_insider_trades: [
                {
                  person_category: "Promoter Group",
                  txn_type: "BUY",
                  quantity: 50000,
                  value_inr: 25000000.0,
                  txn_date: "2025-12-01",
                  published_at: "2025-12-03T09:00:00Z",
                  source: "CSV_IMPORT",
                },
              ],
              limitations: [
                "Governance signals are descriptive and do not predict future price movements.",
              ],
              method_version: "governance_analysis_v1",
              config_key: "governance_analysis",
            }),
          });
        }

        // Return envelope with Step 8 governance components
        return Promise.resolve({
          ok: true,
          json: async () => ({
            subject: "stock:RELIANCE",
            symbol: "RELIANCE",
            company_name: "Reliance Industries Ltd.",
            industry: "Energy",
            effective_time: "2026-01-15",
            method_version: "risk-scorer-1.0.0",
            total_score: 38.5,
            confidence: { score: 88.0 },
            data_coverage: 0.92,
            dimension_scores: {
              market: { score: 40.0, weight: 25.0 },
              governance: { score: 25.0, weight: 15.0 },
            },
            components: [
              {
                component_id: "gov_promoter_pledge",
                name: "Promoter Pledge Risk",
                dimension: "governance",
                direction: "higher_is_riskier",
                raw_value: 0.0,
                percentile_rank: 15.0,
                points: 15.0,
                status: "ok",
                data_as_of: "2025-12-31",
                data_age_days: 15,
                evidence_ref: {},
              },
              {
                component_id: "gov_insider_activity",
                name: "Net Insider Selling Activity",
                dimension: "governance",
                direction: "higher_is_riskier",
                raw_value: 0.0001,
                percentile_rank: 30.0,
                points: 30.0,
                status: "ok",
                data_as_of: "2026-01-15",
                data_age_days: 0,
                evidence_ref: {},
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
        <MemoryRouter initialEntries={["/stocks/RELIANCE"]}>
          <Routes>
            <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Verify governance components dynamically rendered in breakdown (D2, D5)
    expect(await screen.findByText("Promoter Pledge Risk")).toBeInTheDocument();
    expect(screen.getByText("Net Insider Selling Activity")).toBeInTheDocument();

    // Verify GovernancePanel rendered
    expect(await screen.findByText("Governance & Ownership Signals")).toBeInTheDocument();
    expect(screen.getByText("Promoter Group Holding")).toBeInTheDocument();
    expect(screen.getAllByText("50.30%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Institutional Holding (FII+DII)")).toBeInTheDocument();
    expect(screen.getByText("Promoter Group")).toBeInTheDocument();
  });
});

