import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import StockDecisionEngineTab from "./StockDecisionEngineTab";
import type { PortfolioDecisionResponse } from "./types";
import type { PortfolioHolding } from "./PortfolioManager";

afterEach(() => {
  cleanup();
});

const mockResponse: PortfolioDecisionResponse = {
  governance_disclaimer: "Diagnostic health signals only. Not investment advice.",
  methodology_version: "decision-engine-v1",
  summary: {
    total_stocks: 3,
    hold_count: 1,
    wait_and_watch_count: 1,
    sell_count: 1,
    unavailable_count: 0,
    portfolio_weighted_risk_exposure: 30.0,
    average_final_score: 61.3,
    analysis_timestamp: "2026-10-21T08:30:00Z",
  },
  decisions: [
    {
      symbol: "RELIANCE",
      company_name: "Reliance Industries Ltd",
      sector: "Energy",
      fundamental: {
        symbol: "RELIANCE",
        fundamental_strength_score: 85.0,
        fundamental_classification: "Low Risk",
        raw_risk_score: 15.0,
        anomaly_flag: false,
        model_source: "five_factor_risk_score_inverted",
        availability: "available",
      },
      sector_strength: {
        symbol: "RELIANCE",
        sector: "Energy",
        sector_strength_score: 80.0,
        divergence_value: 1.25,
        interpretation: "Industry Outperformer",
        horizon_days: 20,
        source: "existing_sector_divergence_module",
        availability: "available",
      },
      news: {
        symbol: "RELIANCE",
        news_score: 75.0,
        sentiment: "positive",
        news_confidence: 0.85,
        articles_analyzed: 12,
        major_events: ["earnings"],
        sources: ["Reuters"],
        provider_status: "configured",
        is_fallback_neutral: false,
      },
      applied_weights: {
        fundamental: 0.6,
        sector: 0.25,
        news: 0.15,
        regime: "normal",
        regime_reason: "Standard market conditions",
      },
      final_score: 82.25,
      decision: "HOLD",
      confidence: "high",
      explanation: "RELIANCE: Final Health Score = 82.3/100 -> HOLD.",
      reasons: ["Strong fundamental health signal (85/100 strength)."],
      risk_alerts: [],
      analysis_timestamp: "2026-10-21T08:30:00Z",
      status: "analyzed",
    },
    {
      symbol: "TCS",
      company_name: "Tata Consultancy Services",
      sector: "IT",
      fundamental: {
        symbol: "TCS",
        fundamental_strength_score: 55.0,
        fundamental_classification: "Moderate Risk",
        raw_risk_score: 45.0,
        anomaly_flag: false,
        model_source: "five_factor_risk_score_inverted",
        availability: "available",
      },
      sector_strength: {
        symbol: "TCS",
        sector: "IT",
        sector_strength_score: 50.0,
        divergence_value: -0.1,
        interpretation: "Inline",
        horizon_days: 20,
        source: "existing_sector_divergence_module",
        availability: "available",
      },
      news: {
        symbol: "TCS",
        news_score: 50.0,
        sentiment: "neutral",
        news_confidence: 0.5,
        articles_analyzed: 4,
        major_events: [],
        sources: [],
        provider_status: "configured",
        is_fallback_neutral: true,
      },
      applied_weights: {
        fundamental: 0.6,
        sector: 0.25,
        news: 0.15,
        regime: "normal",
        regime_reason: "Standard market conditions",
      },
      final_score: 53.0,
      decision: "WAIT & WATCH",
      confidence: "medium",
      explanation: "TCS: Final Health Score = 53.0/100 -> WAIT & WATCH.",
      reasons: ["Moderate fundamental health signal."],
      risk_alerts: [],
      analysis_timestamp: "2026-10-21T08:30:00Z",
      status: "analyzed",
    },
    {
      symbol: "WEAKCORP",
      company_name: "Weak Corporate Ltd",
      sector: "Finance",
      fundamental: {
        symbol: "WEAKCORP",
        fundamental_strength_score: 25.0,
        fundamental_classification: "High Risk",
        raw_risk_score: 75.0,
        anomaly_flag: true,
        model_source: "five_factor_risk_score_inverted",
        availability: "available",
      },
      sector_strength: {
        symbol: "WEAKCORP",
        sector: "Finance",
        sector_strength_score: 20.0,
        divergence_value: -3.5,
        interpretation: "Severe Underperformance",
        horizon_days: 20,
        source: "existing_sector_divergence_module",
        availability: "available",
      },
      news: {
        symbol: "WEAKCORP",
        news_score: 20.0,
        sentiment: "negative",
        news_confidence: 0.9,
        articles_analyzed: 8,
        major_events: ["litigation"],
        sources: [],
        provider_status: "configured",
        is_fallback_neutral: false,
      },
      applied_weights: {
        fundamental: 0.5,
        sector: 0.15,
        news: 0.35,
        regime: "critical_event",
        regime_reason: "Critical event categories detected",
      },
      final_score: 22.5,
      decision: "SELL",
      confidence: "high",
      explanation: "WEAKCORP: Final Health Score = 22.5/100 -> SELL.",
      reasons: ["Weak fundamental health signal."],
      risk_alerts: ["ANOMALY DETECTED: The isolation-forest ML model flagged unusual price behaviour."],
      analysis_timestamp: "2026-10-21T08:30:00Z",
      status: "analyzed",
    },
  ],
};

