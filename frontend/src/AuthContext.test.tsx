import "@testing-library/jest-dom/vitest";
import type { Session } from "@supabase/supabase-js";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./authState";

const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
}));
vi.mock("./supabase", () => ({ supabase: { auth } }));
let notify: (event: string, session: Session | null) => void;
const session = {
  access_token: "test-session",
  user: { email: "presenter@example.com" },
} as Session;
function Consumer() {
  const state = useAuth();
  return (
    <div>
      {state.loading ? "Restoring" : (state.session?.user.email ?? "Guest")}
    </div>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  auth.onAuthStateChange.mockImplementation((callback) => {
    notify = callback;
    return { data: { subscription: { unsubscribe: auth.unsubscribe } } };
  });
});
afterEach(cleanup);
it("restores an existing session and clears it on sign-out", async () => {
  auth.getSession.mockResolvedValue({ data: { session } });
  const view = render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>,
  );
  expect(await screen.findByText("presenter@example.com")).toBeVisible();
  act(() => notify("SIGNED_OUT", null));
  expect(screen.getByText("Guest")).toBeVisible();
  view.unmount();
  expect(auth.unsubscribe).toHaveBeenCalledOnce();
});
it("does not overwrite a new sign-in with an older session restore", async () => {
  let finish!: (result: { data: { session: null } }) => void;
  auth.getSession.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>,
  );
  act(() => notify("SIGNED_IN", session));
  await act(async () => finish({ data: { session: null } }));
  expect(screen.getByText("presenter@example.com")).toBeVisible();
});
it("releases the loading state if session restoration fails", async () => {
  auth.getSession.mockRejectedValue(new Error("Session unavailable"));
  render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>,
  );
  await waitFor(() => expect(screen.getByText("Guest")).toBeVisible());
});
