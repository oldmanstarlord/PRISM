import type { ElementDefinition, PresetLayoutOptions } from "cytoscape";

import { resolveTerminalColor } from "./terminalTokens";
import type { MstResponse } from "./types";

const SECTOR_COLORS = Array.from(
  { length: 12 },
  (_, index) => `var(--sector-${index + 1})`,
);
const LABEL_HEIGHT = 17;
const LABEL_GAP = 5;
const LABEL_STROKE = 3;
const MIN_NODE_DISTANCE = 40;
const FORCE_TICKS = 300;
const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

type GraphData = Pick<MstResponse, "nodes" | "edges">;
type NodeData = GraphData["nodes"][number];

interface PositionedNode extends NodeData {
  degree: number;
  radius: number;
  hubRank: number;
  color: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  labelHalign: "left" | "center" | "right";
  labelValign: "top" | "center" | "bottom";
  labelMarginX: number;
  labelMarginY: number;
  labelBox: Box;
}

interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface LabelCandidate {
  halign: PositionedNode["labelHalign"];
  valign: PositionedNode["labelValign"];
  marginX: number;
  marginY: number;
  box: Box;
}

export interface MstTopology {
  rootSymbol: string | null;
  maxDegree: number;
  componentCount: number;
}

export interface MstLayoutResult {
  elements: ElementDefinition[];
  topology: MstTopology;
  labelOverlapCount: number;
  minimumNodeDistance: number;
  forceTicks: number;
}

export function industryColors(industries: string[]) {
  return Object.fromEntries(
    [...new Set(industries)]
      .sort()
      .map((industry, index) => [
        industry,
        SECTOR_COLORS[index % SECTOR_COLORS.length],
      ]),
  );
}

function intersects(a: Box, b: Box, padding = 0) {
  return !(
    a.x2 + padding <= b.x1 ||
    a.x1 >= b.x2 + padding ||
    a.y2 + padding <= b.y1 ||
    a.y1 >= b.y2 + padding
  );
}

function labelWidth(symbol: string) {
  return Math.max(28, symbol.length * 6.7 + LABEL_STROKE * 2);
}

function labelCandidates(node: PositionedNode, fontScale: number): LabelCandidate[] {
  const width = labelWidth(node.symbol) * fontScale;
  const height = LABEL_HEIGHT * fontScale;
  const gap = LABEL_GAP * fontScale;
  const radius = node.radius;
  const positions = [
    { halign: "center", valign: "bottom", x1: node.x - width / 2, y1: node.y + radius + gap, mx: 0, my: gap },
    { halign: "right", valign: "center", x1: node.x + radius + gap, y1: node.y - height / 2, mx: gap, my: 0 },
    { halign: "left", valign: "center", x1: node.x - radius - gap - width, y1: node.y - height / 2, mx: -gap, my: 0 },
    { halign: "center", valign: "top", x1: node.x - width / 2, y1: node.y - radius - gap - height, mx: 0, my: -gap },
    { halign: "right", valign: "bottom", x1: node.x + radius * 0.7 + gap, y1: node.y + radius * 0.7 + gap, mx: gap, my: gap },
    { halign: "left", valign: "bottom", x1: node.x - radius * 0.7 - gap - width, y1: node.y + radius * 0.7 + gap, mx: -gap, my: gap },
    { halign: "right", valign: "top", x1: node.x + radius * 0.7 + gap, y1: node.y - radius * 0.7 - gap - height, mx: gap, my: -gap },
    { halign: "left", valign: "top", x1: node.x - radius * 0.7 - gap - width, y1: node.y - radius * 0.7 - gap - height, mx: -gap, my: -gap },
  ] as const;

  return positions.map((position) => ({
    halign: position.halign,
    valign: position.valign,
    marginX: position.mx,
    marginY: position.my,
    box: {
      x1: position.x1,
      y1: position.y1,
      x2: position.x1 + width,
      y2: position.y1 + height,
    },
  }));
}

function labelHitsNode(box: Box, node: PositionedNode, padding: number) {
  const nearestX = Math.max(box.x1, Math.min(node.x, box.x2));
  const nearestY = Math.max(box.y1, Math.min(node.y, box.y2));
  const dx = node.x - nearestX;
  const dy = node.y - nearestY;
  return dx * dx + dy * dy < (node.radius + padding) ** 2;
}

