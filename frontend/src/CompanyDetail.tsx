import { useEffect, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Container, Paper, Stack, Typography } from "@mui/material";
import { Link, useParams } from "react-router-dom";

import { fetchJson } from "./api";
import ComparisonChart from "./ComparisonChart";
import type { CompanyResponse, Horizon } from "./types";

function residualDirection(value: number) { return value >= 0 ? "positive" : "negative"; }

export default function CompanyDetail() {
  const { symbol = "" } = useParams();
  const [data, setData] = useState<CompanyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<Horizon>(20);
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<CompanyResponse>(`/sector-divergence/latest/companies/${encodeURIComponent(symbol)}`, controller.signal)
      .then(setData).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load company detail");
      });
    return () => controller.abort();
  }, [symbol]);

  return <Box sx={{ minHeight: "100vh", bgcolor: "#f4f7f9", color: "#14212b" }}>
    <Box sx={{ bgcolor: "#102b3a", color: "white", py: 3 }}><Container maxWidth="lg"><Typography variant="h4" sx={{ fontWeight: 700 }}>PRISM</Typography></Container></Box>
    <Container maxWidth="lg" sx={{ py: 4 }}><Stack spacing={3}>
      <Button component={Link} to="/" sx={{ alignSelf: "flex-start" }}>Back to rankings</Button>
      {!data && !error && <Box sx={{ display: "grid", placeItems: "center", py: 10 }}><CircularProgress /></Box>}
      {error && <Alert severity="error">{error}</Alert>}
      {data && (() => {
        const chartPoints = data.comparison.points.slice(-(selectedHorizon + 1));
        const first = chartPoints[0];
        const last = chartPoints.at(-1);
        const stockReturn = first && last ? (last.stock_index / first.stock_index - 1) * 100 : 0;
        const benchmarkReturn = first && last ? (last.benchmark_index / first.benchmark_index - 1) * 100 : 0;
        return <>
        <Box><Typography variant="h3" component="h1" sx={{ fontWeight: 700 }}>{data.company.symbol}</Typography><Typography variant="h6" color="text.secondary">{data.company.name} / {data.company.industry}</Typography></Box>
        <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 2 }}>{data.scores.map((score) => <Paper key={score.horizon} onClick={() => setSelectedHorizon(score.horizon)} sx={{ p: 2.5, flex: 1, cursor: "pointer", border: 2, borderColor: selectedHorizon === score.horizon ? "primary.main" : "transparent", borderTop: 4, borderTopColor: score.divergence_value >= 0 ? "success.main" : "error.main" }}>
          <Typography variant="overline">{score.horizon}-day divergence</Typography>
          <Typography variant="h4" sx={{ fontWeight: 700, color: score.divergence_value >= 0 ? "success.main" : "error.main" }}>{score.divergence_value > 0 ? "+" : ""}{score.divergence_value.toFixed(2)} sigma</Typography>
          <Typography>{residualDirection(score.divergence_value)} residual versus peer model</Typography>
          <Chip sx={{ mt: 1 }} size="small" label={score.interpretation} color={score.interpretation === "normal" ? "default" : score.interpretation === "moderate" ? "warning" : "error"} />
        </Paper>)}</Stack>
        <Paper sx={{ p: { xs: 2, md: 3 } }}>
          <Typography variant="h5" sx={{ fontWeight: 650, mb: 0.5 }}>{selectedHorizon}-day actual performance</Typography>
          <Typography sx={{ mb: 0.5 }}><strong>{data.company.symbol}: {stockReturn >= 0 ? "+" : ""}{stockReturn.toFixed(2)}%</strong> / Peer benchmark: {benchmarkReturn >= 0 ? "+" : ""}{benchmarkReturn.toFixed(2)}%</Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>Both lines start at 100 for the selected horizon. The peer line is the daily leave-one-out median of {data.comparison.peer_count} eligible {data.company.industry} peers.</Typography>
          <ComparisonChart points={chartPoints} symbol={data.company.symbol} />
        </Paper>
        <Paper sx={{ p: 3 }}><Typography variant="h6" sx={{ fontWeight: 650 }}>Exact peer set</Typography><Typography color="text.secondary" sx={{ mb: 2 }}>These companies formed the benchmark; {data.company.symbol} was excluded from its own comparison.</Typography><Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>{data.comparison.peer_symbols.map((peer) => <Chip key={peer} label={peer} variant="outlined" />)}</Stack></Paper>
        <Alert severity="info"><strong>Interpretation:</strong> the chart shows raw indexed performance. The sigma score is a standardized model residual after accounting for estimated alpha and beta, so it is not simply the vertical distance between the two lines. It does not establish a cause or predict what happens next. Data through {data.run.signal_date}.</Alert>
      </>;
      })()}
    </Stack></Container>
  </Box>;
}
