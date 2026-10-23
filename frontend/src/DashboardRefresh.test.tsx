import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard";

vi.mock("./AppShell", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("polls published rankings and reports a paused market without hiding the last valid signal", async () => {
  vi.useFakeTimers();
  let closed = false;
  const fetch = vi.fn(async (input: string) => ({ ok: true, json: async () =>
    input.includes("refresh-status") ? {
      enabled: true, market_open: !closed, running: false, refresh_minutes: 30,
      next_refresh_at: closed ? "2026-10-26T09:15:00+05:30" : "2026-10-23T12:15:00+05:30",
      last_success_at: "2026-10-23T06:30:00Z", error: closed ? "Provider unavailable; keeping the previous signal" : null,
    } : {
      run: { signal_date: "2026-10-23", data_cutoff: "2026-10-23T06:30:00Z", completed_at: "2026-10-23T06:31:00Z", implementation_version: "v1", score_count: 1, issue_count: 0, exclusion_count: 0, observation_basis: "current_session_provisional" },
      horizon: 20, results: [{ symbol: "TCS", industry: "IT", divergence_value: 1.2, industry_percentile: 0.8, interpretation: "moderate", observations_used: 60 }],
    },
  }));
  vi.stubGlobal("fetch", fetch);
  await act(async () => { render(<MemoryRouter initialEntries={["/?step=companies&horizon=20"]}><Dashboard /></MemoryRouter>); });
  expect(screen.getByText(/Market open · recalculates every 30 minutes/)).toBeInTheDocument();
  expect(screen.getByText("TCS")).toBeInTheDocument();
  closed = true;
  await act(async () => { vi.advanceTimersByTime(60_000); });
  expect(screen.getByText(/Market closed · signals paused/)).toBeInTheDocument();
  expect(screen.getByText("Provider unavailable; keeping the previous signal")).toBeInTheDocument();
  expect(screen.getByText("TCS")).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([url]) => url.includes("/rankings"))).toHaveLength(2);
});
