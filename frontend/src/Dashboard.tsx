import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Container, FormControl, InputLabel, MenuItem,
  Paper, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";

import { fetchJson } from "./api";
import type { Horizon, PipelineStatus, RankingsResponse } from "./types";

const bandColor = { normal: "default", moderate: "warning", strong: "error", extreme: "error" } as const;

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [horizon, setHorizon] = useState<Horizon>(20);
  const [data, setData] = useState<RankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<RankingsResponse>(
      `/sector-divergence/latest/rankings?horizon=${horizon}&limit=25`, controller.signal,
    )
      .then(setData)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load results");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [horizon]);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<PipelineStatus>("/pipeline/status", controller.signal)
      .then(setPipeline)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#f4f7f9", color: "#14212b" }}>
      <Box sx={{ bgcolor: "#102b3a", color: "white", py: 4 }}>
        <Container maxWidth="lg">
          <Typography variant="h3" component="h1" sx={{ fontWeight: 700 }}>PRISM</Typography>
          <Typography sx={{ color: "#b9d5df", mt: 0.5 }}>Explainable NIFTY 200 market intelligence</Typography>
        </Container>
      </Box>
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack spacing={3}>
          {pipeline && <Alert severity={pipeline.is_stale || pipeline.status === "failed" ? "warning" : "success"}>
            Pipeline: <strong>{pipeline.status}</strong>. Market data: {pipeline.latest_market_date ?? "unavailable"}; Layer 1: {pipeline.layer_1_date ?? "unavailable"}; Layer 2: {pipeline.layer_2_date ?? "unavailable"}.
            {pipeline.failed_stage && ` Failed stage: ${pipeline.failed_stage}.`}
            {pipeline.is_stale && " Displayed analysis is stale relative to stored market data."}
          </Alert>}
          <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography variant="h4" component="h2" sx={{ fontWeight: 650 }}>Sector divergence</Typography>
              <Typography color="text.secondary">Select a company to inspect its exact peer comparison.</Typography>
            </Box>
            <Stack direction="row" sx={{ gap: 1, alignItems: "center" }}>
              <Button component={Link} to="/portfolio-demo" variant="outlined">Portfolio demo</Button>
              <Button component={Link} to="/mst" variant="contained">Explore correlation MST</Button>
              <FormControl size="small" sx={{ minWidth: 170 }}>
                <InputLabel id="horizon-label">Horizon</InputLabel>
                <Select labelId="horizon-label" label="Horizon" value={horizon} onChange={(event) => {
                  setLoading(true); setError(null); setHorizon(event.target.value as Horizon);
                }}>
                  <MenuItem value={1}>1 trading day</MenuItem>
                  <MenuItem value={5}>5 trading days</MenuItem>
                  <MenuItem value={20}>20 trading days</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </Stack>
          {error && <Alert severity="warning">Results are not available ({error}).</Alert>}
          {data && <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 2 }}>
            <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline" color="text.secondary">Market data through</Typography><Typography variant="h6">{data.run.signal_date}</Typography></Paper>
            <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline" color="text.secondary">Calculated</Typography><Typography variant="h6">{formatTimestamp(data.run.completed_at)}</Typography></Paper>
            <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline" color="text.secondary">Coverage</Typography><Typography variant="h6">{data.run.score_count} scores</Typography><Typography variant="body2" color="text.secondary">{data.run.exclusion_count} exclusions / {data.run.issue_count} issues</Typography></Paper>
          </Stack>}
          <TableContainer component={Paper}>
            {loading && <Box sx={{ display: "grid", placeItems: "center", py: 8 }}><CircularProgress /></Box>}
            {!loading && data && <Table aria-label="sector divergence rankings">
              <TableHead><TableRow><TableCell>Symbol</TableCell><TableCell>Industry</TableCell><TableCell align="right">Divergence (sigma)</TableCell><TableCell align="right">Direction</TableCell><TableCell align="right">Industry percentile</TableCell><TableCell>Band</TableCell></TableRow></TableHead>
              <TableBody>{data.results.map((score) => <TableRow key={score.symbol} hover tabIndex={0} onClick={() => navigate(`/companies/${score.symbol}`)} onKeyDown={(event) => { if (event.key === "Enter") navigate(`/companies/${score.symbol}`); }} sx={{ cursor: "pointer" }}>
                <TableCell sx={{ fontWeight: 700 }}>{score.symbol}</TableCell><TableCell>{score.industry}</TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums", color: score.divergence_value >= 0 ? "success.main" : "error.main", fontWeight: 700 }}>{score.divergence_value > 0 ? "+" : ""}{score.divergence_value.toFixed(2)}</TableCell>
                <TableCell align="right">{score.divergence_value >= 0 ? "Positive residual" : "Negative residual"}</TableCell>
                <TableCell align="right">{score.industry_percentile.toFixed(1)}%</TableCell>
                <TableCell><Chip size="small" label={score.interpretation} color={bandColor[score.interpretation]} variant={score.interpretation === "normal" ? "outlined" : "filled"} /></TableCell>
              </TableRow>)}</TableBody>
            </Table>}
          </TableContainer>
          <Alert severity="info" icon={false}>Daily closing-price analysis, not live intraday data. Divergence is descriptive, not a forecast or investment recommendation.</Alert>
          <Typography variant="caption" color="text.secondary">PRISM does not provide investment advice.</Typography>
        </Stack>
      </Container>
    </Box>
  );
}
