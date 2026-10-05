import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "./App";

vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
  })),
}));

vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="mock-plotly-chart">Plotly Chart</div>,
}));

const mockMeta = {
  platform: "PRISM",
  authority: "PRISM_SRS.md",
  disclaimer:
    "PRISM is descriptive risk and explanation, NOT price prediction and NOT investment advice. " +
    "No look-ahead anywhere. Every score, alert, forecast and scenario must show reason, inputs, " +
    "thresholds, method version, data age and limitations. MST/correlation is never presented as " +
    "causal. Shock simulation is a scenario, not a forecast.",
  universe: "NIFTY 200",
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/meta")) {
        return Promise.resolve({
          ok: true,
          json: async () => mockMeta,
        });
      }
      if (url.includes("/data/quality/summary")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: "healthy",
            datasets: {
              securities: { active_count: 200 },
              raw_prices: { total_records: 503226, min_date: "2015-01-01", max_date: "2026-10-01" },
              adjusted_prices: { total_records: 591176 },
              corporate_actions: { total_records: 2864 },
              benchmarks: { active_series_count: 1, total_records: 2500 },
              shares_outstanding: { total_filings: 800 },
              derived_market_stats: {
                total_records: 500000,
                zero_volume_flagged: 12,
                thin_trading_flagged: 5,
              },
            },
            quality_policy: "PRISM SRS Section 7.6 (reject invalid, flag suspicious, never overwrite)",
          }),
        });
      }
      if (url.includes("/data/freshness")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            as_of_utc: "2026-10-05T00:00:00Z",
            datasets: [
              {
                dataset: "daily_prices",
                latest_trade_date: "2026-10-01",
                latest_ingested_at: "2026-10-01T18:00:00Z",
                age_days: 3,
              },
            ],
          }),
        });
      }
      if (url.includes("/data/crosscheck/latest")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            run_id: "test-run",
            checked_at: "2026-10-05T00:00:00Z",
            sources: { source_a: "yfinance", source_b: "exchange_daily_bhavcopy" },
            total_compared: 100,
            mismatch_count: 0,
            mismatch_rate: 0.0,
            worst_discrepancies: [],
          }),
        });
      }
      if (url.includes("/sector-divergence/latest/rankings")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            run: {
              signal_date: "2026-10-01",
              data_cutoff: "2026-10-01T23:59:59Z",
              completed_at: "2026-10-01T18:00:00Z",
              implementation_version: "sector-divergence-v1",
              score_count: 186,
              issue_count: 2,
              exclusion_count: 14,
            },
            horizon: 20,
            results: [],
          }),
        });
      }
      if (url.includes("/sector-divergence/latest/companies")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            run: { signal_date: "2026-10-01" },
            company: { symbol: "TEST", name: "Test Ltd", industry: "Banks" },
            scores: [],
            comparison: {
              basis: "leave-one-out median",
              indexed_to: 100,
              peer_count: 5,
              peer_symbols: ["A", "B"],
              omitted_earlier_paired_observations: 0,
              points: [],
            },
            limitations: [],
          }),
        });
      }
      if (url.includes("/mst/latest")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            run: {
              id: "mst-1",
              window_start: "2026-04-01",
              window_end: "2026-10-01",
              data_cutoff: "2026-10-01",
              requested_symbol_count: 200,
              included_symbol_count: 199,
              edge_count: 198,
              is_connected: true,
              is_acyclic: true,
              implementation_version: "correlation-mst-v1",
              configuration: {},
              computed_at: "2026-10-01T18:00:00Z",
              exclusions: [],
            },
            nodes: [],
            edges: [],
            limitations: [],
          }),
        });
      }
      if (url.includes("/stocks/TEST/risk/latest")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            subject: "stock:TEST",
            symbol: "TEST",
            company_name: "Test Ltd",
            industry: "Technology",
            effective_time: "2026-10-01",
            total_score: 45.0,
            confidence: { score: 85.0, factors: {} },
            data_coverage: 0.8,
            dimension_scores: {},
            components: [],
            limitations: [],
            computed_at: "2026-10-01T18:00:00Z",
          }),
        });
      }
      if (url.includes("/portfolios")) {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      if (url.includes("/macro/regime/latest")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            as_of: "2024-03-28",
            regime: "stressed",
            features: {
              realised_vol_percentile: 92.4,
              correlation_percentile: 85.0,
              india_vix: 24.5,
              regime_multiplier: 1.5,
              hysteresis_applied: true,
            },
            config_version: "v1.0.0",
          }),
        });
      }
      if (url.includes("/macro/series/crude_oil")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            series: {
              series_key: "crude_oil",
              name: "Brent Crude Oil",
              source: "Yahoo Finance",
              frequency: "daily",
              unit: "USD/bbl",
              license_note: "Open",
              is_active: true,
            },
            observations: [],
            total_observations: 0,
            latest_observation: null,
          }),
        });
      }
      if (url.includes("/macro/series")) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              series_key: "crude_oil",
              name: "Brent Crude Oil",
              source: "Yahoo Finance",
              frequency: "daily",
              unit: "USD/bbl",
              license_note: "Open",
              is_active: true,
            },
          ],
        });
      }
      if (url.includes("/macro/sensitivities")) {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      if (url.includes("/stocks/TEST/macro")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            symbol: "TEST",
            industry: "Oil & Gas",
            regime: "stressed",
            regime_multiplier: 1.5,
            macro_score: 5.0,
            sensitivities: [],
            recent_shocks: {},
            limitations: [],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderRoute(path: string) {
  const testClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: Infinity,
      },
    },
  });

  return render(
    <QueryClientProvider client={testClient}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AppRoutes across all views", () => {
  const routesToTest = [
    { path: "/", expectedTitle: /sector divergence/i },
    { path: "/mst", expectedTitle: /correlation minimum spanning tree/i },
    { path: "/portfolio", expectedTitle: /portfolio risk & holdings/i },
    { path: "/stocks", expectedTitle: /stock risk explorer/i },
    { path: "/macro", expectedTitle: /macroeconomic series & sector sensitivity/i },
    { path: "/shock", expectedTitle: /shock & scenario simulation/i },
    { path: "/validation", expectedTitle: /walk-forward & purged validation/i },
    { path: "/data-health", expectedTitle: /data health & quality surveillance/i },
    { path: "/companies/TEST", expectedTitle: "TEST" },
    { path: "/stocks/TEST", expectedTitle: "TEST" },
  ];

  routesToTest.forEach(({ path, expectedTitle }) => {
    it(`renders route "${path}" with AppLayout and displays regulatory disclaimer`, async () => {
      renderRoute(path);

      // Check expected page title
      expect(await screen.findByRole("heading", { name: expectedTitle })).toBeInTheDocument();

      // Check header PRISM title
      expect(screen.getByRole("heading", { name: "PRISM" })).toBeInTheDocument();

      // Check navigation buttons are present
      expect(screen.getByRole("link", { name: "Sector Divergence" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Data Health" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Portfolio" })).toBeInTheDocument();

      // Check regulatory disclaimer in footer
      expect(
        screen.getByText(/PRISM is descriptive risk and explanation/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/PRISM does not provide investment advice/i)
      ).toBeInTheDocument();
    });
  });
});
