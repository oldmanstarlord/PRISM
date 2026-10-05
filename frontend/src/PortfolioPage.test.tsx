import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PortfolioPage from "./PortfolioPage";

// Mock Plotly component to avoid canvas/webgl issues in jsdom test runner
vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="mock-plotly-chart">Plotly Chart</div>,
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderPortfolioPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <PortfolioPage />
    </QueryClientProvider>
  );
}

describe("PortfolioPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/portfolios")) {
          return Promise.resolve({
            ok: true,
            json: async () => [],
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        });
      })
    );
  });

  it("renders page header and tabs", async () => {
    renderPortfolioPage();

    expect(
      screen.getByRole("heading", { name: /portfolio risk & holdings/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/manual holdings form/i)).toBeInTheDocument();
    expect(screen.getByText(/csv upload & import/i)).toBeInTheDocument();
  });

  it("displays row-level validation errors when CSV import returns errors", async () => {
    // Mock CSV import endpoint returning row errors
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/portfolios/import-csv")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              portfolio: null,
              errors: [
                {
                  row: 2,
                  symbol: "UNKNOWN_SYM",
                  field: "symbol",
                  error: "Unknown security symbol or ISIN 'UNKNOWN_SYM'",
                },
                {
                  row: 3,
                  symbol: "TCS",
                  field: "weight",
                  error: "Negative weight -0.2",
                },
              ],
              warnings: [],
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      })
    );

    renderPortfolioPage();

    // Switch to CSV tab
    const csvTab = screen.getByText(/csv upload & import/i);
    fireEvent.click(csvTab);

    // Enter some CSV text
    const textareas = screen.getAllByRole("textbox");
    const csvInput = textareas[textareas.length - 1];
    fireEvent.change(csvInput, {
      target: { value: "symbol,weight\nUNKNOWN_SYM,0.5\nTCS,-0.2\n" },
    });

    // Click submit
    const submitBtn = screen.getByRole("button", { name: /upload & calculate risk/i });
    fireEvent.click(submitBtn);

    // Verify row error alert and table contents
    await waitFor(() => {
      expect(
        screen.getByText(/validation failed for 2 row\(s\)/i)
      ).toBeInTheDocument();
    });

    expect(screen.getByText("UNKNOWN_SYM")).toBeInTheDocument();
    expect(
      screen.getByText("Unknown security symbol or ISIN 'UNKNOWN_SYM'")
    ).toBeInTheDocument();
    expect(screen.getByText("Negative weight -0.2")).toBeInTheDocument();
  });

  it("handles empty CSV input validation", async () => {
    renderPortfolioPage();

    const csvTab = screen.getByText(/csv upload & import/i);
    fireEvent.click(csvTab);

    const submitBtn = screen.getByRole("button", { name: /upload & calculate risk/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/please select a csv file or paste csv content/i)
      ).toBeInTheDocument();
    });
  });
});
