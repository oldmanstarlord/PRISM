import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SectorsPage from "./SectorsPage";

afterEach(() => vi.unstubAllGlobals());

describe("SectorsPage", () => {
  it("lists API-driven industry trends and opens the sector explanation", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/sectors/overview")) {
        return {
          ok: true,
          json: async () => ({
            subject: "sectors:NIFTY_200",
            effective_time: "2026-10-05",
            method: "stored",
            method_version: "sector-divergence-v1",
            input_fingerprint: "input",
            config_fingerprint: "config",
            data_age_days: 1,
            computed_at: "2026-10-05T12:00:00Z",
            items: [{ industry: "Technology", trend: "up", return_20d: 4.2, breadth: 75, dispersion: 2.1, stock_count: 8, flagged_count: 2 }],
            limitations: ["Daily prices."],
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          schema_version: "1.0",
          headline: "Stored trend and divergence evidence for Technology",
          summary_points: [],
          sections: [],
          evidence: [],
          limitations: ["Daily prices."],
          confidence: { level: "high", reasons: [] },
          data_age: { days: 1, as_of: "2026-10-05", status: "fresh" },
          template_version: "1.0.0",
          subject: { type: "sector", key: "Technology" },
          disclaimer: "Not investment advice.",
        }),
      };
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SectorsPage /></QueryClientProvider>);
    expect(await screen.findByText("Technology")).toBeInTheDocument();
    expect(screen.getByText("2 / 8")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Why?" }));
    expect(await screen.findByText(/stored trend and divergence evidence/i)).toBeInTheDocument();
  });
});
