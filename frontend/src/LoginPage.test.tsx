import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";
import { storeLocalSession } from "./accountSession";

vi.mock("./authState", () => ({
  useAuth: () => ({ session: null, loading: false }),
}));
vi.mock("./accountSession", () => ({
  localLogin: true,
  storeLocalSession: vi.fn(),
}));
vi.mock("./api", () => ({ apiBase: "/api/v1" }));
vi.mock("./supabase", () => ({ supabase: null }));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("submits credentials and saves the authenticated session", async () => {
  const session = {
    access_token: "signed-token",
    user: { id: "priya", email: "priya@prism.com" },
  };
  const fetch = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => session });
  vi.stubGlobal("fetch", fetch);
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText(/Email/), {
    target: { value: "priya@prism.com" },
  });
  fireEvent.change(screen.getByLabelText(/Password/), {
    target: { value: "password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(storeLocalSession).toHaveBeenCalledWith(session));
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/auth/login",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ email: "priya@prism.com", password: "password" }),
    }),
  );
  expect(screen.queryByText(/create account|demo/i)).not.toBeInTheDocument();
});

it("shows invalid credentials without saving a session", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Incorrect email or password" }),
      }),
  );
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText(/Email/), {
    target: { value: "priya@prism.com" },
  });
  fireEvent.change(screen.getByLabelText(/Password/), {
    target: { value: "wrong" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Incorrect email or password",
  );
  expect(storeLocalSession).not.toHaveBeenCalled();
});
