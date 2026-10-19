import { useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
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
  Typography,
  SvgIcon,
  SvgIconProps,
} from "@mui/material";

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

function TrendingDownIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M16 18l2.29-2.29-4.88-4.88-4 4L2 7.41 3.41 6l6 6 4-4 6.3 6.29L22 12v6z" />
    </SvgIcon>
  );
}

function TrendingUpIcon(props: SvgIconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z" />
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

export function StructuralMonitoringDashboard({
  monitoring,
}: {
  monitoring: StructuralMonitoringSnapshot | null;
  analysis?: PortfolioAnalysisResponse | null;
}) {
  if (!monitoring) {
    return (
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No structural monitoring data available. Please run portfolio analysis first.
        </Typography>
      </Box>
    );
  }

  const triggeredIndicators = monitoring.indicators.filter((ind) => ind.triggered);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Executive Overview Banner */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          bgcolor: "#292D2A",
          color: "#F9EBD7",
          boxShadow: "0 10px 28px rgba(41,45,42,0.18)",
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
          <Box>
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, mb: 1 }}>
              <Typography variant="overline" sx={{ letterSpacing: 1.5, color: "#E3D7C4", fontWeight: 700 }}>
                EXECUTIVE MONITORING OVERVIEW
              </Typography>
              <Chip
                size="small"
                label={monitoring.data_freshness}
                sx={{ bgcolor: "#E3D7C4", color: "#292D2A", fontSize: "0.72rem", borderRadius: 0, fontWeight: 600 }}
              />
            </Stack>
            <Typography variant="h5" sx={{ fontWeight: 800, color: "#F9EBD7" }}>
              Portfolio Structural Health & Concentration Risk
            </Typography>
            <Typography variant="body2" sx={{ color: "#E3D7C4", mt: 0.5, maxWidth: 780 }}>
              Real-time aggregation of multi-factor risk, network topology, covariance stability,
              and prudential concentration benchmarks across all held assets.
            </Typography>
          </Box>
          <Box sx={{ textAlign: { xs: "left", md: "right" } }}>
            <Typography variant="caption" sx={{ color: "#E3D7C4" }}>
              Estimated Portfolio Value
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, color: "#F9EBD7", fontFamily: "JetBrains Mono" }}>
              ₹{monitoring.portfolio_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </Typography>
            <Stack
              direction="row"
              sx={{
                gap: 0.5,
                justifyContent: { xs: "flex-start", md: "flex-end" },
                alignItems: "center",
                mt: 0.5,
              }}
            >
              {monitoring.overall_return >= 0 ? (
                <TrendingUpIcon sx={{ color: "#046A38", fontSize: 18 }} />
              ) : (
                <TrendingDownIcon sx={{ color: "#E34222", fontSize: 18 }} />
              )}
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 700,
                  fontFamily: "JetBrains Mono",
                  color: monitoring.overall_return >= 0 ? "#046A38" : "#E34222",
                }}
              >
                {monitoring.overall_return >= 0 ? "+" : ""}
                {monitoring.overall_return.toFixed(2)}% Overall Unrealized
              </Typography>
            </Stack>
          </Box>
        </Stack>
      </Paper>

      {/* KPI Summary Cards */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
          gap: 2,
        }}
      >
        <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700 }}>
              PORTFOLIO RISK SCORE
            </Typography>
            <Stack direction="row" sx={{ alignItems: "baseline", gap: 1, mt: 0.75 }}>
              <Typography variant="h4" sx={{ fontWeight: 800, color: "#292D2A", fontFamily: "JetBrains Mono" }}>
                {monitoring.portfolio_risk_score.toFixed(0)}
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64" }}>
                / 100
              </Typography>
            </Stack>
            <Chip
              size="small"
              label={monitoring.portfolio_classification}
              sx={{
                mt: 1,
                fontWeight: 700,
                borderRadius: 0,
                bgcolor:
                  monitoring.portfolio_classification === "Low"
                    ? "#DCE9DE"
                    : monitoring.portfolio_classification === "Moderate"
                    ? "#E3D7C4"
                    : "#F6D9CC",
                color:
                  monitoring.portfolio_classification === "Low"
                    ? "#046A38"
                    : monitoring.portfolio_classification === "Moderate"
                    ? "#8A5A00"
                    : "#B8321A",
              }}
            />
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700 }}>
              DIVERSIFICATION SCORE
            </Typography>
            <Stack direction="row" sx={{ alignItems: "baseline", gap: 1, mt: 0.75 }}>
              <Typography variant="h4" sx={{ fontWeight: 800, color: "#046A38", fontFamily: "JetBrains Mono" }}>
                {monitoring.diversification_score.toFixed(0)}
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64" }}>
                / 100
              </Typography>
            </Stack>
            <Chip
              size="small"
              label={`Grade ${monitoring.diversification_grade}`}
              sx={{ mt: 1, fontWeight: 700, borderRadius: 0, bgcolor: "#DCE9DE", color: "#046A38" }}
            />
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700 }}>
              TOP SECTOR EXPOSURE
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A", mt: 0.75 }} noWrap>
              {monitoring.top_sector}
            </Typography>
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, mt: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono" }}>
                {monitoring.top_sector_weight.toFixed(1)}% Weight
              </Typography>
              <Chip
                size="small"
                label={monitoring.top_sector_status}
                sx={{
                  fontWeight: 600,
                  fontSize: "0.72rem",
                  borderRadius: 0,
                  bgcolor:
                    monitoring.top_sector_status === "Balanced"
                      ? "#DCE9DE"
                      : monitoring.top_sector_status === "Elevated"
                      ? "#F9EBD7"
                      : "#F6D9CC",
                  color:
                    monitoring.top_sector_status === "Balanced"
                      ? "#046A38"
                      : monitoring.top_sector_status === "Elevated"
                      ? "#8A5A00"
                      : "#B8321A",
                }}
              />
            </Stack>
          </CardContent>
        </Card>

        <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)", height: "100%" }}>
          <CardContent>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700 }}>
              LARGEST POSITION
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A", mt: 0.75 }}>
              {monitoring.largest_holding}
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64", mt: 1, fontFamily: "JetBrains Mono" }}>
              {monitoring.largest_holding_weight.toFixed(1)}% of total portfolio capital
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Active Monitoring Indicators */}
      <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
        <CardContent>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 2 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 750 }}>
                Prudential Monitoring Indicators & Analytical Alerts
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Configurable threshold triggers across concentration, market sensitivity, and downside volatility.
              </Typography>
            </Box>
            <Chip
              label={`${triggeredIndicators.length} Active Alert${triggeredIndicators.length === 1 ? "" : "s"}`}
              color={triggeredIndicators.length > 0 ? "warning" : "success"}
              sx={{ fontWeight: 700 }}
            />
          </Stack>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
              gap: 2,
            }}
          >
            {monitoring.indicators.map((ind) => (
              <Paper
                key={ind.id}
                elevation={0}
                sx={{
                  p: 2,
                  borderRadius: 0,
                  bgcolor: ind.triggered
                    ? ind.severity === "critical"
                      ? "#F6D9CC"
                      : "#F9EBD7"
                    : "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "flex-start", gap: 1 }}>
                  <Box>
                    <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
                      {ind.triggered ? (
                        <WarningIcon
                          sx={{
                            color: ind.severity === "critical" ? "#E34222" : "#8A5A00",
                            fontSize: 20,
                          }}
                        />
                      ) : (
                        <InfoIcon sx={{ color: "#046A38", fontSize: 20 }} />
                      )}
                      <Typography variant="subtitle2" sx={{ fontWeight: 750 }}>
                        {ind.title}
                      </Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.25 }}>
                      {ind.metric_name} · Threshold: {ind.threshold_value} · {ind.observation_period}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={ind.triggered ? ind.severity.toUpperCase() : "NORMAL"}
                    sx={{
                      fontSize: "0.68rem",
                      fontWeight: 700,
                      borderRadius: 0,
                      bgcolor: ind.triggered
                        ? ind.severity === "critical"
                          ? "#F6D9CC"
                          : "#F9EBD7"
                        : "#E3D7C4",
                      color: ind.triggered
                        ? ind.severity === "critical"
                          ? "#B8321A"
                          : "#8A5A00"
                        : "#292D2A",
                    }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ mt: 1, color: "#292D2A", fontSize: "0.85rem" }}>
                  {ind.explanation}
                </Typography>
              </Paper>
            ))}
          </Box>

          <Paper
            elevation={0}
            sx={{
              mt: 2.5,
              p: 2,
              borderRadius: 0,
              border: "none",
              bgcolor: "#F9EBD7",
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
            }}
          >
            <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
              <strong style={{ color: "#292D2A" }}>Non-Advisory Disclaimer:</strong> Monitoring indicators represent mathematical
              warning thresholds based on historical parameters. They are not automated trade recommendations,
              stop-loss triggers, or investment advice.
            </Typography>
          </Paper>
        </CardContent>
      </Card>

      {/* Structural Clusters & Euler Risk Decomposition */}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
        {/* Correlated Groups of Holdings */}
        <Card
          elevation={0}
          sx={{
            borderRadius: 0,
            border: "none",
            bgcolor: "#F9EBD7",
            boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
            height: "100%",
          }}
        >
          <CardContent>
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, mb: 1 }}>
              <HubIcon sx={{ color: "#1F6F78" }} />
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                Correlated Holding Groups (MST Clusters)
              </Typography>
            </Stack>
            <Typography variant="body2" sx={{ mb: 2, color: "#686B64" }}>
              Groups of held assets exhibiting strong return co-movement (mean ρ ≥ 0.50).
            </Typography>

            {monitoring.correlated_groups.length === 0 ? (
              <Box
                sx={{
                  p: 3,
                  textAlign: "center",
                  bgcolor: "#F9EBD7",
                  borderRadius: 0,
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  No major correlation clusters detected (ρ &lt; 0.50 across all held pairs).
                  Your assets exhibit healthy return independence.
                </Typography>
              </Box>
            ) : (
              <Stack spacing={1.5}>
                {monitoring.correlated_groups.map((grp) => (
                  <Paper
                    key={grp.cluster_id}
                    elevation={0}
                    sx={{
                      p: 2,
                      borderRadius: 0,
                      border: "none",
                      bgcolor: "#F9EBD7",
                      boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                    }}
                  >
                    <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 0.75 }}>
                      <Stack direction="row" sx={{ gap: 0.75, alignItems: "center" }}>
                        {grp.holding_symbols.map((sym) => (
                          <Chip
                            key={sym}
                            size="small"
                            label={sym}
                            sx={{
                              borderRadius: 0,
                              fontWeight: 700,
                              bgcolor: "#E3D7C4",
                              color: "#292D2A",
                              boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                            }}
                          />
                        ))}
                      </Stack>
                      <Chip
                        size="small"
                        label={`ρ = ${grp.average_correlation.toFixed(2)}`}
                        sx={{
                          borderRadius: 0,
                          bgcolor: grp.average_correlation >= 0.5 ? "#F6D9CC" : "#DCE9DE",
                          color: grp.average_correlation >= 0.5 ? "#B8321A" : "#046A38",
                          fontWeight: 700,
                        }}
                      />
                    </Stack>
                    <Typography variant="caption" sx={{ display: "block", mt: 0.5, color: "#686B64" }}>
                      {grp.interpretation}
                    </Typography>
                  </Paper>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>

        {/* Top Euler Risk Contributors */}
        <Card
          elevation={0}
          sx={{
            borderRadius: 0,
            border: "none",
            bgcolor: "#F9EBD7",
            boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
            height: "100%",
          }}
        >
          <CardContent>
            <Stack direction="row" sx={{ alignItems: "center", gap: 1, mb: 1 }}>
              <TimelineIcon sx={{ color: "#3F5B7A" }} />
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                Euler Risk Contribution Decomposition
              </Typography>
            </Stack>
            <Typography variant="body2" sx={{ mb: 2, color: "#686B64" }}>
              Holding share of total portfolio volatility variance vs. invested capital weight.
            </Typography>

            <Stack spacing={1.75}>
              {monitoring.largest_risk_contributors.map((contrib) => (
                <Box key={contrib.symbol}>
                  <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 0.5 }}>
                    <Stack direction="row" sx={{ gap: 1, alignItems: "center" }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
                        {contrib.symbol}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "#686B64" }}>
                        {contrib.sector}
                      </Typography>
                    </Stack>
                    <Stack direction="row" sx={{ gap: 1, alignItems: "center" }}>
                      <Typography variant="caption" sx={{ color: "#686B64", fontFamily: "JetBrains Mono, monospace" }}>
                        Cap: {contrib.weight_percent.toFixed(1)}%
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 700,
                          fontFamily: "JetBrains Mono, monospace",
                          color: contrib.is_amplified ? "#B8321A" : "#046A38",
                        }}
                      >
                        Risk: {contrib.risk_contribution_percent.toFixed(1)}%
                      </Typography>
                      {contrib.is_amplified && (
                        <Chip
                          size="small"
                          label="Risk Amplified"
                          sx={{
                            fontSize: "0.65rem",
                            height: 18,
                            borderRadius: 0,
                            bgcolor: "#F6D9CC",
                            color: "#B8321A",
                            fontWeight: 700,
                          }}
                        />
                      )}
                    </Stack>
                  </Stack>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, contrib.risk_contribution_percent * 2)}
                    sx={{
                      height: 7,
                      borderRadius: 0,
                      bgcolor: "#E3D7C4",
                      "& .MuiLinearProgress-bar": {
                        bgcolor: contrib.is_amplified ? "#E34222" : "#046A38",
                        borderRadius: 0,
                      },
                    }}
                  />
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>
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
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography variant="body1" color="text.secondary">
          No historical risk tracking data available yet.
        </Typography>
      </Box>
    );
  }

  const series = monitoring.historical_risk_series;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          bgcolor: "#F9EBD7",
          border: "none",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 1.5 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
              Historical Risk Progression & Score Audit
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64" }}>
              Consistent 252-day lookback window evaluated at historical observation horizons.
            </Typography>
          </Box>
          <Stack direction="row" sx={{ gap: 1, alignItems: "center" }}>
            <Chip
              size="small"
              label={`${monitoring.persisted_history_count} Snapshots Saved`}
              sx={{
                borderRadius: 0,
                fontWeight: 700,
                bgcolor: "#F9EBD7",
                color: "#292D2A",
              }}
            />
            <Chip
              size="small"
              label="Audit Log Verified"
              sx={{
                borderRadius: 0,
                fontWeight: 700,
                bgcolor: "#DCE9DE",
                color: "#046A38",
              }}
            />
          </Stack>
        </Stack>
      </Paper>

      {/* Historical Trend Table */}
      <Card
        elevation={0}
        sx={{
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <CardContent sx={{ p: 0 }}>
          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Observation Date</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Horizon / Window</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Risk Score (0–100)</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Annual Volatility</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Downside Vol</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Max Drawdown</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Diversification</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Data Coverage</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {series.map((pt, idx) => (
                  <TableRow
                    key={pt.observation_date + pt.lookback_window}
                    hover
                    sx={{
                      bgcolor: idx === 0 ? "#F9EBD7" : "inherit",
                      "&:hover": { bgcolor: "#E3D7C4 !important" },
                    }}
                  >
                    <TableCell sx={{ fontWeight: idx === 0 ? 700 : 500, color: "#292D2A", borderBottom: "none" }}>
                      {pt.observation_date}{" "}
                      {idx === 0 && (
                        <Chip
                          size="small"
                          label="LATEST"
                          sx={{
                            ml: 1,
                            fontSize: "0.65rem",
                            height: 18,
                            borderRadius: 0,
                            bgcolor: "#DCE9DE",
                            color: "#046A38",
                            fontWeight: 700,
                          }}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={{ color: "#292D2A", borderBottom: "none" }}>{pt.lookback_window}</TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={`${pt.portfolio_risk_score.toFixed(1)} · ${pt.portfolio_classification}`}
                        sx={{
                          borderRadius: 0,
                          fontWeight: 700,
                          fontFamily: "JetBrains Mono, monospace",
                          bgcolor:
                            pt.portfolio_classification === "Low"
                              ? "#DCE9DE"
                              : pt.portfolio_classification === "Moderate"
                              ? "#E3D7C4"
                              : "#F6D9CC",
                          color:
                            pt.portfolio_classification === "Low"
                              ? "#046A38"
                              : pt.portfolio_classification === "Moderate"
                              ? "#8A5A00"
                              : "#B8321A",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                      {pt.annualized_volatility.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                      {pt.downside_volatility.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ color: "#B8321A", fontWeight: 700, fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                      -{pt.max_drawdown.toFixed(1)}%
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Typography variant="body2" sx={{ fontWeight: 700, color: "#046A38", fontFamily: "JetBrains Mono, monospace" }}>
                        {pt.diversification_score.toFixed(0)}/100
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={pt.coverage_status.toUpperCase()}
                        sx={{
                          borderRadius: 0,
                          fontSize: "0.68rem",
                          bgcolor: "#F9EBD7",
                          color: "#292D2A",
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
      <Box sx={{ p: 4, textAlign: "center" }}>
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

  // Find paths involving the active stock
  const connectedPaths = analysis.mst.holding_paths.filter(
    (p) => p.symbol_a === activeStock || p.symbol_b === activeStock
  );

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Selector & Ego Network Header */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 2 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
              Holding Relationship & Ego-Network Inspector
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64" }}>
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
                bgcolor: "#F9EBD7",
                borderRadius: 0,
                border: "none",
                boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
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
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 1 }}>
            Direct Topological Links for {activeStock}
          </Typography>
          <Typography variant="body2" sx={{ color: "#686B64", mb: 2 }}>
            Minimum Spanning Tree edges connected directly to {activeStock}. Edges represent the
            shortest correlation distance: d = √(2(1 - ρ)).
          </Typography>

          {connectedEdges.length === 0 ? (
            <Typography variant="body2" sx={{ color: "#686B64" }}>
              No direct subtree edges found for {activeStock}.
            </Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Connected Asset</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Pearson Correlation (ρ)</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Mantegna Distance (d)</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Stability / Persistence</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Implication for Diversification</TableCell>
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
                        sx={{ "&:hover": { bgcolor: "#E3D7C4 !important" } }}
                      >
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>{peer}</TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontWeight: 700,
                            fontFamily: "JetBrains Mono, monospace",
                            color: isStrong ? "#B8321A" : "#046A38",
                            borderBottom: "none",
                          }}
                        >
                          {edge.correlation.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                          {edge.distance.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ borderBottom: "none" }}>
                          <Chip
                            size="small"
                            label={edge.confidence.toUpperCase()}
                            sx={{
                              borderRadius: 0,
                              fontSize: "0.68rem",
                              bgcolor: "#F9EBD7",
                              color: "#292D2A",
                              fontWeight: 600,
                            }}
                          />
                        </TableCell>
                        <TableCell sx={{ borderBottom: "none" }}>
                          <Typography variant="body2" sx={{ fontSize: "0.82rem", color: "#686B64" }}>
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

      {/* Path Relationships to Other Holdings */}
      {connectedPaths.length > 0 && (
        <Card
          elevation={0}
          sx={{
            borderRadius: 0,
            border: "none",
            bgcolor: "#F9EBD7",
            boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
          }}
        >
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 1 }}>
              Topological MST Paths from {activeStock}
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64", mb: 2 }}>
              Shortest path routes through the NIFTY 200 spanning tree to other portfolio holdings.
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Target Holding</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Hops</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Mean Path ρ</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Weakest Link ρ</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>MST Path Route</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {connectedPaths.map((p) => {
                    const target = p.symbol_a === activeStock ? p.symbol_b : p.symbol_a;
                    return (
                      <TableRow
                        key={`${p.symbol_a}-${p.symbol_b}`}
                        hover
                        sx={{ "&:hover": { bgcolor: "#E3D7C4 !important" } }}
                      >
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>{target}</TableCell>
                        <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                          {p.hops}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                          {p.average_correlation.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                          {p.weakest_correlation.toFixed(2)}
                        </TableCell>
                        <TableCell sx={{ borderBottom: "none" }}>
                          <Typography variant="caption" sx={{ fontFamily: "JetBrains Mono, monospace", color: "#1F6F78", fontWeight: 600 }}>
                            {p.path.join(" → ")}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Methodological Limitations Callout Card */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
          Methodological Scope & Limitations of the Minimum Spanning Tree
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, fontSize: "0.85rem", color: "#686B64" }}>
          The Minimum Spanning Tree (MST) reduces complex market co-movements into an acyclic topological
          backbone by minimizing Mantegna distances:
        </Typography>
        <Box component="ul" sx={{ pl: 2.5, my: 0.5, fontSize: "0.82rem", color: "#292D2A" }}>
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
      <Box sx={{ p: 4, textAlign: "center" }}>
        <Typography variant="body1" sx={{ color: "#686B64" }}>
          News signals contract not loaded. Please ensure backend is running.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Decoupling Notice Banner */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
          Phase 3 Architecture Preview: Decoupled News Intelligence Contracts
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, fontSize: "0.85rem", color: "#686B64" }}>
          {newsSummary.methodology_disclaimer}
        </Typography>
      </Paper>

      {/* News Overview Card */}
      <Card
        elevation={0}
        sx={{
          borderRadius: 0,
          border: "none",
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <CardContent>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 2 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                Portfolio News Sentiment & Qualitative Signals (Preview)
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64" }}>
                Contract version {newsSummary.contract_version} · {newsSummary.architecture_status}
              </Typography>
            </Box>
            <Chip
              icon={<NewsIcon sx={{ color: "#292D2A !important" }} />}
              label={`Avg Sentiment: ${newsSummary.portfolio_sentiment_average >= 0 ? "+" : ""}${newsSummary.portfolio_sentiment_average.toFixed(2)}`}
              sx={{
                borderRadius: 0,
                fontWeight: 700,
                bgcolor: newsSummary.portfolio_sentiment_average >= 0.1 ? "#DCE9DE" : "#F9EBD7",
                color: newsSummary.portfolio_sentiment_average >= 0.1 ? "#046A38" : "#292D2A",
              }}
            />
          </Stack>

          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Symbol</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>7-Day Sentiment</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Sentiment Label</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>24h Volume</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>7d Volume</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Corporate Events</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>News Risk Factor</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {newsSummary.stock_signals.map((sig) => (
                  <TableRow
                    key={sig.symbol}
                    hover
                    sx={{ "&:hover": { bgcolor: "#E3D7C4 !important" } }}
                  >
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>{sig.symbol}</TableCell>
                    <TableCell
                      sx={{
                        fontWeight: 600,
                        fontFamily: "JetBrains Mono, monospace",
                        color: sig.sentiment_average_7d >= 0 ? "#046A38" : "#B8321A",
                        borderBottom: "none",
                      }}
                    >
                      {sig.sentiment_average_7d >= 0 ? "+" : ""}
                      {sig.sentiment_average_7d.toFixed(2)}
                    </TableCell>
                    <TableCell sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={sig.sentiment_label.toUpperCase()}
                        sx={{
                          borderRadius: 0,
                          fontWeight: 700,
                          fontSize: "0.68rem",
                          bgcolor:
                            sig.sentiment_label === "positive"
                              ? "#DCE9DE"
                              : sig.sentiment_label === "negative"
                              ? "#F6D9CC"
                              : "#F9EBD7",
                          color:
                            sig.sentiment_label === "positive"
                              ? "#046A38"
                              : sig.sentiment_label === "negative"
                              ? "#B8321A"
                              : "#292D2A",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                      {sig.news_volume_24h}
                    </TableCell>
                    <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                      {sig.news_volume_7d}
                    </TableCell>
                    <TableCell sx={{ borderBottom: "none" }}>
                      {sig.significant_events.length > 0 ? (
                        <Typography variant="body2" sx={{ fontSize: "0.82rem", color: "#8A5A00", fontWeight: 600 }}>
                          {sig.significant_events.join("; ")}
                        </Typography>
                      ) : (
                        <Typography variant="caption" sx={{ color: "#686B64" }}>
                          Routine coverage
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: "none" }}>
                      <Chip
                        size="small"
                        label={`${sig.news_risk_multiplier.toFixed(2)}x (Isolated)`}
                        sx={{
                          borderRadius: 0,
                          fontSize: "0.72rem",
                          bgcolor: "#F9EBD7",
                          color: "#292D2A",
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
