import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { DivergenceExplanationPanel } from "./DivergenceExplanationPanel";

const sentence = (text: string, evidence_ids: string[]) => ({ text, evidence_ids });
const evidence = (evidence_id: string, value: string | number) => ({
  evidence_id,
  kind: "statistic",
  label: evidence_id,
  value,
  unit: null,
  window: null,
  source_table: "stored_table",
  source_ref: evidence_id,
  as_of: "2026-10-05",
  data_age_days: 1,
});

const payload = {
  schema_version: "1.0",
  headline: "TEST is underperforming its peer model",
  summary_points: [],
  sections: [
    {
      key: "sector_trend",
      title: "Sector trend",
      sentences: [sentence("The sector trend is up.", ["sector_return_20"])],
      chart_spec: {
        type: "stock_sector_rebased",
        indexed_to: 100,
        residual_shaded: true,
        points: [
          { date: "2026-10-01", stock: 100, sector: 100, residual: 0 },
          { date: "2026-10-05", stock: 96, sector: 103, residual: -7 },
        ],
        event_markers: [],
      },
    },
    { key: "stock_trend", title: "Stock trend", sentences: [] },
    { key: "why_flagged", title: "Why flagged", sentences: [sentence("Stored z was -2.1.", ["z_20"])] },
    { key: "risk_reading", title: "Is it risky?", sentences: [sentence("A divergence alone is not a risk verdict.", ["risk_rule"])] },
    { key: "contribution", title: "How much it matters", sentences: [sentence("It represented 12.5%.", ["contribution_share"])] },
  ],
  evidence: [
    evidence("sector_return_20", 3),
    evidence("sector_trend_20", "up"),
    evidence("stock_return_20", -4),
    evidence("stock_trend_20", "down"),
    evidence("z_20", -2.1),
    evidence("risk_rule", "configured"),
    evidence("contribution_share", 12.5),
  ],
  limitations: ["A divergence alone is not a risk verdict."],
  confidence: { level: "high", reasons: [] },
  data_age: { days: 1, as_of: "2026-10-05", status: "fresh" },
  template_version: "1.0.0",
  subject: { type: "sector_divergence", key: "TEST" },
  disclaimer: "Not investment advice.",
};

afterEach(() => vi.unstubAllGlobals());

it("renders trend cards, rebased chart, flag, risk, and contribution sections", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DivergenceExplanationPanel symbol="TEST" />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(payload.headline)).toBeInTheDocument();
  expect(screen.getByText("+3.00%")).toBeInTheDocument();
  expect(screen.getByText("-4.00%")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /rebased stock and sector trend/i })).toBeInTheDocument();
  expect(screen.getByText("Why flagged")).toBeInTheDocument();
  expect(screen.getByText("Is it risky?")).toBeInTheDocument();
  expect(screen.getByText("How much it matters")).toBeInTheDocument();
});
