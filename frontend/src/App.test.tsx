import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

describe("App", () => {
  it("shows the project identity and disclaimer", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => undefined)) as typeof fetch;
    render(<App />);

    expect(screen.getByRole("heading", { name: "PRISM" })).toBeInTheDocument();
    expect(screen.getByText(/does not provide investment advice/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /sector divergence/i })).toBeInTheDocument();
  });
});
