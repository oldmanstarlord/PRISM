import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MacroPage from "./MacroPage";
import { MacroPanel } from "./components/MacroPanel";

// Mock Plotly component to avoid canvas/webgl issues in jsdom test runner
vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="mock-plotly-chart">Plotly Chart</div>,
}));

const mockRegime = {
  as_of: "2024-03-28",
  regime: "stressed",
  features: {
    realised_vol_percentile: 92.4,
    correlation_percentile: 85.0,
    india_vix: 24.5,
    regime_multiplier: 1.5,
    hysteresis_applied: true,
  },
  config_version: "v1.0.0",
};

const mockSeriesList = [
  {
    series_key: "crude_oil",
    name: "Brent Crude Oil",
    source: "Yahoo Finance (BZ=F)",
    frequency: "daily",
    unit: "USD/bbl",
    license_note: "Public / Open Data",
    is_active: true,
  },
  {
    series_key: "usd_inr",
    name: "USD/INR Exchange Rate",
    source: "Yahoo Finance (INR=X)",
    frequency: "daily",
    unit: "INR",
    license_note: "Public / Open Data",
    is_active: true,
  },
];

const mockSeriesDetail = {
  series: mockSeriesList[0],
  observations: [
    { obs_date: "2024-03-27", value: 85.4, published_at: "2024-03-27T18:00:00Z", version: 1 },
    { obs_date: "2024-03-28", value: 87.2, published_at: "2024-03-28T18:00:00Z", version: 1 },
  ],
  total_observations: 2,
  latest_observation: {
    obs_date: "2024-03-28",
    value: 87.2,
    published_at: "2024-03-28T18:00:00Z",
    version: 1,
  },
};

const mockSensitivities = [
  {
    industry: "Oil & Gas",
    series_key: "crude_oil",
    series_name: "Brent Crude Oil",
    window_end: "2024-03-28",
    beta: 0.3542,
    t_stat: 3.12,
    n_obs: 63,
    p_value: 0.0028,
    is_significant: true,
    config_version: "v1.0.0",
  },
  {
    industry: "Information Technology",
    series_key: "crude_oil",
    series_name: "Brent Crude Oil",
    window_end: "2024-03-28",
    beta: -0.0412,
    t_stat: -0.52,
    n_obs: 63,
    p_value: 0.6041,
    is_significant: false,
    config_version: "v1.0.0",
  },
];

const mockStockMacro = {
  symbol: "RELIANCE",
  industry: "Oil & Gas",
  regime: "stressed",
  regime_multiplier: 1.5,
  macro_score: 5.05,
  sensitivities: [mockSensitivities[0]],
  recent_shocks: {
    crude_oil: {
      move_21d: 0.085,
      z_score: 2.14,
      vol_252d: 0.28,
      latest_val: 87.2,
    },
  },
  limitations: [
    "Rolling 63-day window statistical beta; indicates correlation, not direct causality.",
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/macro/regime/latest")) {
        return Promise.resolve({ ok: true, json: async () => mockRegime });
      }
      if (url.includes("/macro/series/crude_oil")) {
        return Promise.resolve({ ok: true, json: async () => mockSeriesDetail });
      }
      if (url.includes("/macro/series")) {
        return Promise.resolve({ ok: true, json: async () => mockSeriesList });
      }
      if (url.includes("/macro/sensitivities")) {
        return Promise.resolve({ ok: true, json: async () => mockSensitivities });
      }
      if (url.includes("/stocks/RELIANCE/macro")) {
        return Promise.resolve({ ok: true, json: async () => mockStockMacro });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderMacroPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MacroPage />
    </QueryClientProvider>
  );
}

describe("MacroPage", () => {
  it("renders regime classification, indicators, and multiplier", async () => {
    renderMacroPage();

    expect(
      await screen.findByRole("heading", { name: /macroeconomic series & sector sensitivity/i })
    ).toBeInTheDocument();

    expect(await screen.findByText("STATE: STRESSED")).toBeInTheDocument();
    expect(screen.getByText("92.4%ile")).toBeInTheDocument();
    expect(screen.getByText("85.0%ile")).toBeInTheDocument();
    expect(screen.getByText("24.5")).toBeInTheDocument();
    expect(screen.getByText("1.50x")).toBeInTheDocument();
    expect(screen.getByText(/hysteresis active/i)).toBeInTheDocument();
  });

  it("renders series explorer chips and mounts Plotly chart", async () => {
    renderMacroPage();

    expect(await screen.findByText("USD/INR Exchange Rate")).toBeInTheDocument();
    expect((await screen.findAllByText("Brent Crude Oil")).length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByTestId("mock-plotly-chart")).toBeInTheDocument();
  });

  it("renders sector sensitivity table with betas and significance badges", async () => {
    renderMacroPage();

    expect(await screen.findByText("Oil & Gas")).toBeInTheDocument();
    expect(screen.getByText("Information Technology")).toBeInTheDocument();
    expect(screen.getByText("+0.3542")).toBeInTheDocument();
    expect(screen.getByText("-0.0412")).toBeInTheDocument();
    expect(screen.getByText("Significant")).toBeInTheDocument();
    expect(screen.getByText("Insignificant")).toBeInTheDocument();
  });

  it("filters sensitivity table when toggling 'Significant Only'", async () => {
    renderMacroPage();

    expect(await screen.findByText("Information Technology")).toBeInTheDocument();

    const switchEl = screen.getByLabelText(/significant only/i);
    fireEvent.click(switchEl);

    // After filtering to significant only, IT should be excluded
    await waitFor(() => {
      expect(screen.queryByText("Information Technology")).not.toBeInTheDocument();
      expect(screen.getByText("Oil & Gas")).toBeInTheDocument();
    });
  });
});

describe("MacroPanel on StockDetailPage", () => {
  it("renders stock-level sector macro exposures and recent moves", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MacroPanel symbol="RELIANCE" />
      </QueryClientProvider>
    );

    expect(
      await screen.findByText(/macroeconomic factor sensitivity/i)
    ).toBeInTheDocument();
    expect(screen.getByText("REGIME: STRESSED")).toBeInTheDocument();
    expect(screen.getByText("Multiplier: 1.50x")).toBeInTheDocument();
    expect(screen.getByText("5.05 pts")).toBeInTheDocument();
    expect(screen.getByText("2.14")).toBeInTheDocument(); // z-score
    expect(screen.getByText("+8.50%")).toBeInTheDocument(); // 21d move
  });
});
