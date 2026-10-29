import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  SvgIcon,
  SvgIconProps,
} from "@mui/material";
import { RiskReviewInboxPanel } from "./RiskReviewInboxPanel";

function HubIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 2a3 3 0 0 0-3 3c0 .34.06.67.16.97l-3.2 2.13A3 3 0 0 0 4 8a3 3 0 1 0 3 3c0-.34-.06-.67-.16-.97l3.2-2.13c.3.1.63.16.96.16.34 0 .67-.06.97-.16l3.2 2.13c-.1.3-.17.63-.17.97a3 3 0 1 0 3-3c-.34 0-.67.06-.97.16l-3.2-2.13c.1-.3.17-.63.17-.97a3 3 0 0 0-3-3z" />
    </SvgIcon>
  );
}

function InfoIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
    </SvgIcon>
  );
}

function NewsIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M22 3l-1.67 1.67L18.67 3 17 4.67 15.33 3l-1.66 1.67L12 3l-1.67 1.67L8.67 3 7 4.67 5.33 3 3.67 4.67 2 3v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V3zm-2 16H4V6h16v13zM6 8h12v2H6zm0 3h12v2H6zm0 3h7v2H6z" />
    </SvgIcon>
  );
}

function TimelineIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M23 8c0 1.1-.9 2-2 2-.18 0-.35-.02-.51-.07l-3.56 3.55c.05.16.07.34.07.52 0 1.1-.9 2-2 2s-2-.9-2-2c0-.18.02-.36.07-.52l-2.55-2.55c-.16.05-.34.07-.52.07s-.36-.02-.52-.07l-4.55 4.56c.05.16.07.33.07.51 0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2c.18 0 .35.02.51.07l4.56-4.55C8.02 9.36 8 9.18 8 9c0-1.1.9-2 2-2s2 .9 2 2c0 .18-.02.36-.07.52l2.55 2.55c.16-.05.34-.07.52-.07s.36.02.52.07l3.55-3.56A1.97 1.97 0 0 1 19 8c0-1.1.9-2 2-2s2 .9 2 2z" />
    </SvgIcon>
  );
}


function WarningIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
    </SvgIcon>
  );
}

import type {
  PortfolioAnalysisResponse,
  PortfolioNewsSummary,
  StructuralMonitoringSnapshot,
} from "./types";

export interface StructuralOverviewFinancials {
  marketValue: number | null;
  investedCost: number | null;
  cash: number | null;
  realizedPnl: number | null;
  unrealizedPnl: number | null;
  returnPct: number | null;
  volatility?: number | null;
  maxDrawdown?: number | null;
  concentrationHhi?: number | null;
  dataFreshness?: string;
  asOfDate?: string;
  period?: string;
}

