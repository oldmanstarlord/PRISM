import { describe, expect, it } from "vitest";

import {
  parseDemoPortfolioCsv,
  portfolioMstEdges,
  validateDemoPortfolio,
} from "./demoPortfolio";

describe("presentation portfolio helpers", () => {
  it("parses and validates a 100 percent portfolio", () => {
    const rows = parseDemoPortfolioCsv("symbol,weight\nTCS,40\nRELIANCE,60\n");
    const result = validateDemoPortfolio(rows, new Set(["TCS", "RELIANCE"]));

    expect(result.valid).toBe(true);
    expect(result.holdings).toEqual([
      { symbol: "RELIANCE", weight: 0.6 },
      { symbol: "TCS", weight: 0.4 },
    ]);
  });

  it("rejects unsupported symbols and incomplete weights", () => {
    const result = validateDemoPortfolio(
      [{ symbol: "UNKNOWN", weightPercent: 50 }],
      new Set(["TCS"]),
    );

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Not in the current MST universe: UNKNOWN");
    expect(result.errors).toContain("Weights must total 100%; received 50.00%");
  });

  it("retains only direct MST links between holdings", () => {
    const edges = portfolioMstEdges(
      [
        { symbol: "A", weight: 0.5 },
        { symbol: "B", weight: 0.5 },
      ],
      [
        {
          source: "1", target: "2", symbol_a: "A", symbol_b: "B",
          correlation: 0.8, distance: 0.6, paired_observations: 120, edge_rank: 1,
        },
        {
          source: "2", target: "3", symbol_a: "B", symbol_b: "C",
          correlation: 0.9, distance: 0.4, paired_observations: 120, edge_rank: 2,
        },
      ],
    );

    expect(edges).toHaveLength(1);
    expect(edges[0].symbol_a).toBe("A");
    expect(edges[0].symbol_b).toBe("B");
  });
});
