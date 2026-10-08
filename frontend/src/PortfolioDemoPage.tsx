import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  InputLabel,
  LinearProgress,
  Link as MuiLink,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { Link } from "react-router-dom";

import { postJson } from "./api";
import PortfolioMstGraph from "./PortfolioMstGraph";
import {
  type DemoPortfolioRow,
  parseDemoPortfolioCsv,
  validateDemoPortfolio,
} from "./demoPortfolio";
import type {
  PortfolioAnalysisResponse,
  PortfolioHoldingAnalytics,
  PortfolioPerformancePoint,
  PortfolioStressInput,
} from "./types";

const sampleRows: DemoPortfolioRow[] = [
  { symbol: "BAJAJ-AUTO", weightPercent: 20 },
  { symbol: "M&M", weightPercent: 15 },
  { symbol: "GODREJPROP", weightPercent: 20 },
  { symbol: "DLF", weightPercent: 15 },
  { symbol: "INFY", weightPercent: 15 },
  { symbol: "TCS", weightPercent: 15 },
];

const bandColor = {
  normal: "default",
  moderate: "warning",
  strong: "error",
  extreme: "error",
} as const;

const formatPercent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

export default function PortfolioDemoPage() {
  const [rows, setRows] = useState<DemoPortfolioRow[]>(sampleRows);
  const [fileName, setFileName] = useState("Prepared six-stock sample");
  const [analysis, setAnalysis] = useState<PortfolioAnalysisResponse | null>(null);
  const [messages, setMessages] = useState<{ errors: string[]; warnings: string[] }>({
    errors: [],
    warnings: [],
  });
  const [loading, setLoading] = useState(false);

  async function analyze(inputRows = rows, stress?: PortfolioStressInput) {
    setLoading(true);
    setMessages({ errors: [], warnings: [] });
    const controller = new AbortController();
    try {
      const validation = validateDemoPortfolio(inputRows);
      setMessages({ errors: validation.errors, warnings: validation.warnings });
      if (!validation.valid) return;
      const result = await postJson<PortfolioAnalysisResponse>(
        "/portfolio-analysis/preview",
        { holdings: validation.holdings, window: 250, stress: stress ?? null },
        controller.signal,
      );
      setAnalysis(result);
    } catch (reason) {
      setMessages({
        errors: [reason instanceof Error ? reason.message : "Unable to calculate portfolio analytics"],
        warnings: [],
      });
    } finally {
      setLoading(false);
    }
  }

  function loadSample() {
    setRows(sampleRows);
    setFileName("Prepared six-stock sample");
    setAnalysis(null);
    void analyze(sampleRows);
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#f4f7f9",
        color: "#14212b",
        "@media print": {
          bgcolor: "white",
          "& .no-print": { display: "none !important" },
          "& .MuiPaper-root": { boxShadow: "none", breakInside: "avoid" },
        },
      }}
    >
      <Box className="no-print" sx={{ bgcolor: "#102b3a", color: "white", py: 3 }}>
        <Container maxWidth="lg">
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{ gap: 2, alignItems: { sm: "center" }, justifyContent: "space-between" }}
          >
            <Box>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>PRISM</Typography>
              <Typography sx={{ color: "#b9d5df" }}>Portfolio risk and explainability</Typography>
            </Box>
            <Stack direction="row" spacing={2}>
              <MuiLink component={Link} to="/" color="inherit">Market</MuiLink>
              <MuiLink component={Link} to="/mst" color="inherit">Full MST</MuiLink>
            </Stack>
          </Stack>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Stack spacing={3}>
          <Alert severity="info" className="no-print">
            <strong>Session-only mode:</strong> holdings are not saved. Results use real persisted
            adjusted prices, Layer 1 divergence and the latest Layer 2 MST.
          </Alert>
          <InputPanel
            rows={rows}
            fileName={fileName}
            loading={loading}
            onSample={loadSample}
            onAnalyze={() => void analyze()}
            onFile={(file, parsed) => {
              setRows(parsed);
              setFileName(file);
              setAnalysis(null);
              void analyze(parsed);
            }}
            onError={(message) => setMessages({ errors: [message], warnings: [] })}
          />
          {loading && (
            <Paper sx={{ p: 2 }}>
              <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                <CircularProgress size={24} />
                <Typography>Calculating performance, covariance risk and MST paths…</Typography>
              </Stack>
            </Paper>
          )}
          {messages.errors.map((message) => (
            <Alert severity="error" key={message}>{message}</Alert>
          ))}
          {messages.warnings.map((message) => (
            <Alert severity="warning" key={message}>{message}</Alert>
          ))}

          {analysis && (
            <>
              <ReportHeader analysis={analysis} />
              <SummaryCards analysis={analysis} />
              <Stack spacing={1}>
                {analysis.findings.map((finding) => (
                  <Alert severity="success" variant="outlined" key={finding}>{finding}</Alert>
                ))}
              </Stack>
              <PerformanceChart points={analysis.performance.points} />
              <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
                <ExposurePanel analysis={analysis} />
                <DiversificationPanel analysis={analysis} />
              </Stack>
              <RiskContributionTable holdings={analysis.holdings} />
              <MstDiagnostics analysis={analysis} />
              <StressPanel
                analysis={analysis}
                loading={loading}
                onRun={(stress) => void analyze(rows, stress)}
              />
              <HoldingTable holdings={analysis.holdings} />
              <MethodAndLimitations analysis={analysis} />
            </>
          )}
        </Stack>
      </Container>
    </Box>
  );
}

