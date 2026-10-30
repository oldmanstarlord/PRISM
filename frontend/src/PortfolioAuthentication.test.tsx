import "@testing-library/jest-dom/vitest";
import type { Session } from "@supabase/supabase-js";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import PortfolioManager from "./PortfolioManager";
import { AuthContext } from "./authState";

const api = vi.hoisted(() => ({
  fetchJson: vi.fn(),
  postJson: vi.fn(),
  fetchAuthenticatedJson: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  ...api,
}));
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});
it("requests protected news only after sign-in and sends the current holdings", async () => {
  localStorage.setItem(
    "prism_portfolio_holdings",
    JSON.stringify([
      {
        id: "holding-1",
        symbol: "TCS",
        companyName: "Tata Consultancy Services",
        quantity: 2,
        buyPrice: 3000,
        buyDate: "2026-10-01",
        exchange: "NSE",
        sector: "Information Technology",
      },
    ]),
  );
  api.fetchJson.mockImplementation(() => new Promise(() => {}));
  api.postJson.mockImplementation(() => new Promise(() => {}));
  api.fetchAuthenticatedJson.mockImplementation(() => new Promise(() => {}));
  const view = (session: Session | null) => (
    <MemoryRouter>
      <AuthContext.Provider value={{ session, loading: false }}>
        <PortfolioManager />
      </AuthContext.Provider>
    </MemoryRouter>
  );
  const mounted = render(view(null));
  expect(
    api.postJson.mock.calls.some(
      ([path]) => path === "/portfolio-analysis/news-signals",
    ),
  ).toBe(false);
  const session = {
    access_token: "signed-in-token",
    user: { id: "presenter" },
  } as Session;
  mounted.rerender(view(session));
  await waitFor(() =>
    expect(api.postJson).toHaveBeenCalledWith(
      "/portfolio-analysis/news-signals",
      expect.objectContaining({
        holdings: [expect.objectContaining({ symbol: "TCS", quantity: 2 })],
      }),
      expect.any(AbortSignal),
    ),
  );
  const call = api.postJson.mock.calls.find(
    ([path]) => path === "/portfolio-analysis/news-signals",
  )!;
  mounted.rerender(view(null));
  expect((call[2] as AbortSignal).aborted).toBe(true);
});
