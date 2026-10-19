import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { Link } from "react-router-dom";

import type {
  ComprehensiveRiskResponse,
  EulerRiskContribution,
  PortfolioAnalysisResponse,
  RiskLevel,
  SectorExposureItem,
  StockRiskProfile,
} from "./types";

function formatCurrency(val: number | null | undefined, maximumFractionDigits = 0): string {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `₹${val.toLocaleString("en-IN", {
    minimumFractionDigits: maximumFractionDigits === 0 ? 0 : 2,
    maximumFractionDigits,
  })}`;
}

function formatPercent(val: number | null | undefined, digits = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `${val >= 0 ? "+" : ""}${val.toFixed(digits)}%`;
}

const riskLevelColors: Record<RiskLevel, { bg: string; text: string }> = {
  Low: { bg: "#DCE9DE", text: "#046A38" },
  Moderate: { bg: "#E3D7C4", text: "#8A5A00" },
  High: { bg: "#F6D9CC", text: "#B8321A" },
  "Very High": { bg: "#F6D9CC", text: "#E34222" },
};

const trendIcons: Record<string, { icon: string; label: string; color: "success" | "warning" | "error" | "default" }> = {
  increasing: { icon: "↗ Rising", label: "Rising risk", color: "error" },
  decreasing: { icon: "↘ Cooling", label: "Cooling risk", color: "success" },
  stable: { icon: "→ Stable", label: "Stable risk", color: "default" },
};

/* ─────────────────────────────────────────────────────────────
   1. STOCK-LEVEL RISK SECTION
   ───────────────────────────────────────────────────────────── */

interface StockRiskSectionProps {
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function StockRiskSection({ comprehensiveRisk, loading, onRefresh }: StockRiskSectionProps) {
  const [selectedStock, setSelectedStock] = useState<StockRiskProfile | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<"1M" | "3M" | "6M" | "1Y">("1Y");

  if (!comprehensiveRisk) {
    return (
      <Paper sx={{ p: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Stock Risk Assessment
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Multi-window volatility, downside semi-deviation, max drawdown, and explainable scoring for your holdings.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "#F9EBD7" }} /> : "Calculate Stock Risk"}
        </Button>
      </Paper>
    );
  }

  const { stock_profiles } = comprehensiveRisk;

