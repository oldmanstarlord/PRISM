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
  StockDecision,
  StockRiskProfile,
} from "./types";
import { METRIC_REGISTRY } from "./methodologyRegistry";

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
  Low: { bg: "var(--line)", text: "var(--up)" },
  Moderate: { bg: "var(--line)", text: "var(--amber)" },
  High: { bg: "var(--gray)", text: "var(--down)" },
  "Very High": { bg: "var(--gray)", text: "var(--down)" },
};

const trendIcons: Record<string, { icon: string; label: string; color: "success" | "warning" | "error" | "default" }> = {
  increasing: { icon: "/ Rising", label: "Rising risk", color: "error" },
  decreasing: { icon: "↘ Cooling", label: "Cooling risk", color: "success" },
  stable: { icon: "/ Stable", label: "Stable risk", color: "default" },
};

/* ─────────────────────────────────────────────────────────────
   1. STOCK-LEVEL RISK SECTION
   ───────────────────────────────────────────────────────────── */

interface StockRiskSectionProps {
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  loading: boolean;
  onRefresh: () => void;
  decisionMap?: Map<string, StockDecision>;
  onSelectTab?: (tab: any) => void;
}

export function StockRiskSection({
  comprehensiveRisk,
  loading,
  onRefresh,
  decisionMap,
  onSelectTab,
}: StockRiskSectionProps) {
  const [selectedStock, setSelectedStock] = useState<StockRiskProfile | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<"1M" | "3M" | "6M" | "1Y">("1Y");

  if (!comprehensiveRisk) {
    return (
      <Paper sx={{ p: "var(--space-3)", textAlign: "center" }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Stock Risk Assessment
        </Typography>
        <Typography color="text.secondary" sx={{ mb: "var(--space-2)" }}>
          Multi-window volatility, downside semi-deviation, max drawdown, and explainable scoring for your holdings.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "var(--white)" }} /> : "Calculate Stock Risk"}
        </Button>
      </Paper>
    );
  }

  const { stock_profiles } = comprehensiveRisk;

  return (
    <Stack spacing={2}>
      {/* Header & Horizon Controls */}
      <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-2)" }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 600, fontSize: "var(--text-title)" }}>
            Stock-Level Risk Assessment
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: "var(--text-title)" }}>
            Multi-horizon volatility, market sensitivity (Beta), and explainable 0–100 risk scoring.
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: "text.secondary", fontSize: "var(--text-title)" }}>
            LOOKBACK:
          </Typography>
          {(["1M", "3M", "6M", "1Y"] as const).map((h) => (
            <Button
              key={h}
              size="small"
              variant={selectedHorizon === h ? "contained" : "outlined"}
              onClick={() => setSelectedHorizon(h)}
              sx={{ minWidth: 36, py: "var(--space-1)", px: "var(--space-1)", fontSize: "var(--text-title)" }}
            >
              {h}
            </Button>
          ))}
        </Stack>
      </Stack>

      {/* Main Stock Risk Table */}
      <Paper sx={{ p: "var(--space-2)", overflowX: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Holding</TableCell>
              <TableCell align="right">Weight</TableCell>
              <TableCell align="center">Decision Signal</TableCell>
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
              const riskColor = riskLevelColors[s.risk_classification] || { bg: "var(--line)", text: "var(--gray)" };
              const trendInfo = trendIcons[s.recent_risk_change] || trendIcons.stable;

              return (
                <TableRow key={s.symbol} hover>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <Typography sx={{ fontWeight: 600 }}>
                        <Link to={`/companies/${s.symbol}`} style={{ textDecoration: "none", color: "var(--up)" }}>
                          {s.symbol}
                        </Link>
                      </Typography>
                      {s.sector_divergence_20d !== undefined && s.sector_divergence_20d !== null && Math.abs(s.sector_divergence_20d) >= 1.5 ? (
                        <Tooltip title={`Model estimate: Sector divergence residual (${s.sector_divergence_20d.toFixed(1)}σ) signals unusual behaviour.`}>
                          <Chip
                            size="small"
                            label="Model: Unusual"
                            sx={{
                              height: 18,
                              borderRadius: "var(--radius)",
                              fontSize: "var(--text-title)",
                              fontWeight: 600,
                              bgcolor: "var(--gray)",
                              color: "var(--down)",
                              border: "none",
                            }}
                          />
                        </Tooltip>
                      ) : null}
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      {s.company_name} · {s.sector}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{(s.weight * 100).toFixed(1)}%</TableCell>
                  <TableCell align="center">
                    {decisionMap?.get(s.symbol.toUpperCase()) ? (
                      (() => {
                        const dec = decisionMap.get(s.symbol.toUpperCase())!;
                        const isHold = dec.decision === "HOLD";
                        const isSell = dec.decision === "SELL";
                        const bg = isHold ? "var(--up)" : isSell ? "var(--down)" : "var(--amber)";

                        return (
                          <Tooltip
                            title={
                              <Box sx={{ p: "var(--space-1)" }}>
                                <Typography variant="caption" sx={{ fontWeight: 600, display: "block" }}>
                                  {dec.decision} — Health: {dec.final_score.toFixed(1)}/100
                                </Typography>
                                <Typography variant="caption" sx={{ display: "block" }}>
                                  Fundamental: {dec.fundamental.fundamental_strength_score.toFixed(0)} | Sector: {dec.sector_strength.sector_strength_score.toFixed(0)} | News: {dec.news.news_score.toFixed(0)}
                                </Typography>
                                <Typography variant="caption" sx={{ color: "var(--line)", display: "block", mt: "var(--space-1)" }}>
                                  Click to view full 3-factor breakdown & analysis
                                </Typography>
                              </Box>
                            }
                            arrow
                          >
                            <Chip
                              size="small"
                              label={dec.decision}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                onSelectTab?.("stock-decisions");
                              }}
                              sx={{
                                cursor: onSelectTab ? "pointer" : "default",
                                height: 24,
                                borderRadius: "var(--radius)",
                                fontWeight: 600,
                                fontSize: "var(--text-title)",
                                bgcolor: bg,
                                color: "var(--white)",
                                boxShadow: "none",
                                "&:hover": { opacity: 1 },
                              }}
                            />
                          </Tooltip>
                        );
                      })()
                    ) : (
                      <Chip
                        size="small"
                        label="Decision Engine"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onSelectTab?.("stock-decisions");
                        }}
                        sx={{
                          cursor: onSelectTab ? "pointer" : "default",
                          height: 20,
                          borderRadius: "var(--radius)",
                          fontSize: "var(--text-title)",
                          bgcolor: "var(--line)",
                        }}
                      />
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      size="small"
                      label={`${s.overall_score.toFixed(0)}/100`}
                      sx={{
                        bgcolor: riskColor.bg,
                        color: riskColor.text,
                        fontWeight: 600,
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
                            fontWeight: 600,
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
                    <Chip size="small" label={trendInfo.icon} color={trendInfo.color} sx={{ fontSize: "var(--text-title)" }} />
                  </TableCell>
                  <TableCell align="center">
                    {s.sector_divergence_20d !== null ? (
                      <Chip
                        size="small"
                        label={`${s.sector_divergence_20d > 0 ? "+" : ""}${s.sector_divergence_20d.toFixed(2)}σ`}
                        color={Math.abs(s.sector_divergence_20d) > 2.0 ? "warning" : "default"}
                        sx={{ fontSize: "var(--text-title)" }}
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
                        borderRadius: "var(--radius)",
                        border: "none",
                        bgcolor: "var(--line)",
                        color: "var(--white)",
                        fontWeight: 600,
                        boxShadow: "none",
                        "&:hover": { bgcolor: "var(--up)", color: "var(--line)" },
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
          <DialogTitle sx={{ bgcolor: "var(--line)", color: "var(--white)", borderBottom: "var(--border-width) solid var(--gray)" }}>
            <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }}>
                  {selectedStock.symbol} — Explainable Risk Breakdown
                </Typography>
                <Typography variant="caption" sx={{ color: "var(--gray)" }}>
                  {selectedStock.company_name} · {selectedStock.sector} · {selectedStock.data_coverage}
                </Typography>
              </Box>
              <Chip
                label={`${selectedStock.overall_score.toFixed(0)}/100 · ${selectedStock.risk_classification}`}
                sx={{
                  bgcolor: riskLevelColors[selectedStock.risk_classification]?.bg || "var(--line)",
                  color: riskLevelColors[selectedStock.risk_classification]?.text || "var(--white)",
                  fontWeight: 600,
                  borderRadius: "var(--radius)",
                }}
              />
            </Stack>
          </DialogTitle>

          <DialogContent sx={{ mt: "var(--space-2)" }}>
            <Stack spacing={3}>
              {/* Dynamic Narrative Explanation */}
              <Alert severity="info" icon={false} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", color: "var(--white)", border: "none", boxShadow: "none" }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)", color: "var(--white)" }}>
                  Dynamic Quantitative Explanation
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--white)" }}>{selectedStock.narrative_explanation}</Typography>
              </Alert>

              {/* Primary Risk Drivers */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)", color: "var(--white)" }}>
                  Primary Identified Risk Drivers:
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                  {selectedStock.primary_drivers.map((d) => (
                    <Chip
                      key={d}
                      label={d}
                      size="small"
                      sx={{
                        borderRadius: "var(--radius)",
                        fontWeight: 600,
                        bgcolor: "var(--line)",
                        color: "var(--up)",
                      }}
                    />
                  ))}
                </Stack>
              </Box>

              {/* 5 Normalized Factor Scores */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)" }}>
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
                            sx={{ height: 20, fontSize: "var(--text-title)" }}
                          />
                        </TableCell>
                        <TableCell align="right">{(f.weight * 100).toFixed(0)}%</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          +{f.contribution.toFixed(2)} pts
                        </TableCell>
                        <TableCell sx={{ color: "text.secondary", fontSize: "var(--text-title)" }}>
                          {f.interpretation}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>

              {/* Multi-Window Comparison Matrix */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)" }}>
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
                          <TableCell sx={{ fontWeight: 600 }}>{wKey}</TableCell>
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
                  bgcolor: "var(--bg)",
                  p: "var(--space-2)",
                  borderRadius: "var(--radius)",
                  border: "none",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)", color: "var(--white)" }}>
                  Position-Level Performance Since Purchase
                </Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" }, gap: "var(--space-2)" }}>
                  <Box>
                    <Typography variant="caption" sx={{ color: "var(--gray)" }}>
                      Purchase Price
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                      {formatCurrency(selectedStock.purchase_price, 2)}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Current Price
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 600 }}>
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
                        fontWeight: 600,
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
                    <Typography variant="body1" sx={{ fontWeight: 600, color: "error.main" }}>
                      {selectedStock.drawdown_since_purchase !== null
                        ? `-${selectedStock.drawdown_since_purchase.toFixed(1)}%`
                        : "—"}
                    </Typography>
                  </Box>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ mt: "var(--space-1)", display: "block" }}>
                  * Purchase-price comparisons describe your investment position, while volatility, downside risk, and market sensitivity determine the stock's objective risk score.
                </Typography>
              </Box>
            </Stack>
          </DialogContent>

          <DialogActions sx={{ p: "var(--space-2)" }}>
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
      <Paper sx={{ p: "var(--space-3)", textAlign: "center" }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Portfolio Risk Analytics
        </Typography>
        <Typography color="text.secondary" sx={{ mb: "var(--space-2)" }}>
          Annualized covariance volatility, historical drawdown, portfolio beta, and Euler risk decomposition.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "var(--white)" }} /> : "Calculate Portfolio Risk"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const pRiskColor = riskLevelColors[portfolio_profile.portfolio_classification] || { bg: "var(--line)", text: "var(--gray)" };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Portfolio-Level Risk Analysis
        </Typography>
        <Typography color="text.secondary">
          Covariance-derived volatility, systematic market beta, and Euler risk contribution shares.
        </Typography>
      </Box>

      {/* Top Metric KPI Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
        {/* Card 1: Portfolio Risk Score */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 200px" }}>
          <Typography variant="overline" color="text.secondary">
            Overall Portfolio Risk
          </Typography>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mt: "var(--space-1)" }}>
            <Box
              sx={{
                width: 52,
                height: 52,
                borderRadius: "var(--radius)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: pRiskColor.bg,
                boxShadow: "none",
              }}
            >
              <Typography sx={{ fontWeight: 600, color: pRiskColor.text, fontSize: "var(--text-title)" }}>
                {portfolio_profile.portfolio_risk_score.toFixed(0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600, color: pRiskColor.text }}>
                {portfolio_profile.portfolio_classification} Risk
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Trend: {portfolio_profile.historical_risk_trend.toUpperCase()}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Card 2: Annualized Volatility */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Portfolio Volatility
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {portfolio_profile.annualized_volatility.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Annualized covariance σ
          </Typography>
        </Paper>

        {/* Card 3: Downside Volatility */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Downside Volatility
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {portfolio_profile.downside_volatility.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Negative-return semi-deviation
          </Typography>
        </Paper>

        {/* Card 4: Historical Maximum Drawdown */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Max Drawdown
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "error.main" }}>
            -{portfolio_profile.max_drawdown.toFixed(1)}%
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Peak-to-trough decline
          </Typography>
        </Paper>

        {/* Card 5: Portfolio Beta */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Portfolio Beta (vs NIFTY 50)
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {portfolio_profile.portfolio_beta.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Systematic market sensitivity
          </Typography>
        </Paper>
      </Stack>



      {/* Holding Euler Risk Contributions Table */}
      <Paper sx={{ p: "var(--space-3)", overflowX: "auto" }}>
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, mb: "var(--space-1)", gap: "var(--space-1)" }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              Holding Risk Contribution (Euler Decomposition)
            </Typography>
            <Typography color="text.secondary" variant="body2">
              Exact variance decomposition: Component Volatility C_i = w_i * (Σ w)_i / σ_p. Components sum exactly to portfolio volatility.
            </Typography>
          </Box>
        </Stack>

        <Table size="small" sx={{ mt: "var(--space-1)" }}>
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Portfolio Weight</TableCell>
              <TableCell align="right">Asset Volatility</TableCell>
              <TableCell align="right">Marginal Risk</TableCell>
              <TableCell align="right">Component Volatility</TableCell>
              <TableCell align="right">Risk Share</TableCell>
              <TableCell sx={{ minWidth: 200 }}>Share of Total Portfolio Risk</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {portfolio_profile.risk_contributions
              .slice()
              .sort((a, b) => b.risk_contribution_share - a.risk_contribution_share)
              .map((rc: EulerRiskContribution) => {
                const isHedge = (rc.component_risk !== undefined && rc.component_risk < 0) || rc.risk_contribution_share < 0;
                return (
                  <TableRow key={rc.symbol} hover>
                    <TableCell sx={{ fontWeight: 600 }}>
                      <Link to={`/companies/${rc.symbol}`} style={{ textDecoration: "none", color: "var(--up)" }}>
                        {rc.symbol}
                      </Link>
                      {isHedge && (
                        <Chip
                          label="HEDGE"
                          size="small"
                          sx={{ ml: "var(--space-1)", bgcolor: "var(--line)", color: "var(--up)", fontWeight: 600, height: 18, fontSize: "var(--text-title)", borderRadius: "var(--radius)" }}
                        />
                      )}
                    </TableCell>
                    <TableCell align="right" sx={{ fontFamily: "var(--font-data)" }}>{(rc.weight * 100).toFixed(1)}%</TableCell>
                    <TableCell align="right" sx={{ fontFamily: "var(--font-data)" }}>{(rc.annualized_volatility * 100).toFixed(1)}%</TableCell>
                    <TableCell align="right" sx={{ fontFamily: "var(--font-data)" }}>{(rc.marginal_risk * 100).toFixed(1)}%</TableCell>
                    <TableCell align="right" sx={{ fontFamily: "var(--font-data)", fontWeight: 600 }}>
                      {rc.component_risk !== undefined ? `${(rc.component_risk * 100).toFixed(2)}%` : "—"}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                      {rc.risk_contribution_share.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(Math.max(rc.risk_contribution_share, 0), 100)}
                          color={rc.risk_contribution_share > 35 ? "error" : rc.risk_contribution_share > 20 ? "warning" : "primary"}
                          sx={{ flex: 1, height: 8, borderRadius: "var(--radius)" }}
                        />
                        <Typography variant="caption" sx={{ minWidth: 35, fontWeight: 600, fontFamily: "var(--font-data)" }}>
                          {rc.risk_contribution_share.toFixed(0)}%
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>

        {/* Euler Decomposition Reconciliation Banner */}
        {(() => {
          const sumCompVol = portfolio_profile.risk_contributions.reduce(
            (acc, r) => acc + (r.component_risk !== undefined ? r.component_risk * 100 : 0),
            0
          );
          const portVol = portfolio_profile.annualized_volatility;
          const residual = Math.abs(sumCompVol - portVol);
          const sumShares = portfolio_profile.risk_contributions.reduce((acc, r) => acc + r.risk_contribution_share, 0);

          return (
            <Box sx={{ mt: "var(--space-2)", p: "var(--space-2)", bgcolor: "var(--line)", display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "var(--space-1)" }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                Euler Reconciliation: Σ Component Volatilities = {sumCompVol.toFixed(2)}% vs Portfolio Volatility = {portVol.toFixed(2)}%
                {" "}(Residual: {residual < 1e-4 ? "< 0.0001%" : `${residual.toFixed(4)}%`})
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                Total Risk Share: {sumShares.toFixed(1)}% / 100.0%
              </Typography>
            </Box>
          );
        })()}
      </Paper>

      {/* Historical Performance & Drawdown Chart if analysis is available */}
      {analysis?.performance && analysis.performance.points.length > 0 && (
        <Paper sx={{ p: "var(--space-3)" }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            Simulated 250-Day Portfolio Performance & Drawdown
          </Typography>
          <Typography color="text.secondary" gutterBottom>
            Constant-weight daily-rebalanced equity curve (base = 100) and historical drawdown profile.
          </Typography>
          <Box sx={{ mt: "var(--space-2)" }}>
            <PortfolioPerformanceMiniChart points={analysis.performance.points} />
          </Box>
        </Paper>
      )}

      {/* Methodology & Documentation rendered from Methodology Registry */}
      <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: "var(--space-1)" }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Methodology & Mathematical Invariants
          </Typography>
          <Chip label="Methodology v1.0.0" size="small" sx={{ bgcolor: "var(--line)", color: "var(--white)", fontWeight: 600, borderRadius: "var(--radius)" }} />
        </Stack>

        <Typography variant="body2" sx={{ mb: "var(--space-2)", color: "var(--gray)" }}>
          PRISM risk calculations adhere to strict quantitative specifications. All metrics below are rendered directly from the authoritative methodology registry:
        </Typography>

        <Stack spacing={2}>
          {/* Return Construction Note */}
          <Box sx={{ p: "var(--space-2)", bgcolor: "var(--line)" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
              Return Construction: Daily-Rebalanced vs Buy-and-Hold
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
              • <strong>Constant-Weight Daily Rebalanced:</strong> Used for covariance matrices, volatility, beta, and historical VaR/CVaR (r_p,t = Σ w_i r_i,t).
              <br />
              • <strong>Buy-and-Hold Wealth Series:</strong> Used for drawdown and actual performance equity curves (W_t = Σ N_i P_i,t).
              <br />
              • <strong>Log-Return Linear Sum Gap:</strong> By Jensen&apos;s inequality, Σ w_i ln(1+R_i) &le; ln(1+Σ w_i R_i). PRISM uses exact linear compounding simple returns to eliminate this bias.
            </Typography>
          </Box>

          {/* Core Metric Definitions from METRIC_REGISTRY */}
          {[
            "portfolio_risk_score",
            "portfolio_volatility",
            "downside_volatility",
            "max_drawdown",
            "portfolio_beta",
            "var_historical_95",
            "cvar_historical_95",
            "euler_contribution",
          ]
            .map((k) => METRIC_REGISTRY[k])
            .filter(Boolean)
            .map((metric) => (
              <Box key={metric.name} sx={{ pb: "var(--space-2)", borderBottom: "var(--border-width) solid var(--gray)" }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
                    {metric.label ?? metric.name}
                  </Typography>
                  <Chip label={metric.units} size="small" sx={{ bgcolor: "var(--gray)", color: "var(--down)", fontSize: "var(--text-title)", height: 18, borderRadius: "var(--radius)" }} />
                  <Typography variant="caption" color="text.secondary">
                    Window: {metric.window ?? metric.defaultWindow} (min {metric.min_observations ?? metric.minObservations} obs)
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
                  {metric.definition}
                </Typography>
                <Typography variant="caption" sx={{ fontFamily: "var(--font-data)", color: "var(--gray)", display: "block", mt: "var(--space-1)" }}>
                  Formula: {metric.formula ?? metric.formulaPlain}
                </Typography>
                <Typography variant="caption" sx={{ color: "var(--amber)", display: "block", mt: "var(--space-1)" }}>
                  Limitations: {Array.isArray(metric.limitations) ? metric.limitations.join("; ") : metric.limitations}
                </Typography>
              </Box>
            ))}
        </Stack>
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
      <Paper sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Sector Exposure & Concentration
        </Typography>
        <Typography color="text.secondary" sx={{ mb: "var(--space-2)" }}>
          Sector allocation weights, benchmark limits, and sector-related risk contribution shares.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "var(--white)" }} /> : "Analyze Sector Exposure"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const sectors = portfolio_profile.sector_exposure;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Sector Exposure & Concentration Analysis
        </Typography>
        <Typography color="text.secondary">
          Distribution of capital across industries compared with documented prudent concentration targets (25% ceiling).
        </Typography>
      </Box>

      {/* Sector KPI Summary Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <Paper sx={{ p: "var(--space-3)", flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Effective Number of Sectors
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 600 }}>
            {portfolio_profile.effective_sectors.toFixed(1)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            1 / Sector HHI (higher = broader sector breadth)
          </Typography>
        </Paper>

        <Paper sx={{ p: "var(--space-3)", flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Sector HHI Index
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 600 }}>
            {portfolio_profile.sector_hhi.toFixed(3)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Herfindahl–Hirschman Index (&lt; 0.25 is balanced)
          </Typography>
        </Paper>

        <Paper sx={{ p: "var(--space-3)", flex: 1 }}>
          <Typography variant="overline" color="text.secondary">
            Top Sector Allocation
          </Typography>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 600,
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
      <Paper sx={{ p: "var(--space-3)", overflowX: "auto" }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Industry Weights vs Risk Contribution Share
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Compares capital allocation with actual Euler risk contribution. Disproportionate risk shares indicate high-volatility sectors.
        </Typography>

        <Table size="small" sx={{ mt: "var(--space-1)" }}>
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
                  <TableCell sx={{ fontWeight: 600 }}>{sec.sector}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
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
                      fontWeight: 600,
                      color: sec.risk_contribution_share > sec.weight * 1.25 ? "error.main" : "inherit",
                    }}
                  >
                    {sec.risk_contribution_share.toFixed(1)}%
                  </TableCell>
                  <TableCell align="center">{sec.stock_count}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
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
                            borderRadius: "var(--radius)",
                            border: "none",
                            bgcolor: "var(--bg)",
                            color: "var(--white)",
                            fontWeight: 600,
                            "&:hover": { bgcolor: "var(--line)" },
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
                        sx={{ fontSize: "var(--text-title)" }}
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
      <Paper sx={{ p: "var(--space-3)" }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }} gutterBottom>
          Capital Allocation vs Risk Contribution by Sector
        </Typography>
        <Stack spacing={2} sx={{ mt: "var(--space-2)" }}>
          {sectors.map((sec: SectorExposureItem) => (
            <Box key={sec.sector}>
              <Stack direction="row" sx={{ justifyContent: "space-between", mb: "var(--space-1)" }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {sec.sector}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Weight: {sec.weight.toFixed(1)}% | Risk Share: {sec.risk_contribution_share.toFixed(1)}%
                </Typography>
              </Stack>
              <Box sx={{ display: "flex", gap: "var(--space-1)" }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ fontSize: "var(--text-title)", color: "var(--gray)" }}>
                    Capital:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(sec.weight, 100)}
                    sx={{ height: 6, borderRadius: "var(--radius)" }}
                    color="primary"
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ fontSize: "var(--text-title)", color: "var(--gray)" }}>
                    Risk Contribution:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(Math.max(sec.risk_contribution_share, 0), 100)}
                    sx={{ height: 6, borderRadius: "var(--radius)" }}
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
      <Paper sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Diversification Index & Correlation Matrix
        </Typography>
        <Typography color="text.secondary" sx={{ mb: "var(--space-2)" }}>
          Comprehensive multi-asset diversification scoring, HHI effective holdings, and co-movement matrix.
        </Typography>
        <Button variant="contained" onClick={onRefresh} disabled={loading}>
          {loading ? <CircularProgress size={20} sx={{ color: "var(--white)" }} /> : "Compute Diversification Index"}
        </Button>
      </Paper>
    );
  }

  const { portfolio_profile } = comprehensiveRisk;
  const gradeColors: Record<string, { bg: string; text: string }> = {
    A: { bg: "var(--line)", text: "var(--up)" },
    B: { bg: "var(--line)", text: "var(--up)" },
    C: { bg: "var(--bg)", text: "var(--amber)" },
    D: { bg: "var(--gray)", text: "var(--down)" },
  };
  const gColor = gradeColors[portfolio_profile.diversification_grade] || { bg: "var(--line)", text: "var(--white)" };

  const symbols = Object.keys(portfolio_profile.correlation_matrix);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Portfolio Diversification Assessment
        </Typography>
        <Typography color="text.secondary">
          Mathematical measures of asset dispersion, effective bets, and pairwise correlation co-movements.
        </Typography>
      </Box>

      {/* Diversification Score & Metrics Cards */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
        {/* Card 1: Diversification Score */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 240px" }}>
          <Typography variant="overline" color="text.secondary">
            Diversification Score (0–100)
          </Typography>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center", mt: "var(--space-1)" }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: "var(--radius)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: gColor.bg,
                boxShadow: "none",
              }}
            >
              <Typography sx={{ fontWeight: 600, color: gColor.text, fontSize: "var(--text-title)" }}>
                {portfolio_profile.diversification_grade}
              </Typography>
            </Box>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 600, color: gColor.text }}>
                {portfolio_profile.diversification_score.toFixed(0)} / 100
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Higher = Greater Diversification
              </Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Card 2: Effective Holdings */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Effective Holdings
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {portfolio_profile.effective_holdings.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Out of {symbols.length} total holdings (1 / Stock HHI)
          </Typography>
        </Paper>

        {/* Card 3: Effective Sectors */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Effective Sectors
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {portfolio_profile.effective_sectors.toFixed(2)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Out of {portfolio_profile.sector_exposure.length} active sectors
          </Typography>
        </Paper>

        {/* Card 4: Diversification Ratio */}
        <Paper sx={{ p: "var(--space-3)", flex: "1 1 180px" }}>
          <Typography variant="overline" color="text.secondary">
            Diversification Ratio
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "primary.main" }}>
            {portfolio_profile.diversification_ratio.toFixed(2)}x
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Weighted vol / Portfolio vol (&gt; 1.0 is beneficial)
          </Typography>
        </Paper>
      </Stack>

      {/* Qualitative Interpretation */}
      <Alert severity={portfolio_profile.diversification_score >= 60 ? "success" : "warning"} icon={false}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: "var(--space-1)" }}>
          Diversification Rating: {portfolio_profile.diversification_grade} Grade ({portfolio_profile.diversification_score.toFixed(0)}/100)
        </Typography>
        <Typography variant="body2">{portfolio_profile.diversification_interpretation}</Typography>
      </Alert>

      {/* Pairwise Holdings Correlation Matrix Heatmap */}
      <Paper sx={{ p: "var(--space-3)", overflowX: "auto" }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Holdings Return Correlation Matrix
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Pearson correlation coefficients of daily adjusted closing returns over trailing 252 trading days.
        </Typography>

        <Box sx={{ mt: "var(--space-2)", overflowX: "auto" }}>
          <Table size="small" sx={{ minWidth: 400 }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, bgcolor: "var(--line)", color: "var(--white)", borderBottom: "none" }}>Symbol</TableCell>
                {symbols.map((sym) => (
                  <TableCell key={sym} align="center" sx={{ fontWeight: 600, bgcolor: "var(--line)", color: "var(--white)", borderBottom: "none" }}>
                    {sym}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {symbols.map((rowSym) => (
                <TableRow key={rowSym} hover sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                  <TableCell sx={{ fontWeight: 600, bgcolor: "var(--line)", color: "var(--white)", borderBottom: "none" }}>{rowSym}</TableCell>
                  {symbols.map((colSym) => {
                    const corr = portfolio_profile.correlation_matrix[rowSym]?.[colSym] ?? 0;
                    // Color gradient: 1.0 (self) is Sand Beige; high correlation (>0.6) is Pale Terracotta/Vermilion, low/negative (<0.3) is Pale Sage/Emerald
                    let cellBg = "var(--bg)";
                    let cellColor = "var(--white)";
                    if (rowSym === colSym) {
                      cellBg = "var(--line)";
                      cellColor = "var(--gray)";
                    } else if (corr > 0.65) {
                      cellBg = "var(--gray)";
                      cellColor = "var(--down)";
                    } else if (corr > 0.45) {
                      cellBg = "var(--line)";
                      cellColor = "var(--amber)";
                    } else if (corr < 0.25) {
                      cellBg = "var(--line)";
                      cellColor = "var(--up)";
                    }

                    return (
                      <TableCell
                        key={colSym}
                        align="center"
                        sx={{
                          bgcolor: cellBg,
                          color: cellColor,
                          fontWeight: 600,
                          fontSize: "var(--text-title)",
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
      <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }} gutterBottom>
          Diversification Index Formula & Interpretation Notice
        </Typography>
        <Typography variant="body2" sx={{ mb: "var(--space-2)" }}>
          The PRISM 0–100 Diversification Index measures the structural resilience of your portfolio across three dimensions:
        </Typography>
        <Box component="ul" sx={{ m: "var(--space-1)", pl: "var(--space-2)", mb: "var(--space-2)" }}>
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
      <polyline fill="none" stroke="var(--up)" strokeWidth="var(--border-width)" points={indexPoly} />
      <polyline fill="none" stroke="var(--down)" strokeWidth="var(--border-width)" points={ddPoly} />
      <text x={left} y={top + 12} fontSize="var(--text-tag)" fill="var(--up)" fontWeight="400">
        Index (Base 100)
      </text>
      <text x={left} y={mid + 32} fontSize="var(--text-tag)" fill="var(--down)" fontWeight="400">
        Drawdown Profile
      </text>
    </Box>
  );
}
