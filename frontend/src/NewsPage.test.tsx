import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import NewsPage from "./NewsPage";

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><NewsPage /></MemoryRouter></QueryClientProvider>);
}

describe("NewsPage", () => {
  it("shows source status in the honest empty state", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => ({
      ok: true,
      json: async () => String(input).includes("/portfolios") ? [] : ({
        items: [],
        source_statuses: [{ source_key: "news_rbi_rss", dataset: "news_policy", owner: "Reserve Bank of India", access_method: "rss", terms_url: "https://example.test", license_note: "metadata", cadence: "30m", expected_grace_days: 1, status: "live", freshness_status: "fresh", last_verified_at: null, last_success_at: null, notes: null }],
        limitations: [],
      }),
    })));
    renderPage();
    expect(await screen.findByText(/No qualifying news impacts/)).toBeInTheDocument();
    expect(screen.getByText(/Reserve Bank of India: live \/ fresh/)).toBeInTheDocument();
  });

  it("opens the generic five-section explanation", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/portfolios")) return { ok: true, json: async () => [] };
      if (String(input).includes("/explain/news/")) return {
        ok: true,
        json: async () => ({
          schema_version: "1.0",
          headline: "Possible transmission paths",
          summary_points: [],
          sections: [{
            key: "who_may_be_affected",
            title: "Who may be affected",
            sentences: [],
            chart_spec: {
              type: "affected_stocks_table",
              rows: [{
                symbol: "ABC",
                industry: "Banks",
                direction: "headwind",
                exposure_score: 0.7,
                exposure_band: "high",
                confidence: 0.8,
                paths: [{ path_type: "rule" }],
              }],
            },
          }],
          evidence: [],
          limitations: ["Possible effect, not a prediction."],
          confidence: { level: "medium", reasons: [] },
          data_age: { days: 0, as_of: "2026-10-06", status: "available" },
          template_version: "1.0.0",
          subject: { type: "news", key: "1" },
          disclaimer: "Not investment advice.",
        }),
      };
      return { ok: true, json: async () => ({ items: [{ news_id: "1", headline: "Policy update", source: "RBI", published_at: "2026-10-06T09:00:00Z", url: "https://example.test/item", severity: 8, affected_industries: ["Banks"], matched_rules: ["liquidity_rule"], unreviewed: true, affected_stocks: [] }], source_statuses: [], limitations: [] }) };
    }));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "View explanation" }));
    expect(await screen.findByText("Who may be affected")).toBeInTheDocument();
    expect(screen.getByText("UNREVIEWED")).toBeInTheDocument();
    expect(screen.getByText("ABC")).toBeInTheDocument();
  });
});