const mockHoldings: PortfolioHolding[] = [
  { id: "1", symbol: "RELIANCE", companyName: "Reliance Industries", quantity: 10, buyPrice: 2500, buyDate: "2026-01-01", exchange: "NSE" },
  { id: "2", symbol: "TCS", companyName: "Tata Consultancy Services", quantity: 5, buyPrice: 3500, buyDate: "2026-01-01", exchange: "NSE" },
  { id: "3", symbol: "WEAKCORP", companyName: "Weak Corporate", quantity: 100, buyPrice: 180, buyDate: "2026-01-01", exchange: "NSE" },
];

describe("StockDecisionEngineTab Component", () => {
  it("renders header and summary metrics", () => {
    render(
      <StockDecisionEngineTab
        response={mockResponse}
        loading={false}
        error={null}
        holdings={mockHoldings}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { name: "Stock decisions" })).toBeDefined();
    expect(screen.getByText("PORTFOLIO STOCKS")).toBeDefined();
    expect(screen.getByText("AVG HEALTH SCORE")).toBeDefined();
    expect(screen.getByText("RISK EXPOSURE")).toBeDefined();
    expect(screen.getByText("30.0%")).toBeDefined();
  });

  it("renders stock decision cards with flags", () => {
    render(
      <StockDecisionEngineTab
        response={mockResponse}
        loading={false}
        error={null}
        holdings={mockHoldings}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByTestId("stock-card-RELIANCE")).toBeDefined();
    expect(screen.getByTestId("stock-card-TCS")).toBeDefined();
    expect(screen.getByTestId("stock-card-WEAKCORP")).toBeDefined();
  });

  it("filters decisions by flag", () => {
    render(
      <StockDecisionEngineTab
        response={mockResponse}
        loading={false}
        error={null}
        holdings={mockHoldings}
        onRefresh={vi.fn()}
      />
    );

    // Click SELL filter chip
    const sellFilterChip = screen.getByTestId("filter-chip-SELL");
    fireEvent.click(sellFilterChip);

    expect(screen.getByTestId("stock-card-WEAKCORP")).toBeDefined();
    expect(screen.queryByTestId("stock-card-RELIANCE")).toBeNull();
    expect(screen.queryByTestId("stock-card-TCS")).toBeNull();
  });

  it("expands stock details when clicking Details button", () => {
    render(
      <StockDecisionEngineTab
        response={mockResponse}
        loading={false}
        error={null}
        holdings={mockHoldings}
        onRefresh={vi.fn()}
      />
    );

    const detailsButtons = screen.getAllByText("Details");
    expect(detailsButtons.length).toBeGreaterThan(0);
    fireEvent.click(detailsButtons[0]);

    expect(screen.getByText("1. Fundamental Health (60%)")).toBeDefined();
    expect(screen.getByText("2. Sector Divergence (25%)")).toBeDefined();
    expect(screen.getByText("3. News Intelligence (15%)")).toBeDefined();
    expect(screen.getByText("Decision Rationale & Contributing Factors")).toBeDefined();
  });
});
