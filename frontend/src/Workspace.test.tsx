import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Workspace from "./Workspace";

vi.mock("./api", () => ({ fetchJson: () => new Promise(() => {}) }));
beforeEach(() => sessionStorage.clear());
afterEach(cleanup);
function setup() {
  render(
    <MemoryRouter>
      <Workspace
        renderPage={(url) => (
          <input aria-label={`Notes ${url}`} defaultValue="" />
        )}
      />
    </MemoryRouter>,
  );
}
describe("Research workspace", () => {
  it("keeps page state when switching tabs and avoids duplicate destinations", () => {
    setup();
    fireEvent.change(screen.getByLabelText("Notes /"), {
      target: { value: "Keep this research" },
    });
    fireEvent.click(screen.getByRole("link", { name: "Network" }));
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    fireEvent.click(screen.getByRole("tab", { name: "Markets" }));
    expect(
      within(screen.getByRole("tabpanel")).getByRole("textbox"),
    ).toHaveValue("Keep this research");
    fireEvent.click(screen.getByRole("link", { name: "Network" }));
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });
  it("reorders with the keyboard, persists order, and closes the active tab", () => {
    setup();
    fireEvent.click(screen.getByRole("link", { name: "Network" }));
    fireEvent.keyDown(screen.getByRole("tab", { name: "Network" }), {
      key: "ArrowLeft",
      altKey: true,
    });
    expect(screen.getAllByRole("tab")[0]).toHaveTextContent("Network");
    expect(
      JSON.parse(sessionStorage.getItem("prism.workspace.tabs")!)[0].path,
    ).toBe("/mst");
    fireEvent.click(screen.getByRole("button", { name: "Close Network" }));
    expect(screen.getByRole("tab", { name: "Markets" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Close Markets" }),
    ).toBeDisabled();
  });
});
