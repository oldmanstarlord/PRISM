import { accountStorageKey } from "./accountSession";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard";
import PortfolioManager from "./PortfolioManager";

vi.mock("./AppShell", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it("carries the chosen period into company comparisons, paginates, and recovers from an empty search", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => ({
      ok: true,
      json: async () =>
        input.includes("refresh-status")
          ? { enabled: true, market_open: false }
          : {
              horizon: Number(
                new URL(input, "http://localhost").searchParams.get("horizon"),
              ),
              run: { signal_date: "2026-10-23" },
              results: Array.from({ length: 16 }, (_, index) => ({
                symbol: `COMPANY${index}`,
                industry: "Banks",
                divergence_value: 16 - index,
                industry_percentile: 80,
                interpretation: "normal",
              })),
            },
    })),
  );
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
  expect(screen.getByRole("button", { name: /One month/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  fireEvent.click(screen.getByRole("button", { name: /One week/ }));
  // Changing the period now updates the visible research table immediately.
  expect(
    await screen.findByRole("link", { name: "Compare COMPANY0" }),
  ).toHaveAttribute("href", "/companies/COMPANY0?horizon=5");
  expect(within(screen.getByRole("table", {name:"Companies compared with industry peers"})).getAllByRole("row")).toHaveLength(16);
  expect(screen.getAllByText("80%")).toHaveLength(15);
  fireEvent.click(screen.getByRole("button", { name: "Next companies" }));
  expect(screen.getByRole("link", { name: "Compare COMPANY15" })).toBeVisible();
  fireEvent.change(
    screen.getByRole("textbox", { name: "Find a company or industry" }),
    { target: { value: "missing" } },
  );
  expect(
    screen.getByRole("heading", { name: "No companies match these filters" }),
  ).toBeVisible();
  fireEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
  expect(screen.getByRole("link", { name: "Compare COMPANY0" })).toBeVisible();
});

it("starts an empty portfolio with a clear action and keeps all risk and research views accessible", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => {})),
  );
  render(
    <MemoryRouter>
      <PortfolioManager />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("heading", { name: "NO HOLDINGS" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Add your first holding" }),
  ).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "2. Review risk" }));
  for (const name of [
    "Summary",
    "Company risk",
    "Portfolio risk",
    "Sectors",
    "Diversification",
  ])
    expect(screen.getByRole("button", { name })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "3. Research" }));
  for (const name of [
    "Portfolio network",
    "Performance",
    "Stress testing",
    "Decision review",
    "AI insights",
    "News",
  ])
    expect(screen.getByRole("button", { name })).toBeVisible();
  expect(screen.getByRole("button", { name: "Portfolio network" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("heading", { name: "Portfolio network" })).toBeVisible();
  expect(localStorage.getItem(accountStorageKey("prism_portfolio_active_tab"))).toBe("network");
  fireEvent.click(screen.getByRole("button", { name: "Stress testing" }));
  expect(screen.getByRole("heading", { name: "Stress testing" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Stress testing" })).toHaveAttribute("aria-current", "page");
  expect(localStorage.getItem(accountStorageKey("prism_portfolio_active_tab"))).toBe("stress");
  fireEvent.click(screen.getByRole("button", { name: "1. Holdings" }));
  fireEvent.click(screen.getByRole("button", { name: "Activity" }));
  expect(localStorage.getItem(accountStorageKey("prism_portfolio_active_tab"))).toBe(
    "transactions",
  );
});