function placeLabels(nodes: PositionedNode[], fontScale: number) {
  const placed: Box[] = [];
  const ordered = [...nodes].sort(
    (a, b) => b.degree - a.degree || compare(a.symbol, b.symbol),
  );
  let unplaced = 0;

  for (const node of ordered) {
    const candidate = labelCandidates(node, fontScale).find(
      (option) =>
        !placed.some((box) => intersects(option.box, box, 3 * fontScale)) &&
        !nodes.some(
          (other) =>
            other.id !== node.id &&
            labelHitsNode(option.box, other, 3 * fontScale),
        ),
    );
    if (!candidate) {
      unplaced += 1;
      const fallback = labelCandidates(node, fontScale)[0];
      node.labelBox = fallback.box;
      node.labelHalign = fallback.halign;
      node.labelValign = fallback.valign;
      node.labelMarginX = fallback.marginX;
      node.labelMarginY = fallback.marginY;
      placed.push(fallback.box);
      continue;
    }
    node.labelBox = candidate.box;
    node.labelHalign = candidate.halign;
    node.labelValign = candidate.valign;
    node.labelMarginX = candidate.marginX;
    node.labelMarginY = candidate.marginY;
    placed.push(candidate.box);
  }
  return unplaced;
}

function countLabelOverlaps(nodes: PositionedNode[]) {
  let count = 0;
  for (let left = 0; left < nodes.length; left += 1) {
    for (let right = left + 1; right < nodes.length; right += 1) {
      if (intersects(nodes[left].labelBox, nodes[right].labelBox, 1)) count += 1;
    }
  }
  return count;
}

function minimumDistance(nodes: PositionedNode[]) {
  let minimum = Number.POSITIVE_INFINITY;
  for (let left = 0; left < nodes.length; left += 1) {
    for (let right = left + 1; right < nodes.length; right += 1) {
      minimum = Math.min(
        minimum,
        Math.hypot(nodes[left].x - nodes[right].x, nodes[left].y - nodes[right].y),
      );
    }
  }
  return Number.isFinite(minimum) ? minimum : 0;
}

function separateNodes(nodes: PositionedNode[], iterations = 80) {
  for (let tick = 0; tick < iterations; tick += 1) {
    let moved = false;
    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        const required = Math.max(
          MIN_NODE_DISTANCE,
          a.radius + b.radius + 16,
        );
        if (distance >= required) continue;
        if (distance < 0.001) {
          const angle = (left + right + 1) * 2.399963;
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }
        const shift = (required - distance) / 2 + 0.2;
        const ux = dx / distance;
        const uy = dy / distance;
        a.x -= ux * shift;
        a.y -= uy * shift;
        b.x += ux * shift;
        b.y += uy * shift;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

function settleForce(
  nodes: PositionedNode[],
  edges: GraphData["edges"],
  sectorCenters: Map<string, { x: number; y: number }>,
) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (let tick = 0; tick < FORCE_TICKS; tick += 1) {
    const cooling = 1 - tick / FORCE_TICKS;

    for (let left = 0; left < nodes.length; left += 1) {
      for (let right = left + 1; right < nodes.length; right += 1) {
        const a = nodes[left];
        const b = nodes[right];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.001) {
          const angle = (left + right + 1) * 2.399963;
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }
        const ux = dx / distance;
        const uy = dy / distance;
        const collision = Math.max(MIN_NODE_DISTANCE, a.radius + b.radius + 16);
        const repel = Math.min(5.5, 4200 / (distance * distance));
        const overlap = Math.max(0, collision - distance) * 0.22;
        const force = repel + overlap;
        a.vx -= ux * force;
        a.vy -= uy * force;
        b.vx += ux * force;
        b.vy += uy * force;
      }
    }

    for (const edge of edges) {
      const source = byId.get(edge.source);
      const target = byId.get(edge.target);
      if (!source || !target) continue;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const desired = 92 + (1 - Math.abs(edge.correlation)) * 34;
      const spring = (distance - desired) * 0.012;
      const ux = dx / distance;
      const uy = dy / distance;
      source.vx += ux * spring;
      source.vy += uy * spring;
      target.vx -= ux * spring;
      target.vy -= uy * spring;
    }

    for (const node of nodes) {
      const sector = sectorCenters.get(node.industry) ?? { x: 0, y: 0 };
      if (node.degree === 0) {
        const angle = node.hubRank * 2.399963;
        const targetRadius = 420;
        node.vx += (Math.cos(angle) * targetRadius - node.x) * 0.008;
        node.vy += (Math.sin(angle) * targetRadius - node.y) * 0.008;
      } else {
        node.vx += (sector.x - node.x) * 0.0028;
        node.vy += (sector.y - node.y) * 0.0028;
        node.vx += -node.x * 0.0009;
        node.vy += -node.y * 0.0009;
      }
      node.vx *= 0.82;
      node.vy *= 0.82;
      const speed = Math.max(1, Math.hypot(node.vx, node.vy));
      const limit = 7 * (0.35 + cooling * 0.65);
      node.x += (node.vx / speed) * Math.min(speed, limit);
      node.y += (node.vy / speed) * Math.min(speed, limit);
    }
  }
  separateNodes(nodes);
}

