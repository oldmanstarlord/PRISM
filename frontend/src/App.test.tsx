import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App", () => {
  it("shows the project identity and disclaimer", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => undefined)) as typeof fetch;
    render(<App />);

    expect(screen.getByRole("link", { name: "PRISM" })).toBeInTheDocument();
    expect(screen.getByText(/NO INVESTMENT ADVICE/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /explore the market/i })).toBeInTheDocument();
  });
});