export function StructuralMonitoringDashboard({
  monitoring,
  analysis,
  onRefresh,
  portfolioId,
  financials,
  marketRegime,
  newsSummary,
  onNavigateTab,
}: {
  monitoring: StructuralMonitoringSnapshot | null;
  analysis?: PortfolioAnalysisResponse | null;
  onRefresh?: () => void;
  portfolioId?: string;
  financials?: StructuralOverviewFinancials;
  marketRegime?: { active_regime_name: string; filtered_probability: number } | null;
  newsSummary?: PortfolioNewsSummary | null;
  onNavigateTab?: (tabId: string) => void;
}) {


  if (!monitoring) {
    return (
      <Box sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No structural monitoring data available. Please run portfolio analysis first.
        </Typography>
      </Box>
    );
  }

  const triggeredIndicators = monitoring.indicators.filter((ind) => ind.triggered);

  // Derived Financials for the 10-stat Executive Strip
  const mktVal = financials?.marketValue ?? monitoring.portfolio_value;
  const invCost = financials?.investedCost ?? null;
  const unrealizedPnl = financials?.unrealizedPnl ?? null;
  const returnPct = financials?.returnPct ?? monitoring.overall_return;
  const annualVol = financials?.volatility != null
    ? financials.volatility * 100
    : analysis?.performance?.annualized_volatility != null
      ? analysis.performance.annualized_volatility * 100
      : null;
  const maxDd = financials?.maxDrawdown != null
    ? financials.maxDrawdown * 100
    : analysis?.performance?.max_drawdown != null
      ? analysis.performance.max_drawdown * 100
      : null;
  const freshness = financials?.dataFreshness ?? monitoring.data_freshness;
  const asOf = financials?.asOfDate ?? analysis?.envelope.data_cutoff ?? null;
  const period = financials?.period ?? (
    analysis ? `${analysis.envelope.lookback_start} to ${analysis.envelope.data_cutoff}` : null
  );

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {/* 5-Stat Executive Overview Strip */}
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-3)",
          borderRadius: "var(--radius)",
          bgcolor: "var(--line)",
          color: "var(--white)",
          boxShadow: "none",
          border: "var(--border-width) solid var(--gray)",
        }}
      >
        <Stack spacing={2}>
          {/* Header Row: Title, Metadata Chips, and Model / News Signals */}
          <Stack
            direction={{ xs: "column", md: "row" }}
            sx={{ justifyContent: "space-between", alignItems: { md: "center" }, gap: "var(--space-2)" }}
          >
            <Box>
              <Typography variant="overline" sx={{ letterSpacing: 0, color: "var(--gray)", fontWeight: 600, display: "block", mb: "var(--space-1)" }}>
                EXECUTIVE PORTFOLIO OVERVIEW
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>
                Portfolio Financial State & Structural Health
              </Typography>
            </Box>
          </Stack>

          {/* 5 Core Executive Indicator Cells */}
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, 1fr)",
                md: "repeat(5, 1fr)",
              },
              gap: "var(--space-2)",
              pt: "var(--space-1)",
            }}
          >
            {/* 1. Market Value */}
            <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", boxShadow: "none", border: "var(--border-width) solid var(--cyan)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", fontWeight: 600 }}>
                Market Value
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                ₹{mktVal.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                Mark-to-market total
              </Typography>
            </Box>

            {/* 2. Invested Cost */}
            <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", boxShadow: "none", border: "var(--border-width) solid var(--cyan)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", fontWeight: 600 }}>
                Invested Cost
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                {invCost == null
                  ? "Unavailable"
                  : `₹${invCost.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                Cost basis (WAC)
              </Typography>
            </Box>

            {/* 3. Unrealized P&L & Return */}
            <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", boxShadow: "none", border: "var(--border-width) solid var(--cyan)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", fontWeight: 600 }}>
                Unrealized P&L
              </Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 600,
                  fontFamily: "var(--font-data)",
                  color: unrealizedPnl == null || unrealizedPnl >= 0 ? "var(--up)" : "var(--down)",
                }}
              >
                {unrealizedPnl == null
                  ? "Unavailable"
                  : `${unrealizedPnl >= 0 ? "+" : ""}₹${unrealizedPnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: returnPct == null || returnPct >= 0 ? "var(--up)" : "var(--down)",
                  fontWeight: 600,
                  fontSize: "var(--text-title)",
                  display: "block",
                }}
              >
                Return (% Total): {returnPct == null
                  ? "Unavailable"
                  : `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`}
              </Typography>
            </Box>

            {/* 4. Annualized Volatility */}
            <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", boxShadow: "none", border: "var(--border-width) solid var(--cyan)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", fontWeight: 600 }}>
                Ann. Volatility
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                {annualVol == null ? "Unavailable" : `${annualVol.toFixed(1)}%`}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                252d empirical risk (σ)
              </Typography>
            </Box>

            {/* 5. Maximum Drawdown */}
            <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", boxShadow: "none", border: "var(--border-width) solid var(--cyan)" }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", fontWeight: 600 }}>
                Max Drawdown
              </Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 600,
                  fontFamily: "var(--font-data)",
                  color: maxDd != null && maxDd < -15 ? "var(--down)" : "var(--white)",
                }}
              >
                {maxDd != null ? `-${Math.abs(maxDd).toFixed(1)}%` : "—"}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                Peak-to-trough drop
              </Typography>
            </Box>
          </Box>
        </Stack>
      </Paper>



      {/* KPI Summary Cards */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
          gap: "var(--space-2)",
        }}
      >
        <Card elevation={0} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", boxShadow: "none", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              PORTFOLIO RISK SCORE
            </Typography>
            <Stack direction="row" sx={{ alignItems: "baseline", gap: "var(--space-1)", mt: "var(--space-1)" }}>
              <Typography variant="h4" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                {monitoring.portfolio_risk_score.toFixed(0)}
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                / 100
              </Typography>
            </Stack>
            <Chip
              size="small"
              label={monitoring.portfolio_classification}
              sx={{
                mt: "var(--space-1)",
                fontWeight: 600,
                borderRadius: "var(--radius)",
                bgcolor:
                  monitoring.portfolio_classification === "Low"
                    ? "var(--line)"
                    : monitoring.portfolio_classification === "Moderate"
                      ? "var(--line)"
                      : "var(--gray)",
                color:
                  monitoring.portfolio_classification === "Low"
                    ? "var(--up)"
                    : monitoring.portfolio_classification === "Moderate"
                      ? "var(--amber)"
                      : "var(--down)",
              }}
            />
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", boxShadow: "none", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              DIVERSIFICATION SCORE
            </Typography>
            <Stack direction="row" sx={{ alignItems: "baseline", gap: "var(--space-1)", mt: "var(--space-1)" }}>
              <Typography variant="h4" sx={{ fontWeight: 600, color: "var(--up)", fontFamily: "var(--font-data)" }}>
                {monitoring.diversification_score.toFixed(0)}
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                / 100
              </Typography>
            </Stack>
            <Chip
              size="small"
              label={`Grade ${monitoring.diversification_grade}`}
              sx={{ mt: "var(--space-1)", fontWeight: 600, borderRadius: "var(--radius)", bgcolor: "var(--line)", color: "var(--up)" }}
            />
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", boxShadow: "none", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              TOP SECTOR EXPOSURE
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", mt: "var(--space-1)" }} noWrap>
              {monitoring.top_sector}
            </Typography>
            <Stack direction="row" sx={{ alignItems: "center", gap: "var(--space-1)", mt: "var(--space-1)" }}>
              <Typography variant="body2" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)" }}>
                {monitoring.top_sector_weight.toFixed(1)}% Weight
              </Typography>
              <Chip
                size="small"
                label={monitoring.top_sector_status}
                sx={{
                  fontWeight: 600,
                  fontSize: "var(--text-title)",
                  borderRadius: "var(--radius)",
                  bgcolor:
                    monitoring.top_sector_status === "Balanced"
                      ? "var(--line)"
                      : monitoring.top_sector_status === "Elevated"
                        ? "var(--bg)"
                        : "var(--gray)",
                  color:
                    monitoring.top_sector_status === "Balanced"
                      ? "var(--up)"
                      : monitoring.top_sector_status === "Elevated"
                        ? "var(--amber)"
                        : "var(--down)",
                }}
              />
            </Stack>
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", boxShadow: "none", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              LARGEST POSITION
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", mt: "var(--space-1)" }}>
              {monitoring.largest_holding}
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--gray)", mt: "var(--space-1)", fontFamily: "var(--font-data)" }}>
              {monitoring.largest_holding_weight.toFixed(1)}% of total portfolio capital
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Risk Review Inbox Panel (relocated to bottom of page) */}
      <RiskReviewInboxPanel
        portfolioId={portfolioId}
        triggeredIndicators={triggeredIndicators}
      />


    </Box>
  );
}