function graphMetrics(data: GraphData) {
  const nodes = [...data.nodes].sort(
    (a, b) => compare(a.symbol, b.symbol) || compare(a.id, b.id),
  );
  const edges = [...data.edges].sort(
    (a, b) => compare(a.source, b.source) || compare(a.target, b.target),
  );
  const neighbors = new Map(nodes.map((node) => [node.id, [] as string[]]));
  const incident = new Map(nodes.map((node) => [node.id, [] as GraphData["edges"]]));
  for (const edge of edges) {
    if (!neighbors.has(edge.source) || !neighbors.has(edge.target)) continue;
    neighbors.get(edge.source)?.push(edge.target);
    neighbors.get(edge.target)?.push(edge.source);
    incident.get(edge.source)?.push(edge);
    incident.get(edge.target)?.push(edge);
  }
  const degree = new Map(
    [...neighbors].map(([id, adjacent]) => [id, adjacent.length]),
  );
  const ranked = [...nodes].sort(
    (a, b) =>
      (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) ||
      compare(a.symbol, b.symbol),
  );
  const hubRank = new Map(ranked.map((node, index) => [node.id, index + 1]));
  const maxDegree = Math.max(0, ...degree.values());
  const minDegree = Math.min(maxDegree, ...degree.values());
  const rankByNode = new Map<string, Map<string, number>>();
  for (const node of nodes) {
    const ranks = new Map<string, number>();
    [...(incident.get(node.id) ?? [])]
      .sort(
        (a, b) =>
          Math.abs(b.correlation) - Math.abs(a.correlation) ||
          compare(`${a.source}-${a.target}`, `${b.source}-${b.target}`),
      )
      .forEach((edge, index) => ranks.set(`${edge.source}-${edge.target}`, index + 1));
    rankByNode.set(node.id, ranks);
  }

  const seen = new Set<string>();
  let componentCount = 0;
  for (const node of nodes) {
    if (seen.has(node.id)) continue;
    componentCount += 1;
    const queue = [node.id];
    seen.add(node.id);
    for (let index = 0; index < queue.length; index += 1) {
      for (const next of neighbors.get(queue[index]) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return {
    nodes,
    edges,
    degree,
    hubRank,
    maxDegree,
    minDegree,
    rankByNode,
    componentCount,
    rootSymbol: ranked[0]?.symbol ?? null,
  };
}

export function layoutMst(
  data: GraphData,
  viewport = { width: 1000, height: 650 },
): MstLayoutResult {
  const metrics = graphMetrics(data);
  if (!metrics.nodes.length) {
    return {
      elements: [],
      topology: { rootSymbol: null, maxDegree: 0, componentCount: 0 },
      labelOverlapCount: 0,
      minimumNodeDistance: 0,
      forceTicks: FORCE_TICKS,
    };
  }
  const colors = industryColors(metrics.nodes.map((node) => node.industry));
  const sectors = [...new Set(metrics.nodes.map((node) => node.industry))].sort();
  const sectorCenters = new Map(
    sectors.map((sector, index) => {
      const angle = (index / Math.max(1, sectors.length)) * Math.PI * 2 - Math.PI / 2;
      return [sector, { x: Math.cos(angle) * 230, y: Math.sin(angle) * 175 }];
    }),
  );
  const withinSector = new Map<string, number>();
  const nodes: PositionedNode[] = metrics.nodes.map((node, index) => {
    const sectorIndex = withinSector.get(node.industry) ?? 0;
    withinSector.set(node.industry, sectorIndex + 1);
    const center = sectorCenters.get(node.industry) ?? { x: 0, y: 0 };
    const angle = sectorIndex * 2.399963 + index * 0.13;
    const spread = 26 * Math.sqrt(sectorIndex + 1);
    const degree = metrics.degree.get(node.id) ?? 0;
    const importance =
      metrics.maxDegree === metrics.minDegree
        ? 0.5
        : (degree - metrics.minDegree) /
          (metrics.maxDegree - metrics.minDegree);
    const radius = 6 + Math.sqrt(Math.max(0, importance)) * 16;
    return {
      ...node,
      degree,
      radius,
      hubRank: metrics.hubRank.get(node.id) ?? index + 1,
      color: resolveTerminalColor(colors[node.industry]),
      x: center.x + Math.cos(angle) * spread,
      y: center.y + Math.sin(angle) * spread,
      vx: 0,
      vy: 0,
      labelHalign: "center",
      labelValign: "bottom",
      labelMarginX: 0,
      labelMarginY: LABEL_GAP,
      labelBox: { x1: 0, y1: 0, x2: 0, y2: 0 },
    };
  });

  settleForce(nodes, metrics.edges, sectorCenters);

  const recenter = () => {
    const centerX = nodes.reduce((sum, node) => sum + node.x, 0) / Math.max(1, nodes.length);
    const centerY = nodes.reduce((sum, node) => sum + node.y, 0) / Math.max(1, nodes.length);
    for (const node of nodes) {
      node.x -= centerX;
      node.y -= centerY;
    }
  };
  recenter();

  const bounds = () => ({
    width: Math.max(1, Math.max(...nodes.map((node) => node.x)) - Math.min(...nodes.map((node) => node.x))),
    height: Math.max(1, Math.max(...nodes.map((node) => node.y)) - Math.min(...nodes.map((node) => node.y))),
  });
  let graphBounds = bounds();
  let estimatedZoom = Math.min(
    1,
    (Math.max(120, viewport.width) - 80) / graphBounds.width,
    (Math.max(120, viewport.height) - 80) / graphBounds.height,
  );
  estimatedZoom = Math.max(0.25, estimatedZoom);

  for (let attempt = 0; attempt < 18; attempt += 1) {
    const unplaced = placeLabels(nodes, 1 / estimatedZoom);
    if (unplaced === 0 && countLabelOverlaps(nodes) === 0) break;
    for (const node of nodes) {
      node.x *= 1.08;
      node.y *= 1.08;
    }
    separateNodes(nodes, 20);
    graphBounds = bounds();
    estimatedZoom = Math.max(
      0.25,
      Math.min(
        1,
        (Math.max(120, viewport.width) - 80) / graphBounds.width,
        (Math.max(120, viewport.height) - 80) / graphBounds.height,
      ),
    );
  }
  placeLabels(nodes, 1 / estimatedZoom);
  const labelOverlapCount = countLabelOverlaps(nodes);

  return {
    elements: [
      ...nodes.map((node) => ({
        data: {
          id: node.id,
          symbol: node.symbol,
          industry: node.industry,
          observations_used: node.observations_used,
          degree: node.degree,
          radius: node.radius,
          hubRank: node.hubRank,
          color: node.color,
          labelHalign: node.labelHalign,
          labelValign: node.labelValign,
          labelMarginX: node.labelMarginX,
          labelMarginY: node.labelMarginY,
        },
        position: { x: node.x, y: node.y },
      })),
      ...metrics.edges.map((edge) => {
        const id = `${edge.source}-${edge.target}`;
        const strength = Math.min(1, Math.abs(edge.correlation));
        return {
          data: {
            id,
            ...edge,
            strength,
            edgeOpacity: 0.34 + strength * 0.26,
            sourceRank: metrics.rankByNode.get(edge.source)?.get(id) ?? 1,
            targetRank: metrics.rankByNode.get(edge.target)?.get(id) ?? 1,
          },
        };
      }),
    ],
    topology: {
      rootSymbol: metrics.rootSymbol,
      maxDegree: metrics.maxDegree,
      componentCount: metrics.componentCount,
    },
    labelOverlapCount,
    minimumNodeDistance: minimumDistance(nodes),
    forceTicks: FORCE_TICKS,
  };
}

export function mstTopology(data: GraphData): MstTopology {
  return layoutMst(data).topology;
}

export function mstElements(data: GraphData): ElementDefinition[] {
  return layoutMst(data).elements;
}

export function mstLayout(): PresetLayoutOptions {
  return { name: "preset", animate: false, fit: false, padding: 40 };
}
