import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Container, Paper, Stack, Typography } from "@mui/material";
import cytoscape, { type Core } from "cytoscape";
import { Link } from "react-router-dom";

import { fetchJson } from "./api";
import type { MstResponse } from "./types";

const colors = ["#16697a", "#489fb5", "#82c0cc", "#ffa62b", "#db6400", "#7b2cbf", "#2d6a4f", "#bc4749", "#577590", "#6a994e", "#b56576", "#4d908e"];

function industryColors(industries: string[]) {
  return Object.fromEntries([...new Set(industries)].sort().map((industry, index) => [industry, colors[index % colors.length]]));
}

export default function MstPage() {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const [data, setData] = useState<MstResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ title: string; detail: string } | null>(null);

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
        { selector: "node", style: { "background-color": "data(color)", label: "data(symbol)", width: "mapData(degree, 1, 8, 18, 42)", height: "mapData(degree, 1, 8, 18, 42)", "font-size": 8, "text-valign": "bottom", "text-margin-y": 4, color: "#23343d" } },
        { selector: "edge", style: { width: "mapData(correlation, -1, 1, 0.5, 3)", "line-color": "#a8b6bd", opacity: 0.72, "curve-style": "straight" } },
        { selector: ":selected", style: { "border-width": 4, "border-color": "#e76f51", "line-color": "#e76f51", opacity: 1 } },
      ],
      layout: { name: "cose", animate: false, randomize: false, nodeRepulsion: () => 800000, idealEdgeLength: () => 70 },
      minZoom: 0.2,
      maxZoom: 3,
    });
    graph.current.on("tap", "node", (event) => {
      const node = event.target.data();
      setSelected({ title: node.symbol, detail: `${node.industry} / ${node.degree} MST connection${node.degree === 1 ? "" : "s"}` });
    });
    graph.current.on("tap", "edge", (event) => {
      const edge = event.target.data();
      setSelected({ title: `${edge.symbol_a} - ${edge.symbol_b}`, detail: `Correlation ${Number(edge.correlation).toFixed(3)} / distance ${Number(edge.distance).toFixed(3)} / ${edge.paired_observations} paired returns` });
    });
    return () => { graph.current?.destroy(); graph.current = null; };
  }, [data]);

  return <Box sx={{ minHeight: "100vh", bgcolor: "#f4f7f9", color: "#14212b" }}>
    <Box sx={{ bgcolor: "#102b3a", color: "white", py: 3 }}><Container maxWidth="xl"><Typography variant="h4" sx={{ fontWeight: 700 }}>PRISM</Typography></Container></Box>
    <Container maxWidth="xl" sx={{ py: 4 }}><Stack spacing={3}>
      <Button component={Link} to="/" sx={{ alignSelf: "flex-start" }}>Back to sector divergence</Button>
      <Box><Typography variant="h3" component="h1" sx={{ fontWeight: 700 }}>Correlation minimum spanning tree</Typography><Typography color="text.secondary">The sparsest tree connecting eligible NIFTY 200 stocks by return co-movement.</Typography></Box>
      {!data && !error && <Box sx={{ display: "grid", placeItems: "center", py: 10 }}><CircularProgress /></Box>}
      {error && <Alert severity="warning">{error}. Apply the Layer 2 migration and run the MST calculation job.</Alert>}
      {data && <>
        <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 2 }}>
          <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline">Window</Typography><Typography variant="h6">{data.run.window_start} to {data.run.window_end}</Typography></Paper>
          <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline">Validated topology</Typography><Typography variant="h6">{data.run.included_symbol_count} nodes / {data.run.edge_count} edges</Typography><Typography color="text.secondary">Connected: {data.run.is_connected ? "yes" : "no"} / Acyclic: {data.run.is_acyclic ? "yes" : "no"}</Typography></Paper>
          <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline">Exclusions</Typography><Typography variant="h6">{data.run.exclusions.length}</Typography><Typography color="text.secondary">No missing values were imputed</Typography></Paper>
        </Stack>
        {selected && <Alert severity="info"><strong>{selected.title}</strong>: {selected.detail}</Alert>}
        <Paper sx={{ overflow: "hidden" }}><Box ref={container} aria-label="correlation minimum spanning tree" sx={{ width: "100%", height: { xs: 560, md: 760 }, bgcolor: "#fff" }} /></Paper>
        <Paper sx={{ p: 3 }}><Typography variant="h6" sx={{ fontWeight: 650 }}>Method</Typography><Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", my: 2 }}><Chip label="120 daily log returns" /><Chip label="Pearson correlation" /><Chip label="Mantegna distance" /><Chip label="Kruskal + Union-Find" /></Stack><Typography color="text.secondary">Node size reflects MST degree, not company size or importance. Select a node or edge for details. The tree shows statistical co-movement, not causal influence.</Typography></Paper>
        <Alert severity="warning">An MST deliberately keeps only {data.run.edge_count} of the possible pair relationships. A missing edge does not mean two stocks are uncorrelated, and an edge does not imply that one stock affects another.</Alert>
      </>}
    </Stack></Container>
  </Box>;
}