function InputPanel({
  rows,
  fileName,
  loading,
  onSample,
  onAnalyze,
  onFile,
  onError,
}: {
  rows: DemoPortfolioRow[];
  fileName: string;
  loading: boolean;
  onSample: () => void;
  onAnalyze: () => void;
  onFile: (fileName: string, rows: DemoPortfolioRow[]) => void;
  onError: (message: string) => void;
}) {
  return (
    <Paper className="no-print" sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Typography variant="h4">Analyze a weighted portfolio</Typography>
        <Typography color="text.secondary">
          Upload <code>symbol,weight</code> with percentage weights totaling 100, or use the
          prepared sample.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button variant="contained" onClick={onSample} disabled={loading}>
            Run prepared sample
          </Button>
          <Button component="label" variant="outlined" disabled={loading}>
            Choose CSV
            <input
              hidden
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                void file.text()
                  .then((text) => onFile(file.name, parseDemoPortfolioCsv(text)))
                  .catch((reason: unknown) => onError(
                    reason instanceof Error ? reason.message : "Unable to read CSV",
                  ));
              }}
            />
          </Button>
          <Button variant="outlined" onClick={onAnalyze} disabled={loading || !rows.length}>
            Analyze loaded portfolio
          </Button>
        </Stack>
        <Typography variant="body2">
          {fileName} · {rows.length} rows · {rows.reduce(
            (sum, row) => sum + row.weightPercent, 0,
          ).toFixed(2)}%
        </Typography>
      </Stack>
    </Paper>
  );
}

