import { afterEach, expect, it, vi } from "vitest";
import { postJson } from "./api";
const auth = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("./supabase", () => ({ supabase: { auth } }));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
it("attaches the Supabase bearer token to portfolio news requests", async () => {
  auth.getSession.mockResolvedValue({
    data: { session: { access_token: "test-access-token" } },
  });
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  await postJson("/portfolio-analysis/news-signals", { holdings: [] });
  expect(
    new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization"),
  ).toBe("Bearer test-access-token");
});
