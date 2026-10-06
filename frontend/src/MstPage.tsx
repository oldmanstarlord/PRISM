import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import cytoscape, { type Core } from "cytoscape";
import { Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useApi } from "./api";
import { ExplainPanel } from "./ExplainPanel";
import { ExplainDrawer, GlossaryTerm } from "./components";
import type { MstResponse } from "./types";

const industryPalette = [
  "#16697a",
  "#489fb5",
  "#82c0cc",
  "#ffa62b",
  "#db6400",
  "#7b2cbf",
  "#2d6a4f",
  "#bc4749",
  "#577590",
  "#6a994e",
  "#b56576",
  "#4d908e",
];

const clusterPalette = [
  "#e63946",
  "#457b9d",
  "#2a9d8f",
  "#e76f51",
  "#f4a261",
  "#9b5de5",
  "#00bbf9",
  "#00f5d4",
  "#f15bb5",
  "#fee440",
  "#3a86ff",
  "#8338ec",
];

function buildPaletteMap(items: string[], palette: string[]) {
  return Object.fromEntries(
    [...new Set(items)].sort().map((item, index) => [item, palette[index % palette.length]])
  );
}

interface SelectedNodeState {
  id: string;
  symbol: string;
  industry: string;
  degree: number;
  weighted_centrality: number | null;
  hub_rank: number | null;
  cluster_id: string | null;
}

