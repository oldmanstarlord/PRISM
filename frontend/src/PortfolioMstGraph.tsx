import { useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import cytoscape, { type Core } from "cytoscape";

import type { PortfolioAnalysisResponse } from "./types";

type MstSummary = PortfolioAnalysisResponse["mst"];
type Holding = PortfolioAnalysisResponse["holdings"][number];

type Selection = {
  eyebrow: string;
  title: string;
  detail: string;
  secondary: string;
};

const clusterColors = ["#0f766e", "#2563eb", "#7c3aed", "#be123c", "#a16207", "#047857"];

function edgeKey(symbolA: string, symbolB: string) {
  return [symbolA, symbolB].sort().join("::");
}

function correlationLabel(value: number) {
  return `ρ ${value.toFixed(2)}`;
}

export default function PortfolioMstGraph({ mst, holdings }: { mst: MstSummary; holdings: Holding[] }) {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);

  const graphData = useMemo(() => {
    const heldBySymbol = new Map(holdings.map((holding) => [holding.symbol, holding]));
    const bridgeBySymbol = new Map(mst.bridge_stocks.map((bridge) => [bridge.symbol, bridge]));
    const clusterBySymbol = new Map<string, { name: string; color: string }>();
    mst.clusters.forEach((cluster, index) => {
      cluster.holding_symbols.forEach((symbol) => {
        clusterBySymbol.set(symbol, {
          name: cluster.cluster_id,
          color: clusterColors[index % clusterColors.length],
        });
      });
    });

    const symbols = new Set(holdings.map((holding) => holding.symbol));
    mst.subtree_edges.forEach((edge) => {
      symbols.add(edge.symbol_a);
      symbols.add(edge.symbol_b);
    });

    const nodeDegree = new Map([...symbols].map((symbol) => [symbol, 0]));
    mst.subtree_edges.forEach((edge) => {
      nodeDegree.set(edge.symbol_a, (nodeDegree.get(edge.symbol_a) ?? 0) + 1);
      nodeDegree.set(edge.symbol_b, (nodeDegree.get(edge.symbol_b) ?? 0) + 1);
    });

    const nodes = [...symbols].sort().map((symbol) => {
      const holding = heldBySymbol.get(symbol);
      const bridge = bridgeBySymbol.get(symbol);
      const cluster = clusterBySymbol.get(symbol);
      return {
        data: {
          id: symbol,
          symbol,
          isHolding: Boolean(holding),
          weight: holding?.weight ?? 0,
          weightLabel: holding ? `${(holding.weight * 100).toFixed(1)}% portfolio weight` : "Not held",
          cluster: cluster?.name ?? "Bridge stock",
          color: cluster?.color ?? "#dbe4e8",
          pathCount: bridge?.path_pair_count ?? 0,
          degree: nodeDegree.get(symbol) ?? 0,
        },
        classes: holding ? "holding" : "bridge",
      };
    });

    const edges = mst.subtree_edges.map((edge) => {
      const direct = heldBySymbol.has(edge.symbol_a) && heldBySymbol.has(edge.symbol_b);
      return {
        data: {
          id: edgeKey(edge.symbol_a, edge.symbol_b),
          source: edge.symbol_a,
          target: edge.symbol_b,
          symbolA: edge.symbol_a,
          symbolB: edge.symbol_b,
          correlation: edge.correlation,
          correlationLabel: correlationLabel(edge.correlation),
          distance: edge.distance,
          persistence: edge.persistence,
          confidence: edge.confidence,
          direct,
        },
        classes: `${edge.correlation >= mst.cluster_correlation_floor ? "strong" : "weak"}${direct ? " direct" : ""}`,
      };
    });

    const root = [...symbols].sort((left, right) => {
      const pathDifference = (bridgeBySymbol.get(right)?.path_pair_count ?? 0)
        - (bridgeBySymbol.get(left)?.path_pair_count ?? 0);
      if (pathDifference !== 0) return pathDifference;
      return (nodeDegree.get(right) ?? 0) - (nodeDegree.get(left) ?? 0);
    })[0];

    return { nodes, edges, root };
  }, [holdings, mst]);

  function resetGraph() {
    const current = graph.current;
    if (!current) return;
    current.elements().removeClass("faded");
    current.elements().unselect();
    current.fit(undefined, 42);
    setSelection(null);
  }

  useEffect(() => {
    if (!container.current) return;
    setSelection(null);

    const instance = cytoscape({
      container: container.current,
      elements: [...graphData.nodes, ...graphData.edges],
      style: [
        {
          selector: "node",
          style: {
            label: "data(symbol)",
            "font-family": 'Inter, "Segoe UI", sans-serif',
            "font-size": 11,
            "font-weight": 700,
            "text-wrap": "none",
            "overlay-opacity": 0,
            "transition-property": "opacity, border-width, border-color",
            "transition-duration": 160,
          },
        },
        {
          selector: "node.holding",
          style: {
            shape: "round-rectangle",
            width: "mapData(weight, 0, 0.5, 52, 78)",
            height: "mapData(weight, 0, 0.5, 34, 48)",
            "background-color": "data(color)",
            "border-width": 3,
            "border-color": "#ffffff",
            color: "#ffffff",
            "text-outline-color": "data(color)",
            "text-outline-width": 2,
          },
        },
        {
          selector: "node.bridge",
          style: {
            shape: "ellipse",
            width: "mapData(pathCount, 0, 15, 24, 45)",
            height: "mapData(pathCount, 0, 15, 24, 45)",
            "background-color": "#f8fafc",
            "border-width": 2,
            "border-color": "#82939d",
            color: "#33434c",
            "text-valign": "bottom",
            "text-margin-y": 7,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.82,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(correlation, -1, 1, 1.25, 5)",
            "line-color": "#8ba4ad",
            "curve-style": "straight",
            opacity: 0.78,
            "overlay-opacity": 0,
            "transition-property": "opacity, line-color, width",
            "transition-duration": 160,
          },
        },
        { selector: "edge.strong", style: { "line-color": "#14b8a6" } },
        { selector: "edge.weak", style: { "line-color": "#f59e0b", "line-style": "dashed" } },
        { selector: "edge.direct", style: { width: 6 } },
        {
          selector: "edge:selected",
          style: {
            label: "data(correlationLabel)",
            "font-size": 11,
            "font-weight": 700,
            color: "#172b35",
            "text-background-color": "#ffffff",
            "text-background-opacity": 1,
            "text-background-padding": "4px",
            "line-color": "#e11d48",
            width: 7,
            opacity: 1,
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 5, "border-color": "#fb7185" },
        },
        { selector: ".faded", style: { opacity: 0.12 } },
      ],
      layout: { name: "preset" },
      minZoom: 0.45,
      maxZoom: 2.2,
      wheelSensitivity: 0.18,
      autoungrabify: true,
      boxSelectionEnabled: false,
    });

    graph.current = instance;
    instance.layout({
      name: "breadthfirst",
      roots: graphData.root ? [graphData.root] : undefined,
      directed: false,
      spacingFactor: 1.45,
      padding: 42,
      animate: false,
      circle: false,
      maximal: true,
    }).run();
    instance.nodes().positions((node) => ({
      x: node.position("y"),
      y: node.position("x"),
    }));
    instance.fit(undefined, 42);

    instance.on("tap", "node", (event) => {
      const node = event.target;
      const data = node.data();
      instance.elements().addClass("faded");
      node.closedNeighborhood().removeClass("faded");
      node.select();
      setSelection({
        eyebrow: data.isHolding ? "Portfolio holding" : "Bridge stock",
        title: data.symbol,
        detail: data.isHolding
          ? `${data.weightLabel} · ${data.cluster}`
          : `Appears on ${data.pathCount} holding-to-holding path${data.pathCount === 1 ? "" : "s"}`,
        secondary: `${data.degree} direct MST connection${data.degree === 1 ? "" : "s"} in this portfolio subtree.`,
      });
    });
    instance.on("tap", "edge", (event) => {
      const edge = event.target;
      const data = edge.data();
      instance.elements().addClass("faded");
      edge.connectedNodes().add(edge).removeClass("faded");
      edge.select();
      setSelection({
        eyebrow: data.direct ? "Direct holding link" : "MST route segment",
        title: `${data.symbolA} ↔ ${data.symbolB}`,
        detail: `Correlation ${Number(data.correlation).toFixed(2)} · Mantegna distance ${Number(data.distance).toFixed(2)}`,
        secondary: `${data.correlation >= mst.cluster_correlation_floor
          ? `This edge meets the ${mst.cluster_correlation_floor.toFixed(2)} cluster threshold.`
          : `This weaker edge joins groups separated by the ${mst.cluster_correlation_floor.toFixed(2)} cluster threshold.`} ${data.persistence === null
          ? "Stability is unavailable until another compatible MST run exists."
          : `It persisted in ${(Number(data.persistence) * 100).toFixed(0)}% of compared runs (${data.confidence} confidence).`}`,
      });
    });
    instance.on("tap", (event) => {
      if (event.target === instance) resetGraph();
    });

    const resizeObserver = new ResizeObserver(() => instance.resize());
    resizeObserver.observe(container.current);
    return () => {
      resizeObserver.disconnect();
      instance.destroy();
      graph.current = null;
    };
  }, [graphData, mst.cluster_correlation_floor]);

  const bridgeCount = graphData.nodes.filter((node) => node.classes === "bridge").length;
  const weakEdgeCount = mst.subtree_edges.filter(
    (edge) => edge.correlation < mst.cluster_correlation_floor,
  ).length;

  return (
    <Box sx={{ mt: 2.5, border: "1px solid #dbe5e9", borderRadius: 2.5, overflow: "hidden" }}>
      <Box
        sx={{
          px: { xs: 2, md: 2.5 },
          py: 2,
          color: "white",
          background: "linear-gradient(115deg, #0d3444 0%, #12566a 55%, #0f766e 100%)",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: 1.5, justifyContent: "space-between" }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 750 }}>Portfolio MST map</Typography>
            <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.76)" }}>
              The smallest part of the market tree needed to connect every holding.
            </Typography>
          </Box>
          <Stack direction="row" sx={{ gap: 0.75, flexWrap: "wrap", alignItems: "center" }}>
            <Chip size="small" label={`${holdings.length} held`} sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "white" }} />
            <Chip size="small" label={`${bridgeCount} bridge${bridgeCount === 1 ? "" : "s"}`} sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "white" }} />
            <Chip size="small" label={`${mst.subtree_edges.length} links`} sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "white" }} />
            <Chip size="small" label={`${mst.stability.confidence} confidence`} sx={{ bgcolor: "rgba(255,255,255,0.15)", color: "white" }} />
          </Stack>
        </Stack>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} sx={{ minHeight: 470 }}>
        <Box sx={{ position: "relative", flex: 1, minWidth: 0, bgcolor: "#f8fbfc" }}>
          <Box
            ref={container}
            role="img"
            aria-label="Interactive minimum spanning subtree connecting the portfolio holdings"
            sx={{ width: "100%", height: { xs: 430, md: 500 } }}
          />
          <Button
            size="small"
            variant="outlined"
            onClick={resetGraph}
            className="no-print"
            sx={{ position: "absolute", top: 12, right: 12, bgcolor: "rgba(255,255,255,0.92)" }}
          >
            Reset view
          </Button>
        </Box>

        <Box sx={{ width: { md: 300 }, p: 2.5, bgcolor: "white", borderLeft: { md: "1px solid #dbe5e9" } }}>
          {selection ? (
            <Box sx={{ minHeight: 145 }}>
              <Typography variant="overline" color="text.secondary">{selection.eyebrow}</Typography>
              <Typography variant="h6" sx={{ fontWeight: 750, mb: 0.75 }}>{selection.title}</Typography>
              <Typography variant="body2">{selection.detail}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{selection.secondary}</Typography>
            </Box>
          ) : (
            <Box sx={{ minHeight: 145 }}>
              <Typography variant="overline" color="text.secondary">How to explore</Typography>
              <Typography variant="h6" sx={{ fontWeight: 750, mb: 0.75 }}>Select a stock or link</Typography>
              <Typography variant="body2" color="text.secondary">
                A selection isolates its local connections and explains why it matters. Pan, zoom, or tap the background to clear it.
              </Typography>
            </Box>
          )}

          <Box sx={{ borderTop: "1px solid #e4eaed", pt: 2, mt: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Legend</Typography>
            <LegendItem color="#0f766e" shape="rounded" label="Held stock · size shows weight" />
            <LegendItem color="#dbe4e8" shape="circle" label="Bridge stock · not held" />
            <LegendItem color="#14b8a6" label={`Correlation ≥ ${mst.cluster_correlation_floor.toFixed(2)}`} />
            <LegendItem color="#f59e0b" dashed label={`Weaker connector < ${mst.cluster_correlation_floor.toFixed(2)}`} />
          </Box>

          <Box sx={{ borderTop: "1px solid #e4eaed", pt: 2, mt: 2 }}>
            <Typography variant="subtitle2">What stands out</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {weakEdgeCount === 0
                ? "All displayed links meet the cluster threshold."
                : `${weakEdgeCount} weaker link${weakEdgeCount === 1 ? "" : "s"} connect the portfolio’s denser groups.`}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {mst.stability.reason}
            </Typography>
          </Box>
        </Box>
      </Stack>
    </Box>
  );
}

function LegendItem({
  color,
  label,
  shape,
  dashed = false,
}: {
  color: string;
  label: string;
  shape?: "rounded" | "circle";
  dashed?: boolean;
}) {
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: "center", mb: 1 }}>
      {shape ? (
        <Box sx={{ width: shape === "rounded" ? 24 : 16, height: 16, borderRadius: shape === "rounded" ? 1 : "50%", bgcolor: color, border: "1px solid #82939d", flex: "0 0 auto" }} />
      ) : (
        <Box sx={{ width: 25, borderTop: `3px ${dashed ? "dashed" : "solid"} ${color}`, flex: "0 0 auto" }} />
      )}
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  );
}
