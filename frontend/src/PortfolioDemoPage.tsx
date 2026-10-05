import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  LinearProgress,
  Link as MuiLink,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { Link } from "react-router-dom";

import { fetchJson } from "./api";
import {
  type DemoPortfolioRow,
  parseDemoPortfolioCsv,
  portfolioMstEdges,
  validateDemoPortfolio,
} from "./demoPortfolio";
import type { MstResponse, RankingsResponse, Score } from "./types";

const sampleRows: DemoPortfolioRow[] = [
  { symbol: "BAJAJ-AUTO", weightPercent: 20 },
  { symbol: "M&M", weightPercent: 15 },
  { symbol: "GODREJPROP", weightPercent: 20 },
  { symbol: "DLF", weightPercent: 15 },
  { symbol: "INFY", weightPercent: 15 },
  { symbol: "TCS", weightPercent: 15 },
];

interface AnalyzedHolding {
  symbol: string;
  weight: number;
  industry: string;
  score: Score | null;
  scoreError: string | null;
}

interface Analysis {
  divergenceDate: string;
  correlationDate: string;
  holdings: AnalyzedHolding[];
  sectorWeights: Array<{ industry: string; weight: number }>;
  mstEdges: MstResponse["edges"];
  warnings: string[];
}

const bandColor = {
  normal: "default",
  moderate: "warning",
  strong: "error",
  extreme: "error",
} as const;

