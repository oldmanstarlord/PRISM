import { resolveTerminalStyles, resolveTerminalColor, SERIES } from "./terminalTokens";
import { useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import cytoscape, { type Core } from "cytoscape";
import { Link, useNavigate } from "react-router-dom";

import { getDecisionsCountMap, getNotesCountMap } from "./journalStorage";
import type { PortfolioAnalysisResponse } from "./types";

type MstSummary = PortfolioAnalysisResponse["mst"];
type Holding = PortfolioAnalysisResponse["holdings"][number];

type Selection = {
  eyebrow: string;
  title: string;
  detail: string;
  secondary: string;
  symbol?: string;
  isNode?: boolean;
  isHolding?: boolean;
  riskMetrics?: {
    volatility: number;
    marginalRisk: number;
    riskContribution: number;
    divergence: number | null;
  } | null;
};

const clusterColors = SERIES.map(resolveTerminalColor);

function edgeKey(symbolA: string, symbolB: string) {
  return [symbolA, symbolB].sort().join("::");
}

function correlationLabel(value: number) {
  return `ρ ${value.toFixed(2)}`;
}

export default function PortfolioMstGraph({ mst, holdings }: { mst: MstSummary; holdings: Holding[] }) {
  const navigate = useNavigate();
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [notesCountMap, setNotesCountMap] = useState<Record<string, number>>({});
  const [decisionsCountMap, setDecisionsCountMap] = useState<Record<string, number>>({});

  useEffect(() => {
    void getNotesCountMap().then(setNotesCountMap).catch(() => { });
    void getDecisionsCountMap().then(setDecisionsCountMap).catch(() => { });
  }, []);

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
          color: cluster?.color ?? "var(--line)",
          pathCount: bridge?.path_pair_count ?? 0,
          degree: nodeDegree.get(symbol) ?? 0,
          volatility: holding?.annualized_volatility ?? null,
          marginalRisk: holding?.marginal_risk ?? null,
          riskContribution: holding?.risk_contribution ?? null,
          divergence: holding?.divergence_20d ?? null,
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
      style: resolveTerminalStyles([
        {
          selector: "node",
          style: {
            label: "data(symbol)",
            "font-family": "var(--font-data)",
            "font-size": "var(--text-data)",
            "font-weight": 600,
            "text-wrap": "none",
            "overlay-opacity": 0,
            "transition-property": "none",
            "transition-duration": 0,
          },
        },
        {
          selector: "node.holding",
          style: {
            shape: "rectangle",
            width: "mapData(weight, 0, 0.5, 52, 78)",
            height: "mapData(weight, 0, 0.5, 34, 48)",
            "background-color": "data(color)",
            "border-width": 1,
            color: "var(--white)",
            "text-outline-color": "data(color)",
            "text-outline-width": 0,
          },
        },
        {
          selector: "node.bridge",
          style: {
            shape: "rectangle",
            width: "mapData(pathCount, 0, 15, 24, 45)",
            height: "mapData(pathCount, 0, 15, 24, 45)",
            "background-color": "var(--line)",
            "border-width": 1,
            color: "var(--white)",
            "text-valign": "bottom",
            "text-margin-y": 7,
            "text-background-color": "var(--bg)",
            "text-background-opacity": 1,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(correlation, -1, 1, 1.25, 5)",
            "line-color": "var(--gray)",
            "curve-style": "straight",
            opacity: 1,
            "overlay-opacity": 0,
            "transition-property": "none",
            "transition-duration": 0,
          },
        },
        { selector: "edge.strong", style: { "line-color": "var(--up)" } },
        { selector: "edge.weak", style: { "line-color": "var(--amber)", "line-style": "solid" } },
        { selector: "edge.direct", style: { width: 1 } },
        {
          selector: "edge:selected",
          style: {
            label: "data(correlationLabel)",
            "font-size": "var(--text-data)",
            "font-weight": 600,
            color: "var(--white)",
            "text-background-color": "var(--bg)",
            "text-background-opacity": 1,
            "text-background-padding": "4px",
            "line-color": "var(--down)",
            width: 1,
            opacity: 1,
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 1, "border-color": "var(--up)" },
        },
        { selector: "node.faded", style: { "background-color": "var(--gray)", color: "var(--gray)" } }, { selector: "edge.faded", style: { "line-color": "var(--line)" } },
      ]),
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
        symbol: data.symbol,
        isNode: true,
        isHolding: Boolean(data.isHolding),
        riskMetrics: data.isHolding
          ? {
            volatility: data.volatility,
            marginalRisk: data.marginalRisk,
            riskContribution: data.riskContribution,
            divergence: data.divergence,
          }
          : null,
      });
    });
    instance.on("dbltap", "node", (event) => {
      const sym = event.target.data()?.symbol;
      if (sym) {
        navigate(`/companies/${sym}`);
      }
    });
    instance.on("tap", "edge", (event) => {
      const edge = event.target;
      const data = edge.data();
      instance.elements().addClass("faded");
      edge.connectedNodes().add(edge).removeClass("faded");
      edge.select();
      setSelection({
        eyebrow: data.direct ? "Direct holding link" : "MST route segment",
        title: `${data.symbolA} / ${data.symbolB}`,
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
  }, [graphData, mst.cluster_correlation_floor, navigate]);

  const bridgeCount = graphData.nodes.filter((node) => node.classes === "bridge").length;
  const weakEdgeCount = mst.subtree_edges.filter(
    (edge) => edge.correlation < mst.cluster_correlation_floor,
  ).length;

  return (
    <Box sx={{ mt: "var(--space-3)", borderRadius: "var(--radius)", overflow: "hidden", boxShadow: "none" }}>
      <Box
        sx={{
          px: { xs: 2, md: 2.5 },
          py: "var(--space-2)",
          color: "var(--white)",
          bgcolor: "var(--line)",
          borderBottom: "var(--border-width) solid var(--gray)",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: "var(--space-2)", justifyContent: "space-between" }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>Portfolio MST map</Typography>
            <Typography variant="body2" sx={{ color: "var(--gray)" }}>
              The smallest part of the market tree needed to connect every holding.
            </Typography>
          </Box>
          <Stack direction="row" sx={{ gap: "var(--space-1)", flexWrap: "wrap", alignItems: "center" }}>
            <Chip size="small" label={`${holdings.length} held`} sx={{ bgcolor: "var(--bg)", color: "var(--white)", borderRadius: "var(--radius)", fontWeight: 600, border: "var(--border-width) solid var(--gray)" }} />
            <Chip size="small" label={`${bridgeCount} bridge${bridgeCount === 1 ? "" : "s"}`} sx={{ bgcolor: "var(--bg)", color: "var(--white)", borderRadius: "var(--radius)", fontWeight: 600, border: "var(--border-width) solid var(--gray)" }} />
            <Chip size="small" label={`${mst.subtree_edges.length} links`} sx={{ bgcolor: "var(--bg)", color: "var(--white)", borderRadius: "var(--radius)", fontWeight: 600, border: "var(--border-width) solid var(--gray)" }} />
            <Chip size="small" label={`${mst.stability.confidence} confidence`} sx={{ bgcolor: "var(--bg)", color: "var(--white)", borderRadius: "var(--radius)", fontWeight: 600, border: "var(--border-width) solid var(--gray)" }} />
          </Stack>
        </Stack>
      </Box>

      <Stack direction={{ xs: "column", md: "row" }} sx={{ minHeight: 470 }}>
        <Box sx={{ position: "relative", flex: 1, minWidth: 0, bgcolor: "var(--bg)" }}>
          <Box
            ref={container}
            role="img"
            aria-label="Interactive minimum spanning subtree connecting the portfolio holdings"
            sx={{ width: "100%", height: { xs: 430, md: 500 } }}
          />
          <Button
            size="small"
            onClick={resetGraph}
            className="no-print"
            sx={{
              position: "absolute",
              top: 12,
              right: 12,
              bgcolor: "var(--line)",
              color: "var(--white)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--line)" },
            }}
          >
            Reset view
          </Button>
        </Box>

        <Box sx={{ width: { md: 320 }, p: "var(--space-3)", bgcolor: "var(--bg)", boxShadow: "none" }}>
          {selection ? (
            <Box sx={{ minHeight: 145 }}>
              <Typography variant="overline" color="text.secondary">{selection.eyebrow}</Typography>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: "var(--space-1)", color: "var(--white)" }}>{selection.title}</Typography>
              <Typography variant="body2">{selection.detail}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: "var(--space-1)" }}>{selection.secondary}</Typography>

              {selection.isNode && selection.symbol && (
                <Box sx={{ mt: "var(--space-2)" }}>
                  <Stack direction="row" spacing={0.75} sx={{ mb: "var(--space-1)", flexWrap: "wrap" }}>
                    <Chip
                      size="small"
                      label={`${notesCountMap[selection.symbol] ?? 0} notes`}
                      sx={{
                        fontSize: "var(--text-title)",
                        borderRadius: "var(--radius)",
                        bgcolor: (notesCountMap[selection.symbol] ?? 0) > 0 ? "var(--line)" : "var(--line)",
                        color: (notesCountMap[selection.symbol] ?? 0) > 0 ? "var(--up)" : "var(--white)",
                        fontWeight: 600,
                      }}
                    />
                    <Chip
                      size="small"
                      label={`${decisionsCountMap[selection.symbol] ?? 0} decisions`}
                      sx={{
                        fontSize: "var(--text-title)",
                        borderRadius: "var(--radius)",
                        bgcolor: (decisionsCountMap[selection.symbol] ?? 0) > 0 ? "var(--line)" : "var(--line)",
                        color: (decisionsCountMap[selection.symbol] ?? 0) > 0 ? "var(--up)" : "var(--white)",
                        fontWeight: 600,
                      }}
                    />
                  </Stack>

                  {selection.riskMetrics && (
                    <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)", mb: "var(--space-2)", boxShadow: "none" }}>
                      <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block", mb: "var(--space-1)" }}>
                        Risk Profile
                      </Typography>
                      <Stack spacing={0.35}>
                        <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-title)" }}>
                          <span style={{ color: "var(--gray)" }}>Ann. Volatility:</span>
                          <strong style={{ fontFamily: "var(--font-data)", color: "var(--white)" }}>{(selection.riskMetrics.volatility * 100).toFixed(1)}%</strong>
                        </Box>
                        <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-title)" }}>
                          <span style={{ color: "var(--gray)" }}>Marginal Risk:</span>
                          <strong style={{ fontFamily: "var(--font-data)", color: "var(--white)" }}>{(selection.riskMetrics.marginalRisk * 100).toFixed(2)}%</strong>
                        </Box>
                        <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-title)" }}>
                          <span style={{ color: "var(--gray)" }}>Risk Share:</span>
                          <strong style={{ fontFamily: "var(--font-data)", color: "var(--white)" }}>{(selection.riskMetrics.riskContribution * 100).toFixed(1)}%</strong>
                        </Box>
                        {selection.riskMetrics.divergence !== null && (
                          <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-title)" }}>
                            <span style={{ color: "var(--gray)" }}>20D Divergence:</span>
                            <strong style={{ fontFamily: "var(--font-data)", color: "var(--white)" }}>{selection.riskMetrics.divergence.toFixed(2)}σ</strong>
                          </Box>
                        )}
                      </Stack>
                    </Box>
                  )}

                  <Button
                    component={Link}
                    to={`/companies/${selection.symbol}`}
                    size="small"
                    variant="contained"
                    fullWidth
                    sx={{
                      textTransform: "none",
                      bgcolor: "var(--up)", color: "var(--line)",
                      borderRadius: "var(--radius)",
                      fontSize: "var(--text-title)",
                      fontWeight: 600,
                      boxShadow: "none",
                      "&:hover": { bgcolor: "var(--up)" },
                    }}
                  >
                    Open Company Details ({selection.symbol}) /
                  </Button>
                </Box>
              )}
            </Box>
          ) : (
            <Box sx={{ minHeight: 145 }}>
              <Typography variant="overline" color="text.secondary">How to explore</Typography>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: "var(--space-1)", color: "var(--white)" }}>Select a stock or link</Typography>
              <Typography variant="body2" color="text.secondary">
                A selection isolates its local connections and explains why it matters. Pan, zoom, or tap the background to clear it.
              </Typography>
            </Box>
          )}

          <Box sx={{ pt: "var(--space-2)", mt: "var(--space-1)" }}>
            <Typography variant="subtitle2" sx={{ mb: "var(--space-1)", fontWeight: 600, color: "var(--white)" }}>Legend</Typography>
            <LegendItem color="var(--up)" shape="square" label="Held stock · size shows weight" />
            <LegendItem color="var(--line)" shape="square" label="Bridge stock · not held" />
            <LegendItem color="var(--up)" label={`Correlation ≥ ${mst.cluster_correlation_floor.toFixed(2)}`} />
            <LegendItem color="var(--amber)" dashed label={`Weaker connector < ${mst.cluster_correlation_floor.toFixed(2)}`} />
          </Box>

          <Box sx={{ pt: "var(--space-2)", mt: "var(--space-1)" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>What stands out</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: "var(--space-1)" }}>
              {weakEdgeCount === 0
                ? "All displayed links meet the cluster threshold."
                : `${weakEdgeCount} weaker link${weakEdgeCount === 1 ? "" : "s"} connect the portfolio’s denser groups.`}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: "var(--space-1)" }}>
              {mst.stability.reason}
            </Typography>
            <Typography variant="caption" sx={{ display: "block", mt: "var(--space-2)", color: "var(--amber)" }}>
              <strong>Topological Invariants:</strong> Spanning tree retains exactly N-1 edges from N(N-1)/2 pairs using Mantegna distance d = √(2(1 - ρ)) ∈ [0, 2]. Tree isolates ultrametric connectivity while discarding cycles. It visualizes empirical co-movement and does not imply causation or lead-lag relationships.
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
}: {
  color: string;
  label: string;
  shape?: "square";
  dashed?: boolean;
}) {
  return (
    <Stack direction="row" sx={{ gap: "var(--space-1)", alignItems: "center", mb: "var(--space-1)" }}>
      {shape ? (
        <Box sx={{ width: 16, height: 16, borderRadius: "var(--radius)", bgcolor: color, flex: "0 0 auto", boxShadow: "none" }} />
      ) : (
        <Box sx={{ width: 25, height: 0, borderTop: `var(--border-width) solid ${color}`, flex: "0 0 auto" }} />
      )}
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  );
}
