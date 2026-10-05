import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MstPage from "./MstPage";

vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({
    on: vi.fn(),
    destroy: vi.fn(),
    $: vi.fn(() => ({
      select: vi.fn(),
      unselect: vi.fn(),
      length: 1,
    })),
    animate: vi.fn(),
  })),
}));

const mockMstResponse = {
  run: {
    id: "mst-run-123",
    window_start: "2025-06-01",
    window_end: "2026-01-15",
    data_cutoff: "2026-01-15T23:59:59Z",
    requested_symbol_count: 5,
    included_symbol_count: 5,
    edge_count: 4,
    is_connected: true,
    is_acyclic: true,
    implementation_version: "correlation-mst-v1",
    configuration: { variant: "raw" },
    computed_at: "2026-01-16T02:00:00Z",
    exclusions: [],
    variant: "raw",
  },
  variant: "raw",
  stability_grade: "HIGH",
  edge_persistence: 0.685,
  clusters_count: 2,
  nodes: [
    {
      id: "sec-1",
      symbol: "TCS",
      industry: "Information Technology",
      observations_used: 120,
      degree: 3,
      weighted_centrality: 2.1,
      hub_rank: 1,
      cluster_id: "CLUST-01",
    },
    {
      id: "sec-2",
      symbol: "INFY",
      industry: "Information Technology",
      observations_used: 120,
      degree: 1,
      weighted_centrality: 0.85,
      hub_rank: 2,
      cluster_id: "CLUST-01",
    },
    {
      id: "sec-3",
      symbol: "RELIANCE",
      industry: "Energy",
      observations_used: 120,
      degree: 2,
      weighted_centrality: 1.2,
      hub_rank: 3,
      cluster_id: "CLUST-02",
    },
  ],
  edges: [
    {
      source: "sec-1",
      target: "sec-2",
      symbol_a: "TCS",
      symbol_b: "INFY",
      correlation: 0.85,
      distance: 0.5477,
      paired_observations: 120,
      edge_rank: 1,
    },
  ],
  limitations: [
    "Correlation measures co-movement, not causation.",
    "The MST retains only N-1 relationships and omits many valid correlations.",
    "The topology can change when the lookback window or eligible universe changes.",
    "Edges are a sparse subset of all pairwise relationships.",
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/mst/latest")) {
        return Promise.resolve({
          ok: true,
          json: async () => mockMstResponse,
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderMstPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <MstPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("MstPage Step 4 diagnostics and controls", () => {
  it("renders page header and stability badge", async () => {
    renderMstPage();

    expect(
      await screen.findByRole("heading", { name: /correlation minimum spanning tree/i })
    ).toBeInTheDocument();

    // Stability badge with HIGH grade and 68.5%
    expect(await screen.findByText(/Stability: HIGH \(68.5% persistence\)/i)).toBeInTheDocument();
  });

  it("renders variant selector and color encoding controls", async () => {
    renderMstPage();

    expect(await screen.findByRole("button", { name: /raw returns mst/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /residual variant/i })).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Industry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cluster/i })).toBeInTheDocument();
  });

  it("switches color encoding when cluster toggle is clicked", async () => {
    renderMstPage();

    const clusterToggle = await screen.findByRole("button", { name: /cluster/i });
    fireEvent.click(clusterToggle);
    expect(clusterToggle).toHaveAttribute("aria-pressed", "true");
  });

  it("displays ExplainPanel with descriptive non-causal limitations", async () => {
    renderMstPage();

    expect(
      await screen.findByText(/MST Methodology & Non-Causal Limitations/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Correlation measures co-movement, not causation/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/deliberately retains only 4 relationships/i)
    ).toBeInTheDocument();
  });

  it("displays segmentation card showing cluster count", async () => {
    renderMstPage();

    expect(await screen.findByText("2 Clusters")).toBeInTheDocument();
    expect(screen.getByText(/Formed via deterministic k-longest edge cuts/i)).toBeInTheDocument();
  });
});
