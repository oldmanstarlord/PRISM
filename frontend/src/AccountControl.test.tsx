import "@testing-library/jest-dom/vitest";
import type { Session } from "@supabase/supabase-js";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import AccountControl from "./AccountControl";
import { AuthContext } from "./authState";

const auth = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("./supabase", () => ({ supabase: { auth } }));
beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);
function openAccount(session: Session | null = null, onCommand = vi.fn()) {
  render(
    <AuthContext.Provider value={{ session, loading: false }}>
      <form onSubmit={onCommand}>
        <AccountControl />
      </form>
    </AuthContext.Provider>,
  );
  fireEvent.click(
    screen.getByRole("button", { name: session ? "Account" : "Sign in" }),
  );
  return onCommand;
}
function fillCredentials() {
  fireEvent.change(screen.getByLabelText(/Email/), {
    target: { value: "presenter@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/Password/), {
    target: { value: "test-password" },
  });
}
it("signs in without submitting the workspace command form", async () => {
  auth.signInWithPassword.mockResolvedValue({
    data: { session: { access_token: "test" } },
    error: null,
  });
  const onCommand = openAccount();
  fillCredentials();
  fireEvent.submit(
    within(screen.getByRole("dialog"))
      .getByRole("button", { name: "Sign in" })
      .closest("form")!,
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(auth.signInWithPassword).toHaveBeenCalledWith({
    email: "presenter@example.com",
    password: "test-password",
  });
  expect(onCommand).not.toHaveBeenCalled();
});
it("keeps failed credentials visible with the authentication error", async () => {
  auth.signInWithPassword.mockResolvedValue({
    data: { session: null },
    error: new Error("Invalid login credentials"),
  });
  openAccount();
  fillCredentials();
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Sign in",
    }),
  );
  expect(await screen.findByText("Invalid login credentials")).toBeVisible();
  expect(screen.getByRole("dialog")).toBeVisible();
});
it("explains confirmation when creating an account", async () => {
  auth.signUp.mockResolvedValue({ data: { session: null }, error: null });
  openAccount();
  fillCredentials();
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText(/Check your email/)).toBeVisible();
});
it("signs out of the current account", async () => {
  auth.signOut.mockResolvedValue({ error: null });
  openAccount({
    access_token: "test",
    user: { email: "presenter@example.com" },
  } as Session);
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(auth.signOut).toHaveBeenCalledOnce();
});
