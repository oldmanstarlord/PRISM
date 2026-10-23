import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
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

import { postJson } from "./api";
import type { PortfolioHolding } from "./PortfolioManager";
import { COLORS, SHADOWS } from "./theme";
import { GnnPortfolioDriftPanel } from "./GnnStructuralDriftPanel";

type OutputStatus =
  | "ready"
  | "stale"
  | "baseline_selected"
  | "failed"
  | "untrained"
  | "insufficient_data"
  | "unavailable";

interface ModelStatusItem {
  model_name: string;
  model_version: string | null;
  model_type: string | null;
  status: OutputStatus;
  data_cutoff: string | null;
  prediction_date?: string | null;
  trained_at: string | null;
  last_successful_training_date?: string | null;
  training_window?: string | null;
  test_period?: string | null;
  methodology_version?: string | null;
  model_selected?: string | null;
  metrics_vs_baseline: Record<string, unknown>;
  baseline_comparison?: Record<string, unknown>;
  failure_reason?: string | null;
}

interface HoldingForecast {
  symbol: string;
  weight?: number | null;
  status: OutputStatus;
  failure_reason?: string | null;
  prediction_date?: string | null;
  data_cutoff?: string | null;
  forecast_volatility?: number | null;
  lower_bound_90?: number | null;
  upper_bound_90?: number | null;
  trailing_21d_vol?: number | null;
  model_selected?: string | null;
}

interface AnomalyResult {
  symbol: string;
  company_name?: string | null;
  status: OutputStatus;
  failure_reason?: string | null;
  anomaly_score?: number | null;
  is_anomaly?: boolean | null;
  primary_driver?: string | null;
  rationale?: string | null;
}

interface AiInsights {
  model_statuses: Record<string, ModelStatusItem>;
  volatility: {
    status: OutputStatus;
    data_cutoff?: string | null;
    portfolio_forecast?: null;
    portfolio_reason?: string | null;
    holdings_forecasts?: HoldingForecast[];
    error?: string | null;
  };
  regime: {
    status: OutputStatus;
    error?: string | null;
    market_regime?: Record<string, unknown> | null;
  };
  anomalies: {
    status: OutputStatus;
    error?: string | null;
    anomaly_analysis?: {
      data_cutoff?: string | null;
      flag_rate_pct?: number | null;
      stability_score?: number | null;
      disclaimer?: string | null;
      unusual_holdings?: AnomalyResult[];
    } | null;
  };
  score_validation: {
    status: OutputStatus;
    error?: string | null;
    score_validation?: Record<string, unknown> | null;
  };
  governance: { methodology_version: string; disclaimer: string };
}

interface AiInsightsTabProps {
  holdings: PortfolioHolding[];
  totalInvestedValue: number;
}

const statusColor = (status: OutputStatus) =>
  status === "ready" || status === "baseline_selected"
    ? { background: COLORS.paleSage, color: COLORS.emerald }
    : { background: COLORS.paleTerracotta, color: COLORS.vermilionText };

const show = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "Unavailable";
  return String(value);
};

const decimalPercent = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined || !Number.isFinite(value)
    ? "Unavailable"
    : `${(value * 100).toFixed(digits)}%`;

const number = (value: unknown, digits = 3): string =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";

function StatusChip({ status }: { status: OutputStatus }) {
  const colors = statusColor(status);
  return (
    <Chip
      label={status.replaceAll("_", " ").toUpperCase()}
      size="small"
      sx={{ borderRadius: 0, fontWeight: 700, fontSize: "0.875rem", bgcolor: colors.background, color: colors.color }}
    />
  );
}

function PanelHeader({ title, open, toggle }: { title: string; open: boolean; toggle: () => void }) {
  return (
    <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: open ? 2 : 0 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>{title}</Typography>
        <Chip label="Persisted model output" size="small" sx={{ borderRadius: 0, bgcolor: COLORS.sandBeige, fontSize: "0.875rem" }} />
      </Stack>
      <IconButton size="small" onClick={toggle} sx={{ color: COLORS.deepCharcoal }}>{open ? "▲" : "▼"}</IconButton>
    </Stack>
  );
}

