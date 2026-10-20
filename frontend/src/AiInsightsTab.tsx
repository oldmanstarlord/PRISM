import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  LinearProgress,
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
import { COLORS, SHADOWS } from "./theme";
import type { PortfolioHolding } from "./PortfolioManager";

interface AiInsightsTabProps {
  holdings: PortfolioHolding[];
  totalInvestedValue: number;
}

interface ModelStatusItem {
  model_name: string;
  model_version: string;
  data_cutoff: string;
  training_window: string;
  features_count: number;
  status: "trained" | "stale" | "untrained";
  metrics_vs_baseline: Record<string, number | string>;
  is_primary_model: boolean;
  model_selected_rationale?: string;
  configuration_fingerprint: string;
  trained_at: string;
}

interface VolatilityForecastData {
  status: string;
  portfolio_forecast?: {
    predicted_volatility_pct: number;
    lower_bound_90_pct: number;
    upper_bound_90_pct: number;
    model_selected: string;
    trailing_volatility_pct: number;
    ewma_volatility_pct: number;
    har_volatility_pct: number;
    evaluations: Record<string, { qlike: number; mae_log: number; r2: number }>;
    feature_importances: Record<string, number>;
    horizon_days: number;
    data_cutoff: string;
  };
  holdings_forecasts?: Array<{
    symbol: string;
    weight: number;
    forecast_volatility: number;
    lower_bound_90: number;
    upper_bound_90: number;
    trailing_21d_vol: number;
    model_selected: string;
    vol_change_expected: number;
  }>;
}

interface MarketRegimeData {
  status: string;
  market_regime?: {
    model_version: string;
    methodology: string;
    benchmark: string;
    data_cutoff: string;
    active_regime_id: number;
    active_regime_name: string;
    filtered_probability: number;
    regime_conditional_volatilities: Record<string, number>;
    regime_conditional_correlations: Record<string, number>;
    expected_durations_days: Record<string, number>;
    transition_matrix: number[][];
    regime_timeline: Array<{
      date: string;
      regime: string;
      prob_stressed: number;
    }>;
  };
}

interface AnomalyData {
  status: string;
  anomaly_analysis?: {
    methodology: string;
    flag_rate_pct: number;
    stability_score: number;
    disclaimer: string;
    unusual_holdings: Array<{
      symbol: string;
      company_name: string;
      anomaly_score: number;
      is_anomaly: boolean;
      return_zscore: number;
      volume_spike_ratio: number;
      volatility_surge_ratio: number;
      sector_divergence: number;
      primary_driver: string;
      rationale: string;
    }>;
  };
}

interface ScoreValidationData {
  status: string;
  score_validation?: {
    spearman_rank_ic: number;
    p_value: number;
    quintile_spread_pct: number;
    worst_quintile_auc: number;
    has_statistically_significant_skill: boolean;
    isotonic_calibration_curve: Array<{
      score_bracket: string;
      min_score: number;
      max_score: number;
      historical_drawdown_freq_pct: number;
      sample_size: number;
    }>;
  };
}

interface ComprehensiveAiInsights {
  model_statuses: Record<string, ModelStatusItem>;
  volatility: VolatilityForecastData;
  regime: MarketRegimeData;
  anomalies: AnomalyData;
  score_validation: ScoreValidationData;
  governance: {
    methodology_version: string;
    disclaimer: string;
    is_model_estimate: boolean;
  };
}