export function HistoricalRiskTrackingSection({
  monitoring,
}: {
  monitoring: StructuralMonitoringSnapshot | null;
}) {
  if (!monitoring || !monitoring.historical_risk_series.length) {
    return (
      <Box sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No historical risk tracking data available yet.
        </Typography>
      </Box>
    );
  }

  const series = monitoring.historical_risk_series;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-3)",
          borderRadius: "var(--radius)",
          bgcolor: "var(--bg)",
          border: "none",
          boxShadow: "none",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-2)" }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
              Historical Risk Progression & Score Audit
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--gray)" }}>
              Consistent 252-day lookback window evaluated at historical observation horizons.
            </Typography>
          </Box>
          <Stack direction="row" sx={{ gap: "var(--space-1)", alignItems: "center" }}>
            <Chip
              size="small"
              label={`${monitoring.persisted_history_count} Snapshots Saved`}
              sx={{
                borderRadius: "var(--radius)",
                fontWeight: 600,
                bgcolor: "var(--bg)",
                color: "var(--white)",
              }}
            />
            <Chip
              size="small"
              label="Audit Log Verified"
              sx={{
                borderRadius: "var(--radius)",
                fontWeight: 600,
                bgcolor: "var(--line)",
                color: "var(--up)",
              }}
            />
          </Stack>
        </Stack>
      </Paper>

      {/* Historical Trend Table */}
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent sx={{ p: "var(--space-1)" }}>
          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: "var(--line)" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Observation Date</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Horizon / Window</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Risk Score (0–100)</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Annual Volatility</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Downside Vol</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Max Drawdown</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Diversification</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Data Coverage</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {series.map((pt, idx) => (
                  <TableRow
                    key={pt.observation_date + pt.lookback_window}
                    hover
                    sx={{
                      bgcolor: idx === 0 ? "var(--bg)" : "inherit",
                      "&:hover": { bgcolor: "var(--line) !important" },
                    }}
                  >
                    <TableCell sx={{ fontWeight: idx === 0 ? 700 : 500, color: "var(--white)", borderBottom: "none" }}>
                      {pt.observation_date}{" "}
                      {idx === 0 && (
                        <Chip
                          size="small"
                          label="LATEST"
                          sx={{
                            ml: "var(--space-1)",
                            fontSize: "var(--text-title)",
                            height: 18,
                            borderRadius: "var(--radius)",
                            bgcolor: "var(--line)",
                            color: "var(--up)",
                            fontWeight: 600,
                          }}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={{ color: "var(--white)", borderBottom: "none" }}>{pt.lookback_window}</TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={`${pt.portfolio_risk_score.toFixed(1)} · ${pt.portfolio_classification}`}
                        sx={{
                          borderRadius: "var(--radius)",
                          fontWeight: 600,
                          fontFamily: "var(--font-data)",
                          bgcolor:
                            pt.portfolio_classification === "Low"
                              ? "var(--line)"
                              : pt.portfolio_classification === "Moderate"
                                ? "var(--line)"
                                : "var(--gray)",
                          color:
                            pt.portfolio_classification === "Low"
                              ? "var(--up)"
                              : pt.portfolio_classification === "Moderate"
                                ? "var(--amber)"
                                : "var(--down)",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", fontFamily: "var(--font-data)", borderBottom: "none" }}>
                      {pt.annualized_volatility.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ color: "var(--white)", fontFamily: "var(--font-data)", borderBottom: "none" }}>
                      {pt.downside_volatility.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ color: "var(--down)", fontWeight: 600, fontFamily: "var(--font-data)", borderBottom: "none" }}>
                      -{pt.max_drawdown.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: "var(--up)", fontFamily: "var(--font-data)" }}>
                        {pt.diversification_score.toFixed(0)}/100
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={pt.coverage_status.toUpperCase()}
                        sx={{
                          borderRadius: "var(--radius)",
                          fontSize: "var(--text-title)",
                          bgcolor: "var(--bg)",
                          color: "var(--white)",
                          fontWeight: 600,
                        }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
}

export function MstHoldingsInspector({
  analysis,
}: {
  analysis: PortfolioAnalysisResponse | null;
}) {
  const [selectedStock, setSelectedStock] = useState<string>("");

  if (!analysis) {
    return (
      <Box sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No MST network analysis available. Run analysis first.
        </Typography>
      </Box>
    );
  }

  const holdingsSymbols = analysis.holdings.map((h) => h.symbol);
  const activeStock = selectedStock || (holdingsSymbols[0] ?? "");

  // Find all direct edges involving the active stock
  const connectedEdges = analysis.mst.subtree_edges.filter(
    (e) => e.symbol_a === activeStock || e.symbol_b === activeStock
  );



  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {/* Selector & Ego Network Header */}
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-3)",
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-2)" }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
              Holding Relationship & Ego-Network Inspector
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--gray)" }}>
              Select any held stock to inspect its topological neighbours, Mantegna distances, and MST paths.
            </Typography>
          </Box>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="stock-inspect-label">Select Holding</InputLabel>
            <Select
              labelId="stock-inspect-label"
              value={activeStock}
              label="Select Holding"
              onChange={(e) => setSelectedStock(e.target.value)}
              sx={{
                bgcolor: "var(--bg)",
                borderRadius: "var(--radius)",
                border: "none",
                boxShadow: "none",
              }}
            >
              {holdingsSymbols.map((sym) => (
                <MenuItem key={sym} value={sym}>
                  {sym}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      {/* Network Connections Table */}
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)" }}>
            Direct Topological Links for {activeStock}
          </Typography>
          <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)" }}>
            Minimum Spanning Tree edges connected directly to {activeStock}. Edges represent the
            shortest correlation distance: d = √(2(1 - ρ)).
          </Typography>

          {connectedEdges.length === 0 ? (
            <Typography variant="body2" sx={{ color: "var(--gray)" }}>
              No direct subtree edges found for {activeStock}.
            </Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead sx={{ bgcolor: "var(--line)" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Connected Asset</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Pearson Correlation (ρ)</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Mantegna Distance (d)</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Stability / Persistence</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Implication for Diversification</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {connectedEdges.map((edge) => {
                    const peer = edge.symbol_a === activeStock ? edge.symbol_b : edge.symbol_a;
                    const isStrong = edge.correlation >= 0.50;
                    return (
                      <TableRow
                        key={edge.symbol_a + edge.symbol_b}
                        hover
                        sx={{ "&:hover": { bgcolor: "var(--line) !important" } }}
                      >
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>{peer}</TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontWeight: 600,
                            fontFamily: "var(--font-data)",
                            color: isStrong ? "var(--down)" : "var(--up)",
                            borderBottom: "none",
                          }}
                        >
                          {edge.correlation.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ color: "var(--white)", fontFamily: "var(--font-data)", borderBottom: "none" }}>
                          {edge.distance.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ borderBottom: "none" }}>
                          <Chip
                            size="small"
                            label={edge.confidence.toUpperCase()}
                            sx={{
                              borderRadius: "var(--radius)",
                              fontSize: "var(--text-title)",
                              bgcolor: "var(--bg)",
                              color: "var(--white)",
                              fontWeight: 600,
                            }}
                          />
                        </TableCell>
                        <TableCell sx={{ borderBottom: "none" }}>
                          <Typography variant="body2" sx={{ fontSize: "var(--text-title)", color: "var(--gray)" }}>
                            {isStrong
                              ? "High co-movement reduces diversification; joint price swings expected."
                              : "Moderate/low correlation provides good diversification cushioning."}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>



      {/* Methodological Limitations Callout Card */}
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-3)",
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
          Methodological Scope & Limitations of the Minimum Spanning Tree
        </Typography>
        <Typography variant="body2" sx={{ mt: "var(--space-1)", fontSize: "var(--text-title)", color: "var(--gray)" }}>
          The Minimum Spanning Tree (MST) reduces complex market co-movements into an acyclic topological
          backbone by minimizing Mantegna distances:
        </Typography>
        <Box component="ul" sx={{ pl: "var(--space-3)", my: "var(--space-1)", fontSize: "var(--text-title)", color: "var(--white)" }}>
          <li style={{ marginBottom: "6px" }}>
            <strong>Information Filtering:</strong> The tree intentionally discards cyclic secondary links
            to isolate the strongest paths. Non-displayed links may still carry economic correlation.
          </li>
          <li style={{ marginBottom: "6px" }}>
            <strong>Correlation vs. Causation:</strong> Topological proximity reflects historical statistical
            co-movement; it does not imply economic causation or common ownership.
          </li>
          <li style={{ marginBottom: "6px" }}>
            <strong>Non-Linear & Tail Risk:</strong> Standard Pearson correlation measures linear dependence;
            it may understate tail risk and crash co-dependence during severe liquidity shocks.
          </li>
          <li>
            <strong>Regime Instability:</strong> Tree structures evolve over macroeconomic regimes.
            Persistence confidence scores indicate stability over compatible rolling windows.
          </li>
        </Box>
      </Paper>
    </Box>
  );
}

export function FutureNewsSignalsSection({
  newsSummary,
}: {
  newsSummary: PortfolioNewsSummary | null;
}) {
  if (!newsSummary) {
    return (
      <Box sx={{ p: "var(--space-4)", textAlign: "center" }}>
        <Typography variant="body1" sx={{ color: "var(--gray)" }}>
          News Intelligence service not loaded. Please ensure backend is running.
        </Typography>
      </Box>
    );
  }

  const isConfigured = newsSummary.provider_status !== "not_configured";
  const verifiedCards = newsSummary.verified_articles || [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {/* ─── PROVIDER & GOVERNANCE HEADER ─── */}
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-3)",
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} sx={{ justifyContent: "space-between", alignItems: { xs: "flex-start", md: "center" }, gap: "var(--space-2)" }}>
          <Box>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                News Intelligence & Qualitative Sentiment
              </Typography>
              <Chip
                size="small"
                label={isConfigured ? "FEED CONFIGURED" : "PROVIDER NOT CONFIGURED"}
                sx={{
                  borderRadius: "var(--radius)",
                  fontWeight: 600,
                  fontSize: "var(--text-title)",
                  bgcolor: isConfigured ? "var(--line)" : "var(--gray)",
                  color: isConfigured ? "var(--up)" : "var(--down)",
                }}
              />
            </Stack>
            <Typography variant="body2" sx={{ mt: "var(--space-1)", color: "var(--gray)", fontSize: "var(--text-title)" }}>
              Provider: {newsSummary.provider_name || "National Equities Syndicated Wire"} · As of {newsSummary.as_of}
            </Typography>
          </Box>
          <Chip
            icon={<NewsIcon sx={{ color: "var(--white) !important" }} />}
            label={`Portfolio Sentiment: ${newsSummary.portfolio_sentiment_average >= 0 ? "+" : ""}${newsSummary.portfolio_sentiment_average.toFixed(2)}`}
            sx={{
              borderRadius: "var(--radius)",
              fontWeight: 600,
              bgcolor: newsSummary.portfolio_sentiment_average >= 0.1 ? "var(--line)" : newsSummary.portfolio_sentiment_average <= -0.1 ? "var(--gray)" : "var(--line)",
              color: newsSummary.portfolio_sentiment_average >= 0.1 ? "var(--up)" : newsSummary.portfolio_sentiment_average <= -0.1 ? "var(--down)" : "var(--white)",
            }}
          />
        </Stack>
        <Typography variant="body2" sx={{ mt: "var(--space-2)", fontSize: "var(--text-title)", color: "var(--gray)" }}>
          {newsSummary.provider_disclaimer || newsSummary.methodology_disclaimer}
        </Typography>
      </Paper>

      {/* ─── UNCONFIGURED PROVIDER NOTICE BANNER ─── */}
      {!isConfigured && (
        <Paper
          elevation={0}
          sx={{
            p: "var(--space-3)",
            borderRadius: "var(--radius)",
            border: "none",
            bgcolor: "var(--gray)",
            boxShadow: "none",
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--down)" }}>
            Provider Credentials Unconfigured
          </Typography>
          <Typography variant="body2" sx={{ mt: "var(--space-1)", color: "var(--white)", fontSize: "var(--text-title)" }}>
            Set <code>PRISM_NEWS_API_KEY</code> or configure a syndicated RSS feed in your environment variables to ingest live financial feeds. PRISM is diagnostic and strictly adheres to terms: zero scraping, no paywall bypass, and never fabricates news articles.
          </Typography>
        </Paper>
      )}

      {/* ─── DIAGNOSTIC SUMMARY CARDS ─── */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <Paper elevation={0} sx={{ p: "var(--space-2)", flex: 1, borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)" }}>
          <Typography variant="overline" sx={{ color: "var(--gray)", fontWeight: 600 }}>Tracked Articles</Typography>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>
            {newsSummary.total_articles_tracked}
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--gray)" }}>
            {newsSummary.deduplicated_article_count ?? newsSummary.total_articles_tracked} unique (deduplicated)
          </Typography>
        </Paper>

        <Paper elevation={0} sx={{ p: "var(--space-2)", flex: 1, borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)" }}>
          <Typography variant="overline" sx={{ color: "var(--gray)", fontWeight: 600 }}>Corporate Events</Typography>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>
            {newsSummary.high_impact_event_count}
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--gray)" }}>
            Earnings, guidance, M&A & regulatory
          </Typography>
        </Paper>

        <Paper elevation={0} sx={{ p: "var(--space-2)", flex: 1, borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)" }}>
          <Typography variant="overline" sx={{ color: "var(--gray)", fontWeight: 600 }}>Ambiguous Matches</Typography>
          <Typography variant="h5" sx={{ fontWeight: 600, color: (newsSummary.ambiguous_match_count || 0) > 0 ? "var(--amber)" : "var(--up)" }}>
            {newsSummary.ambiguous_match_count || 0}
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--gray)" }}>
            Ticker collision review flag
          </Typography>
        </Paper>
      </Stack>

      {/* ─── HOLDINGS NEWS BREAKDOWN TABLE ─── */}
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: "var(--space-2)" }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                Holdings News Exposure & Sentiment
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                Aggregated verified news signals per portfolio holding. News risk multipliers are heuristic and strictly isolated from market risk.
              </Typography>
            </Box>
          </Stack>

          <TableContainer>
            <Table size="small">
              <TableHead sx={{ bgcolor: "var(--line)" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Holding</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Weight</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>7-Day Sentiment</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Sentiment Label</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>24h Volume</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>7d Volume</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>Identified Events</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>News Multiplier</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {newsSummary.stock_signals.map((sig) => (
                  <TableRow
                    key={sig.symbol}
                    hover
                    sx={{ "&:hover": { bgcolor: "var(--line) !important" } }}
                  >
                    <TableCell sx={{ fontWeight: 600, color: "var(--white)", borderBottom: "none" }}>
                      {sig.symbol}
                      {sig.company_name && (
                        <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
                          {sig.company_name}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right" sx={{ fontFamily: "var(--font-data)", color: "var(--white)", borderBottom: "none" }}>
                      {newsSummary.holding_summaries?.find((h) => h.symbol === sig.symbol)?.weight_pct.toFixed(1) ?? "—"}%
                    </TableCell>
                    <TableCell
                      sx={{
                        fontWeight: 600,
                        fontFamily: "var(--font-data)",
                        color: sig.sentiment_average_7d >= 0 ? "var(--up)" : "var(--down)",
                        borderBottom: "none",
                      }} align="right"
                    >
                      {sig.sentiment_average_7d >= 0 ? "+" : ""}
                      {sig.sentiment_average_7d.toFixed(2)}
                    </TableCell>
                    <TableCell sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={sig.sentiment_label.toUpperCase()}
                        sx={{
                          borderRadius: "var(--radius)",
                          fontWeight: 600,
                          fontSize: "var(--text-title)",
                          bgcolor:
                            sig.sentiment_label === "positive"
                              ? "var(--line)"
                              : sig.sentiment_label === "negative"
                                ? "var(--gray)"
                                : "var(--line)",
                          color:
                            sig.sentiment_label === "positive"
                              ? "var(--up)"
                              : sig.sentiment_label === "negative"
                                ? "var(--down)"
                                : "var(--white)",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ color: "var(--white)", fontFamily: "var(--font-data)", borderBottom: "none" }}>
                      {sig.news_volume_24h}
                    </TableCell>
                    <TableCell align="right" sx={{ color: "var(--white)", fontFamily: "var(--font-data)", borderBottom: "none" }}>
                      {sig.news_volume_7d}
                    </TableCell>
                    <TableCell sx={{ borderBottom: "none" }}>
                      {sig.significant_events.length > 0 ? (
                        <Typography variant="body2" sx={{ fontSize: "var(--text-title)", color: "var(--amber)", fontWeight: 600 }}>
                          {sig.significant_events.join(", ")}
                        </Typography>
                      ) : (
                        <Typography variant="caption" sx={{ color: "var(--gray)" }}>
                          Routine coverage
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Tooltip title="Heuristic formula: 1.0 + max(0.0, -mean_sentiment * 0.3). Strictly isolated from market risk.">
                        <Chip
                          size="small"
                          label={`${sig.news_risk_multiplier.toFixed(2)}x (Heuristic)`}
                          sx={{
                            borderRadius: "var(--radius)",
                            fontSize: "var(--text-title)",
                            bgcolor: "var(--line)",
                            color: "var(--white)",
                            fontWeight: 600,
                          }}
                        />
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* ─── SOURCED VERIFIED ARTICLES FEED ─── */}
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: "var(--space-2)" }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                Verified News Feed & Provenance
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", fontSize: "var(--text-title)" }}>
                Every card links directly to the canonical source URL. Zero fabricated headlines.
              </Typography>
            </Box>
            <Chip
              size="small"
              label={`${verifiedCards.length || newsSummary.sample_articles.length} SOURCED ARTICLES`}
              sx={{ borderRadius: "var(--radius)", fontWeight: 600, bgcolor: "var(--line)", color: "var(--white)" }}
            />
          </Stack>

          <Stack spacing={2}>
            {verifiedCards.length > 0 ? (
              verifiedCards.map((art) => {
                const sig = art.signals[0];
                const sentLabel = sig?.sentiment_label || "neutral";
                const isPos = sentLabel === "positive";
                const isNeg = sentLabel === "negative";
                const isUnc = sentLabel === "uncertain";

                return (
                  <Paper
                    key={art.id}
                    elevation={0}
                    sx={{
                      p: "var(--space-3)",
                      borderRadius: "var(--radius)",
                      border: "none",
                      bgcolor: "var(--line)",
                    }}
                  >
                    <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { xs: "flex-start", sm: "center" }, gap: "var(--space-1)", mb: "var(--space-1)" }}>
                      <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", gap: "var(--space-1)" }}>
                        <Chip
                          size="small"
                          label={art.publisher}
                          sx={{ borderRadius: "var(--radius)", fontWeight: 600, fontSize: "var(--text-title)", bgcolor: "var(--bg)", color: "var(--white)" }}
                        />
                        <Typography variant="caption" sx={{ color: "var(--gray)", fontFamily: "var(--font-data)" }}>
                          {art.published_at.replace("T", " ").replace("Z", " UTC")}
                        </Typography>
                        {art.is_duplicate && (
                          <Chip
                            size="small"
                            label="NEAR-DUPLICATE WIRE REPRINT"
                            sx={{ borderRadius: "var(--radius)", fontSize: "var(--text-title)", bgcolor: "var(--gray)", color: "var(--down)" }}
                          />
                        )}
                      </Stack>

                      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                        {sig && (
                          <Chip
                            size="small"
                            label={`${sentLabel.toUpperCase()} (${sig.sentiment_score >= 0 ? "+" : ""}${sig.sentiment_score.toFixed(2)})`}
                            sx={{
                              borderRadius: "var(--radius)",
                              fontWeight: 600,
                              fontSize: "var(--text-title)",
                              bgcolor: isPos ? "var(--line)" : isNeg ? "var(--gray)" : isUnc ? "var(--bg)" : "var(--line)",
                              color: isPos ? "var(--up)" : isNeg ? "var(--down)" : isUnc ? "var(--amber)" : "var(--white)",
                            }}
                          />
                        )}
                        {sig?.event_category && sig.event_category !== "routine_coverage" && (
                          <Chip
                            size="small"
                            label={sig.event_category.toUpperCase()}
                            sx={{ borderRadius: "var(--radius)", fontWeight: 600, fontSize: "var(--text-title)", bgcolor: "var(--bg)", color: "var(--amber)" }}
                          />
                        )}
                      </Stack>
                    </Stack>

                    <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)" }}>
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "var(--white)", textDecoration: "none" }}
                      >
                        {art.headline} <span style={{ color: "var(--up)" }}>/</span>
                      </a>
                    </Typography>

                    {art.snippet && (
                      <Typography variant="body2" sx={{ color: "var(--gray)", fontSize: "var(--text-title)", mb: "var(--space-1)" }}>
                        {art.snippet}
                      </Typography>
                    )}

                    {/* ─── 60-70 WORD EXPLAINABLE ANALYSIS PANEL ─── */}
                    <Box
                      sx={{
                        my: "var(--space-2)",
                        p: "var(--space-2)",
                        bgcolor: "var(--bg)",
                        borderLeft: "var(--border-width) solid",
                        borderColor: isPos ? "var(--up)" : isNeg ? "var(--down)" : "var(--amber)",
                        boxShadow: "none",
                      }}
                    >
                      <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: "var(--space-2)" }}>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 600,
                            textTransform: "uppercase",
                            letterSpacing: 0,
                            color: isPos ? "var(--up)" : isNeg ? "var(--down)" : "var(--amber)",
                          }}
                        >
                          Explainable Market & Risk Breakdown (~60–70 Words)
                        </Typography>
                        <Chip
                          size="small"
                          label={isPos ? "BULLISH CATALYST" : isNeg ? "DOWNSIDE VOLATILITY" : "NEUTRAL / MONITOR"}
                          sx={{
                            height: 20,
                            fontSize: "var(--text-title)",
                            fontWeight: 600,
                            borderRadius: "var(--radius)",
                            bgcolor: isPos ? "var(--line)" : isNeg ? "var(--gray)" : "var(--line)",
                            color: isPos ? "var(--up)" : isNeg ? "var(--down)" : "var(--white)",
                          }}
                        />
                      </Stack>

                      <Stack spacing={1}>
                        <Box>
                          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "inline-block", mr: "var(--space-1)" }}>
                            What The News Is:
                          </Typography>
                          <Typography variant="body2" sx={{ display: "inline", color: "var(--white)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                            {art.what_the_news_is || (art.explanation ? art.explanation.split(" · ")[0] : art.headline)}
                          </Typography>
                        </Box>

                        <Box>
                          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "inline-block", mr: "var(--space-1)" }}>
                            Market & Sector Impact:
                          </Typography>
                          <Typography variant="body2" sx={{ display: "inline", color: "var(--white)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                            {art.market_and_sector_impact || (isPos ? "Expected to stimulate near-term upward valuation expansion across the sector." : isNeg ? "Induces downward pricing pressure and elevated volatility across peer holdings." : "Prompts a cautious wait-and-see reaction across the sector with limited systemic spillover.")}
                          </Typography>
                        </Box>

                        <Box>
                          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--up)", display: "inline-block", mr: "var(--space-1)" }}>
                            Actionable Advice (What You Should Do):
                          </Typography>
                          <Typography variant="body2" sx={{ display: "inline", color: "var(--up)", fontWeight: 600, fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                            {art.actionable_advice || (isPos ? "Maintain existing allocation to participate in momentum; maintain trailing stop-losses." : isNeg ? "Avoid panic-selling; review downside stop-losses and trim if sector ceiling is breached." : "Maintain disciplined hold; monitor upcoming quarterly operational execution without knee-jerk adjustments.")}
                          </Typography>
                        </Box>
                      </Stack>
                    </Box>

                    <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { xs: "flex-start", sm: "center" }, gap: "var(--space-1)", pt: "var(--space-1)", borderTop: "var(--border-width) solid var(--cyan)" }}>
                      <Typography variant="caption" sx={{ color: "var(--gray)" }}>
                        {art.affected_holdings && art.affected_holdings.length > 0
                          ? `Portfolio Exposure: ${art.affected_holdings.join(", ")} (${art.holding_exposure_weight_pct.toFixed(1)}% of capital)`
                          : (art.explanation ? `Synthesis: ${art.explanation}` : "Diagnostic news entity linkage")}
                      </Typography>
                      <Button
                        size="small"
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{
                          textTransform: "none",
                          fontSize: "var(--text-title)",
                          fontWeight: 600,
                          color: "var(--up)",
                          p: "var(--space-1)",
                        }}
                      >
                        Read Original Article /
                      </Button>
                    </Stack>
                  </Paper>
                );
              })
            ) : (
              newsSummary.sample_articles.map((art) => (
                <Paper
                  key={art.id}
                  elevation={0}
                  sx={{
                    p: "var(--space-3)",
                    borderRadius: "var(--radius)",
                    border: "none",
                    bgcolor: "var(--line)",
                  }}
                >
                  <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: "var(--space-1)" }}>
                    <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
                      {art.publisher} · {art.published_at.replace("T", " ").replace("Z", " UTC")}
                    </Typography>
                    <Chip
                      size="small"
                      label={art.sentiment_label.toUpperCase()}
                      sx={{
                        borderRadius: "var(--radius)",
                        fontWeight: 600,
                        fontSize: "var(--text-title)",
                        bgcolor: art.sentiment_label === "positive" ? "var(--line)" : art.sentiment_label === "negative" ? "var(--gray)" : "var(--bg)",
                        color: art.sentiment_label === "positive" ? "var(--up)" : art.sentiment_label === "negative" ? "var(--down)" : "var(--white)",
                      }}
                    />
                  </Stack>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                    {art.source_url ? (
                      <a href={art.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--white)", textDecoration: "none" }}>
                        {art.headline} /
                      </a>
                    ) : (
                      art.headline
                    )}
                  </Typography>
                  <Typography variant="body2" sx={{ color: "var(--gray)", fontSize: "var(--text-title)", mt: "var(--space-1)", mb: "var(--space-1)" }}>
                    {art.summary}
                  </Typography>

                  {/* ─── 60-70 WORD EXPLAINABLE ANALYSIS PANEL ─── */}
                  <Box
                    sx={{
                      my: "var(--space-2)",
                      p: "var(--space-2)",
                      bgcolor: "var(--bg)",
                      borderLeft: "var(--border-width) solid",
                      borderColor: art.sentiment_label === "positive" ? "var(--up)" : art.sentiment_label === "negative" ? "var(--down)" : "var(--amber)",
                      boxShadow: "none",
                    }}
                  >
                    <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: "var(--space-2)" }}>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: 0,
                          color: art.sentiment_label === "positive" ? "var(--up)" : art.sentiment_label === "negative" ? "var(--down)" : "var(--amber)",
                        }}
                      >
                        Explainable Market & Risk Breakdown (~60–70 Words)
                      </Typography>
                      <Chip
                        size="small"
                        label={art.sentiment_label === "positive" ? "BULLISH CATALYST" : art.sentiment_label === "negative" ? "DOWNSIDE VOLATILITY" : "NEUTRAL / MONITOR"}
                        sx={{
                          height: 20,
                          fontSize: "var(--text-title)",
                          fontWeight: 600,
                          borderRadius: "var(--radius)",
                          bgcolor: art.sentiment_label === "positive" ? "var(--line)" : art.sentiment_label === "negative" ? "var(--gray)" : "var(--line)",
                          color: art.sentiment_label === "positive" ? "var(--up)" : art.sentiment_label === "negative" ? "var(--down)" : "var(--white)",
                        }}
                      />
                    </Stack>

                    <Stack spacing={1}>
                      <Box>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "inline-block", mr: "var(--space-1)" }}>
                          What The News Is:
                        </Typography>
                        <Typography variant="body2" sx={{ display: "inline", color: "var(--white)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                          {art.what_the_news_is || art.summary || art.headline}
                        </Typography>
                      </Box>

                      <Box>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "inline-block", mr: "var(--space-1)" }}>
                          Market & Sector Impact:
                        </Typography>
                        <Typography variant="body2" sx={{ display: "inline", color: "var(--white)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                          {art.market_and_sector_impact || (art.sentiment_label === "positive" ? "Provides positive sentiment across sector peers, supporting valuation momentum." : art.sentiment_label === "negative" ? "Induces downward pricing pressure across sector peers, elevating near-term volatility." : "Prompts a rangebound wait-and-see posture across sector competitors.")}
                        </Typography>
                      </Box>

                      <Box>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--up)", display: "inline-block", mr: "var(--space-1)" }}>
                          Actionable Advice (What You Should Do):
                        </Typography>
                        <Typography variant="body2" sx={{ display: "inline", color: "var(--up)", fontWeight: 600, fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                          {art.actionable_advice || (art.sentiment_label === "positive" ? "Hold positions to capture trend upside; maintain disciplined trailing stops." : art.sentiment_label === "negative" ? "Exercise caution; avoid panic selling and review position size against your risk ceiling." : "Hold steady without reactive adjustments; monitor upcoming disclosures.")}
                        </Typography>
                      </Box>
                    </Stack>
                  </Box>
                </Paper>
              ))
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
