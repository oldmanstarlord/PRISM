import type { CoseLayoutOptions, ElementDefinition } from "cytoscape";
import type { MstResponse } from "./types";

const compare = (left: string, right: string) => left < right ? -1 : left > right ? 1 : 0;

export function mstElements(data: MstResponse, colors: Record<string, string>): ElementDefinition[] {
  const nodes = [...data.nodes].sort((a, b) => compare(a.symbol, b.symbol) || compare(a.id, b.id));
  const edges = [...data.edges].sort((a, b) =>
    a.edge_rank - b.edge_rank || compare(a.source, b.source) || compare(a.target, b.target),
  );
  const degree = Object.fromEntries(nodes.map(node => [node.id, 0]));
  for (const edge of edges) {
    degree[edge.source] += 1;
    degree[edge.target] += 1;
  }

  return [
    ...nodes.map((node, index) => {
      // CoSE uses random forces for coincident nodes even with randomize:false.
      // A stable, asymmetric spiral keeps every starting position distinct.
      const angle = index * Math.PI * (3 - Math.sqrt(5));
      const radius = 60 * Math.sqrt(index + 1);
      return {
        data: { ...node, degree: degree[node.id], color: colors[node.industry] },
        position: { x: radius * Math.cos(angle), y: radius * Math.sin(angle) },
      };
    }),
    ...edges.map(edge => ({ data: { id: `${edge.source}-${edge.target}`, ...edge } })),
  ];
}

export const mstLayout: CoseLayoutOptions = {
  name: "cose",
  animate: false,
  randomize: false,
  // Calculate in fixed model coordinates; viewport size only changes the fit.
  boundingBox: { x1: 0, y1: 0, w: 1600, h: 1600 },
  nodeRepulsion: () => 7000,
  idealEdgeLength: () => 85,
  nodeOverlap: 20,
  numIter: 1500,
  padding: 55,
  componentSpacing: 100,
};
