import { SERIES, resolveTerminalColor } from "./terminalTokens";
import type { CoseLayoutOptions, ElementDefinition } from "cytoscape";
import type { MstResponse } from "./types";

const clusterColors = SERIES;
const compare = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;

export function industryColors(industries: string[]) {
  return Object.fromEntries([...new Set(industries)].sort().map(
    (industry, index) => [industry, clusterColors[index % clusterColors.length]],
  ));
}

export const mstLayout: CoseLayoutOptions = {
  name: "cose",
  animate: false,
  randomize: false,
  nodeRepulsion: () => 7000,
  idealEdgeLength: () => 85,
  nodeOverlap: 20,
  numIter: 1500,
  padding: 55,
  componentSpacing: 100,
};

export function mstElements(data: Pick<MstResponse, "nodes" | "edges">): ElementDefinition[] {
  // CoSE uses random collision forces for coincident nodes even with randomize:false.
  // Start at distinct, reproducible points and keep iteration order stable on reload.
  const nodes = [...data.nodes].sort((a, b) => compare(a.symbol, b.symbol) || compare(a.id, b.id));
  const edges = [...data.edges].sort((a, b) => compare(a.source, b.source) || compare(a.target, b.target));
  const colors = industryColors(nodes.map((node) => node.industry));
  const degree = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }

  return [
    ...nodes.map((node, index) => {
      const angle = index * Math.PI * (3 - Math.sqrt(5));
      const radius = 85 * Math.sqrt(index + 1);
      return {
        data: { ...node, degree: degree.get(node.id), color: resolveTerminalColor(colors[node.industry]) },
        position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
      };
    }),
    ...edges.map((edge) => ({ data: { id: `${edge.source}-${edge.target}`, ...edge } })),
  ];
}
