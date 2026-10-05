import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NewsPolicyPanel } from "./NewsPolicyPanel";
import type { StockNewsResponse } from "../types";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("NewsPolicyPanel", () => {
  const sampleData: StockNewsResponse = {
    symbol: "HDFCBANK",
    company_name: "HDFC Bank Limited",
    industry: "Financial Services",
    macro_pressure_points: 0.35,
    disclaimer:
      "Markets may have already priced this in. PRISM event signals are descriptive risk indicators and not investment advice or directional forecasts.",
    items: [
      {
        news_item: {
          id: "news-1",
          source: "RBI",
          published_at: "2026-03-10T11:00:00Z",
          ingested_at: "2026-03-10T11:05:00Z",
          headline: "Monetary Policy Committee raises Repo Rate by 25 bps to curb inflation",
          url: "https://www.rbi.org.in/press-release/1",
          content_hash: "hash123",
        },
        relevance_reason: "industry_policy_match",
        matched_events: [
          {
            id: "evt-1",
            news_item_id: "news-1",
            rule_id: "rule-1",
            matched_at: "2026-03-10T11:06:00Z",
            affected_industry: "Financial Services",
            severity: 7.0,
            evidence: { matched_keywords: ["repo rate", "monetary policy"] },
            rule_key: "POL_RBI_RATE_HIKE_V1",
            direction: "headwind",
            rationale:
              "Higher policy rates elevate funding costs and compress margins for rate-sensitive lenders.",
          },
        ],
      },
    ],
  };

  it("renders news items, matched policy rule, rationale, and non-causal disclaimer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleData,
      })
    );

    renderWithClient(<NewsPolicyPanel symbol="HDFCBANK" />);

    // Disclaimer
    expect(
      await screen.findByText(/Markets may have already priced this in/i)
    ).toBeInTheDocument();

    // Headline
    expect(
      screen.getByText(/Monetary Policy Committee raises Repo Rate/i)
    ).toBeInTheDocument();

    // Matched Rule & Direction
    expect(screen.getByText(/POL_RBI_RATE_HIKE_V1/i)).toBeInTheDocument();
    expect(screen.getByText("HEADWIND")).toBeInTheDocument();
    expect(screen.getByText(/Severity: 7.0 \/ 10.0/i)).toBeInTheDocument();

    // Written Economic Rationale
    expect(
      screen.getByText(/Higher policy rates elevate funding costs and compress margins/i)
    ).toBeInTheDocument();

    // Source link
    const link = screen.getByText(/Official Source/i);
    expect(link).toHaveAttribute("href", "https://www.rbi.org.in/press-release/1");
  });

  it("renders empty state message when no items match the stock or industry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          symbol: "XYZ",
          company_name: "XYZ Corp",
          industry: "Specialty Chemicals",
          items: [],
          macro_pressure_points: null,
          disclaimer: sampleData.disclaimer,
        }),
      })
    );

    renderWithClient(<NewsPolicyPanel symbol="XYZ" />);

    expect(
      await screen.findByText(/No recent regulatory or policy headlines currently matched/i)
    ).toBeInTheDocument();
  });
});