  return (
    <Stack spacing={3}>
      {/* Header & Horizon Controls */}
      <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Stock-Level Risk Assessment
          </Typography>
          <Typography color="text.secondary">
            Multi-horizon volatility, market sensitivity (Beta), and explainable 0–100 risk scoring.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>
            LOOKBACK:
          </Typography>
          {(["1M", "3M", "6M", "1Y"] as const).map((h) => (
            <Button
              key={h}
              size="small"
              variant={selectedHorizon === h ? "contained" : "outlined"}
              onClick={() => setSelectedHorizon(h)}
              sx={{ minWidth: 46 }}
            >
              {h}
            </Button>
          ))}
        </Stack>
      </Stack>

      {/* Main Stock Risk Table */}
      <Paper sx={{ p: 3, overflowX: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Holding</TableCell>
              <TableCell align="right">Weight</TableCell>
              <TableCell align="center">Risk Score (0–100)</TableCell>
              <TableCell align="center">Classification</TableCell>
              <TableCell align="right">Volatility ({selectedHorizon})</TableCell>
              <TableCell align="right">Downside Vol</TableCell>
              <TableCell align="right">Max Drawdown</TableCell>
              <TableCell align="right">Beta (NIFTY)</TableCell>
              <TableCell align="right">Return vs Cost</TableCell>
              <TableCell align="center">Recent Trend</TableCell>
              <TableCell align="center">Sector Divergence</TableCell>
              <TableCell align="center">Deep Dive</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {stock_profiles.map((s) => {
              const win = s.windows[selectedHorizon] || s.windows["1Y"];
              const riskColor = riskLevelColors[s.risk_classification] || { bg: "#f5f5f5", text: "#666" };
              const trendInfo = trendIcons[s.recent_risk_change] || trendIcons.stable;

              return (
                <TableRow key={s.symbol} hover>
                  <TableCell>
                    <Typography sx={{ fontWeight: 700 }}>
                      <Link to={`/companies/${s.symbol}`} style={{ textDecoration: "none", color: "#00796b" }}>
                        {s.symbol}
                      </Link>
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {s.company_name} · {s.sector}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{(s.weight * 100).toFixed(1)}%</TableCell>
                  <TableCell align="center">
                    <Chip
                      size="small"
                      label={`${s.overall_score.toFixed(0)}/100`}
                      sx={{
                        bgcolor: riskColor.bg,
                        color: riskColor.text,
                        fontWeight: 700,
                        border: `1px solid ${riskColor.text}44`,
                      }}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2" sx={{ fontWeight: 600, color: riskColor.text }}>
                      {s.risk_classification}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {(win.annualized_volatility * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell align="right">{(win.downside_volatility * 100).toFixed(1)}%</TableCell>
                  <TableCell align="right" sx={{ color: "error.main", fontWeight: 600 }}>
                    -{(win.max_drawdown * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Beta relative to NIFTY 50 index">
                      <span>{win.beta.toFixed(2)}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">
                    {s.unrealized_return !== null ? (
                      <Box>
                        <Typography
                          variant="body2"
                          sx={{
                            fontWeight: 700,
                            color: s.unrealized_return >= 0 ? "success.main" : "error.main",
                          }}
                        >
                          {formatPercent(s.unrealized_return)}
                        </Typography>
                        {s.unrealized_pnl !== null && (
                          <Typography variant="caption" color="text.secondary">
                            {formatCurrency(s.unrealized_pnl)}
                          </Typography>
                        )}
                      </Box>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Chip size="small" label={trendInfo.icon} color={trendInfo.color} sx={{ fontSize: "0.72rem" }} />
                  </TableCell>
                  <TableCell align="center">
                    {s.sector_divergence_20d !== null ? (
                      <Chip
                        size="small"
                        label={`${s.sector_divergence_20d > 0 ? "+" : ""}${s.sector_divergence_20d.toFixed(2)}σ`}
                        color={Math.abs(s.sector_divergence_20d) > 2.0 ? "warning" : "default"}
                        sx={{ fontSize: "0.75rem" }}
                      />
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Button
                      size="small"
                      onClick={() => setSelectedStock(s)}
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        bgcolor: "#E3D7C4",
                        color: "#292D2A",
                        fontWeight: 600,
                        boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                        "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                      }}
                    >
                      Explain
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Paper>

      {/* Deep-Dive Explainable Stock Modal */}
      {selectedStock && (
        <Dialog open onClose={() => setSelectedStock(null)} maxWidth="md" fullWidth>
          <DialogTitle sx={{ bgcolor: "#292D2A", color: "#F9EBD7" }}>
            <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 700, color: "#F9EBD7" }}>
                  {selectedStock.symbol} — Explainable Risk Breakdown
                </Typography>
                <Typography variant="caption" sx={{ color: "#E3D7C4" }}>
                  {selectedStock.company_name} · {selectedStock.sector} · {selectedStock.data_coverage}
                </Typography>
              </Box>
              <Chip
                label={`${selectedStock.overall_score.toFixed(0)}/100 · ${selectedStock.risk_classification}`}
                sx={{
                  bgcolor: riskLevelColors[selectedStock.risk_classification]?.bg || "#E3D7C4",
                  color: riskLevelColors[selectedStock.risk_classification]?.text || "#292D2A",
                  fontWeight: 700,
                  borderRadius: 0,
                }}
              />
            </Stack>
          </DialogTitle>

          <DialogContent sx={{ mt: 2 }}>
            <Stack spacing={3}>
              {/* Dynamic Narrative Explanation */}
              <Alert severity="info" icon={false} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", color: "#292D2A", border: "none", boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5, color: "#292D2A" }}>
                  Dynamic Quantitative Explanation
                </Typography>
                <Typography variant="body2" sx={{ color: "#292D2A" }}>{selectedStock.narrative_explanation}</Typography>
              </Alert>

              {/* Primary Risk Drivers */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, color: "#292D2A" }}>
                  Primary Identified Risk Drivers:
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                  {selectedStock.primary_drivers.map((d) => (
                    <Chip
                      key={d}
                      label={d}
                      size="small"
                      sx={{
                        borderRadius: 0,
                        fontWeight: 600,
                        bgcolor: "#DCE9DE",
                        color: "#046A38",
                      }}
                    />
                  ))}
                </Stack>
              </Box>

              {/* 5 Normalized Factor Scores */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Configurable Risk Factor Contributions (Sum = {selectedStock.overall_score.toFixed(1)}/100)
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Risk Factor</TableCell>
                      <TableCell align="right">Observed Value</TableCell>
                      <TableCell align="right">Normalized (0–100)</TableCell>
                      <TableCell align="right">Weight</TableCell>
                      <TableCell align="right">Score Contribution</TableCell>
                      <TableCell>Factor Interpretation</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedStock.factors.map((f) => (
                      <TableRow key={f.factor_name}>
                        <TableCell sx={{ fontWeight: 600 }}>{f.factor_name}</TableCell>
                        <TableCell align="right">{f.raw_value}</TableCell>
                        <TableCell align="right">
                          <Chip
                            size="small"
                            label={f.normalized_score.toFixed(1)}
                            color={f.normalized_score > 65 ? "error" : f.normalized_score > 40 ? "warning" : "success"}
                            sx={{ height: 20, fontSize: "0.75rem" }}
                          />
                        </TableCell>
                        <TableCell align="right">{(f.weight * 100).toFixed(0)}%</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>
                          +{f.contribution.toFixed(2)} pts
                        </TableCell>
                        <TableCell sx={{ color: "text.secondary", fontSize: "0.85rem" }}>
                          {f.interpretation}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>

              {/* Multi-Window Comparison Matrix */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Multi-Horizon Risk & Performance Matrix (1M, 3M, 6M, 1Y)
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Horizon</TableCell>
                      <TableCell align="right">Trading Days</TableCell>
                      <TableCell align="right">Stock Return</TableCell>
                      <TableCell align="right">NIFTY 50 Return</TableCell>
                      <TableCell align="right">Excess Alpha</TableCell>
                      <TableCell align="right">Ann. Volatility</TableCell>
                      <TableCell align="right">Downside Vol</TableCell>
                      <TableCell align="right">Max Drawdown</TableCell>
                      <TableCell align="right">Beta</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(["1M", "3M", "6M", "1Y"] as const).map((wKey) => {
                      const m = selectedStock.windows[wKey];
                      if (!m) return null;
                      return (
                        <TableRow key={wKey}>
                          <TableCell sx={{ fontWeight: 700 }}>{wKey}</TableCell>
                          <TableCell align="right">{m.observations}</TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              fontWeight: 600,
                              color: m.stock_return >= 0 ? "success.main" : "error.main",
                            }}
                          >
                            {formatPercent(m.stock_return * 100)}
                          </TableCell>
                          <TableCell align="right">{formatPercent(m.benchmark_return * 100)}</TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              color: m.excess_return >= 0 ? "success.main" : "error.main",
                            }}
                          >
                            {formatPercent(m.excess_return * 100)}
                          </TableCell>
                          <TableCell align="right">{(m.annualized_volatility * 100).toFixed(1)}%</TableCell>
                          <TableCell align="right">{(m.downside_volatility * 100).toFixed(1)}%</TableCell>
                          <TableCell align="right" sx={{ color: "error.main" }}>
                            -{(m.max_drawdown * 100).toFixed(1)}%
                          </TableCell>
                          <TableCell align="right">{m.beta.toFixed(2)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </Box>

              {/* Since-Purchase Analysis */}
              <Box
                sx={{
                  bgcolor: "#F9EBD7",
                  p: 2,
                  borderRadius: 0,
                  border: "none",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, color: "#292D2A" }}>
                  Position-Level Performance Since Purchase
                </Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" }, gap: 2 }}>
                  <Box>
                    <Typography variant="caption" sx={{ color: "#686B64" }}>
                      Purchase Price
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                      {formatCurrency(selectedStock.purchase_price, 2)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Current Price
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 700 }}>
                      {formatCurrency(selectedStock.current_price, 2)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Unrealized Return
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{
                        fontWeight: 700,
                        color:
                          selectedStock.unrealized_return !== null && selectedStock.unrealized_return >= 0
                            ? "success.main"
                            : "error.main",
                      }}
                    >
                      {formatPercent(selectedStock.unrealized_return)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Drawdown Since Purchase
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 700, color: "error.main" }}>
                      {selectedStock.drawdown_since_purchase !== null
                        ? `-${selectedStock.drawdown_since_purchase.toFixed(1)}%`
                        : "—"}
                    </Typography>
                  </Box>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                  * Purchase-price comparisons describe your investment position, while volatility, downside risk, and market sensitivity determine the stock's objective risk score.
                </Typography>
              </Box>
            </Stack>
          </DialogContent>

          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setSelectedStock(null)}>Close</Button>
          </DialogActions>
        </Dialog>
      )}
    </Stack>
  );
}

/* ─────────────────────────────────────────────────────────────
   2. PORTFOLIO-LEVEL RISK SECTION
   ───────────────────────────────────────────────────────────── */

interface PortfolioRiskSectionProps {
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  analysis: PortfolioAnalysisResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function PortfolioRiskSection({
  comprehensiveRisk,
  analysis,
  loading,
  onRefresh,
}: PortfolioRiskSectionProps) {
  if (!comprehensiveRisk) {
    return (
      <Paper sx={{ p: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Portfolio Risk Analytics
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Annualized covariance volatility, historical drawdown, portfolio beta, and Euler risk decomposition.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "#F9EBD7" }} /> : "Calculate Portfolio Risk"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const pRiskColor = riskLevelColors[portfolio_profile.portfolio_classification] || { bg: "#f5f5f5", text: "#666" };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Portfolio-Level Risk Analysis
        </Typography>
        <Typography color="text.secondary">
          Covariance-derived volatility, systematic market beta, and Euler risk contribution shares.
        </Typography>
      </Box>

      {/* Top Metric KPI Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
        {/* Card 1: Portfolio Risk Score */}
        <Paper sx={{ p: 2.5, flex: "1 1 200px" }}>
          <Typography variant="overline" color="text.secondary">
            Overall Portfolio Risk
          </Typography>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mt: 0.5 }}>
            <Box
              sx={{
                width: 52,
                height: 52,
                borderRadius: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: pRiskColor.bg,
                boxShadow: "0 2px 6px rgba(41,45,42,0.10)",
              }}
            >
              <Typography sx={{ fontWeight: 800, color: pRiskColor.text, fontSize: "1.2rem" }}>
                {portfolio_profile.portfolio_risk_score.toFixed(0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: pRiskColor.text }}>
                {portfolio_profile.portfolio_classification} Risk
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Trend: {portfolio_profile.historical_risk_trend.toUpperCase()}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Card 2: Annualized Volatility */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Portfolio Volatility
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {portfolio_profile.annualized_volatility.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Annualized covariance σ
          </Typography>
        </Paper>

        {/* Card 3: Downside Volatility */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Downside Volatility
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {portfolio_profile.downside_volatility.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Negative-return semi-deviation
          </Typography>
        </Paper>

        {/* Card 4: Historical Maximum Drawdown */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Max Drawdown
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700, color: "error.main" }}>
            -{portfolio_profile.max_drawdown.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Peak-to-trough decline
          </Typography>
        </Paper>

        {/* Card 5: Portfolio Beta */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Portfolio Beta (vs NIFTY 50)
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {portfolio_profile.portfolio_beta.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Systematic market sensitivity
          </Typography>
        </Paper>
      </Stack>

      {/* Summary Findings & Dynamic Commentary */}
      {portfolio_profile.summary_findings.length > 0 && (
        <Alert severity="info" icon={false} sx={{ borderLeft: "4px solid #00796b" }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
            Key Portfolio Risk Observations:
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2 }}>
            {portfolio_profile.summary_findings.map((f) => (
              <li key={f}>
                <Typography variant="body2">{f}</Typography>
              </li>
            ))}
          </Box>
        </Alert>
      )}

      {/* Holding Euler Risk Contributions Table */}
      <Paper sx={{ p: 3, overflowX: "auto" }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Holding Risk Contribution (Euler Decomposition)
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Decomposes total portfolio variance via covariance: w_i * (Σ w)_i / σ_p^2. Shares sum to ~100%.
        </Typography>

        <Table size="small" sx={{ mt: 1 }}>
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Portfolio Weight</TableCell>
              <TableCell align="right">Asset Volatility</TableCell>
              <TableCell align="right">Marginal Risk</TableCell>
              <TableCell align="right">Risk Contribution Share</TableCell>
              <TableCell sx={{ minWidth: 200 }}>Share of Total Portfolio Risk</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {portfolio_profile.risk_contributions
              .slice()
              .sort((a, b) => b.risk_contribution_share - a.risk_contribution_share)
              .map((rc: EulerRiskContribution) => (
                <TableRow key={rc.symbol} hover>
                  <TableCell sx={{ fontWeight: 700 }}>
                    <Link to={`/companies/${rc.symbol}`} style={{ textDecoration: "none", color: "#00796b" }}>
                      {rc.symbol}
                    </Link>
                  </TableCell>
                  <TableCell align="right">{(rc.weight * 100).toFixed(1)}%</TableCell>
                  <TableCell align="right">{(rc.annualized_volatility * 100).toFixed(1)}%</TableCell>
                  <TableCell align="right">{(rc.marginal_risk * 100).toFixed(1)}%</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {rc.risk_contribution_share.toFixed(1)}%
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                      <LinearProgress
                        variant="determinate"
                        value={Math.min(Math.max(rc.risk_contribution_share, 0), 100)}
                        color={rc.risk_contribution_share > 35 ? "error" : rc.risk_contribution_share > 20 ? "warning" : "primary"}
                        sx={{ flex: 1, height: 8, borderRadius: 0 }}
                      />
                      <Typography variant="caption" sx={{ minWidth: 35, fontWeight: 700, fontFamily: "JetBrains Mono, monospace" }}>
                        {rc.risk_contribution_share.toFixed(0)}%
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </Paper>

      {/* Historical Performance & Drawdown Chart if analysis is available */}
      {analysis?.performance && analysis.performance.points.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            Simulated 250-Day Portfolio Performance & Drawdown
          </Typography>
          <Typography color="text.secondary" gutterBottom>
            Constant-weight daily-rebalanced equity curve (base = 100) and historical drawdown profile.
          </Typography>
          <Box sx={{ mt: 2 }}>
            <PortfolioPerformanceMiniChart points={analysis.performance.points} />
          </Box>
        </Paper>
      )}

      {/* Methodology & Documentation */}
      <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }} gutterBottom>
          Methodology: Custom 0–100 Risk Score vs Statistical Metrics
        </Typography>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          The PRISM 0–100 Portfolio Risk Score is a calibrated synthesis constructed from four fundamental factors:
        </Typography>
        <Box component="ul" sx={{ m: 0, pl: 2, mb: 1.5 }}>
          <li>
            <Typography variant="body2">
              <strong>Annualized Volatility (35% weight):</strong> Derived from the 252-day sample covariance matrix (w^T Σ w).
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              <strong>Downside Volatility (25% weight):</strong> Annualized semi-deviation measuring negative return variance.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              <strong>Historical Maximum Drawdown (25% weight):</strong> Peak-to-trough capital decline over simulated historical wealth.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              <strong>Portfolio Beta (15% weight):</strong> Capital-weighted systematic sensitivity to the NIFTY 50 benchmark.
            </Typography>
          </li>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Note: This custom scoring is distinct from raw mathematical standard deviation. It does not average individual stock scores, but evaluates true portfolio co-movements and cross-asset covariance.
        </Typography>
      </Paper>
    </Stack>
  );
}

/* ─────────────────────────────────────────────────────────────
   3. SECTOR EXPOSURE SECTION
   ───────────────────────────────────────────────────────────── */

interface SectorExposureSectionProps {
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function SectorExposureSection({ comprehensiveRisk, loading, onRefresh }: SectorExposureSectionProps) {
  if (!comprehensiveRisk) {
    return (
      <Paper sx={{ p: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Sector Exposure & Concentration
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Sector allocation weights, benchmark limits, and sector-related risk contribution shares.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "#F9EBD7" }} /> : "Analyze Sector Exposure"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const sectors = portfolio_profile.sector_exposure;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Sector Exposure & Concentration Analysis
        </Typography>
        <Typography color="text.secondary">
          Distribution of capital across industries compared with documented prudent concentration targets (25% ceiling).
        </Typography>
      </Box>

      {/* Sector KPI Summary Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <Paper sx={{ p: 2.5, flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Effective Number of Sectors
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {portfolio_profile.effective_sectors.toFixed(1)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            1 / Sector HHI (higher = broader sector breadth)
          </Typography>
        </Paper>

        <Paper sx={{ p: 2.5, flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Sector HHI Index
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {portfolio_profile.sector_hhi.toFixed(3)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Herfindahl–Hirschman Index (&lt; 0.25 is balanced)
          </Typography>
        </Paper>

        <Paper sx={{ p: 2.5, flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Top Sector Allocation
          </Typography>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              color: sectors[0]?.weight > 35 ? "error.main" : sectors[0]?.weight > 25 ? "warning.main" : "text.primary",
            }}
          >
            {sectors[0]?.weight.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {sectors[0]?.sector || "None"} (Benchmark target: 25%)
          </Typography>
        </Paper>
      </Stack>

      {/* Sector Breakdown Table */}
      <Paper sx={{ p: 3, overflowX: "auto" }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Industry Weights vs Risk Contribution Share
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Compares capital allocation with actual Euler risk contribution. Disproportionate risk shares indicate high-volatility sectors.
        </Typography>

        <Table size="small" sx={{ mt: 1 }}>
          <TableHead>
            <TableRow>
              <TableCell>Industry Sector</TableCell>
              <TableCell align="right">Capital Weight</TableCell>
              <TableCell align="right">Benchmark Ceiling</TableCell>
              <TableCell align="center">Allocation Status</TableCell>
              <TableCell align="right">Risk Contribution Share</TableCell>
              <TableCell align="center">Holdings Count</TableCell>
              <TableCell>Constituent Stocks</TableCell>
              <TableCell align="center">Avg. 20D Sector Divergence</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sectors.map((sec: SectorExposureItem) => {
              const statusColor: "success" | "warning" | "error" =
                sec.allocation_status === "Excessive"
                  ? "error"
                  : sec.allocation_status === "Elevated"
                  ? "warning"
                  : "success";

              return (
                <TableRow key={sec.sector} hover>
                  <TableCell sx={{ fontWeight: 700 }}>{sec.sector}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {sec.weight.toFixed(1)}%
                  </TableCell>
                  <TableCell align="right" sx={{ color: "text.secondary" }}>
                    {sec.benchmark_target.toFixed(1)}%
                  </TableCell>
                  <TableCell align="center">
                    <Chip size="small" label={sec.allocation_status} color={statusColor} sx={{ fontWeight: 600 }} />
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontWeight: 700,
                      color: sec.risk_contribution_share > sec.weight * 1.25 ? "error.main" : "inherit",
                    }}
                  >
                    {sec.risk_contribution_share.toFixed(1)}%
                  </TableCell>
                  <TableCell align="center">{sec.stock_count}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
                      {sec.stocks.map((sym: string) => (
                        <Chip
                          key={sym}
                          label={sym}
                          size="small"
                          component={Link}
                          to={`/companies/${sym}`}
                          clickable
                          sx={{
                            textDecoration: "none",
                            borderRadius: 0,
                            border: "none",
                            bgcolor: "#F9EBD7",
                            color: "#292D2A",
                            fontWeight: 600,
                            "&:hover": { bgcolor: "#E3D7C4" },
                          }}
                        />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell align="center">
                    {sec.average_sector_divergence !== null ? (
                      <Chip
                        size="small"
                        label={`${sec.average_sector_divergence > 0 ? "+" : ""}${sec.average_sector_divergence.toFixed(2)}σ`}
                        color={Math.abs(sec.average_sector_divergence) > 1.5 ? "warning" : "default"}
                        sx={{ fontSize: "0.75rem" }}
                      />
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Paper>

      {/* Visual Weight vs Risk Contribution Comparison */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }} gutterBottom>
          Capital Allocation vs Risk Contribution by Sector
        </Typography>
        <Stack spacing={2} sx={{ mt: 2 }}>
          {sectors.map((sec: SectorExposureItem) => (
            <Box key={sec.sector}>
              <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {sec.sector}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Weight: {sec.weight.toFixed(1)}% | Risk Share: {sec.risk_contribution_share.toFixed(1)}%
                </Typography>
              </Stack>
              <Box sx={{ display: "flex", gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ fontSize: "0.68rem", color: "#686B64" }}>
                    Capital:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(sec.weight, 100)}
                    sx={{ height: 6, borderRadius: 0 }}
                    color="primary"
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ fontSize: "0.68rem", color: "#686B64" }}>
                    Risk Contribution:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(Math.max(sec.risk_contribution_share, 0), 100)}
                    sx={{ height: 6, borderRadius: 0 }}
                    color={sec.risk_contribution_share > sec.weight ? "warning" : "success"}
                  />
                </Box>
              </Box>
            </Box>
          ))}
        </Stack>
      </Paper>
    </Stack>
  );
}

/* ─────────────────────────────────────────────────────────────
   4. DIVERSIFICATION INDEX SECTION
   ───────────────────────────────────────────────────────────── */

interface DiversificationSectionProps {
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export function DiversificationSection({
  comprehensiveRisk,
  loading,
  onRefresh,
}: DiversificationSectionProps) {
  if (!comprehensiveRisk) {
    return (
      <Paper sx={{ p: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Diversification Index & Correlation Matrix
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Comprehensive multi-asset diversification scoring, HHI effective holdings, and co-movement matrix.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "#F9EBD7" }} /> : "Compute Diversification Index"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const gradeColors: Record<string, { bg: string; text: string }> = {
    A: { bg: "#DCE9DE", text: "#046A38" },
    B: { bg: "#E3D7C4", text: "#046A38" },
    C: { bg: "#F9EBD7", text: "#8A5A00" },
    D: { bg: "#F6D9CC", text: "#B8321A" },
  };
  const gColor = gradeColors[portfolio_profile.diversification_grade] || { bg: "#E3D7C4", text: "#292D2A" };

  const symbols = Object.keys(portfolio_profile.correlation_matrix);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Portfolio Diversification Assessment
        </Typography>
        <Typography color="text.secondary">
          Mathematical measures of asset dispersion, effective bets, and pairwise correlation co-movements.
        </Typography>
      </Box>

      {/* Diversification Score & Metrics Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
        {/* Card 1: Diversification Score */}
        <Paper sx={{ p: 2.5, flex: "1 1 240px" }}>
          <Typography variant="overline" color="text.secondary">
            Diversification Score (0–100)
          </Typography>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center", mt: 0.5 }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: gColor.bg,
                boxShadow: "0 2px 6px rgba(41,45,42,0.10)",
              }}
            >
              <Typography sx={{ fontWeight: 800, color: gColor.text, fontSize: "1.3rem" }}>
                {portfolio_profile.diversification_grade}
              </Typography>
            </Box>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, color: gColor.text }}>
                {portfolio_profile.diversification_score.toFixed(0)} / 100
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Higher = Greater Diversification
              </Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Card 2: Effective Holdings */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Effective Holdings
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {portfolio_profile.effective_holdings.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Out of {symbols.length} total holdings (1 / Stock HHI)
          </Typography>
        </Paper>

        {/* Card 3: Effective Sectors */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Effective Sectors
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            {portfolio_profile.effective_sectors.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Out of {portfolio_profile.sector_exposure.length} active sectors
          </Typography>
        </Paper>

        {/* Card 4: Diversification Ratio */}
        <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Diversification Ratio
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 700, color: "primary.main" }}>
            {portfolio_profile.diversification_ratio.toFixed(2)}x
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Weighted vol / Portfolio vol (&gt; 1.0 is beneficial)
          </Typography>
        </Paper>
      </Stack>

      {/* Qualitative Interpretation */}
      <Alert severity={portfolio_profile.diversification_score >= 60 ? "success" : "warning"} icon={false}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
          Diversification Rating: {portfolio_profile.diversification_grade} Grade ({portfolio_profile.diversification_score.toFixed(0)}/100)
        </Typography>
        <Typography variant="body2">{portfolio_profile.diversification_interpretation}</Typography>
      </Alert>

      {/* Pairwise Holdings Correlation Matrix Heatmap */}
      <Paper sx={{ p: 3, overflowX: "auto" }}>
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Holdings Return Correlation Matrix
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Pearson correlation coefficients of daily adjusted closing returns over trailing 252 trading days.
        </Typography>

        <Box sx={{ mt: 2, overflowX: "auto" }}>
          <Table size="small" sx={{ minWidth: 400 }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700, bgcolor: "#E3D7C4", color: "#292D2A", borderBottom: "none" }}>Symbol</TableCell>
                {symbols.map((sym) => (
                  <TableCell key={sym} align="center" sx={{ fontWeight: 700, bgcolor: "#E3D7C4", color: "#292D2A", borderBottom: "none" }}>
                    {sym}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {symbols.map((rowSym) => (
                <TableRow key={rowSym} hover sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                  <TableCell sx={{ fontWeight: 700, bgcolor: "#E3D7C4", color: "#292D2A", borderBottom: "none" }}>{rowSym}</TableCell>
                  {symbols.map((colSym) => {
                    const corr = portfolio_profile.correlation_matrix[rowSym]?.[colSym] ?? 0;
                    // Color gradient: 1.0 (self) is Sand Beige; high correlation (>0.6) is Pale Terracotta/Vermilion, low/negative (<0.3) is Pale Sage/Emerald
                    let cellBg = "#F9EBD7";
                    let cellColor = "#292D2A";
                    if (rowSym === colSym) {
                      cellBg = "#E3D7C4";
                      cellColor = "#686B64";
                    } else if (corr > 0.65) {
                      cellBg = "#F6D9CC";
                      cellColor = "#B8321A";
                    } else if (corr > 0.45) {
                      cellBg = "#E3D7C4";
                      cellColor = "#8A5A00";
                    } else if (corr < 0.25) {
                      cellBg = "#DCE9DE";
                      cellColor = "#046A38";
                    }

                    return (
                      <TableCell
                        key={colSym}
                        align="center"
                        sx={{
                          bgcolor: cellBg,
                          color: cellColor,
                          fontWeight: 700,
                          fontSize: "0.82rem",
                          border: "none",
                        }}
                      >
                        {corr.toFixed(2)}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </Paper>

      {/* Normalization & Disclaimer Card */}
      <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }} gutterBottom>
          Diversification Index Formula & Interpretation Notice
        </Typography>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          The PRISM 0–100 Diversification Index measures the structural resilience of your portfolio across three dimensions:
        </Typography>
        <Box component="ul" sx={{ m: 0, pl: 2, mb: 1.5 }}>
          <li>
            <Typography variant="body2">
              <strong>Holding Weight Dispersion (35% weight):</strong> Effective holdings ratio (N_eff / N_total). Penalizes portfolio domination by 1 or 2 mega-positions.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              <strong>Sector Spread (35% weight):</strong> Effective sector count scaled against a prudent 5-sector benchmark.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              <strong>Correlation Diversification Benefit (30% weight):</strong> Diversification Ratio (DR = Σ w_i σ_i / σ_p). Rewards lower co-movement where portfolio volatility is meaningfully lower than the sum of component risks.
            </Typography>
          </li>
        </Box>
        <Alert severity="warning" icon={false}>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>
            Important Disclaimer: A high diversification score indicates effective risk dispersion across non-correlated equities and multi-sector exposure. However, high diversification does NOT guarantee against market losses during broad systemic market downturns.
          </Typography>
        </Alert>
      </Paper>
    </Stack>
  );
}

function PortfolioPerformanceMiniChart({
  points,
}: {
  points: { trade_date: string; portfolio_index: number; drawdown: number }[];
}) {
  const width = 900;
  const height = 280;
  const left = 55;
  const right = 20;
  const top = 20;
  const mid = 175;
  const bottom = 255;

  const indexValues = points.map((p) => p.portfolio_index);
  const minIdx = Math.min(...indexValues);
  const maxIdx = Math.max(...indexValues);
  const pad = Math.max((maxIdx - minIdx) * 0.1, 1);
  const yMin = minIdx - pad;
  const yMax = maxIdx + pad;

  const minDd = Math.min(...points.map((p) => p.drawdown), -0.01);

  const x = (i: number) => left + (i / Math.max(points.length - 1, 1)) * (width - left - right);
  const yIndex = (v: number) => top + ((yMax - v) / (yMax - yMin)) * (mid - top);
  const yDrawdown = (v: number) => mid + 20 + (v / minDd) * (bottom - mid - 20);

  const indexPoly = points.map((p, i) => `${x(i)},${yIndex(p.portfolio_index)}`).join(" ");
  const ddPoly = points.map((p, i) => `${x(i)},${yDrawdown(p.drawdown)}`).join(" ");

  return (
    <Box
      component="svg"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Simulated portfolio index and drawdown history"
      sx={{ width: "100%", height: "auto", display: "block" }}
    >
      <polyline fill="none" stroke="#00796b" strokeWidth="2.5" points={indexPoly} />
      <polyline fill="none" stroke="#d32f2f" strokeWidth="1.8" points={ddPoly} />
      <text x={left} y={top + 12} fontSize="11" fill="#00796b" fontWeight="bold">
        Index (Base 100)
      </text>
      <text x={left} y={mid + 32} fontSize="11" fill="#d32f2f" fontWeight="bold">
        Drawdown Profile
      </text>
    </Box>
  );
}