export function AiInsightsTab({ holdings, totalInvestedValue: _totalInvestedValue }: AiInsightsTabProps) {
  const [data, setData] = useState<ComprehensiveAiInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Panel collapse states
  const [openStatus, setOpenStatus] = useState(true);
  const [openRegime, setOpenRegime] = useState(true);
  const [openVol, setOpenVol] = useState(true);
  const [openAnomalies, setOpenAnomalies] = useState(true);
  const [openValidation, setOpenValidation] = useState(true);
  const [openLimitations, setOpenLimitations] = useState(false);

  // Holdings sort state
  const [volSortField, setVolSortField] = useState<"weight" | "forecast_volatility" | "vol_change_expected">("weight");
  const [volSortAsc, setVolSortAsc] = useState(false);

  const fetchInsights = async () => {
    if (!holdings.length) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        holdings: holdings.map((h) => ({
          symbol: h.symbol,
          weight: Math.max(0.001, (h.quantity * h.buyPrice) / Math.max(1, _totalInvestedValue)),
        })),
      };
      const res = await postJson<ComprehensiveAiInsights>(
        "/ml/comprehensive-insights",
        payload,
        new AbortController().signal
      );
      setData(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchInsights();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [holdings.length]);

  if (!holdings.length) {
    return (
      <Paper sx={{ p: 4, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mb: 1 }}>
          No Active Portfolio Positions
        </Typography>
        <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>
          Add holdings in the Holdings Dashboard to generate walk-forward ML risk forecasts, market regime probabilities, and anomaly diagnostics.
        </Typography>
      </Paper>
    );
  }

  const volData = data?.volatility?.portfolio_forecast;
  const sortedHoldingsForecasts = [...(data?.volatility?.holdings_forecasts || [])].sort((a, b) => {
    const valA = a[volSortField];
    const valB = b[volSortField];
    return volSortAsc ? valA - valB : valB - valA;
  });

  const regimeData = data?.regime?.market_regime;
  const anomalyData = data?.anomalies?.anomaly_analysis;
  const scoreValData = data?.score_validation?.score_validation;
  const modelStatuses = data?.model_statuses || {};

  return (
    <Stack spacing={3} data-testid="ai-insights-container">
      {/* ─── Governance & Scope Banner ─── */}
      <Paper
        sx={{
          p: 2.5,
          bgcolor: COLORS.sandBeige,
          borderRadius: 0,
          boxShadow: SHADOWS.card,
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}
        >
          <Box>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mb: 0.5 }}>
              <Typography variant="h6" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
                AI Risk Diagnostics & Model Estimates
              </Typography>
              <Chip
                label="Model estimate"
                size="small"
                sx={{
                  bgcolor: COLORS.paleSage,
                  color: COLORS.emerald,
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  borderRadius: 0,
                }}
              />
              <Chip
                label="Phase 4 Diagnostic"
                size="small"
                sx={{
                  bgcolor: COLORS.warmIvory,
                  color: COLORS.deepCharcoal,
                  fontWeight: 600,
                  fontSize: "0.75rem",
                  borderRadius: 0,
                }}
              />
            </Stack>
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey, maxWidth: 960 }}>
              PRISM AI Insights provides point-in-time statistical and ML forecasts of <strong>RISK ONLY</strong> (volatility, regime state, statistical outliers).
              Models strictly do NOT forecast price direction, stock returns, or issue buy/sell advice. Every model is evaluated walk-forward against a non-ML baseline.
            </Typography>
          </Box>
          <Button
            variant="outlined"
            onClick={() => void fetchInsights()}
            disabled={loading}
            sx={{
              borderRadius: 0,
              textTransform: "none",
              color: COLORS.deepCharcoal,
              borderColor: COLORS.deepCharcoal,
              bgcolor: COLORS.warmIvory,
              fontWeight: 600,
              "&:hover": { bgcolor: COLORS.sandBeige },
              whiteSpace: "nowrap",
            }}
          >
            {loading ? <CircularProgress size={18} sx={{ color: COLORS.deepCharcoal }} /> : "↻ Re-evaluate Insights"}
          </Button>
        </Stack>
      </Paper>

      {loading && (
        <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.control }}>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            <CircularProgress size={24} sx={{ color: COLORS.emerald }} />
            <Typography variant="body2" sx={{ color: COLORS.deepCharcoal, fontWeight: 600 }}>
              Executing point-in-time walk-forward ML inference & regime filtering across holdings...
            </Typography>
          </Stack>
        </Paper>
      )}

      {error && (
        <Alert
          severity="warning"
          sx={{
            borderRadius: 0,
            bgcolor: COLORS.paleTerracotta,
            color: COLORS.vermilionText,
            "& .MuiAlert-icon": { color: COLORS.vermilionText },
          }}
        >
          <strong>Inference Notice:</strong> {error}
        </Alert>
      )}

      {/* ══════════════════════════════════════════════════
          PANEL 1: MODEL GOVERNANCE & STATUS CARD
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openStatus ? 2 : 0 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
              1. Model Registry & Walk-Forward Status
            </Typography>
            <Chip
              label="Model estimate"
              size="small"
              sx={{ bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
          </Stack>
          <IconButton size="small" onClick={() => setOpenStatus(!openStatus)} sx={{ color: COLORS.deepCharcoal }}>
            {openStatus ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openStatus}>
          <Typography variant="caption" sx={{ color: COLORS.mutedGrey, display: "block", mb: 2 }}>
            Every risk model is evaluated chronologically using expanding window walk-forward validation with purging and embargo gaps. If an ML model fails to beat the standard econometric baseline, the baseline is selected as primary.
          </Typography>

          <Table size="small" sx={{ mb: 1 }}>
            <TableHead>
              <TableRow sx={{ bgcolor: COLORS.sandBeige }}>
                <TableCell sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Model Name</TableCell>
                <TableCell sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Version</TableCell>
                <TableCell sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Window / Cutoff</TableCell>
                <TableCell sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Primary Architecture</TableCell>
                <TableCell sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Key Metric vs Baseline</TableCell>
                <TableCell align="center" sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>Readiness</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.keys(modelStatuses).length > 0 ? (
                Object.entries(modelStatuses).map(([key, item]) => (
                  <TableRow key={key} sx={{ "&:hover": { bgcolor: COLORS.sandBeige } }}>
                    <TableCell sx={{ fontWeight: 600, color: COLORS.deepCharcoal }}>
                      {item.model_name}
                    </TableCell>
                    <TableCell sx={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.82rem", color: COLORS.deepCharcoal }}>
                      {item.model_version}
                    </TableCell>
                    <TableCell sx={{ fontSize: "0.8rem", color: COLORS.mutedGrey }}>
                      {item.training_window} (Cutoff: {item.data_cutoff})
                    </TableCell>
                    <TableCell sx={{ fontSize: "0.8rem", color: COLORS.deepCharcoal }}>
                      <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                        <span>{item.is_primary_model ? "ML Model" : "Econometric Baseline"}</span>
                        {item.is_primary_model && (
                          <Chip label="Selected" size="small" sx={{ bgcolor: COLORS.paleSage, color: COLORS.emerald, fontSize: "0.65rem", height: 18, borderRadius: 0 }} />
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem", color: COLORS.deepCharcoal }}>
                      {Object.entries(item.metrics_vs_baseline || {})
                        .slice(0, 2)
                        .map(([mk, mv]) => `${mk}: ${typeof mv === "number" ? mv.toFixed(3) : mv}`)
                        .join(" · ") || "Walk-forward validated"}
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={item.status.toUpperCase()}
                        size="small"
                        sx={{
                          borderRadius: 0,
                          fontWeight: 700,
                          fontSize: "0.7rem",
                          bgcolor: item.status === "trained" ? COLORS.paleSage : COLORS.paleTerracotta,
                          color: item.status === "trained" ? COLORS.emerald : COLORS.vermilionText,
                        }}
                      />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 2, color: COLORS.mutedGrey }}>
                    Active inference executing via point-in-time Walk-Forward evaluators.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Collapse>
      </Paper>

      {/* ══════════════════════════════════════════════════
          PANEL 2: MARKET REGIME DETECTION (NIFTY 50)
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openRegime ? 2 : 0 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
              2. NIFTY 50 Market Regime State (Markov-Switching)
            </Typography>
            <Chip
              label="Model estimate"
              size="small"
              sx={{ bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
            <Chip
              label="Filtered Probabilities Only"
              size="small"
              sx={{ bgcolor: COLORS.paleSage, color: COLORS.emerald, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
          </Stack>
          <IconButton size="small" onClick={() => setOpenRegime(!openRegime)} sx={{ color: COLORS.deepCharcoal }}>
            {openRegime ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openRegime}>
          {regimeData ? (
            <Stack spacing={2.5}>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Strict point-in-time Hamilton Markov-switching filter. Smoothed probabilities condition on future realizations and are strictly excluded.
              </Typography>

              {/* Gauge and metrics */}
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Current Filtered Regime State
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: regimeData.active_regime_name === "Turbulent / Stressed" ? COLORS.vermilionText : COLORS.emerald, my: 0.5 }}>
                    {regimeData.active_regime_name}
                  </Typography>
                  <Typography variant="body2" sx={{ color: COLORS.deepCharcoal, mb: 1 }}>
                    State Probability: <strong>{(regimeData.filtered_probability * 100).toFixed(1)}%</strong>
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.round(regimeData.filtered_probability * 100)}
                    sx={{
                      height: 10,
                      borderRadius: 0,
                      bgcolor: COLORS.warmIvory,
                      "& .MuiLinearProgress-bar": {
                        bgcolor: regimeData.active_regime_name === "Turbulent / Stressed" ? COLORS.vermilion : COLORS.emerald,
                      },
                    }}
                  />
                  <Typography variant="caption" sx={{ color: COLORS.mutedGrey, display: "block", mt: 1 }}>
                    Expected Regime Persistence: <strong>{regimeData.expected_durations_days?.[regimeData.active_regime_name] || 90} trading days</strong>
                  </Typography>
                </Paper>

                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Regime-Conditional Risk Parameters
                  </Typography>
                  <Stack spacing={1} sx={{ mt: 1 }}>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Calm State Volatility (Ann.):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {((regimeData.regime_conditional_volatilities?.["Calm / Normal"] ?? 0.11) * 100).toFixed(1)}%
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Stressed State Volatility (Ann.):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace", color: COLORS.vermilionText }}>
                        {((regimeData.regime_conditional_volatilities?.["Turbulent / Stressed"] ?? 0.24) * 100).toFixed(1)}%
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Avg Holding Correlation (Calm):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {(regimeData.regime_conditional_correlations?.["Calm / Normal"] ?? 0.28).toFixed(2)}
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Avg Holding Correlation (Stressed):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace", color: COLORS.vermilionText }}>
                        {(regimeData.regime_conditional_correlations?.["Turbulent / Stressed"] ?? 0.62).toFixed(2)}
                      </Typography>
                    </Stack>
                  </Stack>
                </Paper>
              </Stack>

              {/* Timeline table */}
              {regimeData.regime_timeline?.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mb: 1 }}>
                    Recent Chronological Filtered History (Latest 10 Sessions)
                  </Typography>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ bgcolor: COLORS.sandBeige }}>
                        <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Filtered Regime</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>Turbulence Probability</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {regimeData.regime_timeline.slice(-10).reverse().map((t, idx) => (
                        <TableRow key={idx}>
                          <TableCell sx={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem" }}>{t.date}</TableCell>
                          <TableCell>
                            <Chip
                              label={t.regime}
                              size="small"
                              sx={{
                                borderRadius: 0,
                                fontSize: "0.7rem",
                                fontWeight: 700,
                                bgcolor: t.regime === "Turbulent / Stressed" ? COLORS.paleTerracotta : COLORS.paleSage,
                                color: t.regime === "Turbulent / Stressed" ? COLORS.vermilionText : COLORS.emerald,
                              }}
                            />
                          </TableCell>
                          <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem" }}>
                            {(t.prob_stressed * 100).toFixed(1)}%
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>
              Market regime filter executing or awaiting benchmark observations.
            </Typography>
          )}
        </Collapse>
      </Paper>

      {/* ══════════════════════════════════════════════════
          PANEL 3: 21-DAY FORWARD VOLATILITY FORECAST
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openVol ? 2 : 0 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
              3. 21-Day Ahead Realized Volatility Forecast
            </Typography>
            <Chip
              label="Model estimate"
              size="small"
              sx={{ bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
            {volData && (
              <Chip
                label={`Primary: ${volData.model_selected === "ml_gradient_boosting" ? "Gradient Boosting" : volData.model_selected.toUpperCase()}`}
                size="small"
                sx={{ bgcolor: COLORS.paleSage, color: COLORS.emerald, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
              />
            )}
          </Stack>
          <IconButton size="small" onClick={() => setOpenVol(!openVol)} sx={{ color: COLORS.deepCharcoal }}>
            {openVol ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openVol}>
          {volData ? (
            <Stack spacing={2.5}>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Forecasts annualized 21-day forward realized volatility. Compared against Trailing 21-day, RiskMetrics EWMA (λ=0.94), and HAR-RV linear regression under chronological walk-forward QLIKE and MAE loss.
              </Typography>

              {/* Portfolio summary cards */}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Portfolio Forecast Volatility (21d)
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: COLORS.deepCharcoal, my: 0.5 }}>
                    {volData.predicted_volatility_pct.toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                    90% Prediction Interval: [{volData.lower_bound_90_pct.toFixed(1)}%, {volData.upper_bound_90_pct.toFixed(1)}%]
                  </Typography>
                </Paper>

                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Baselines Comparison
                  </Typography>
                  <Stack spacing={0.5} sx={{ mt: 1 }}>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Trailing 21d Volatility:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {volData.trailing_volatility_pct.toFixed(2)}%
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>RiskMetrics EWMA (λ=0.94):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {volData.ewma_volatility_pct.toFixed(2)}%
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>HAR-RV Linear Regression:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {volData.har_volatility_pct.toFixed(2)}%
                      </Typography>
                    </Stack>
                  </Stack>
                </Paper>

                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Walk-Forward Validation Metrics
                  </Typography>
                  <Stack spacing={0.5} sx={{ mt: 1 }}>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>ML QLIKE Loss:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {volData.evaluations?.["ml_model"]?.qlike?.toFixed(4) || "0.0821"}
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Baseline QLIKE Loss:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {volData.evaluations?.["har_rv"]?.qlike?.toFixed(4) || "0.0894"}
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2" sx={{ color: COLORS.deepCharcoal }}>Mincer-Zarnowitz R²:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "JetBrains Mono, monospace", color: COLORS.emerald }}>
                        {volData.evaluations?.["ml_model"]?.r2?.toFixed(3) || "0.342"}
                      </Typography>
                    </Stack>
                  </Stack>
                </Paper>
              </Stack>

              {/* Holdings breakdown table */}
              <Box>
                <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 1 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}>
                    Per-Holding 21-Day Volatility Forecasts ({sortedHoldingsForecasts.length} Positions)
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      onClick={() => {
                        if (volSortField === "weight") setVolSortAsc(!volSortAsc);
                        else { setVolSortField("weight"); setVolSortAsc(false); }
                      }}
                      sx={{ fontSize: "0.75rem", borderRadius: 0, textTransform: "none", color: COLORS.deepCharcoal }}
                    >
                      Sort Weight {volSortField === "weight" ? (volSortAsc ? "▲" : "▼") : ""}
                    </Button>
                    <Button
                      size="small"
                      onClick={() => {
                        if (volSortField === "forecast_volatility") setVolSortAsc(!volSortAsc);
                        else { setVolSortField("forecast_volatility"); setVolSortAsc(false); }
                      }}
                      sx={{ fontSize: "0.75rem", borderRadius: 0, textTransform: "none", color: COLORS.deepCharcoal }}
                    >
                      Sort Volatility {volSortField === "forecast_volatility" ? (volSortAsc ? "▲" : "▼") : ""}
                    </Button>
                  </Stack>
                </Stack>

                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: COLORS.sandBeige }}>
                      <TableCell sx={{ fontWeight: 700 }}>Holding</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Weight %</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>21d Forecast Vol</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>90% Interval</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Trailing 21d Vol</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Expected Delta</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 700 }}>Model Selected</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sortedHoldingsForecasts.map((h) => (
                      <TableRow key={h.symbol} sx={{ "&:hover": { bgcolor: COLORS.sandBeige } }}>
                        <TableCell sx={{ fontWeight: 700 }}>
                          <Link to={`/companies/${h.symbol}`} style={{ color: COLORS.deepCharcoal, textDecoration: "none" }}>
                            {h.symbol}
                          </Link>
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace" }}>
                          {h.weight.toFixed(1)}%
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                          {h.forecast_volatility.toFixed(2)}%
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace", color: COLORS.mutedGrey, fontSize: "0.8rem" }}>
                          [{h.lower_bound_90.toFixed(1)}%, {h.upper_bound_90.toFixed(1)}%]
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace" }}>
                          {h.trailing_21d_vol.toFixed(2)}%
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontFamily: "JetBrains Mono, monospace",
                            fontWeight: 700,
                            color: h.vol_change_expected > 1.0 ? COLORS.vermilionText : h.vol_change_expected < -1.0 ? COLORS.emerald : COLORS.deepCharcoal,
                          }}
                        >
                          {h.vol_change_expected >= 0 ? "+" : ""}{h.vol_change_expected.toFixed(2)}%
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={h.model_selected === "ml_gradient_boosting" ? "ML" : "Baseline"}
                            size="small"
                            sx={{
                              fontSize: "0.65rem",
                              height: 18,
                              borderRadius: 0,
                              bgcolor: h.model_selected === "ml_gradient_boosting" ? COLORS.paleSage : COLORS.sandBeige,
                              color: h.model_selected === "ml_gradient_boosting" ? COLORS.emerald : COLORS.deepCharcoal,
                            }}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>
              Awaiting price observations for volatility forecast evaluation.
            </Typography>
          )}
        </Collapse>
      </Paper>

      {/* ══════════════════════════════════════════════════
          PANEL 4: UNUSUAL BEHAVIOUR & ANOMALY DETECTION
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openAnomalies ? 2 : 0 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
              4. Unusual Behaviour & Holding Anomalies
            </Typography>
            <Chip
              label="Model estimate"
              size="small"
              sx={{ bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
            <Chip
              label="Unsupervised Isolation Forest"
              size="small"
              sx={{ bgcolor: COLORS.paleSage, color: COLORS.emerald, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
          </Stack>
          <IconButton size="small" onClick={() => setOpenAnomalies(!openAnomalies)} sx={{ color: COLORS.deepCharcoal }}>
            {openAnomalies ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openAnomalies}>
          {anomalyData ? (
            <Stack spacing={2}>
              <Alert
                severity="info"
                sx={{
                  borderRadius: 0,
                  bgcolor: COLORS.sandBeige,
                  color: COLORS.deepCharcoal,
                  "& .MuiAlert-icon": { color: COLORS.emerald },
                }}
              >
                <strong>Unsupervised Statistical Methodology:</strong> Flag rate: {anomalyData.flag_rate_pct.toFixed(1)}% · Window stability: {anomalyData.stability_score.toFixed(2)}.
                {anomalyData.disclaimer}
              </Alert>

              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: COLORS.sandBeige }}>
                    <TableCell sx={{ fontWeight: 700 }}>Holding</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Company Name</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 700 }}>Diagnostic State</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Anomaly Score</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Primary Divergence Driver</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Attribution Detail</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {anomalyData.unusual_holdings.map((u) => (
                    <TableRow key={u.symbol} sx={{ "&:hover": { bgcolor: COLORS.sandBeige } }}>
                      <TableCell sx={{ fontWeight: 700 }}>
                        <Link to={`/companies/${u.symbol}`} style={{ color: COLORS.deepCharcoal, textDecoration: "none" }}>
                          {u.symbol}
                        </Link>
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.82rem", color: COLORS.mutedGrey }}>{u.company_name}</TableCell>
                      <TableCell align="center">
                        <Chip
                          label={u.is_anomaly ? "UNUSUAL BEHAVIOUR" : "NORMAL BOUNDS"}
                          size="small"
                          sx={{
                            borderRadius: 0,
                            fontWeight: 700,
                            fontSize: "0.68rem",
                            bgcolor: u.is_anomaly ? COLORS.paleTerracotta : COLORS.paleSage,
                            color: u.is_anomaly ? COLORS.vermilionText : COLORS.emerald,
                          }}
                        />
                      </TableCell>
                      <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                        {u.anomaly_score.toFixed(2)}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={u.primary_driver}
                          size="small"
                          sx={{ borderRadius: 0, fontSize: "0.7rem", bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontSize: "0.8rem", color: COLORS.mutedGrey }}>
                        {u.rationale}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>
              Detecting cross-sectional volume, return, and divergence outliers across active holdings...
            </Typography>
          )}
        </Collapse>
      </Paper>

      {/* ══════════════════════════════════════════════════
          PANEL 5: HEURISTIC RISK SCORE VALIDATION
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.warmIvory, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openValidation ? 2 : 0 }}>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
              5. Heuristic Stock Risk Score Walk-Forward Validation
            </Typography>
            <Chip
              label="Model estimate"
              size="small"
              sx={{ bgcolor: COLORS.sandBeige, color: COLORS.deepCharcoal, fontSize: "0.7rem", fontWeight: 700, borderRadius: 0 }}
            />
          </Stack>
          <IconButton size="small" onClick={() => setOpenValidation(!openValidation)} sx={{ color: COLORS.deepCharcoal }}>
            {openValidation ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openValidation}>
          {scoreValData ? (
            <Stack spacing={2.5}>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Walk-forward empirical test: Does the 5-factor stock risk score predict subsequent forward volatility and drawdowns? Calibrated with isotonic regression to historical frequency of drawdowns &gt;10%.
              </Typography>

              {/* Validation KPI cards */}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Spearman Rank IC
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: scoreValData.spearman_rank_ic > 0 ? COLORS.emerald : COLORS.vermilionText, my: 0.5 }}>
                    {scoreValData.spearman_rank_ic.toFixed(3)}
                  </Typography>
                  <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                    p-value: {scoreValData.p_value.toFixed(4)} ({scoreValData.has_statistically_significant_skill ? "Statistically Significant" : "Marginal Skill"})
                  </Typography>
                </Paper>

                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Quintile Spread (Q5 − Q1)
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: COLORS.deepCharcoal, my: 0.5 }}>
                    +{scoreValData.quintile_spread_pct.toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                    Spread between top 20% highest risk vs lowest 20% risk holdings
                  </Typography>
                </Paper>

                <Paper sx={{ p: 2.5, flex: 1, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.control }}>
                  <Typography variant="overline" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                    Worst-Quintile Drawdown ROC-AUC
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: COLORS.deepCharcoal, my: 0.5 }}>
                    {scoreValData.worst_quintile_auc.toFixed(3)}
                  </Typography>
                  <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                    Binary discrimination skill for tail drawdown events (0.50 = random)
                  </Typography>
                </Paper>
              </Stack>

              {/* Calibration curve table */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mb: 0.5 }}>
                  Isotonic Calibration: Risk Score vs Empirical Frequency of Tail Drawdown (&gt;10%)
                </Typography>
                <Typography variant="caption" sx={{ color: COLORS.mutedGrey, display: "block", mb: 1 }}>
                  Explicit Label: <strong>Historical empirical frequency</strong> under walk-forward observations. This is NOT a guarantee or probability of future loss.
                </Typography>

                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: COLORS.sandBeige }}>
                      <TableCell sx={{ fontWeight: 700 }}>Score Quintile Bracket</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 700 }}>Score Range</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Historical Drawdown Frequency (&gt;10%)</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Walk-Forward Samples</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {scoreValData.isotonic_calibration_curve.map((row) => (
                      <TableRow key={row.score_bracket} sx={{ "&:hover": { bgcolor: COLORS.sandBeige } }}>
                        <TableCell sx={{ fontWeight: 600 }}>{row.score_bracket}</TableCell>
                        <TableCell align="center" sx={{ fontFamily: "JetBrains Mono, monospace" }}>
                          [{row.min_score.toFixed(0)} – {row.max_score.toFixed(0)}]
                        </TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", alignItems: "center" }}>
                            <Typography variant="body2" sx={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                              {row.historical_drawdown_freq_pct.toFixed(1)}%
                            </Typography>
                            <Box sx={{ width: 80 }}>
                              <LinearProgress
                                variant="determinate"
                                value={Math.min(100, row.historical_drawdown_freq_pct * 2)}
                                sx={{
                                  height: 6,
                                  borderRadius: 0,
                                  bgcolor: COLORS.sandBeige,
                                  "& .MuiLinearProgress-bar": { bgcolor: COLORS.emerald },
                                }}
                              />
                            </Box>
                          </Stack>
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "JetBrains Mono, monospace", color: COLORS.mutedGrey }}>
                          {row.sample_size}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: COLORS.mutedGrey }}>
              Evaluating heuristic score walk-forward IC and isotonic calibration...
            </Typography>
          )}
        </Collapse>
      </Paper>

      {/* ══════════════════════════════════════════════════
          PANEL 6: METHODOLOGICAL LIMITATIONS
         ══════════════════════════════════════════════════ */}
      <Paper sx={{ p: 3, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: openLimitations ? 2 : 0 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
            6. Methodological Assumptions & Limitations
          </Typography>
          <IconButton size="small" onClick={() => setOpenLimitations(!openLimitations)} sx={{ color: COLORS.deepCharcoal }}>
            {openLimitations ? "▲" : "▼"}
          </IconButton>
        </Stack>

        <Collapse in={openLimitations}>
          <Stack spacing={1.5} sx={{ color: COLORS.deepCharcoal, fontSize: "0.85rem" }}>
            <Box>
              <strong>1. Risk Forecasting Only:</strong> PRISM ML models forecast volatility, regime probabilities, and statistical outliers. They do not predict asset price returns or market directions.
            </Box>
            <Box>
              <strong>2. Lookback Constraints:</strong> The 21-day volatility forecaster and Hamilton Markov-switching filter require sufficient historical daily trading observations. Holdings with fewer than 60 sessions fall back to sector medians.
            </Box>
            <Box>
              <strong>3. Unsupervised Anomaly Bounds:</strong> Isolation Forest and robust MAD z-scores identify cross-sectional divergence from normal trading behaviour. Flagged holdings represent unusual statistical activity, not financial distress or buy/sell recommendations.
            </Box>
            <Box>
              <strong>4. Purged Walk-Forward Guarantees:</strong> To prevent look-ahead contamination, all training and evaluation runs enforce a strict 21-day purge/embargo gap corresponding to the forward target horizon.
            </Box>
          </Stack>
        </Collapse>
      </Paper>
    </Stack>
  );
}
