import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import PolicyRulesPage from "./PolicyRulesPage";
import type { PolicyRule } from "./types";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("PolicyRulesPage", () => {
  const sampleRules: PolicyRule[] = [
    {
      id: "rule-1",
      rule_key: "POL_RBI_RATE_HIKE_V1",
      description: "Policy repo rate increase by RBI MPC",
      match_keywords: ["repo rate", "rate hike", "monetary policy"],
      match_category: "monetary",
      affected_industries: ["Financial Services", "Banking", "Realty"],
      direction: "headwind",
      severity: 7.0,
      rationale:
        "Higher policy rates elevate funding costs and increase debt service burdens on rate-sensitive sectors.",
      reviewer: "Lead Macro Economist",
      version: "1.0.0",
      active: true,
      created_at: "2026-01-10T10:00:00Z",
      updated_at: "2026-01-10T10:00:00Z",
    },
    {
      id: "rule-2",
      rule_key: "POL_PLI_SCHEME_EXPANSION_V1",
      description: "Expansion of central Production Linked Incentive outlay",
      match_keywords: ["pli scheme", "production linked incentive", "incentive outlay"],
      match_category: "manufacturing",
      affected_industries: ["Automobile and Auto Components", "Electronics"],
      direction: "tailwind",
      severity: 6.0,
      rationale:
        "Fiscal cash subsidies on incremental domestic manufacturing improve operating margins.",
      reviewer: "Senior Policy Analyst",
      version: "1.2.0",
      active: false,
      created_at: "2026-01-12T10:00:00Z",
      updated_at: "2026-01-15T10:00:00Z",
    },
  ];

  it("renders policy rules with rule key, version, reviewer, and economic rationale", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleRules,
      })
    );

    renderWithClient(<PolicyRulesPage />);

    // Header & Disclaimer
    expect(
      await screen.findByText(/Policy & Regulatory Sector Rules/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Descriptive Risk Disclaimer/i)
    ).toBeInTheDocument();

    // Rule 1 details
    expect(await screen.findByText("POL_RBI_RATE_HIKE_V1")).toBeInTheDocument();
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
    expect(screen.getByText("Lead Macro Economist")).toBeInTheDocument();
    expect(
      screen.getByText(/Higher policy rates elevate funding costs/i)
    ).toBeInTheDocument();

    // Rule 2 details
    expect(screen.getByText("POL_PLI_SCHEME_EXPANSION_V1")).toBeInTheDocument();
    expect(screen.getByText("v1.2.0")).toBeInTheDocument();
    expect(screen.getByText("Senior Policy Analyst")).toBeInTheDocument();
  });

  it("filters rules via search input", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleRules,
      })
    );

    renderWithClient(<PolicyRulesPage />);

    expect(await screen.findByText("POL_RBI_RATE_HIKE_V1")).toBeInTheDocument();
    expect(screen.getByText("POL_PLI_SCHEME_EXPANSION_V1")).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/Search rules, keywords, industries/i);
    fireEvent.change(searchInput, { target: { value: "incentive" } });

    // Rule 2 matches "incentive", Rule 1 should disappear
    expect(screen.getByText("POL_PLI_SCHEME_EXPANSION_V1")).toBeInTheDocument();
    expect(screen.queryByText("POL_RBI_RATE_HIKE_V1")).not.toBeInTheDocument();
  });
});
