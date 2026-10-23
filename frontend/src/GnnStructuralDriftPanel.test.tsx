import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { fetchJson, postJson } from "./api";
import { GnnPortfolioDriftPanel } from "./GnnStructuralDriftPanel";

vi.mock("./api", () => ({ fetchJson: vi.fn(), postJson: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("does not blame holdings when no analysis has been published", async () => {
  vi.mocked(postJson).mockResolvedValue({ run: { status: "unavailable" }, results: [] });
  vi.mocked(fetchJson).mockResolvedValue({ history: [] });
  render(<MemoryRouter><GnnPortfolioDriftPanel symbols={["TCS"]} /></MemoryRouter>);
  expect(await screen.findByText("No persisted structural-drift analysis is available.")).toBeVisible();
  expect(screen.queryByText("No current GNN observations match these holdings.")).toBeNull();
});

it("displays published research observations with their date and validation warning", async () => {
  vi.mocked(postJson).mockResolvedValue({
    run: { status: "research_only", analysis_date: "2026-10-13", selection_reason: "Validation gates have not passed" },
    results: [{ symbol: "TCS", drift_percentile: 0.8, alert_level: "normal" }],
    explainability: {
      method: "Supporting evidence",
      diversification: { status: "available", pairs: 1, requested_pairs: 1, prior: .5, current: .3, change: -.2, method: "Equal-weight correlation" },
      stocks: { TCS: {
        peer_comparison: { status: "available", count: 3, stock_return: .05, peer_median_return: .02, gap: .03, symbols: ["INFY", "WIPRO", "TECHM"] },
        persistence: { consecutive_elevated: 0, window_snapshots: 8, missing_snapshots: 0, history: [] },
      } },
    },
  });
  vi.mocked(fetchJson).mockResolvedValue({ history: [] });
  render(<MemoryRouter><GnnPortfolioDriftPanel symbols={["TCS"]} /></MemoryRouter>);
  expect(await screen.findByRole("link", { name: "TCS" })).toBeVisible();
  expect(screen.getByText(/Research-only output/)).toBeVisible();
  expect(screen.getByText("Analysis date: 2026-10-13")).toBeVisible();
  expect(screen.getByText(/Average return correlation moved from 0.50 to 0.30/)).toBeVisible();
  expect(screen.getByText(/Gap: \+3.00 percentage points/)).toBeVisible();
  expect(screen.getByText(/No ongoing elevated structural-change streak/)).toBeVisible();
});
