import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WhatDoesThisMeanExplainer } from "./WhatDoesThisMeanExplainer";
import { RiskReviewInboxPanel } from "./RiskReviewInboxPanel";
import {
  loadRiskReviewInbox,
  syncIndicatorsToInbox,
  markAlertReviewed,
  markAlertDismissed,
  clearInboxForTesting,
} from "./riskInboxStorage";
import { StructuralMonitoringDashboard } from "./Phase3StructuralSections";
import { COLORS } from "./theme";
import type { StructuralMonitoringSnapshot } from "./types";

const mockSnapshot: StructuralMonitoringSnapshot = {
  portfolio_value: 1250000,
  overall_return: 12.5,
  portfolio_risk_score: 42,
  portfolio_classification: "Moderate",
  diversification_score: 68,
  diversification_grade: "B",
  top_sector: "Financial Services",
  top_sector_weight: 32.5,
  top_sector_status: "Elevated",
  largest_holding: "HDFCBANK",
  largest_holding_weight: 18.2,
  data_freshness: "EOD 15m delayed",
  indicators: [
    {
      id: "single_stock_concentration",
      metric_name: "Max Single Stock Weight",
      title: "Prudential Single-Stock Concentration",
      current_value: 18.2,
      threshold_value: 15.0,
      triggered: true,
      severity: "warning",
      category: "concentration",
      explanation: "Single holding exceeds prudential concentration threshold of 15.0%.",
      recommendation_disclaimer: "Diagnostic threshold.",
      contributing_holdings: ["HDFCBANK"],
      observation_period: "Point-in-time",
      assumptions: ["Mark-to-market prices", "Excludes cash buffer"],
    },
    {
      id: "tail_risk_cvar_95",
      metric_name: "Historical 95% CVaR",
      title: "Expected Shortfall Tail Risk",
      current_value: 4.8,
      threshold_value: 6.0,
      triggered: false,
      severity: "info",
      category: "risk",
      explanation: "Expected shortfall remains within calibrated risk tolerances.",
      recommendation_disclaimer: "Diagnostic threshold.",
      contributing_holdings: ["RELIANCE", "TCS"],
      observation_period: "252d daily returns",
      assumptions: ["Historical empirical distribution", "No leverage"],
    },
  ],
  correlated_groups: [],
  largest_risk_contributors: [],
  structural_changes: [],
  historical_risk_series: [],
  persisted_history_count: 1,
  disclaimer: "Diagnostic only.",
};