export function AiInsightsTab({ holdings, totalInvestedValue }: AiInsightsTabProps) {
  const [data, setData] = useState<AiInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState([true, true, true, true, true, false]);

  const toggle = (index: number) =>
    setOpen((current) => current.map((value, position) => (position === index ? !value : value)));

  const fetchInsights = async () => {
    if (!holdings.length) {
      setData(null);
      return;
    }
    if (!(totalInvestedValue > 0)) {
      setError("Portfolio value must be positive before persisted outputs can be mapped to weights.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await postJson<AiInsights>(
        "/ml/comprehensive-insights",
        {
          holdings: holdings.map((holding) => ({
            symbol: holding.symbol,
            weight: (holding.quantity * holding.buyPrice) / totalInvestedValue,
          })),
        },
        new AbortController().signal,
      );
      setData(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchInsights();
    // Fetch only when the portfolio membership changes; the button refreshes persisted output.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [holdings.length]);

  if (!holdings.length) {
    return (
      <Paper sx={{ p: 4, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mb: 1 }}>No Active Portfolio Positions</Typography>
        <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>Add holdings to view their latest persisted model outputs.</Typography>
      </Paper>
    );
  }

  const regime = data?.regime.market_regime;
  const timeline = (regime?.regime_timeline as Array<Record<string, unknown>> | undefined) ?? [];
  const regimeVols = (regime?.regime_conditional_volatilities as Record<string, number | null> | undefined) ?? {};
  const anomalies = data?.anomalies.anomaly_analysis?.unusual_holdings ?? [];
  const score = data?.score_validation.score_validation;
  const models = score?.models as Record<string, Record<string, unknown>> | undefined;
  const fixed = models?.five_factor_fixed_weights;
  const vol21 = fixed?.volatility_21d as Record<string, unknown> | undefined;

  return (
    <Stack spacing={3} data-testid="ai-insights-container">
      <Paper sx={{ p: 2.5, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>AI Risk Diagnostics & Model Estimates</Typography>
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey, maxWidth: 960 }}>
              Persisted point-in-time risk estimates only. Models strictly do NOT forecast price direction, returns, or trading actions.
              Training, evaluation, inference, and dashboard rendering are separate operations.
            </Typography>
          </Box>
          <Button variant="outlined" onClick={() => void fetchInsights()} disabled={loading} sx={{ borderRadius: 0, textTransform: "none", color: COLORS.deepCharcoal }}>
            {loading ? <CircularProgress size={18} /> : "Refresh persisted outputs"}
          </Button>
        </Stack>
      </Paper>
      <GnnPortfolioDriftPanel symbols={holdings.map((holding) => holding.symbol)} />

      {loading && <Alert severity="info">Loading persisted model runs and predictions. This request does not train models.</Alert>}
      {error && <Alert severity="warning"><strong>Output unavailable:</strong> {error}</Alert>}

      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="1. Model Registry & Walk-Forward Status" open={open[0]} toggle={() => toggle(0)} />
        <Collapse in={open[0]}>
          <Table size="small">
            <TableHead><TableRow sx={{ bgcolor: COLORS.sandBeige }}>
              {['Model / Type', 'Version / Method', 'Training / Prediction', 'Test period', 'Selection / comparison', 'Status'].map((label) => <TableCell key={label} sx={{ fontWeight: 700 }}>{label}</TableCell>)}
            </TableRow></TableHead>
            <TableBody>
              {Object.entries(data?.model_statuses ?? {}).map(([key, item]) => (
                <TableRow key={key}>
                  <TableCell><strong>{item.model_name}</strong><br /><Typography variant="caption">{show(item.model_type)}</Typography></TableCell>
                  <TableCell>{show(item.model_version)}<br /><Typography variant="caption">{show(item.methodology_version)}</Typography></TableCell>
                  <TableCell><Typography variant="caption">Trained: {show(item.last_successful_training_date ?? item.trained_at)}<br />Prediction: {show(item.prediction_date)}<br />Cutoff: {show(item.data_cutoff)}</Typography></TableCell>
                  <TableCell>{show(item.test_period)}</TableCell>
                  <TableCell><Typography variant="caption">{show(item.model_selected)}<br />{item.failure_reason ?? JSON.stringify(item.baseline_comparison ?? item.metrics_vs_baseline)}</Typography></TableCell>
                  <TableCell><StatusChip status={item.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Collapse>
      </Paper>

      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="2. NIFTY 50 Market Regime State" open={open[1]} toggle={() => toggle(1)} />
        <Collapse in={open[1]}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}><StatusChip status={data?.regime.status ?? "unavailable"} /><Typography>{show(regime?.active_regime_name)} — filtered probability {decimalPercent(regime?.filtered_probability as number | undefined, 1)}</Typography></Stack>
            <Typography variant="body2">Data cutoff: {show(regime?.data_cutoff)} · Calm volatility: {decimalPercent(regimeVols["Calm / Normal"], 1)} · Stressed volatility: {decimalPercent(regimeVols["Turbulent / Stressed"], 1)}</Typography>
            {data?.regime.error && <Alert severity="warning">{data.regime.error}</Alert>}
            {timeline.length > 0 && <Table size="small"><TableHead><TableRow><TableCell>Date</TableCell><TableCell>Filtered regime</TableCell><TableCell align="right">Stressed probability</TableCell></TableRow></TableHead><TableBody>
              {timeline.slice(-10).reverse().map((row, index) => <TableRow key={index}><TableCell>{show(row.date)}</TableCell><TableCell>{show(row.regime)}</TableCell><TableCell align="right">{decimalPercent(row.stressed_prob as number | undefined, 1)}</TableCell></TableRow>)}
            </TableBody></Table>}
          </Stack>
        </Collapse>
      </Paper>

      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="3. 21-Day Ahead Realized Volatility Forecast" open={open[2]} toggle={() => toggle(2)} />
        <Collapse in={open[2]}>
          <Typography variant="caption" sx={{ display: "block", mb: 2 }}>Stock forecasts use simple-return realized volatility annualized by √252. Intervals use validation residuals. Portfolio volatility remains an on-demand covariance calculation.</Typography>
          <Table size="small"><TableHead><TableRow sx={{ bgcolor: COLORS.sandBeige }}><TableCell>Holding</TableCell><TableCell>Data date</TableCell><TableCell align="right">Forecast</TableCell><TableCell align="right">90% interval</TableCell><TableCell align="right">Trailing 21d</TableCell><TableCell>Selected model</TableCell><TableCell>Status / reason</TableCell></TableRow></TableHead><TableBody>
            {(data?.volatility.holdings_forecasts ?? []).map((item) => <TableRow key={item.symbol}>
              <TableCell><Link to={`/companies/${item.symbol}`} style={{ color: COLORS.deepCharcoal }}>{item.symbol}</Link></TableCell><TableCell>{show(item.prediction_date ?? item.data_cutoff)}</TableCell><TableCell align="right">{decimalPercent(item.forecast_volatility)}</TableCell><TableCell align="right">{item.lower_bound_90 == null || item.upper_bound_90 == null ? "Unavailable" : `${decimalPercent(item.lower_bound_90)} – ${decimalPercent(item.upper_bound_90)}`}</TableCell><TableCell align="right">{decimalPercent(item.trailing_21d_vol)}</TableCell><TableCell>{show(item.model_selected)}</TableCell><TableCell><StatusChip status={item.status} />{item.failure_reason && <Typography variant="caption" sx={{ display: "block" }}>{item.failure_reason}</Typography>}</TableCell>
            </TableRow>)}
          </TableBody></Table>
          {(data?.volatility.error ?? data?.volatility.portfolio_reason) && <Typography variant="caption">{data?.volatility.error ?? data?.volatility.portfolio_reason}</Typography>}
        </Collapse>
      </Paper>

      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="4. Unusual Behaviour & Holding Anomalies" open={open[3]} toggle={() => toggle(3)} />
        <Collapse in={open[3]}>
          <Typography variant="caption">Anomalies are observed statistical outliers, not predictions of future loss. Flag rate: {number(data?.anomalies.anomaly_analysis?.flag_rate_pct, 2)}% · Stability Jaccard: {number(data?.anomalies.anomaly_analysis?.stability_score, 3)}</Typography>
          <Table size="small" sx={{ mt: 1 }}><TableHead><TableRow sx={{ bgcolor: COLORS.sandBeige }}><TableCell>Holding</TableCell><TableCell align="right">Score percentile</TableCell><TableCell>Primary driver</TableCell><TableCell>Status / explanation</TableCell></TableRow></TableHead><TableBody>
            {anomalies.map((item) => <TableRow key={item.symbol}><TableCell>{item.company_name ?? item.symbol}</TableCell><TableCell align="right">{number(item.anomaly_score, 2)}</TableCell><TableCell>{show(item.primary_driver)}</TableCell><TableCell><StatusChip status={item.status} /><Typography variant="caption" sx={{ display: "block" }}>{item.failure_reason ?? item.rationale}</Typography></TableCell></TableRow>)}
          </TableBody></Table>
        </Collapse>
      </Paper>

      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="5. Heuristic Stock Risk Score Walk-Forward Validation" open={open[4]} toggle={() => toggle(4)} />
        <Collapse in={open[4]}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mb: 2 }}>
            <Paper sx={{ p: 2, flex: 1, bgcolor: COLORS.sandBeige }}><Typography variant="overline">Mean monthly Spearman IC</Typography><Typography variant="h5">{number(vol21?.mean_monthly_spearman_ic)}</Typography></Paper>
            <Paper sx={{ p: 2, flex: 1, bgcolor: COLORS.sandBeige }}><Typography variant="overline">Descriptive IC t-statistic</Typography><Typography variant="h5">{number(vol21?.ic_t_statistic)}</Typography></Paper>
            <Paper sx={{ p: 2, flex: 1, bgcolor: COLORS.sandBeige }}><Typography variant="overline">Q5 minus Q1 spread</Typography><Typography variant="h5">{number(vol21?.mean_top_minus_bottom_quintile_spread)}</Typography></Paper>
            <Paper sx={{ p: 2, flex: 1, bgcolor: COLORS.sandBeige }}><Typography variant="overline">Worst-quintile drawdown AUC</Typography><Typography variant="h5">{number(fixed?.worst_quintile_drawdown_21d_auc)}</Typography></Paper>
          </Stack>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="body2">Status:</Typography>
            <StatusChip status={data?.score_validation.status ?? "unavailable"} />
            <Typography variant="body2">Test period: {show(score?.test_period)} · Eligible test rows: {show(score?.test_rows)}</Typography>
          </Stack>
          <Typography variant="caption" sx={{ display: "block", mt: 1 }}>Baseline comparisons: {score?.baseline_comparisons ? JSON.stringify(score.baseline_comparisons) : "Unavailable"}</Typography>
          {data?.score_validation.error && <Alert severity="warning">{data.score_validation.error}</Alert>}
        </Collapse>
      </Paper>

      <Paper sx={{ p: 3, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <PanelHeader title="6. Methodological Assumptions & Limitations" open={open[5]} toggle={() => toggle(5)} />
        <Collapse in={open[5]}><Stack spacing={1}>
          <Typography variant="body2">1. Only Step 1 quality-approved database observations are used; missing required features produce explicit unavailable or insufficient-data states.</Typography>
          <Typography variant="body2">2. Chronological train, validation, and untouched test periods are separated by a 21-session purge.</Typography>
          <Typography variant="body2">3. The risk score is an analytical five-factor score, not an ML model. Its validation remains separate from volatility-model evaluation.</Typography>
          <Typography variant="body2">4. Independent anomaly event review is reported unavailable unless a point-in-time second event source is actually present.</Typography>
          <Typography variant="caption">Methodology: {show(data?.governance.methodology_version)}</Typography>
        </Stack></Collapse>
      </Paper>
    </Stack>
  );
}
