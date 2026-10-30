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

const { signInWithPassword } = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
}));
vi.mock("./authState", () => ({
  useAuth: () => ({ session: null, loading: false }),
}));
vi.mock("./accountSession", () => ({
  localLogin: false,
  storeLocalSession: vi.fn(),
}));
vi.mock("./api", () => ({ apiBase: "/api/v1" }));
vi.mock("./supabase", () => ({ supabase: { auth: { signInWithPassword } } }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("uses Supabase email/password authentication in deployed mode", async () => {
  signInWithPassword.mockResolvedValue({ error: null });
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
  await waitFor(() =>
    expect(signInWithPassword).toHaveBeenCalledWith({
      email: "priya@prism.com",
      password: "password",
    }),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("shows errors returned by Supabase", async () => {
  signInWithPassword.mockResolvedValue({
    error: new Error("Invalid login credentials"),
  });
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
    "Invalid login credentials",
  );
});
