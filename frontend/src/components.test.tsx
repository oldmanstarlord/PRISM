import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  BreakdownBars,
  EmptyState,
  ErrorState,
  ExplainPanel,
  FreshnessBadge,
  StatusChip,
} from "./components";
import type { BreakdownItem, ResultEnvelope } from "./types";

afterEach(() => {
  cleanup();
});

describe("Shared Components", () => {
  describe("ExplainPanel", () => {
    it("renders full result envelope metadata, thresholds, and limitations", () => {
      const envelopeFixture: ResultEnvelope = {
        subject: "RELIANCE",
        method_version: "prism-risk-score-v1",
        input_fingerprint: "a9f8b4c2e1d03456789abcdef",
        lookback: { start: "2026-04-01", end: "2026-10-01", window_size: 120 },
        confidence: {
          score: 87.5,
          factors: {
            data_coverage: {
              value: 1.0,
              weight: 1.0,
              description: "Configured dimension coverage.",
            },
            data_freshness: {
              value: 0.95,
              weight: 1.0,
              description: "Observed input freshness.",
            },
          },
          caps: ["coverage_cap"],
        },
        thresholds: {
          outlier_cutoff: 0.15,
          thin_trading_adv: 10000000,
        },
        limitations: [
          "Risk scores are descriptive, not price forecasts or investment advice.",
          "MST co-movement does not imply causal influence.",
        ],
        computed_at: "2026-10-01T18:00:00Z",
      };

      render(<ExplainPanel envelope={envelopeFixture} />);

      expect(screen.getByText("RELIANCE")).toBeInTheDocument();
      expect(screen.getAllByText("prism-risk-score-v1").length).toBeGreaterThan(0);
      expect(screen.getByText("a9f8b4c2e1d03456789abcdef")).toBeInTheDocument();
      expect(screen.getByText(/2026-04-01 to 2026-10-01 \(120d\)/i)).toBeInTheDocument();
      expect(screen.getByText("87.5 / 100")).toBeInTheDocument();
      expect(screen.getByText(/Capped: coverage_cap/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Risk scores are descriptive, not price forecasts/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/MST co-movement does not imply causal influence/i)
      ).toBeInTheDocument();
    });
  });

  describe("BreakdownBars", () => {
    it("renders data-driven risk components without hard-coded dimension names", () => {
      const itemsFixture: BreakdownItem[] = [
        {
          key: "volatility_20d",
          dimension: "Market",
          display_name: "20-Day Realized Volatility",
          percentile: 82.4,
          risk_points: 20.6,
          weight: 25,
          status: "active",
          data_age_days: 1,
          reason: "Top quintile volatility in universe over 20-day window.",
        },
        {
          key: "beta_nifty200",
          dimension: "Market",
          display_name: "Index Market Beta",
          percentile: 65.0,
          risk_points: 16.25,
          weight: 25,
          status: "active",
          data_age_days: 1,
          reason: "Elevated market sensitivity.",
        },
        {
          key: "adv_20_thin",
          dimension: "Liquidity",
          display_name: "Average Daily Value (20d)",
          percentile: 25.0,
          risk_points: 2.5,
          weight: 10,
          status: "approved",
          data_age_days: 2,
          reason: "Robust liquidity exceeding 10M INR daily volume.",
        },
      ];

      render(<BreakdownBars items={itemsFixture} />);

      expect(screen.getByText("20-Day Realized Volatility")).toBeInTheDocument();
      expect(screen.getByText("Index Market Beta")).toBeInTheDocument();
      expect(screen.getByText("Average Daily Value (20d)")).toBeInTheDocument();

      // Check percentile labels
      expect(screen.getByText("82%")).toBeInTheDocument();
      expect(screen.getByText("65%")).toBeInTheDocument();
      expect(screen.getByText("25%")).toBeInTheDocument();

      // Check points & weights
      expect(screen.getByText("20.6")).toBeInTheDocument();
      expect(screen.getByText("16.3")).toBeInTheDocument();
      expect(screen.getByText("2.5")).toBeInTheDocument();

      // Check reason texts
      expect(
        screen.getByText(/Top quintile volatility in universe/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Robust liquidity exceeding 10M INR daily volume/i)
      ).toBeInTheDocument();
    });

    it("renders empty state message when items list is empty", () => {
      render(<BreakdownBars items={[]} />);
      expect(screen.getByText(/No component breakdown available/i)).toBeInTheDocument();
    });
  });

  describe("FreshnessBadge", () => {
    it("renders formatted date and label", () => {
      render(<FreshnessBadge dataThroughDate="2026-10-01" label="Market Data" />);
      expect(screen.getByText("Market Data: 2026-10-01")).toBeInTheDocument();
    });
  });

  describe("StatusChip", () => {
    it("renders status chips with correct labels", () => {
      render(<StatusChip status="approved" />);
      expect(screen.getByText("approved")).toBeInTheDocument();
    });
  });

  describe("EmptyState & ErrorState", () => {
    it("renders empty state title and description", () => {
      render(
        <EmptyState
          title="No Holdings"
          description="Import a portfolio CSV to get started."
        />
      );
      expect(screen.getByText("No Holdings")).toBeInTheDocument();
      expect(
        screen.getByText("Import a portfolio CSV to get started.")
      ).toBeInTheDocument();
    });

    it("renders error state message and title", () => {
      render(<ErrorState title="Database Error" message="Failed to reach server." />);
      expect(screen.getByText("Database Error")).toBeInTheDocument();
      expect(screen.getByText("Failed to reach server.")).toBeInTheDocument();
    });
  });
});