function ReportHeader({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  function downloadReport() {
    const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `prism-portfolio-report-${analysis.envelope.as_of}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
      <Box>
        <Typography variant="h4">Portfolio analysis</Typography>
        <Typography color="text.secondary">
          Data through {analysis.envelope.as_of} · {analysis.envelope.observations_used} daily
          returns
        </Typography>
      </Box>
      <Stack direction="row" spacing={1} className="no-print">
        <Button variant="outlined" onClick={downloadReport}>Download report</Button>
        <Button variant="contained" onClick={() => window.print()}>Print / save PDF</Button>
      </Stack>
    </Stack>
  );
}

function SummaryCards({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
      <Metric label="Trailing return" value={formatPercent(analysis.performance.total_return)} />
      <Metric label="Annual volatility" value={formatPercent(analysis.performance.annualized_volatility)} />
      <Metric label="Maximum drawdown" value={formatPercent(analysis.performance.max_drawdown)} />
      <Metric label="Effective holdings" value={analysis.concentration.effective_holdings.toFixed(1)} />
      <Metric label="Effective risk bets" value={analysis.diversification.effective_bets_risk.toFixed(1)} />
    </Stack>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
      <Typography variant="overline" color="text.secondary">{label}</Typography>
      <Typography variant="h5">{value}</Typography>
    </Paper>
  );
}

function PerformanceChart({ points }: { points: PortfolioPerformancePoint[] }) {
  const width = 960;
  const height = 430;
  const left = 62;
  const right = 22;
  const top = 28;
  const firstBottom = 255;
  const secondTop = 300;
  const bottom = 392;
  const indexValues = points.map((point) => point.portfolio_index);
  const indexMin = Math.min(...indexValues);
  const indexMax = Math.max(...indexValues);
  const padding = Math.max((indexMax - indexMin) * 0.1, 1);
  const min = indexMin - padding;
  const max = indexMax + padding;
  const minDrawdown = Math.min(...points.map((point) => point.drawdown), -0.001);
  const x = (index: number) => left + (
    index / Math.max(points.length - 1, 1)
  ) * (width - left - right);
  const indexY = (value: number) => top + ((max - value) / (max - min)) * (firstBottom - top);
  const drawdownY = (value: number) => secondTop + (
    value / minDrawdown
  ) * (bottom - secondTop);
  const indexLine = points.map((point, index) => `${x(index)},${indexY(point.portfolio_index)}`).join(" ");
  const drawdownLine = points.map((point, index) => `${x(index)},${drawdownY(point.drawdown)}`).join(" ");

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Historical portfolio performance</Typography>
      <Typography color="text.secondary" gutterBottom>
        Constant-weight daily-rebalanced index; starting value 100. Drawdown is measured from
        the running peak.
      </Typography>
      <Box
        component="svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Portfolio index and drawdown history"
        sx={{ width: "100%", height: "auto", display: "block" }}
      >
        {[0, 0.5, 1].map((ratio) => {
          const value = max - ratio * (max - min);
          const y = top + ratio * (firstBottom - top);
          return <g key={ratio}><line x1={left} x2={width - right} y1={y} y2={y} stroke="#dce3e8" /><text x={left - 8} y={y + 4} textAnchor="end" fontSize="12" fill="#596a75">{value.toFixed(0)}</text></g>;
        })}
        <polyline points={indexLine} fill="none" stroke="#00796b" strokeWidth="3" />
        <line x1={left} x2={width - right} y1={secondTop} y2={secondTop} stroke="#dce3e8" />
        <line x1={left} x2={width - right} y1={bottom} y2={bottom} stroke="#dce3e8" />
        <text x={left - 8} y={secondTop + 4} textAnchor="end" fontSize="12" fill="#596a75">0%</text>
        <text x={left - 8} y={bottom + 4} textAnchor="end" fontSize="12" fill="#596a75">{formatPercent(minDrawdown, 0)}</text>
        <polyline points={drawdownLine} fill="none" stroke="#d32f2f" strokeWidth="2.5" />
        <text x={left} y={height - 10} fontSize="12" fill="#596a75">{points[0]?.trade_date}</text>
        <text x={width - right} y={height - 10} textAnchor="end" fontSize="12" fill="#596a75">{points.at(-1)?.trade_date}</text>
        <text x={left} y={top - 9} fontSize="12" fill="#00796b">Portfolio index</text>
        <text x={left} y={secondTop - 9} fontSize="12" fill="#d32f2f">Drawdown</text>
      </Box>
    </Paper>
  );
}

function ExposurePanel({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3, flex: 1 }}>
      <Typography variant="h5" gutterBottom>Industry exposure</Typography>
      <Stack spacing={2}>
        {analysis.concentration.industry_weights.map((item) => (
          <Box key={item.industry}>
            <Stack direction="row" sx={{ justifyContent: "space-between" }}>
              <Typography variant="body2">{item.industry}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{formatPercent(item.weight)}</Typography>
            </Stack>
            <LinearProgress variant="determinate" value={item.weight * 100} sx={{ height: 8, borderRadius: 4, mt: 0.5 }} />
          </Box>
        ))}
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        Industry HHI {analysis.concentration.industry_hhi.toFixed(3)} · effective industries {analysis.concentration.effective_industries.toFixed(1)}
      </Typography>
    </Paper>
  );
}

function DiversificationPanel({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3, flex: 1 }}>
      <Typography variant="h5" gutterBottom>Diversification</Typography>
      <Stack spacing={2}>
        <Box><Typography variant="overline">Holdings</Typography><Typography variant="h4">{analysis.holdings.length}</Typography></Box>
        <Box><Typography variant="overline">Effective holdings by weight</Typography><Typography variant="h4">{analysis.concentration.effective_holdings.toFixed(2)}</Typography></Box>
        <Box><Typography variant="overline">Effective bets by risk contribution</Typography><Typography variant="h4">{analysis.diversification.effective_bets_risk.toFixed(2)}</Typography></Box>
        <Box><Typography variant="overline">Effective bets by correlation eigenvalues</Typography><Typography variant="h4">{analysis.diversification.effective_bets_correlation.toFixed(2)}</Typography></Box>
        <Alert severity="info" icon={false}>{analysis.diversification.interpretation}</Alert>
      </Stack>
    </Paper>
  );
}

function RiskContributionTable({ holdings }: { holdings: PortfolioHoldingAnalytics[] }) {
  const ordered = [...holdings].sort((left, right) => right.risk_contribution - left.risk_contribution);
  return (
    <Paper sx={{ p: 3, overflowX: "auto" }}>
      <Typography variant="h5">Risk contribution by holding</Typography>
      <Typography color="text.secondary" gutterBottom>
        Euler decomposition of annualized sample covariance; contributions sum to approximately 100%.
      </Typography>
      <Table size="small">
        <TableHead><TableRow><TableCell>Holding</TableCell><TableCell align="right">Weight</TableCell><TableCell align="right">Asset volatility</TableCell><TableCell align="right">Risk contribution</TableCell><TableCell sx={{ minWidth: 180 }}>Share</TableCell></TableRow></TableHead>
        <TableBody>{ordered.map((holding) => (
          <TableRow key={holding.symbol}>
            <TableCell><MuiLink component={Link} to={`/companies/${holding.symbol}`} sx={{ fontWeight: 700 }}>{holding.symbol}</MuiLink></TableCell>
            <TableCell align="right">{formatPercent(holding.weight)}</TableCell>
            <TableCell align="right">{formatPercent(holding.annualized_volatility)}</TableCell>
            <TableCell align="right">{formatPercent(holding.risk_contribution)}</TableCell>
            <TableCell><LinearProgress color={holding.risk_contribution > 0.35 ? "warning" : "primary"} variant="determinate" value={Math.min(Math.max(holding.risk_contribution * 100, 0), 100)} sx={{ height: 8, borderRadius: 4 }} /></TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
    </Paper>
  );
}

function MstDiagnostics({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">MST concentration and indirect connections</Typography>
      <Typography color="text.secondary" gutterBottom>
        Clusters retain MST edges with correlation ≥ {analysis.mst.cluster_correlation_floor.toFixed(2)}.
        Paths use the unique route through the complete NIFTY 200 MST.
      </Typography>
      <Alert
        severity={analysis.mst.stability.confidence === "high" ? "success" : analysis.mst.stability.confidence === "moderate" ? "info" : "warning"}
        sx={{ mt: 2 }}
      >
        MST stability: {analysis.mst.stability.confidence}. {analysis.mst.stability.reason}
      </Alert>
      <PortfolioMstGraph mst={analysis.mst} holdings={analysis.holdings} />
      <Stack direction={{ xs: "column", md: "row" }} spacing={3} sx={{ mt: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">Portfolio clusters</Typography>
          <Stack spacing={1}>{analysis.mst.clusters.map((cluster) => (
            <Box key={cluster.cluster_id} sx={{ borderBottom: "1px solid #e3e8eb", py: 1 }}>
              <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                <Typography sx={{ fontWeight: 700 }}>{cluster.cluster_id}</Typography>
                <Chip size="small" label={formatPercent(cluster.weight)} />
              </Stack>
              <Typography variant="body2">{cluster.holding_symbols.join(", ")}</Typography>
              <Typography variant="caption" color="text.secondary">{cluster.full_node_count} full-MST nodes in component</Typography>
            </Box>
          ))}</Stack>
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">Direct holding links</Typography>
          {!analysis.mst.direct_edges.length && <Typography color="text.secondary">No holdings are directly adjacent.</Typography>}
          {analysis.mst.direct_edges.map((edge) => (
            <Stack direction="row" key={`${edge.symbol_a}-${edge.symbol_b}`} sx={{ justifyContent: "space-between", py: 1, borderBottom: "1px solid #e3e8eb" }}>
              <Typography>{edge.symbol_a} ↔ {edge.symbol_b}</Typography>
              <Chip size="small" label={`ρ ${edge.correlation.toFixed(2)}`} color={edge.correlation >= 0.7 ? "warning" : "default"} />
            </Stack>
          ))}
          <Typography variant="h6" sx={{ mt: 2 }}>Bridge stocks</Typography>
          {analysis.mst.bridge_stocks.slice(0, 6).map((bridge) => (
            <Stack direction="row" key={bridge.symbol} sx={{ justifyContent: "space-between", py: 0.75 }}>
              <Typography>{bridge.symbol}{bridge.is_holding ? " (held)" : ""}</Typography>
              <Typography variant="body2">{bridge.path_pair_count} paths</Typography>
            </Stack>
          ))}
        </Box>
      </Stack>
      <Box sx={{ overflowX: "auto", mt: 3 }}>
        <Typography variant="h6">Holding-to-holding paths</Typography>
        <Table size="small">
          <TableHead><TableRow><TableCell>Pair</TableCell><TableCell align="right">Hops</TableCell><TableCell align="right">Average edge ρ</TableCell><TableCell>Stability</TableCell><TableCell>Unique MST path</TableCell></TableRow></TableHead>
          <TableBody>{analysis.mst.holding_paths.map((path) => (
            <TableRow key={`${path.symbol_a}-${path.symbol_b}`}>
              <TableCell>{path.symbol_a} / {path.symbol_b}</TableCell>
              <TableCell align="right">{path.hops}</TableCell>
              <TableCell align="right">{path.average_correlation.toFixed(2)}</TableCell>
              <TableCell>
                {path.minimum_edge_persistence === null
                  ? "Unavailable"
                  : `${(path.minimum_edge_persistence * 100).toFixed(0)}% · ${path.confidence}`}
              </TableCell>
              <TableCell>{path.path.join(" → ")}</TableCell>
            </TableRow>
          ))}</TableBody>
        </Table>
      </Box>
    </Paper>
  );
}

function StressPanel({
  analysis,
  loading,
  onRun,
}: {
  analysis: PortfolioAnalysisResponse;
  loading: boolean;
  onRun: (stress: PortfolioStressInput) => void;
}) {
  const [kind, setKind] = useState<"stock" | "industry">("stock");
  const stockTargets = analysis.holdings.map((holding) => holding.symbol);
  const industryTargets = analysis.concentration.industry_weights.map((item) => item.industry);
  const targets = kind === "stock" ? stockTargets : industryTargets;
  const [target, setTarget] = useState(stockTargets[0] ?? "");
  const [shock, setShock] = useState(-10);
  const selectedTarget = targets.includes(target) ? target : targets[0] ?? "";

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Hypothetical stress test</Typography>
      <Typography color="text.secondary" gutterBottom>
        Apply a holding shock with historical beta propagation, or a parallel shock to one represented industry.
      </Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} className="no-print" sx={{ mt: 2 }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="stress-kind">Shock type</InputLabel>
          <Select
            labelId="stress-kind"
            label="Shock type"
            value={kind}
            onChange={(event) => {
              const nextKind = event.target.value as "stock" | "industry";
              setKind(nextKind);
              setTarget(nextKind === "stock" ? stockTargets[0] ?? "" : industryTargets[0] ?? "");
            }}
          >
            <MenuItem value="stock">Selected holding</MenuItem>
            <MenuItem value="industry">Selected industry</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="stress-target">Target</InputLabel>
          <Select labelId="stress-target" label="Target" value={selectedTarget} onChange={(event) => setTarget(event.target.value)}>
            {targets.map((item) => <MenuItem value={item} key={item}>{item}</MenuItem>)}
          </Select>
        </FormControl>
        <TextField size="small" label="Shock (%)" type="number" value={shock} onChange={(event) => setShock(Number(event.target.value))} slotProps={{ htmlInput: { min: -30, max: 30, step: 1 } }} />
        <Button variant="contained" disabled={loading || !selectedTarget || shock === 0 || shock < -30 || shock > 30} onClick={() => onRun({ kind, target: selectedTarget, shock_percent: shock })}>Run stress</Button>
      </Stack>
      {analysis.stress && (
        <Stack spacing={2} sx={{ mt: 3 }}>
          <Alert severity="warning">
            Estimated portfolio impact: <strong>{analysis.stress.portfolio_impact_percent.toFixed(2)}%</strong> from a {analysis.stress.shock_percent.toFixed(1)}% shock to {analysis.stress.target}. {analysis.stress.disclaimer}
          </Alert>
          <Typography variant="body2"><strong>Method:</strong> {analysis.stress.method}</Typography>
          <Box sx={{ overflowX: "auto" }}><Table size="small"><TableHead><TableRow><TableCell>Holding</TableCell><TableCell align="right">Sensitivity</TableCell><TableCell align="right">Estimated return</TableCell><TableCell align="right">Portfolio impact</TableCell></TableRow></TableHead><TableBody>{analysis.stress.results.map((result) => <TableRow key={result.symbol}><TableCell>{result.symbol}</TableCell><TableCell align="right">{result.sensitivity.toFixed(2)}</TableCell><TableCell align="right">{result.estimated_return_percent.toFixed(2)}%</TableCell><TableCell align="right">{result.portfolio_contribution_percent.toFixed(2)}%</TableCell></TableRow>)}</TableBody></Table></Box>
          <Box component="ul" sx={{ m: 0 }}>{analysis.stress.assumptions.map((assumption) => <li key={assumption}><Typography variant="body2">{assumption}</Typography></li>)}</Box>
        </Stack>
      )}
    </Paper>
  );
}

function HoldingTable({ holdings }: { holdings: PortfolioHoldingAnalytics[] }) {
  return (
    <Paper sx={{ p: 3, overflowX: "auto" }}>
      <Typography variant="h5" gutterBottom>Holdings and current divergence</Typography>
      <Table size="small">
        <TableHead><TableRow><TableCell>Holding</TableCell><TableCell>Industry</TableCell><TableCell align="right">Weight</TableCell><TableCell align="right">20-day divergence</TableCell><TableCell>Band</TableCell></TableRow></TableHead>
        <TableBody>{holdings.map((holding) => (
          <TableRow key={holding.symbol}>
            <TableCell><MuiLink component={Link} to={`/companies/${holding.symbol}`} sx={{ fontWeight: 700 }}>{holding.symbol}</MuiLink></TableCell>
            <TableCell>{holding.industry}</TableCell>
            <TableCell align="right">{formatPercent(holding.weight)}</TableCell>
            <TableCell align="right" sx={{ color: holding.divergence_20d !== null && holding.divergence_20d >= 0 ? "success.main" : "error.main", fontWeight: 700 }}>{holding.divergence_20d === null ? "—" : `${holding.divergence_20d > 0 ? "+" : ""}${holding.divergence_20d.toFixed(2)}σ`}</TableCell>
            <TableCell>{holding.divergence_band ? <Chip size="small" label={holding.divergence_band} color={bandColor[holding.divergence_band]} /> : "Unavailable"}</TableCell>
          </TableRow>
        ))}</TableBody>
      </Table>
    </Paper>
  );
}

function MethodAndLimitations({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Method and limitations</Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        {analysis.envelope.return_frequency}; {analysis.envelope.annualisation_factor}-day annualisation;
        {" "}{analysis.envelope.weighting_assumption}; {analysis.envelope.missing_data_rule}.
      </Typography>
      <Box component="ul" sx={{ mb: 0 }}>
        {analysis.limitations.map((limitation) => <li key={limitation}><Typography variant="body2">{limitation}</Typography></li>)}
      </Box>
    </Paper>
  );
}
