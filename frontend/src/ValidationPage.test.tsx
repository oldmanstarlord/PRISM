import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ValidationPage from "./ValidationPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ValidationPage", () => {
  it("shows survivorship limitations and failures plainly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.endsWith("/validation/runs")) {
        return Promise.resolve({ ok: true, json: async () => [{
          id: "run-1", kind: "historical_score_validation", config_fingerprint: "abc",
          period: "2025-01-01:2026-01-01", started_at: "2026-10-06T00:00:00Z",
          completed_at: "2026-10-06T00:01:00Z", status: "failed",
          notes: { failures: ["Score did not beat beta."], survivorship_warning: "Current NIFTY 200 membership only." },
        }] });
      }
      return Promise.resolve({ ok: true, json: async () => ({
        id: "run-1", kind: "historical_score_validation", config_fingerprint: "abc",
        period: "2025-01-01:2026-01-01", started_at: "2026-10-06T00:00:00Z",
        completed_at: "2026-10-06T00:01:00Z", status: "failed",
        notes: {
          failures: ["Score did not beat beta."],
          survivorship_warning: "Current NIFTY 200 membership only.",
          limitations: ["Overlapping labels."], labelled_observation_count: 100,
          score_run_count: 12, evaluation_score_run_count: 8, walk_forward_fold_count: 3,
          method_version: "historical-score-validation-v1",
        },
        results: [],
      }) });
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ValidationPage /></QueryClientProvider>);

    expect(await screen.findByText(/Current NIFTY 200 membership only/i)).toBeInTheDocument();
    expect(await screen.findByText("Score did not beat beta.")).toBeInTheDocument();
    expect(screen.getByText(/100 labelled observations from 8 evaluation runs/i)).toBeInTheDocument();
  });
});
