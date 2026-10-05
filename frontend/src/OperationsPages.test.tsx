import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import AlertsPage from "./AlertsPage";
import { AppLayoutInner } from "./AppLayout";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function wrapper(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
}

it("renders alert reasons, inputs, and non-predictive limitation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{
    id: "a1", created_at: "2026-10-06T00:00:00Z", subject_type: "stock", subject_id: "s1",
    alert_type: "risk_jump", reason: "Risk rose 11 points.", inputs_ref: { threshold: 10 },
    score: 11, status: "open", config_version: "1.0.0", config_fingerprint: "f",
  }] }));
  wrapper(<AlertsPage />);
  expect(await screen.findByText("Risk rose 11 points.")).toBeInTheDocument();
  expect(screen.getByText(/not forecasts or investment advice/i)).toBeInTheDocument();
  expect(screen.getByText(/"threshold": 10/i)).toBeInTheDocument();
});

it("shows a global stale-source banner and configured EOD footer", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    if (url.includes("/ops/freshness")) return Promise.resolve({ ok: true, json: async () => [{ source_key: "prices", last_success_at: "2026-10-01T00:00:00Z", last_data_date: "2026-10-01", expected_cadence: 1440, grace: 720, status: "stale" }] });
    if (url.includes("/about/limitations")) return Promise.resolve({ ok: true, json: async () => ({ method_version: "v1", price_frequency_label: "End-of-day prices", filings_news_poll_minutes: 30, limitations: [] }) });
    return Promise.resolve({ ok: true, json: async () => null });
  }));
  wrapper(<AppLayoutInner><div>content</div></AppLayoutInner>);
  expect(await screen.findByText(/Stale data: prices/i)).toBeInTheDocument();
  expect(await screen.findByText(/End-of-day prices; filings and news checked every 30 minutes/i)).toBeInTheDocument();
});
