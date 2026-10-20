import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiInsightsTab } from "./AiInsightsTab";
import type { PortfolioHolding } from "./PortfolioManager";

afterEach(() => vi.restoreAllMocks());

const mockHoldings: PortfolioHolding[] = [
  {
    id: "h1",
    symbol: "RELIANCE",
    companyName: "Reliance Industries Ltd",
    sector: "Oil & Gas",
    quantity: 50,
    buyPrice: 2500,
    buyDate: "2024-01-01",
    exchange: "NSE",
  },
  {
    id: "h2",
    symbol: "TCS",
    companyName: "Tata Consultancy Services Ltd",
    sector: "Technology",
    quantity: 25,
    buyPrice: 3400,
    buyDate: "2024-01-01",
    exchange: "NSE",
  },
];

const mockAiResponse = {
  model_statuses: {
    volatility_forecast: {
      model_name: "21-Day Realized Volatility Forecaster",
      model_version: "1.0.0",
      model_type: "supervised volatility regression",
      data_cutoff: "2026-10-20",
      training_window: "250-750d expanding",
      features_count: 14,
      status: "ready",
      metrics_vs_baseline: { "ML QLIKE": 0.082, "Baseline QLIKE": 0.089, "MZ R2": 0.34 },
      is_primary_model: true,
      configuration_fingerprint: "abc123hash",
      trained_at: "2026-10-20T10:00:00Z",
    },
    market_regime: {
      model_name: "NIFTY 50 Markov-Switching Regime Filter",
      model_version: "1.0.0",
      model_type: "Markov switching",
      data_cutoff: "2026-10-20",
      training_window: "500d expanding",
      features_count: 1,
      status: "ready",
      metrics_vs_baseline: { "LogLikelihood": 1420.5 },
      is_primary_model: true,
      configuration_fingerprint: "regime123hash",
      trained_at: "2026-10-20T10:00:00Z",
    },
  },
  volatility: {
    status: "ready",
    portfolio_forecast: {
      predicted_volatility_pct: 15.4,
      lower_bound_90_pct: 11.2,
      upper_bound_90_pct: 21.8,
      model_selected: "ml_gradient_boosting",
      trailing_volatility_pct: 14.8,
      ewma_volatility_pct: 15.1,
      har_volatility_pct: 15.3,
      evaluations: {
        ml_model: { qlike: 0.082, mae_log: 0.12, r2: 0.34 },
        har_rv: { qlike: 0.089, mae_log: 0.14, r2: 0.28 },
      },
      feature_importances: { vol_21d: 0.45 },
      horizon_days: 21,
      data_cutoff: "2026-10-20",
    },
    holdings_forecasts: [
      {
        symbol: "RELIANCE",
        weight: 60.0,
        status: "ready",
        prediction_date: "2026-10-20",
        forecast_volatility: 0.162,
        lower_bound_90: 0.12,
        upper_bound_90: 0.225,
        trailing_21d_vol: 0.155,
        model_selected: "ml_gradient_boosting",
        vol_change_expected: 0.7,
      },
      {
        symbol: "TCS",
        weight: 40.0,
        status: "ready",
        prediction_date: "2026-10-20",
        forecast_volatility: 0.141,
        lower_bound_90: 0.105,
        upper_bound_90: 0.198,
        trailing_21d_vol: 0.139,
        model_selected: "ml_gradient_boosting",
        vol_change_expected: 0.2,
      },
    ],
  },
  regime: {
    status: "ready",
    market_regime: {
      model_version: "1.0.0",
      methodology: "Hamilton 2-State Markov-Switching Filter",
      benchmark: "NIFTY 50",
      data_cutoff: "2026-10-20",
      active_regime_id: 0,
      active_regime_name: "Calm / Normal",
      filtered_probability: 0.88,
      regime_conditional_volatilities: { "Calm / Normal": 0.112, "Turbulent / Stressed": 0.265 },
      regime_conditional_correlations: { "Calm / Normal": 0.28, "Turbulent / Stressed": 0.64 },
      expected_durations_days: { "Calm / Normal": 140, "Turbulent / Stressed": 28 },
      transition_matrix: [[0.98, 0.02], [0.07, 0.93]],
      regime_timeline: [{ date: "2026-10-20", regime: "Calm", stressed_prob: 0.12 }],
    },
  },
  anomalies: {
    status: "ready",
    anomaly_analysis: {
      methodology: "Isolation Forest vs Robust Z-Score",
      flag_rate_pct: 12.5,
      stability_score: 0.85,
      disclaimer: "No predictive accuracy is claimed.",
      unusual_holdings: [
        {
          symbol: "RELIANCE",
          status: "ready",
          company_name: "Reliance Industries Ltd",
          anomaly_score: 0.18,
          is_anomaly: false,
          return_zscore: 0.45,
          volume_spike_ratio: 1.1,
          volatility_surge_ratio: 1.05,
          sector_divergence: 0.2,
          primary_driver: "Normal Trading",
          rationale: "Trading parameters within normal MAD boundaries.",
        },
      ],
    },
  },
  score_validation: {
    status: "ready",
    score_validation: {
      test_period: ["2025-01-31", "2026-09-30"],
      test_rows: 500,
      models: {
        five_factor_fixed_weights: {
          volatility_21d: {
            mean_monthly_spearman_ic: 0.145,
            ic_t_statistic: 2.4,
            mean_top_minus_bottom_quintile_spread: 0.048,
          },
          worst_quintile_drawdown_21d_auc: 0.612,
        },
      },
      baseline_comparisons: {},
    },
  },
  governance: {
    methodology_version: "2026.1",
    disclaimer: "PRISM AI Insights strictly does NOT provide price-direction predictions.",
    is_model_estimate: true,
  },
};

describe("AiInsightsTab", () => {
  it("renders empty state message when holdings list is empty", () => {
    render(
      <MemoryRouter>
        <AiInsightsTab holdings={[]} totalInvestedValue={0} />
      </MemoryRouter>
    );
    expect(screen.getByText(/No Active Portfolio Positions/i)).toBeInTheDocument();
  });

  it("renders diagnostic panels, model estimate badges, and disclaimer when loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockAiResponse,
      })
    );

    render(
      <MemoryRouter>
        <AiInsightsTab holdings={mockHoldings} totalInvestedValue={217500} />
      </MemoryRouter>
    );

    // Header & Badge check
    expect(await screen.findByText(/AI Risk Diagnostics & Model Estimates/i)).toBeInTheDocument();
    expect(screen.getAllByText("Persisted model output").length).toBeGreaterThan(0);
    expect(screen.getByText(/strictly do NOT forecast price direction/i)).toBeInTheDocument();

    // Section headings check
    expect(screen.getByText(/1\. Model Registry & Walk-Forward Status/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. NIFTY 50 Market Regime State/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. 21-Day Ahead Realized Volatility Forecast/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Unusual Behaviour & Holding Anomalies/i)).toBeInTheDocument();
    expect(screen.getByText(/5\. Heuristic Stock Risk Score Walk-Forward Validation/i)).toBeInTheDocument();
    expect(screen.getByText(/6\. Methodological Assumptions & Limitations/i)).toBeInTheDocument();

    // Metric check
    expect(screen.getByText("16.20%")).toBeInTheDocument();
    expect(screen.getAllByText(/Calm \/ Normal/i).length).toBeGreaterThan(0);
  });
});
