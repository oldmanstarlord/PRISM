import React from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import HowToRegIcon from "@mui/icons-material/HowToReg";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

import { useApi } from "../api";
import type { ShareholdingTableRow, StockGovernanceResponse } from "../types";
import { FreshnessBadge } from "./FreshnessBadge";

interface GovernancePanelProps {
  symbol: string;
}

export function GovernancePanel({ symbol }: GovernancePanelProps): React.ReactElement {
  const { data, isLoading, error } = useApi<StockGovernanceResponse>(
    `/stocks/${encodeURIComponent(symbol)}/governance`
  );

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        Governance data not yet available for {symbol}.
      </Alert>
    );
  }

  const formatPct = (val: number | null | undefined, signed: boolean = false): string => {
    if (val === null || val === undefined) return "—";
    const sign = signed && val > 0 ? "+" : "";
    return `${sign}${val.toFixed(2)}%`;
  };

  const formatINR = (val: number | null | undefined): string => {
    if (val === null || val === undefined) return "—";
    if (Math.abs(val) >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    if (Math.abs(val) >= 100000) {
      return `₹${(val / 100000).toFixed(2)} L`;
    }
    return `₹${val.toLocaleString("en-IN")}`;
  };

  const holdingTable = Array.isArray(data.holding_table) ? data.holding_table : [];
  const recentTrades = Array.isArray(data.recent_insider_trades) ? data.recent_insider_trades : [];
  const limitations = Array.isArray(data.limitations) ? data.limitations : [];

  // Build sorted chronological points for the pledge trend SVG line
  const chronologicalHoldings = [...holdingTable].sort(
    (a, b) => new Date(a.quarter_end).getTime() - new Date(b.quarter_end).getTime()
  );

  const pledgeTrendPoints = chronologicalHoldings
    .filter((h) => h.promoter_pledged_pct_of_promoter !== null)
    .map((h) => ({
      quarter: h.quarter_end,
      pledge: h.promoter_pledged_pct_of_promoter as number,
    }));

  const pledgeLevel = data.pledge.pledge_level_pct;
  const pledgeChange = data.pledge.pledge_change_pct;
  const isPledgeElevated = (pledgeLevel ?? 0) >= 20.0 || (pledgeChange ?? 0) >= 5.0;

  return (
    <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
      <CardContent>
        {/* Panel Header */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, mb: 2.5 }}
          spacing={1}
        >
          <Box>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <HowToRegIcon color="primary" />
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Governance & Ownership Signals
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary">
              SEBI Reg 31 quarterly shareholding disclosures and SEBI PIT Reg 7(2) / SAST insider trades.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            {data.as_of && (
              <FreshnessBadge asOf={data.as_of} label={`As of: ${data.as_of}`} />
            )}
            <Chip
              label="Point-in-Time"
              size="small"
              variant="outlined"
              color="primary"
            />
          </Stack>
        </Stack>

        {/* 4 Summary Metric Cards */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {/* Card 1: Promoter Pledge */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                borderRadius: 2,
                height: "100%",
                borderColor: isPledgeElevated ? "warning.main" : undefined,
                bgcolor: isPledgeElevated ? "action.hover" : undefined,
              }}
            >
              <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  Promoter Pledge
                </Typography>
                {isPledgeElevated && (
                  <Chip
                    icon={<WarningAmberIcon fontSize="small" />}
                    label="Elevated"
                    size="small"
                    color="warning"
                  />
                )}
              </Stack>
              <Typography variant="h5" sx={{ fontWeight: 700, my: 0.5 }}>
                {formatPct(pledgeLevel)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                2Q Δ:{" "}
                <Box
                  component="span"
                  sx={{
                    fontWeight: 600,
                    color:
                      pledgeChange && pledgeChange > 0
                        ? "error.main"
                        : pledgeChange && pledgeChange < 0
                        ? "success.main"
                        : "text.primary",
                  }}
                >
                  {formatPct(pledgeChange, true)}
                </Box>
                {" "}(% of promoter)
              </Typography>
            </Paper>
          </Grid>

          {/* Card 2: Promoter Holding */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                Promoter Group Holding
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, my: 0.5 }}>
                {formatPct(data.promoter_holding.promoter_pct)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                2Q Δ:{" "}
                <Box
                  component="span"
                  sx={{
                    fontWeight: 600,
                    color:
                      (data.promoter_holding.promoter_change_pct ?? 0) < 0
                        ? "error.main"
                        : (data.promoter_holding.promoter_change_pct ?? 0) > 0
                        ? "success.main"
                        : "text.primary",
                  }}
                >
                  {formatPct(data.promoter_holding.promoter_change_pct, true)}
                </Box>
              </Typography>
            </Paper>
          </Grid>

          {/* Card 3: Institutional Flow (FII + DII) */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                Institutional Holding (FII+DII)
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, my: 0.5 }}>
                {formatPct(data.institutional_flow.combined_pct)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                FII: {formatPct(data.institutional_flow.fii_pct)} | DII: {formatPct(data.institutional_flow.dii_pct)}
                <br />
                2Q Net Δ:{" "}
                <Box
                  component="span"
                  sx={{
                    fontWeight: 600,
                    color:
                      (data.institutional_flow.institutional_change_pct ?? 0) < 0
                        ? "warning.main"
                        : "success.main",
                  }}
                >
                  {formatPct(data.institutional_flow.institutional_change_pct, true)}
                </Box>
              </Typography>
            </Paper>
          </Grid>

          {/* Card 4: Insider Selling Activity */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: "100%" }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                Net Insider Selling ({data.insider_activity.window_days}d)
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, my: 0.5 }}>
                {formatINR(data.insider_activity.net_sell_value_inr)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {data.insider_activity.trade_count} trades | Sells: {formatINR(data.insider_activity.sell_value_inr)}
                <br />
                {data.insider_activity.insider_sell_ratio !== null ? (
                  <>Ratio/MCap: {(data.insider_activity.insider_sell_ratio * 100).toFixed(3)}%</>
                ) : (
                  <>Status: {data.insider_activity.status}</>
                )}
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Pledge Trend Line Visualization */}
        {pledgeTrendPoints.length > 1 && (
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3, borderRadius: 2 }}>
            <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Promoter Pledge Trend Line (% of Promoter Holding Pledged)
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Over {pledgeTrendPoints.length} reported quarters
              </Typography>
            </Stack>

            <Box sx={{ width: "100%", height: 100, display: "flex", alignItems: "center" }}>
              <PledgeTrendSvg points={pledgeTrendPoints} />
            </Box>
          </Paper>
        )}

        {/* Shareholding Pattern Table */}
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
          Quarterly Shareholding Patterns (SEBI Reg 31 Disclosures)
        </Typography>
        {holdingTable.length === 0 ? (
          <Alert severity="info" sx={{ mb: 3 }}>
            No shareholding pattern disclosures recorded yet.
          </Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: "action.hover" }}>
                  <TableCell sx={{ fontWeight: 700 }}>Quarter End</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Promoter %</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Pledged % of Promoter</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>FII %</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>DII %</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Public %</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Published At</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {holdingTable.map((row: ShareholdingTableRow) => (
                  <TableRow key={row.quarter_end} hover>
                    <TableCell sx={{ fontWeight: 600 }}>{row.quarter_end}</TableCell>
                    <TableCell align="right">{formatPct(row.promoter_pct)}</TableCell>
                    <TableCell align="right">
                      <Box
                        component="span"
                        sx={{
                          fontWeight: (row.promoter_pledged_pct_of_promoter ?? 0) >= 20 ? 700 : 400,
                          color: (row.promoter_pledged_pct_of_promoter ?? 0) >= 20 ? "warning.main" : "inherit",
                        }}
                      >
                        {formatPct(row.promoter_pledged_pct_of_promoter)}
                      </Box>
                    </TableCell>
                    <TableCell align="right">{formatPct(row.fii_pct)}</TableCell>
                    <TableCell align="right">{formatPct(row.dii_pct)}</TableCell>
                    <TableCell align="right">{formatPct(row.public_pct)}</TableCell>
                    <TableCell align="right">
                      <Typography variant="caption" color="text.secondary">
                        {row.published_at.slice(0, 10)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Recent Insider Trades Table */}
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
          Recent Insider & Promoter Trades (SEBI PIT Reg 7(2) / SAST)
        </Typography>
        {recentTrades.length === 0 ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            No insider trade disclosures reported within the rolling {data.insider_activity?.window_days ?? 180}-day window.
          </Alert>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ mb: 2, borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: "action.hover" }}>
                  <TableCell sx={{ fontWeight: 700 }}>Txn Date</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Person / Category</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Txn Type</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Quantity</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Value (INR)</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Published At</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentTrades.map((trade, idx) => {
                  const isBuy = trade.txn_type.toUpperCase().includes("BUY");
                  const isSell = trade.txn_type.toUpperCase().includes("SELL");
                  const isPledge = trade.txn_type.toUpperCase().includes("PLEDGE");

                  return (
                    <TableRow key={`${trade.txn_date}-${trade.person_category}-${idx}`} hover>
                      <TableCell sx={{ fontWeight: 600 }}>{trade.txn_date}</TableCell>
                      <TableCell>{trade.person_category}</TableCell>
                      <TableCell>
                        <Chip
                          label={trade.txn_type.toUpperCase()}
                          size="small"
                          color={isBuy ? "success" : isSell ? "error" : isPledge ? "warning" : "default"}
                          variant="outlined"
                          sx={{ fontWeight: 600, fontSize: "0.7rem" }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        {trade.quantity !== null ? trade.quantity.toLocaleString("en-IN") : "—"}
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>
                        {formatINR(trade.value_inr)}
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="caption" color="text.secondary">
                          {trade.published_at.slice(0, 10)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Regulatory & Method Limitations */}
        <Box sx={{ mt: 2, p: 1.5, bgcolor: "action.hover", borderRadius: 1.5 }}>
          <Typography variant="caption" color="text.secondary" component="div">
            <strong>Method Transparency & Limitations:</strong>
            <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
              {limitations.map((lim, i) => (
                <li key={i}>{lim}</li>
              ))}
            </ul>
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG Sparkline / Trend Line Component
// ---------------------------------------------------------------------------
interface PledgePoint {
  quarter: string;
  pledge: number;
}

function PledgeTrendSvg({ points }: { points: PledgePoint[] }): React.ReactElement {
  const width = 600;
  const height = 80;
  const paddingX = 40;
  const paddingY = 16;

  const maxVal = Math.max(...points.map((p) => p.pledge), 10);
  const minVal = 0;
  const valRange = maxVal - minVal || 1;

  const coords = points.map((p, i) => {
    const x = paddingX + (i / Math.max(points.length - 1, 1)) * (width - 2 * paddingX);
    const y = height - paddingY - ((p.pledge - minVal) / valRange) * (height - 2 * paddingY);
    return { ...p, x, y };
  });

  const pathD = coords.reduce(
    (acc, curr, idx) => (idx === 0 ? `M ${curr.x} ${curr.y}` : `${acc} L ${curr.x} ${curr.y}`),
    ""
  );

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "100%" }}>
      {/* Horizontal guide lines */}
      <line
        x1={paddingX}
        y1={height - paddingY}
        x2={width - paddingX}
        y2={height - paddingY}
        stroke="#888"
        strokeOpacity={0.2}
      />
      <line
        x1={paddingX}
        y1={paddingY}
        x2={width - paddingX}
        y2={paddingY}
        stroke="#888"
        strokeOpacity={0.2}
      />

      {/* Trend line */}
      <path
        d={pathD}
        fill="none"
        stroke="#1976d2"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Points and labels */}
      {coords.map((c, i) => (
        <g key={i}>
          <circle cx={c.x} cy={c.y} r={4} fill="#1976d2" stroke="#fff" strokeWidth={1.5} />
          <text
            x={c.x}
            y={c.y - 7}
            textAnchor="middle"
            fill="currentColor"
            fontSize="10"
            fontWeight="bold"
          >
            {c.pledge.toFixed(1)}%
          </text>
          <text
            x={c.x}
            y={height - 2}
            textAnchor="middle"
            fill="#888"
            fontSize="9"
          >
            {c.quarter.slice(0, 7)}
          </text>
        </g>
      ))}
    </svg>
  );
}
