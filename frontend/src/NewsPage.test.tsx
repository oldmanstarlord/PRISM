import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import NewsPage from "./NewsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NewsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("NewsPage", () => {
  it("shows source status in the honest empty state (RBI/SEBI live, PIB/MoF TBD)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => ({
        ok: true,
        json: async () =>
          String(input).includes("/portfolios")
            ? []
            : {
                items: [],
                source_statuses: [
                  {
                    source_key: "news_rbi_rss",
                    dataset: "news_policy",
                    owner: "Reserve Bank of India",
                    access_method: "rss",
                    terms_url: "https://example.test",
                    license_note: "metadata",
                    cadence: "30m",
                    expected_grace_days: 1,
                    status: "live",
                    freshness_status: "fresh",
                    last_verified_at: null,
                    last_success_at: null,
                    notes: null,
                  },
                ],
                limitations: [],
              },
      }))
    );
    renderPage();
    expect(await screen.findByText(/No qualifying news impacts/)).toBeInTheDocument();
    expect(screen.getByText(/Reserve Bank of India: live \/ fresh/)).toBeInTheDocument();
    expect(screen.getByText("RBI: LIVE (RSS)")).toBeInTheDocument();
    expect(screen.getByText("SEBI: LIVE (RSS)")).toBeInTheDocument();
    expect(screen.getByText("PIB: TBD")).toBeInTheDocument();
    expect(screen.getByText("Ministry of Finance: TBD")).toBeInTheDocument();
  });

  it("renders news feed items with severity badge, rules, sector chips, UNREVIEWED tag, and affected stocks table", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/portfolios")) {
          return {
            ok: true,
            json: async () => [{ id: "p1", name: "Alpha Portfolio" }],
          };
        }
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                news_id: "news-uuid-1",
                headline: "RBI issues guidelines on risk weights for consumer credit",
                source: "RBI",
                published_at: "2026-10-06T09:00:00Z",
                url: "https://rbi.org.in/item1",
                severity: 8.5,
                affected_industries: ["Private Banks", "NBFC"],
                matched_rules: ["POL_RBI_UNSECURED_WEIGHTS_V1"],
                unreviewed: true,
                affected_stocks: [
                  {
                    symbol: "HDFCBANK",
                    security_id: "s1",
                    industry: "Private Banks",
                    direction: "headwind",
                    exposure_score: 0.72,
                    exposure_band: "high",
                    confidence: 0.85,
                    paths: [{ path_type: "rule" }],
                  },
                ],
              },
            ],
            source_statuses: [],
            limitations: [],
          }),
        };
      })
    );

    renderPage();

    // Verify headline and metadata
    expect(
      await screen.findByText("RBI issues guidelines on risk weights for consumer credit")
    ).toBeInTheDocument();
    expect(screen.getByText("Severity 8.5")).toBeInTheDocument();
    expect(screen.getByText("UNREVIEWED")).toBeInTheDocument();
    expect(screen.getByText("POL_RBI_UNSECURED_WEIGHTS_V1")).toBeInTheDocument();
    expect(screen.getAllByText("Private Banks").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("NBFC")).toBeInTheDocument();

    // Verify affected stocks table
    expect(screen.getByText("HDFCBANK")).toBeInTheDocument();
    expect(screen.getByText("0.720")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("headwind")).toBeInTheDocument();
  });

  it("handles filter inputs and portfolio overlay toggle", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/portfolios")) {
        return {
          ok: true,
          json: async () => [{ id: "p-123", name: "High Conviction" }],
        };
      }
      return {
        ok: true,
        json: async () => ({
          items: [],
          source_statuses: [],
          limitations: [],
        }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    // Change industry filter
    const industryInput = await screen.findByPlaceholderText("e.g. Banking, IT");
    fireEvent.change(industryInput, { target: { value: "Finance" } });
    expect(industryInput).toHaveValue("Finance");

    // Change severity filter
    const severityInput = screen.getByLabelText(/Minimum severity/i);
    fireEvent.change(severityInput, { target: { value: "5" } });
    expect(severityInput).toHaveValue(5);
  });

  it("opens the generic five-section explanation drawer on click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/portfolios")) return { ok: true, json: async () => [] };
        if (String(input).includes("/explain/news/")) {
          return {
            ok: true,
            json: async () => ({
              schema_version: "1.0",
              headline: "Possible transmission paths",
              summary_points: [],
              sections: [
                {
                  key: "what_happened",
                  title: "What happened",
                  sentences: [{ text: "RBI updated regulations.", evidence_ids: ["news:item"] }],
                },
                {
                  key: "who_may_be_affected",
                  title: "Who may be affected",
                  sentences: [],
                  chart_spec: {
                    type: "affected_stocks_table",
                    rows: [
                      {
                        symbol: "ABC",
                        industry: "Banks",
                        direction: "headwind",
                        exposure_score: 0.7,
                        exposure_band: "high",
                        confidence: 0.8,
                        paths: [{ path_type: "rule" }],
                      },
                    ],
                  },
                },
              ],
              evidence: [],
              limitations: ["Possible effect, not a prediction."],
              confidence: { level: "medium", reasons: [] },
              data_age: { days: 0, as_of: "2026-10-06", status: "available" },
              template_version: "1.0.0",
              subject: { type: "news", key: "1" },
              disclaimer: "Not investment advice.",
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                news_id: "news-test-1",
                headline: "Policy update",
                source: "RBI",
                published_at: "2026-10-06T09:00:00Z",
                url: "https://example.test/item",
                severity: 8,
                affected_industries: ["Banks"],
                matched_rules: ["liquidity_rule"],
                unreviewed: true,
                affected_stocks: [],
              },
            ],
            source_statuses: [],
            limitations: [],
          }),
        };
      })
    );

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "View explanation" }));
    expect(await screen.findByText("Who may be affected")).toBeInTheDocument();
    expect(screen.getAllByText("UNREVIEWED").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("ABC")).toBeInTheDocument();
  });
});
