import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import cytoscape, { type Core } from "cytoscape";
import { Link } from "react-router-dom";

import AppShell from "./AppShell";
import { fetchJson } from "./api";
import { CorrelationMstExplainer } from "./PrismExplainer";
import { getDecisionsCountMap, getNotesCountMap } from "./journalStorage";
import type { MstResponse } from "./types";

const clusterColors = [
  "#1F6F78", // deep teal
  "#6B3F69", // plum
  "#3F5B7A", // slate blue
  "#A0522D", // clay
  "#6B7A2A", // olive
  "#8A5A00", // dark ochre
  "#144e54",
  "#4a2d48",
  "#2a3d53",
  "#733b20",
];

function industryColors(industries: string[]) {
  return Object.fromEntries(
    [...new Set(industries)].sort().map((industry, index) => [industry, clusterColors[index % clusterColors.length]])
  );
}

export default function MstPage() {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const [data, setData] = useState<MstResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ title: string; detail: string; symbol?: string; isNode?: boolean } | null>(null);
  const [notesCountMap, setNotesCountMap] = useState<Record<string, number>>({});
  const [decisionsCountMap, setDecisionsCountMap] = useState<Record<string, number>>({});

  useEffect(() => {
    void getNotesCountMap().then(setNotesCountMap).catch(() => { });
    void getDecisionsCountMap().then(setDecisionsCountMap).catch(() => { });
  }, []);

  function resetGraph() {
    if (!graph.current) return;
    graph.current.elements().removeClass("faded");
    graph.current.elements().unselect();
    graph.current.fit(undefined, 35);
    setSelected(null);
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MstResponse>("/mst/latest", controller.signal).then(setData).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "Unable to load MST");
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!data || !container.current) return;
    const colorByIndustry = industryColors(data.nodes.map((node) => node.industry));
    const degree = Object.fromEntries(data.nodes.map((node) => [node.id, 0]));
    for (const edge of data.edges) { degree[edge.source] += 1; degree[edge.target] += 1; }
    graph.current = cytoscape({
      container: container.current,
      elements: [
        ...data.nodes.map((node) => ({ data: { ...node, degree: degree[node.id], color: colorByIndustry[node.industry] } })),
        ...data.edges.map((edge) => ({ data: { id: `${edge.source}-${edge.target}`, ...edge } })),
      ],
      style: [
        {
          selector: "node",
          style: {
            shape: "rectangle",
            "background-color": "data(color)",
            label: "data(symbol)",
            width: "mapData(degree, 1, 8, 22, 46)",
            height: "mapData(degree, 1, 8, 16, 32)",
            "font-size": 9,
            "font-weight": 700,
            "font-family": 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            "text-valign": "bottom",
            "text-margin-y": 4,
            color: "#292D2A",
            "text-background-color": "#F9EBD7",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(correlation, -1, 1, 0.75, 3.5)",
            "line-color": "rgba(41,45,42,0.30)",
            opacity: 0.75,
            "curve-style": "straight",
          },
        },
        {
          selector: ":selected",
          style: {
            "border-width": 3,
            "border-color": "#046A38",
            "line-color": "#046A38",
            width: 4,
            opacity: 1,
          },
        },
        { selector: ".faded", style: { opacity: 0.12 } },
      ],
      layout: { name: "cose", animate: false, randomize: false, nodeRepulsion: () => 800000, idealEdgeLength: () => 70 },
      minZoom: 0.2,
      maxZoom: 3,
    });
    graph.current.on("tap", "node", (event) => {
      const node = event.target;
      const nodeData = node.data();
      graph.current?.elements().addClass("faded");
      node.closedNeighborhood().removeClass("faded");
      node.select();
      setSelected({
        title: nodeData.symbol,
        detail: `${nodeData.industry} · ${nodeData.degree} MST connection${nodeData.degree === 1 ? "" : "s"}`,
        symbol: nodeData.symbol,
        isNode: true,
      });
    });
    graph.current.on("tap", "edge", (event) => {
      const edge = event.target;
      const edgeData = edge.data();
      graph.current?.elements().addClass("faded");
      edge.connectedNodes().add(edge).removeClass("faded");
      edge.select();
      setSelected({
        title: `${edgeData.symbol_a} ↔ ${edgeData.symbol_b}`,
        detail: `Correlation ${Number(edgeData.correlation).toFixed(3)} · distance ${Number(edgeData.distance).toFixed(3)} · ${edgeData.paired_observations} paired returns`,
        isNode: false,
      });
    });
    graph.current.on("tap", (event) => {
      if (event.target === graph.current) {
        resetGraph();
      }
    });

    const handleResize = () => {
      if (graph.current) {
        graph.current.resize();
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      graph.current?.destroy();
      graph.current = null;
    };
  }, [data]);

  return (
    <AppShell subtitle="Market Correlation Minimum Spanning Tree">
      <Stack spacing={2.5}>
        <Box>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "#292D2A" }}>
            Correlation minimum spanning tree
          </Typography>
          <Typography color="text.secondary">
            The sparsest tree connecting eligible NIFTY 200 stocks by return co-movement.
          </Typography>
        </Box>
        {!data && !error && (
          <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
            <CircularProgress />
          </Box>
        )}
        {error && <Alert severity="warning">{error}. Apply the Layer 2 migration and run the MST calculation job.</Alert>}
        {data && (
          <>
            <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: 2 }}>
              <Paper sx={{ p: 2.5, flex: 1, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Typography variant="overline" color="text.secondary">Window</Typography>
                <Typography variant="h6" sx={{ color: "#292D2A", fontWeight: 700 }}>{data.run.window_start} to {data.run.window_end}</Typography>
              </Paper>
              <Paper sx={{ p: 2.5, flex: 1, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Typography variant="overline" color="text.secondary">Validated topology</Typography>
                <Typography variant="h6" sx={{ color: "#292D2A", fontWeight: 700 }}>{data.run.included_symbol_count} nodes / {data.run.edge_count} edges</Typography>
                <Typography color="text.secondary" variant="body2">
                  Connected: {data.run.is_connected ? "yes" : "no"} / Acyclic: {data.run.is_acyclic ? "yes" : "no"}
                </Typography>
              </Paper>
              <Paper sx={{ p: 2.5, flex: 1, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Typography variant="overline" color="text.secondary">Exclusions</Typography>
                <Typography variant="h6" sx={{ color: "#292D2A", fontWeight: 700 }}>{data.run.exclusions.length}</Typography>
                <Typography color="text.secondary" variant="body2">No missing values were imputed</Typography>
              </Paper>
            </Stack>
            {selected && (
              <Alert
                severity="info"
                onClose={resetGraph}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  borderRadius: 0,
                  border: "none",
                  boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
                  "& .MuiAlert-message": { width: "100%" },
                }}
              >
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, width: "100%", gap: 1 }}
                >
                  <Box>
                    <strong>{selected.title}</strong>: {selected.detail}
                    {selected.isNode && selected.symbol && (
                      <Stack direction="row" spacing={0.75} sx={{ mt: 0.75, flexWrap: "wrap" }}>
                        <Chip
                          size="small"
                          label={`${notesCountMap[selected.symbol] ?? 0} notes`}
                          sx={{
                            borderRadius: 0,
                            border: "none",
                            fontSize: "0.72rem",
                            bgcolor: (notesCountMap[selected.symbol] ?? 0) > 0 ? "#DCE9DE" : "#E3D7C4",
                            color: (notesCountMap[selected.symbol] ?? 0) > 0 ? "#046A38" : "#292D2A",
                          }}
                        />
                        <Chip
                          size="small"
                          label={`${decisionsCountMap[selected.symbol] ?? 0} decisions`}
                          sx={{
                            borderRadius: 0,
                            border: "none",
                            fontSize: "0.72rem",
                            bgcolor: (decisionsCountMap[selected.symbol] ?? 0) > 0 ? "#DCE9DE" : "#E3D7C4",
                            color: (decisionsCountMap[selected.symbol] ?? 0) > 0 ? "#046A38" : "#292D2A",
                          }}
                        />
                      </Stack>
                    )}
                  </Box>
                  {selected.isNode && selected.symbol && (
                    <Button
                      component={Link}
                      to={`/companies/${selected.symbol}`}
                      size="small"
                      variant="contained"
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        textTransform: "none",
                        fontSize: "0.78rem",
                        bgcolor: "#046A38",
                        color: "#F9EBD7",
                        boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                        "&:hover": { bgcolor: "#034d28" },
                        flexShrink: 0,
                      }}
                    >
                      Open {selected.symbol} Details →
                    </Button>
                  )}
                </Stack>
              </Alert>
            )}
            <Paper sx={{ overflow: "hidden", borderRadius: 0, border: "none", position: "relative", boxShadow: "0 10px 28px rgba(41,45,42,0.18)" }}>
              <Button
                size="small"
                onClick={resetGraph}
                className="no-print"
                sx={{
                  position: "absolute",
                  top: 12,
                  right: 12,
                  zIndex: 10,
                  bgcolor: "#E3D7C4",
                  color: "#292D2A",
                  borderRadius: 0,
                  border: "none",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                  textTransform: "none",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  "&:hover": { bgcolor: "#d5c7b2" },
                }}
              >
                Reset view
              </Button>
              <Box
                ref={container}
                aria-label="correlation minimum spanning tree"
                sx={{
                  width: "100%",
                  height: { xs: 520, md: 680, lg: 760 },
                  bgcolor: "#F9EBD7",
                }}
              />
            </Paper>
            <CorrelationMstExplainer />
            <Alert severity="warning" sx={{ borderRadius: 0, border: "none", boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}>
              An MST deliberately keeps only {data.run.edge_count} of the possible pair relationships. A missing edge does not mean two stocks are uncorrelated, and an edge does not imply that one stock affects another.
            </Alert>
          </>
        )}
      </Stack>
    </AppShell>
  );
}
