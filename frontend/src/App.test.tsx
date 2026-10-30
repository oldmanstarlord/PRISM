import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./Dashboard", () => ({ default: () => <div>Markets</div> }));
vi.mock("./CompanyDetail", () => ({ default: () => <div>Company</div> }));
vi.mock("./Workspace", () => ({ default: () => <div>Public workspace</div> }));
describe("App", () => {
  it("opens the workspace without a session or sign-in screen", () => {
    render(<App />);
    expect(screen.getByText("Public workspace")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Password/)).not.toBeInTheDocument();
  });
});
