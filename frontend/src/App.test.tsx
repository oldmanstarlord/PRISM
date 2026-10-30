import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthContext } from "./authState";

describe("App", () => {
  it("requires sign-in before opening the workspace", () => {
    globalThis.fetch = vi.fn(
      () => new Promise(() => undefined),
    ) as typeof fetch;
    render(
      <AuthContext.Provider value={{ session: null, loading: false }}>
        <App />
      </AuthContext.Provider>,
    );

    expect(
      screen.getByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/)).toBeInTheDocument();
    expect(screen.queryByText("My portfolio")).not.toBeInTheDocument();
  });
});