describe("Investor Experience Phase 6 Test Suite", () => {
  beforeEach(() => {
    clearInboxForTesting();
    localStorage.clear();
  });

  describe("1. WhatDoesThisMeanExplainer Pattern", () => {
    it("renders expandable explanation with registry metadata", () => {
      render(<WhatDoesThisMeanExplainer metricId="single_stock_concentration" defaultExpanded={false} />);

      expect(screen.getByText(/What does this mean\?/i)).toBeInTheDocument();
      expect(screen.getByText("Explain ▼")).toBeInTheDocument();

      // Click to expand
      fireEvent.click(screen.getByText(/What does this mean\?/i));

      expect(screen.getByText(/What it measures/i)).toBeInTheDocument();
      expect(screen.getByText(/Why it matters/i)).toBeInTheDocument();
      expect(screen.getByText(/Estimation Window & Units/i)).toBeInTheDocument();
      expect(screen.getByText(/Assumptions/i)).toBeInTheDocument();
      expect(screen.getByText(/Diagnostic Limitations/i)).toBeInTheDocument();
    });

    it("renders custom metric title if provided", () => {
      render(
        <WhatDoesThisMeanExplainer
          metricId="tail_risk_cvar_95"
          title="Custom Tail Risk Explainer"
          defaultExpanded={true}
        />
      );

      expect(screen.getByText(/Custom Tail Risk Explainer/i)).toBeInTheDocument();
      expect(screen.getAllByText(/What it measures/i)[0]).toBeInTheDocument();
    });
  });

  describe("2. Risk Review Inbox & Storage", () => {
    it("syncs triggered indicators and manages review audit workflow", () => {
      const records = syncIndicatorsToInbox(mockSnapshot.indicators, "test-portfolio");
      expect(records).toHaveLength(1);
      expect(records[0].indicatorId).toBe("single_stock_concentration");
      expect(records[0].status).toBe("active");
      expect(records[0].currentValue).toBe(18.2);
      expect(records[0].thresholdValue).toBe(15.0);

      // Mark Reviewed
      const reviewed = markAlertReviewed(
        records[0].id,
        "Reviewed allocation; rebalance scheduled for month-end.",
        "test-portfolio"
      );
      expect(reviewed).not.toBeNull();
      expect(reviewed!.status).toBe("reviewed");
      expect(reviewed!.reviewNotes).toContain("rebalance scheduled");
      expect(reviewed!.reviewedAt).toBeDefined();

      // Verify persistence
      const stored = loadRiskReviewInbox("test-portfolio");
      expect(stored[0].status).toBe("reviewed");
    });

    it("allows dismissing an alert with analytical rationale", () => {
      const records = syncIndicatorsToInbox(mockSnapshot.indicators, "test-portfolio-2");
      const dismissed = markAlertDismissed(
        records[0].id,
        "Temporary index reconstitution effect.",
        "test-portfolio-2"
      );
      expect(dismissed).not.toBeNull();
      expect(dismissed!.status).toBe("dismissed");
      expect(dismissed!.reviewNotes).toContain("Temporary index reconstitution");
    });

    it("renders RiskReviewInboxPanel UI with tab filtering and sign-off dialog", async () => {
      render(
        <RiskReviewInboxPanel
          portfolioId="test-ui-portfolio"
          triggeredIndicators={mockSnapshot.indicators.filter((i) => i.triggered)}
        />
      );

      expect(screen.getByText(/Risk Review Inbox/i)).toBeInTheDocument();
      expect(screen.getByText(/Pending Review/i)).toBeInTheDocument();
      expect(screen.getByText(/Pending Active/i)).toBeInTheDocument();
      expect(screen.getByText(/Reviewed \(/i)).toBeInTheDocument();
      expect(screen.getByText(/Dismissed \(/i)).toBeInTheDocument();

      // Open Sign-Off modal
      const reviewBtn = screen.getByRole("button", { name: /Mark Reviewed/i });
      fireEvent.click(reviewBtn);

      expect(await screen.findByText(/Sign-Off on Risk Alert/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Acknowledged concentration/i)).toBeInTheDocument();

      // Type note and confirm
      const input = screen.getByPlaceholderText(/Acknowledged concentration/i);
      fireEvent.change(input, { target: { value: "Approved under quarterly review guidelines." } });

      const confirmBtn = screen.getByRole("button", { name: "Confirm Review" });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(screen.queryByText(/Sign-Off on Risk Alert/i)).not.toBeInTheDocument();
      });
    });
  });

  describe("3. Executive Overview Strip & Diagnostic States", () => {
    it("renders 10 core financial and risk statistics with period and as-of date", () => {
      const onNavigateMock = vi.fn();

      render(
        <MemoryRouter>
          <StructuralMonitoringDashboard
            monitoring={mockSnapshot}
            portfolioId="default"
            financials={{
              marketValue: 1250000,
              investedCost: 1100000,
              cash: 45000,
              realizedPnl: 15000,
              unrealizedPnl: 150000,
              returnPct: 13.64,
              volatility: 0.162,
              maxDrawdown: -0.095,
              concentrationHhi: 0.165,
              dataFreshness: "EOD 15m delayed",
              asOfDate: "2026-10-20",
              period: "1Y (Daily, 252d window)",
            }}
            marketRegime={{
              active_regime_name: "Low Volatility Bull",
              filtered_probability: 0.88,
            }}
            newsSummary={{
              as_of: "2026-10-20T10:00:00Z",
              contract_version: "1.0",
              architecture_status: "active",
              portfolio_sentiment_average: 0.12,
              total_articles_tracked: 14,
              high_impact_event_count: 2,
              stock_signals: [],
              sample_articles: [],
              methodology_disclaimer: "Curated RSS feeds.",
            }}
            onNavigateTab={onNavigateMock}
          />
        </MemoryRouter>
      );

      // Verify Header and Units
      expect(screen.getByText("EXECUTIVE PORTFOLIO OVERVIEW")).toBeInTheDocument();

      // Verify 5 Key Core Metrics
      expect(screen.getByText("Market Value")).toBeInTheDocument();
      expect(screen.getByText("₹12,50,000")).toBeInTheDocument();

      expect(screen.getByText("Invested Cost")).toBeInTheDocument();
      expect(screen.getByText("₹11,00,000")).toBeInTheDocument();

      expect(screen.getByText("Unrealized P&L")).toBeInTheDocument();
      expect(screen.getByText("+₹1,50,000")).toBeInTheDocument();

      expect(screen.getByText(/Return \(% Total\): \+13\.64%/)).toBeInTheDocument();

      expect(screen.getByText("Ann. Volatility")).toBeInTheDocument();
      expect(screen.getByText("16.2%")).toBeInTheDocument();

      expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
      expect(screen.getByText("-9.5%")).toBeInTheDocument();
    });

    it("renders empty/stale state message when monitoring snapshot is null", () => {
      render(<StructuralMonitoringDashboard monitoring={null} />);
      expect(
        screen.getByText(/No structural monitoring data available. Please run portfolio analysis first./i)
      ).toBeInTheDocument();
    });
  });

  describe("4. Strict Design Palette & Invariant Assurance", () => {
    it("ensures theme color tokens strictly follow PRISM palette guidelines", () => {
      expect(COLORS.warmIvory).toBe("#F9EBD7");
      expect(COLORS.sandBeige).toBe("#E3D7C4");
      expect(COLORS.deepCharcoal).toBe("#292D2A");
      expect(COLORS.mutedGrey).toBe("#686B64");
      expect(COLORS.emerald).toBe("#046A38");
      expect(COLORS.vermilion).toBe("#E34222");
      expect(COLORS.vermilionText).toBe("#B8321A");
      expect(COLORS.paleSage).toBe("#DCE9DE");
      expect(COLORS.paleTerracotta).toBe("#F6D9CC");
      expect(COLORS.darkOchre).toBe("#8A5A00");
    });
  });
});
