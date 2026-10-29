// @vitest-environment node
import cytoscape from "cytoscape";
import { describe, expect, it, vi } from "vitest";
import { layoutMst, mstElements, mstLayout, mstTopology } from "./mstLayout";
import type { MstResponse } from "./types";

type GraphData = Pick<MstResponse, "nodes" | "edges">;

function fixture(count: number, shape: "path" | "star" | "forest" = "path"): GraphData {
  const nodes = Array.from({ length: count }, (_, index) => ({
    id: `node-${index}`,
    symbol: `STOCK${String(index).padStart(3, "0")}`,
    industry: `Industry ${index % 4}`,
    observations_used: 250,
  }));
  const edges = nodes.slice(1).flatMap((node, index) => {
    if (shape === "forest" && index % 3 === 0) return [];
    const source = nodes[shape === "star" ? 0 : index];
    return [{
      source: source.id, target: node.id, symbol_a: source.symbol, symbol_b: node.symbol,
      correlation: 0.8, distance: Math.sqrt(0.4), paired_observations: 250, edge_rank: index + 1,
    }];
  });
  return { nodes, edges };
}

function layout(data: GraphData) {
  const cy = cytoscape({
    headless: true,
    styleEnabled: true,
    elements: mstElements(data),
    style: [{ selector: "node", style: {
      width: "mapData(degree, 0, 12, 20, 44)", height: "mapData(degree, 0, 12, 20, 44)",
      "border-width": 2,
    } }],
    layout: { name: "preset" },
  });
  const random = vi.spyOn(Math, "random");
  try {
    cy.layout({ ...mstLayout() }).run();
    expect(random).not.toHaveBeenCalled();
    const positions = cy.nodes().map((node) => ({ id: node.id(), ...node.position() }));
    const edges = cy.edges().map((edge) => edge.data());
    return { positions, edges, bounds: cy.nodes().boundingBox() };
  } finally {
    random.mockRestore();
    cy.destroy();
  }
}

describe("market network layout", () => {
  it.each([
    ["single stock", 1, "path"],
    ["chain", 35, "path"],
    ["symmetric hub", 35, "star"],
    ["disconnected components", 35, "forest"],
  ] as const)("keeps %s in exactly the same positions after a fresh load", (_, count, shape) => {
    const data = fixture(count, shape);
    const first = layout(data);
    expect(layout(structuredClone(data))).toEqual(first);
    // API row order must not change the visual result either.
    expect(layout({ nodes: [...data.nodes].reverse(), edges: [...data.edges].reverse() })).toEqual(first);
    expect(first.positions).toHaveLength(count);
    expect(first.positions.every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
  });

  it("preserves every stock and connection without mutating the API result", () => {
    const data = fixture(12);
    const original = structuredClone(data);
    const result = layout(data);
    expect(data).toEqual(original);
    expect(result.positions.map(({ id }) => id).sort()).toEqual(data.nodes.map(({ id }) => id).sort());
    expect(result.edges).toHaveLength(data.edges.length);
    for (const edge of data.edges) {
      expect(result.edges).toContainEqual(
        expect.objectContaining({ id: `${edge.source}-${edge.target}`, ...edge }),
      );
    }
  });

  it("accepts an empty graph", () => {
    expect(mstElements({ nodes: [], edges: [] })).toEqual([]);
  });

  it("uses the most connected stock as the topology anchor", () => {
    const data = fixture(12, "star");
    const topology = mstTopology(data);
    const elements = mstElements(data);
    const root = elements.find((element) => element.data?.id === "node-0");

    expect(topology).toMatchObject({
      rootSymbol: "STOCK000",
      maxDegree: 11,
      componentCount: 1,
    });
    expect(root?.data).toMatchObject({ id: "node-0", degree: 11, radius: 22 });
  });

  it("settles circles and labels without overlap or a horizontal dump line", () => {
    const result = layoutMst(fixture(120, "forest"), { width: 1120, height: 680 });
    const nodes = result.elements.filter((element) => !element.data?.source);
    const positions = nodes.map((element) => element.position!);
    const distinctRows = new Set(positions.map(({ y }) => Math.round(y / 2))).size;

    expect(result.labelOverlapCount).toBe(0);
    expect(result.minimumNodeDistance).toBeGreaterThanOrEqual(39.9);
    expect(distinctRows).toBeGreaterThan(nodes.length / 2);
    expect(nodes.every((node) => node.data?.symbol)).toBe(true);
    expect(nodes.every((node) => Number(node.data?.radius) >= 6)).toBe(true);
    expect(nodes.every((node) => Number(node.data?.radius) <= 22)).toBe(true);
  });
});