export default function PortfolioDemoPage() {
  const [rows, setRows] = useState<DemoPortfolioRow[]>(sampleRows);
  const [fileName, setFileName] = useState("Prepared six-stock sample");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [messages, setMessages] = useState<{ errors: string[]; warnings: string[] }>({ errors: [], warnings: [] });
  const [loading, setLoading] = useState(false);

  async function analyze(inputRows = rows) {
    setLoading(true); setAnalysis(null); setMessages({ errors: [], warnings: [] });
    const controller = new AbortController();
    try {
      const [mst, rankings] = await Promise.all([
        fetchJson<MstResponse>("/mst/latest", controller.signal),
        fetchJson<RankingsResponse>(
          "/sector-divergence/latest/rankings?horizon=20&limit=200",
          controller.signal,
        ),
      ]);
      const nodes = new Map(mst.nodes.map((node) => [node.symbol, node]));
      const scores = new Map(rankings.results.map((score) => [score.symbol, score]));
      const validation = validateDemoPortfolio(inputRows, new Set(nodes.keys()));
      setMessages({ errors: validation.errors, warnings: validation.warnings });
      if (!validation.valid) return;
      const details = validation.holdings.map((holding): AnalyzedHolding => {
        const node = nodes.get(holding.symbol);
        const score = scores.get(holding.symbol) ?? null;
        return {
          ...holding,
          industry: node?.industry ?? score?.industry ?? "Unknown",
          score,
          scoreError: score ? null : "No 20-day divergence score in the latest Layer 1 run",
        };
      });
      const sectors = new Map<string, number>();
      for (const holding of details) sectors.set(holding.industry, (sectors.get(holding.industry) ?? 0) + holding.weight);
      const sectorWeights = [...sectors.entries()]
        .map(([industry, weight]) => ({ industry, weight }))
        .sort((left, right) => right.weight - left.weight);
      const directEdges = portfolioMstEdges(validation.holdings, mst.edges);
      const warnings = buildWarnings(details, sectorWeights, directEdges);
      setAnalysis({
        divergenceDate: rankings.run.signal_date,
        correlationDate: mst.run.window_end,
        holdings: details,
        sectorWeights,
        mstEdges: directEdges,
        warnings,
      });
    } catch (reason) {
      setMessages({ errors: [reason instanceof Error ? reason.message : "Unable to load portfolio intelligence"], warnings: [] });
    } finally {
      setLoading(false);
    }
  }

  function loadSample() {
    setRows(sampleRows); setFileName("Prepared six-stock sample"); setAnalysis(null);
    void analyze(sampleRows);
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#f4f7f9", color: "#14212b" }}>
      <Box sx={{ bgcolor: "#102b3a", color: "white", py: 3 }}><Container maxWidth="lg"><Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: 2, alignItems: { sm: "center" }, justifyContent: "space-between" }}><Box><Typography variant="h3" sx={{ fontWeight: 700 }}>PRISM</Typography><Typography sx={{ color: "#b9d5df" }}>Portfolio intelligence presentation demo</Typography></Box><Stack direction="row" spacing={2}><MuiLink component={Link} to="/" color="inherit">Market</MuiLink><MuiLink component={Link} to="/mst" color="inherit">Full MST</MuiLink></Stack></Stack></Container></Box>
      <Container maxWidth="lg" sx={{ py: 4 }}><Stack spacing={3}>
        <Alert severity="info"><strong>Presentation mode:</strong> holdings stay in this browser session and are never written to Supabase. Analytics use the real latest Layer 1 and Layer 2 results.</Alert>
        <Paper sx={{ p: 3 }}><Stack spacing={2}>
          <Typography variant="h4">Analyze a weighted portfolio</Typography>
          <Typography color="text.secondary">Upload <code>symbol,weight</code> with percentage weights totaling 100, or run the prepared sample.</Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button variant="contained" onClick={loadSample} disabled={loading}>Run prepared sample</Button>
            <Button component="label" variant="outlined" disabled={loading}>Choose CSV<input hidden type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; void file.text().then((text) => { const parsed = parseDemoPortfolioCsv(text); setRows(parsed); setFileName(file.name); setAnalysis(null); setMessages({ errors: [], warnings: [] }); }).catch((reason: unknown) => setMessages({ errors: [reason instanceof Error ? reason.message : "Unable to read CSV"], warnings: [] })); }} /></Button>
            <Button variant="outlined" onClick={() => void analyze()} disabled={loading || !rows.length}>Analyze loaded portfolio</Button>
          </Stack>
          <Typography variant="body2">{fileName} · {rows.length} rows · {rows.reduce((sum, row) => sum + row.weightPercent, 0).toFixed(2)}%</Typography>
          {loading && <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}><CircularProgress size={24} /><Typography>Loading real divergence and MST results…</Typography></Stack>}
          {messages.errors.map((message) => <Alert severity="error" key={message}>{message}</Alert>)}
          {messages.warnings.map((message) => <Alert severity="warning" key={message}>{message}</Alert>)}
        </Stack></Paper>
        {analysis && <>
          <SummaryCards analysis={analysis} />
          {analysis.warnings.length > 0 && <Stack spacing={1}>{analysis.warnings.map((warning) => <Alert severity="warning" key={warning}>{warning}</Alert>)}</Stack>}
          <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
            <SectorExposure sectors={analysis.sectorWeights} />
            <MstLinks edges={analysis.mstEdges} />
          </Stack>
          <Holdings holdings={analysis.holdings} />
          <Alert severity="info" icon={false}>Daily closing-price analysis: divergence through {analysis.divergenceDate}; MST correlations through {analysis.correlationDate}. These statistics describe historical behaviour; they are not forecasts or investment recommendations.</Alert>
        </>}
      </Stack></Container>
    </Box>
  );
}

function buildWarnings(
  holdings: AnalyzedHolding[],
  sectors: Analysis["sectorWeights"],
  edges: MstResponse["edges"],
) {
  const warnings: string[] = [];
  const largest = [...holdings].sort((left, right) => right.weight - left.weight)[0];
  if (largest && largest.weight > 0.25) warnings.push(`${largest.symbol} is ${(largest.weight * 100).toFixed(1)}% of the portfolio.`);
  const sector = sectors[0];
  if (sector && sector.weight > 0.4) warnings.push(`${sector.industry} represents ${(sector.weight * 100).toFixed(1)}% of the portfolio.`);
  const strong = holdings.filter((holding) => holding.score && Math.abs(holding.score.divergence_value) >= 2);
  if (strong.length) warnings.push(`${strong.map((holding) => holding.symbol).join(", ")} currently show strong 20-day divergence.`);
  const correlated = edges.filter((edge) => edge.correlation >= 0.7);
  if (correlated.length) warnings.push(`${correlated.length} direct portfolio MST link${correlated.length === 1 ? "" : "s"} have correlation of at least 0.70.`);
  return warnings;
}