export function MstPageContent() {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);

  const [variant, setVariant] = useState<"raw" | "residual">("raw");
  const [colorMode, setColorMode] = useState<"industry" | "cluster">("industry");
  const [selectedNode, setSelectedNode] = useState<SelectedNodeState | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<{ title: string; detail: string } | null>(null);
  const [explainPath, setExplainPath] = useState("");
  const [pairA, setPairA] = useState("");
  const [pairB, setPairB] = useState("");

  const {
    data,
    error,
    isLoading,
  } = useApi<MstResponse>(`/mst/latest?variant=${variant}`);

  useEffect(() => {
    if (!data || !container.current) return;

    const colorByIndustry = buildPaletteMap(
      data.nodes.map((n) => n.industry),
      industryPalette
    );
    const colorByCluster = buildPaletteMap(
      data.nodes.map((n) => n.cluster_id || "Unclustered"),
      clusterPalette
    );

    const degreeMap = Object.fromEntries(data.nodes.map((node) => [node.id, node.degree || 0]));
    if (Object.values(degreeMap).every((d) => d === 0)) {
      for (const edge of data.edges) {
        degreeMap[edge.source] = (degreeMap[edge.source] || 0) + 1;
        degreeMap[edge.target] = (degreeMap[edge.target] || 0) + 1;
      }
    }

    graph.current = cytoscape({
      container: container.current,
      elements: [
        ...data.nodes.map((node) => ({
          data: {
            ...node,
            degree: degreeMap[node.id] || 1,
            color:
              colorMode === "industry"
                ? colorByIndustry[node.industry]
                : colorByCluster[node.cluster_id || "Unclustered"],
          },
        })),
        ...data.edges.map((edge) => ({
          data: { id: `${edge.source}-${edge.target}`, ...edge },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(symbol)",
            width: "mapData(degree, 1, 10, 20, 52)",
            height: "mapData(degree, 1, 10, 20, 52)",
            "font-size": 9,
            "text-valign": "bottom",
            "text-margin-y": 4,
            color: "#23343d",
            "font-weight": "bold",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(correlation, -1, 1, 0.6, 3.5)",
            "line-color": "#a8b6bd",
            opacity: 0.75,
            "curve-style": "straight",
          },
        },
        {
          selector: ":selected",
          style: {
            "border-width": 4,
            "border-color": "#e76f51",
            "line-color": "#e76f51",
            opacity: 1,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        randomize: false,
        nodeRepulsion: () => 850000,
        idealEdgeLength: () => 75,
      },
      minZoom: 0.2,
      maxZoom: 3,
    });

    graph.current.on("tap", "node", (event) => {
      const nodeData = event.target.data();
      setSelectedNode({
        id: nodeData.id,
        symbol: nodeData.symbol,
        industry: nodeData.industry,
        degree: nodeData.degree,
        weighted_centrality: nodeData.weighted_centrality ?? null,
        hub_rank: nodeData.hub_rank ?? null,
        cluster_id: nodeData.cluster_id ?? null,
      });
      setSelectedEdge(null);
      setExplainPath(`/explain/mst/node/${encodeURIComponent(nodeData.symbol)}`);
    });

    graph.current.on("tap", "edge", (event) => {
      const edge = event.target.data();
      setSelectedEdge({
        title: `${edge.symbol_a} - ${edge.symbol_b}`,
        detail: `Correlation ${Number(edge.correlation).toFixed(3)} / distance ${Number(edge.distance).toFixed(3)} / ${edge.paired_observations} paired returns (Rank #${edge.edge_rank})`,
      });
      setExplainPath(
        `/explain/mst/edge?run_id=${encodeURIComponent(data.run.id)}&a=${encodeURIComponent(edge.symbol_a)}&b=${encodeURIComponent(edge.symbol_b)}`
      );
    });

    return () => {
      graph.current?.destroy();
      graph.current = null;
    };
  }, [data, colorMode]);

  // Handle clicking a cluster peer chip to select and center on that node
  const handleSelectPeer = (peerSymbol: string) => {
    if (!graph.current || !data) return;
    const targetNode = data.nodes.find((n) => n.symbol === peerSymbol);
    if (!targetNode) return;

    setSelectedNode({
      id: targetNode.id,
      symbol: targetNode.symbol,
      industry: targetNode.industry,
      degree: targetNode.degree || 1,
      weighted_centrality: targetNode.weighted_centrality ?? null,
      hub_rank: targetNode.hub_rank ?? null,
      cluster_id: targetNode.cluster_id ?? null,
    });
    setSelectedEdge(null);

    const cyNode = graph.current.$id(targetNode.id);
    if (cyNode.length) {
      graph.current.$(":selected").unselect();
      cyNode.select();
      graph.current.animate({ center: { eles: cyNode }, zoom: 1.2 }, { duration: 300 });
    }
  };

  const clusterPeers = selectedNode && data
    ? data.nodes
        .filter((n) => n.cluster_id === selectedNode.cluster_id && n.symbol !== selectedNode.symbol)
        .map((n) => n.symbol)
    : [];

  const incidentEdges = selectedNode && data
    ? data.edges.filter(
        (e) => e.symbol_a === selectedNode.symbol || e.symbol_b === selectedNode.symbol
      )
    : [];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Button component={Link} to="/" sx={{ alignSelf: "flex-start" }}>
          Back to sector divergence
        </Button>

        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
          }}
        >
          <Box>
            <Typography variant="h3" component="h1" sx={{ fontWeight: 700 }}>
              Correlation Minimum Spanning Tree
            </Typography>
            <Typography color="text.secondary">
              Descriptive network topology and co-movement subgraphs across NIFTY 200 stocks.
            </Typography>
          </Box>

          {data && (
            <Chip
              label={`Stability: ${data.stability_grade || "N/A"} (${
                data.edge_persistence ? (data.edge_persistence * 100).toFixed(1) + "%" : "Pending"
              } persistence)`}
              color={
                data.stability_grade === "HIGH"
                  ? "success"
                  : data.stability_grade === "MEDIUM"
                  ? "warning"
                  : "default"
              }
              sx={{ fontWeight: "bold", fontSize: "0.85rem", py: 1 }}
            />
          )}
        </Stack>

        {/* Controls: Variant selector & Color mode toggle */}
        <Paper sx={{ p: 2, display: "flex", gap: 3, flexWrap: "wrap", alignItems: "center" }}>
          <Box>
            <Typography variant="caption" sx={{ display: "block", mb: 0.5, fontWeight: "bold" }}>
              TREE VARIANT
            </Typography>
            <ToggleButtonGroup
              size="small"
              value={variant}
              exclusive
              onChange={(_, next) => {
                if (next) {
                  setVariant(next);
                  setSelectedNode(null);
                  setSelectedEdge(null);
                }
              }}
            >
              <ToggleButton value="raw">Raw Returns MST</ToggleButton>
              <ToggleButton value="residual">Residual Variant (Market Neutral)</ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <Box>
            <Typography variant="caption" sx={{ display: "block", mb: 0.5, fontWeight: "bold" }}>
              COLOR ENCODING
            </Typography>
            <ToggleButtonGroup
              size="small"
              value={colorMode}
              exclusive
              onChange={(_, next) => {
                if (next) setColorMode(next);
              }}
            >
              <ToggleButton value="industry">Industry</ToggleButton>
              <ToggleButton value="cluster">Cluster (k-cut forest)</ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <Box sx={{ minWidth: { xs: "100%", md: 430 } }}>
            <Typography variant="caption" sx={{ display: "block", mb: 0.5, fontWeight: "bold" }}>
              RELATIONSHIP BETWEEN TWO STOCKS
            </Typography>
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label="Stock A"
                value={pairA}
                onChange={(event) => setPairA(event.target.value.toUpperCase())}
              />
              <TextField
                size="small"
                label="Stock B"
                value={pairB}
                onChange={(event) => setPairB(event.target.value.toUpperCase())}
              />
              <Button
                variant="contained"
                disabled={!pairA.trim() || !pairB.trim() || pairA.trim() === pairB.trim()}
                onClick={() => setExplainPath(
                  `/explain/mst/pair?a=${encodeURIComponent(pairA.trim())}&b=${encodeURIComponent(pairB.trim())}`
                )}
              >
                Explain
              </Button>
            </Stack>
          </Box>
        </Paper>

        {isLoading && (
          <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Alert severity="warning">
            {error.message}. Compute the MST runs and diagnostic jobs to populate this view.
          </Alert>
        )}

        {data && (
          <>
            {/* Top Stat Cards */}
            <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 2 }}>
              <Paper sx={{ p: 2.5, flex: 1 }}>
                <Typography variant="overline">Rolling Window</Typography>
                <Typography variant="h6">
                  {data.run.window_start} to {data.run.window_end}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Variant: <strong>{data.variant || "raw"}</strong>
                </Typography>
              </Paper>

              <Paper sx={{ p: 2.5, flex: 1 }}>
                <Typography variant="overline">Topology & Structure</Typography>
                <Typography variant="h6">
                  {data.run.included_symbol_count} nodes / {data.run.edge_count} edges
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Connected: {data.run.is_connected ? "yes" : "no"} | Acyclic:{" "}
                  {data.run.is_acyclic ? "yes" : "no"}
                </Typography>
              </Paper>

              <Paper sx={{ p: 2.5, flex: 1 }}>
                <Typography variant="overline">Segmentation</Typography>
                <Typography variant="h6">
                  {data.clusters_count ? `${data.clusters_count} Clusters` : "N/A"}
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Formed via deterministic k-longest edge cuts
                </Typography>
              </Paper>
            </Stack>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                How to read edge weights
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <GlossaryTerm termKey="correlation">Correlation</GlossaryTerm> is transformed into
                <GlossaryTerm termKey="correlation_distance"> distance</GlossaryTerm> using
                d = √(2 × (1 − ρ)). Smaller distance means stronger historical co-movement.
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap" }}>
                {(data.distance_scale ?? []).map((item) => (
                  <Chip
                    key={item.correlation}
                    label={`ρ ${item.correlation.toFixed(1)} → d ${item.distance.toFixed(2)} (${item.label})`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Stack>
              <Stack direction="row" spacing={2} sx={{ mt: 1, alignItems: "center" }}>
                {(data.edge_thickness_legend ?? []).map((item) => (
                  <Box key={item.correlation} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                    <Box sx={{ width: 40, borderTop: `${item.width}px solid`, borderColor: "grey.600" }} />
                    <Typography variant="caption">ρ {item.correlation.toFixed(1)}</Typography>
                  </Box>
                ))}
              </Stack>
            </Paper>

            {/* Edge details prompt */}
            {selectedEdge && (
              <Alert severity="info" onClose={() => setSelectedEdge(null)}>
                <strong>{selectedEdge.title}</strong>: {selectedEdge.detail}
              </Alert>
            )}

            {/* Interactive Graph Container & Node Side Panel */}
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: selectedNode ? { xs: "1fr", lg: "3fr 1.2fr" } : "1fr",
                gap: 2,
              }}
            >
              <Paper sx={{ overflow: "hidden" }}>
                <Box
                  ref={container}
                  aria-label="correlation minimum spanning tree"
                  sx={{ width: "100%", height: { xs: 560, md: 740 }, bgcolor: "#fff" }}
                />
              </Paper>

              {/* Node Side Panel */}
              {selectedNode && (
                <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
                  <CardHeader
                    title={selectedNode.symbol}
                    subheader={selectedNode.industry}
                    action={
                      <Button size="small" onClick={() => setSelectedNode(null)}>
                        Close
                      </Button>
                    }
                  />
                  <Divider />
                  <CardContent sx={{ flex: 1, overflowY: "auto" }}>
                    <Stack spacing={2.5}>
                      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                        <Chip
                          label={`Degree: ${selectedNode.degree}`}
                          color="primary"
                          size="small"
                        />
                        {selectedNode.hub_rank !== null && (
                          <Chip
                            label={`Hub Rank: #${selectedNode.hub_rank}`}
                            color="secondary"
                            size="small"
                          />
                        )}
                        {selectedNode.weighted_centrality !== null && (
                          <Chip
                            label={`Centrality: ${selectedNode.weighted_centrality.toFixed(2)}`}
                            variant="outlined"
                            size="small"
                          />
                        )}
                        {selectedNode.cluster_id && (
                          <Chip
                            label={`Cluster: ${selectedNode.cluster_id}`}
                            color="info"
                            size="small"
                          />
                        )}
                      </Box>

                      {/* Cluster Peers */}
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: "bold", mb: 1 }}>
                          Cluster Peers ({clusterPeers.length})
                        </Typography>
                        {clusterPeers.length > 0 ? (
                          <Box sx={{ display: "flex", gap: 0.8, flexWrap: "wrap" }}>
                            {clusterPeers.map((peer) => (
                              <Chip
                                key={peer}
                                label={peer}
                                size="small"
                                onClick={() => handleSelectPeer(peer)}
                                sx={{ cursor: "pointer" }}
                              />
                            ))}
                          </Box>
                        ) : (
                          <Typography variant="caption" color="text.secondary">
                            Isolated node or single-stock cluster
                          </Typography>
                        )}
                      </Box>

                      <Divider />

                      {/* Incident Connections */}
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: "bold", mb: 1 }}>
                          Tree Incident Edges ({incidentEdges.length})
                        </Typography>
                        <TableContainer component={Paper} variant="outlined">
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell>Neighbor</TableCell>
                                <TableCell align="right">Corr</TableCell>
                                <TableCell align="right">Dist</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {incidentEdges.map((e) => {
                                const neighbor =
                                  e.symbol_a === selectedNode.symbol ? e.symbol_b : e.symbol_a;
                                return (
                                  <TableRow
                                    key={neighbor}
                                    hover
                                    sx={{ cursor: "pointer" }}
                                    onClick={() => handleSelectPeer(neighbor)}
                                  >
                                    <TableCell sx={{ fontWeight: "bold" }}>{neighbor}</TableCell>
                                    <TableCell align="right">
                                      {e.correlation !== null
                                        ? Number(e.correlation).toFixed(2)
                                        : "N/A"}
                                    </TableCell>
                                    <TableCell align="right">
                                      {Number(e.distance).toFixed(2)}
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              )}
            </Box>

            {/* Explain Panel with Non-Causal Limitations */}
            <ExplainPanel
              title="MST Methodology & Non-Causal Limitations"
              limitations={data.limitations}
              sparseEdgesCount={data.run.edge_count}
            />
            <ExplainDrawer
              open={explainPath.length > 0}
              path={explainPath}
              onClose={() => setExplainPath("")}
            />
          </>
        )}
      </Stack>
    </Container>
  );
}

const defaultQueryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: Infinity } },
});

export default function MstPage() {
  return (
    <QueryClientProvider client={defaultQueryClient}>
      <MstPageContent />
    </QueryClientProvider>
  );
}
