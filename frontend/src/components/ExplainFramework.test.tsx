import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ExplanationPayload } from "../types";
import { BreakdownBars } from "./BreakdownBars";
import { ExplainDrawer } from "./ExplainDrawer";
import { GlossaryTerm } from "./GlossaryTerm";

const payload: ExplanationPayload = {
  schema_version: "1.0",
  headline: "Stored component explanation",
  summary_points: [{ text: "The stored value is 0.24.", evidence_ids: ["e1"] }],
  sections: [
    {
      key: "future_unknown_section",
      title: "Future section",
      sentences: [{ text: "This generic section still renders.", evidence_ids: ["e1"] }],
      chart_spec: {
        type: "rolling_correlation",
        window: 60,
        points: [{ date: "2026-09-30", value: 0.5 }],
      },
    },
  ],
  evidence: [
    {
      evidence_id: "e1",
      kind: "statistic",
      label: "Raw value",
      value: 0.24,
      unit: "annualised decimal",
      window: "60 observations",
      source_table: "score_component_value",
      source_ref: "row-1:raw_value",
      as_of: "2026-09-30",
      data_age_days: 0,
    },
  ],
  limitations: ["This is descriptive risk."],
  confidence: {
    level: "high",
    reasons: [{ text: "Stored status is ok.", evidence_ids: ["e1"] }],
  },
  data_age: { days: 0, as_of: "2026-09-30", status: "ok" },
  template_version: "1.0.0",
  subject: { type: "risk_component", key: "TEST:ewma_volatility" },
  disclaimer: "Not investment advice or a price prediction.",
};

function withQueryClient(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("shared explanation UI", () => {
  it("renders an unknown section key and exposes evidence provenance", () => {
    withQueryClient(
      <ExplainDrawer
        open
        symbol="TEST"
        componentKey="ewma_volatility"
        onClose={vi.fn()}
        payload={payload}
      />,
    );
    expect(screen.getByText("Future section")).toBeInTheDocument();
    expect(screen.getByText("This generic section still renders.")).toBeInTheDocument();
    expect(screen.getByText(/Rolling 60.*day correlation/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Raw value: 0.24"));
    expect(screen.getByText(/Source: score_component_value/)).toBeInTheDocument();
    expect(screen.getByText("Window: 60 observations")).toBeInTheDocument();
    expect(screen.getByText("As of: 2026-09-30")).toBeInTheDocument();
  });

  it("renders the glossary definition in a tooltip", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          term_key: "correlation",
          label: "Correlation",
          plain_definition: "How closely two series move together.",
          formula_text: null,
          see_also: [],
          version: "1.0.0",
        }),
      }),
    );
    withQueryClient(<GlossaryTerm termKey="correlation" />);
    const label = await screen.findByText("Correlation");
    fireEvent.mouseOver(label);
    await waitFor(() => {
      expect(screen.getByText("How closely two series move together.")).toBeInTheDocument();
    });
  });

  it("offers a Why button for every breakdown row", () => {
    const onExplain = vi.fn();
    render(
      <BreakdownBars
        items={[
          { key: "one", display_name: "One", percentile: 10, weight: 0.5 },
          { key: "two", display_name: "Two", percentile: 20, weight: 0.5 },
        ]}
        onExplain={onExplain}
      />,
    );
    const buttons = screen.getAllByRole("button", { name: /Why .+\?/ });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[1]);
    expect(onExplain).toHaveBeenCalledWith(expect.objectContaining({ key: "two" }));
  });
});