function SummaryCards({ analysis }: { analysis: Analysis }) {
  const scored = analysis.holdings.filter((holding) => holding.score);
  const strongest = [...scored].sort((left, right) => Math.abs(right.score?.divergence_value ?? 0) - Math.abs(left.score?.divergence_value ?? 0))[0];
  return <Stack direction={{ xs: "column", md: "row" }} spacing={2}><Metric label="Portfolio" value={`${analysis.holdings.length} holdings`} /><Metric label="Largest sector" value={`${analysis.sectorWeights[0]?.industry ?? "—"} ${((analysis.sectorWeights[0]?.weight ?? 0) * 100).toFixed(1)}%`} /><Metric label="Strongest divergence" value={strongest?.score ? `${strongest.symbol} ${strongest.score.divergence_value > 0 ? "+" : ""}${strongest.score.divergence_value.toFixed(2)}σ` : "Unavailable"} /><Metric label="Direct MST links" value={String(analysis.mstEdges.length)} /></Stack>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Paper sx={{ p: 2.5, flex: 1 }}><Typography variant="overline" color="text.secondary">{label}</Typography><Typography variant="h6">{value}</Typography></Paper>;
}

function SectorExposure({ sectors }: { sectors: Analysis["sectorWeights"] }) {
  return <Paper sx={{ p: 3, flex: 1 }}><Typography variant="h5" gutterBottom>Sector exposure</Typography><Stack spacing={2}>{sectors.map((sector) => <Box key={sector.industry}><Stack direction="row" sx={{ justifyContent: "space-between" }}><Typography variant="body2">{sector.industry}</Typography><Typography variant="body2" sx={{ fontWeight: 700 }}>{(sector.weight * 100).toFixed(1)}%</Typography></Stack><LinearProgress variant="determinate" value={sector.weight * 100} sx={{ height: 8, borderRadius: 4, mt: 0.5 }} /></Box>)}</Stack></Paper>;
}

function MstLinks({ edges }: { edges: MstResponse["edges"] }) {
  return <Paper sx={{ p: 3, flex: 1 }}><Typography variant="h5" gutterBottom>Direct MST concentration links</Typography>{!edges.length ? <Typography color="text.secondary">No holdings are directly adjacent in the sparse MST. This does not mean they are uncorrelated.</Typography> : <Stack spacing={1}>{edges.map((edge) => <Box key={`${edge.symbol_a}-${edge.symbol_b}`} sx={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #e5eaed", py: 1 }}><Typography>{edge.symbol_a} ↔ {edge.symbol_b}</Typography><Chip size="small" label={`ρ ${edge.correlation.toFixed(2)}`} color={edge.correlation >= 0.7 ? "warning" : "default"} /></Box>)}</Stack>}<Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>Only N−1 MST edges are retained; absence of a direct edge is not evidence of diversification.</Typography></Paper>;
}

function Holdings({ holdings }: { holdings: AnalyzedHolding[] }) {
  return <Paper sx={{ p: 3, overflowX: "auto" }}><Typography variant="h5" gutterBottom>Owned-stock divergence</Typography><Table><TableHead><TableRow><TableCell>Holding</TableCell><TableCell>Industry</TableCell><TableCell align="right">Weight</TableCell><TableCell align="right">20-day divergence</TableCell><TableCell>Direction / band</TableCell></TableRow></TableHead><TableBody>{holdings.map((holding) => <TableRow key={holding.symbol}><TableCell><MuiLink component={Link} to={`/companies/${holding.symbol}`} sx={{ fontWeight: 700 }}>{holding.symbol}</MuiLink></TableCell><TableCell>{holding.industry}</TableCell><TableCell align="right">{(holding.weight * 100).toFixed(1)}%</TableCell><TableCell align="right" sx={{ color: holding.score && holding.score.divergence_value >= 0 ? "success.main" : "error.main", fontWeight: 700 }}>{holding.score ? `${holding.score.divergence_value > 0 ? "+" : ""}${holding.score.divergence_value.toFixed(2)}σ` : "—"}</TableCell><TableCell>{holding.score ? <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}><span>{holding.score.divergence_value >= 0 ? "Positive residual" : "Negative residual"}</span><Chip size="small" label={holding.score.interpretation} color={bandColor[holding.score.interpretation]} /></Stack> : <Typography variant="body2" color="text.secondary">{holding.scoreError}</Typography>}</TableCell></TableRow>)}</TableBody></Table></Paper>;
}
