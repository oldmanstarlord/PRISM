import React from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
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
import { useApi } from "../api";
import type { StockFundamentalsResponse } from "../types";
import { FreshnessBadge } from "./FreshnessBadge";

interface FundamentalsPanelProps {
  symbol: string;
}

export function FundamentalsPanel({ symbol }: FundamentalsPanelProps): React.ReactElement {
  const { data, isLoading, error } = useApi<StockFundamentalsResponse>(
    `/stocks/${encodeURIComponent(symbol)}/fundamentals`
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
        Fundamental results data not yet available for {symbol}.
      </Alert>
    );
  }

  const formatCr = (val: number | null | undefined): string => {
    if (val === null || val === undefined) return "—";
    const cr = val / 10000000;
    return `₹${cr.toFixed(1)} Cr`;
  };

  const formatMetricVal = (key: string, val: number | null | undefined): string => {
    if (val === null || val === undefined) return "—";
    if (key.includes("growth") || key.includes("margin") || key.includes("trend")) {
      return `${(val * 100).toFixed(1)}%`;
    }
    if (key.includes("volatility")) {
      return val.toFixed(2);
    }
    return `${val.toFixed(2)}x`;
  };

  const getMetricTitle = (key: string): string => {
    const map: Record<string, string> = {
      debt_to_equity: "Debt to Equity (Leverage)",
      asset_to_equity: "Assets to Equity (Leverage)",
      interest_coverage: "Interest Coverage (Solvency)",
      ttm_profit_growth: "TTM YoY Profit Growth",
      profit_growth: "TTM Profit Growth",
      profit_volatility: "Quarterly PAT Volatility",
      cash_flow_quality: "Cash Flow Quality (CFO / PAT)",
      margin_trend: "Operating Margin Trend",
      gross_npa_pct: "Gross NPA %",
      net_npa_pct: "Net NPA %",
      capital_adequacy_ratio: "Capital Adequacy Ratio (CAR)",
    };
    return map[key] || key.replace(/_/g, " ").toUpperCase();
  };

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
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              Fundamental Risk Analysis & Financial Disclosures
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Point-in-time quarterly statements, Trailing-Twelve-Month (TTM) ratios, and peer percentiles.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            {data.data_age_days !== undefined && data.data_age_days !== null && (
              <FreshnessBadge ageDays={data.data_age_days} />
            )}
            <Chip
              label={data.source_note.includes("Yahoo") ? "Yahoo Unofficial" : "Official Exchange"}
              size="small"
              color={data.source_note.includes("Yahoo") ? "warning" : "success"}
              variant="outlined"
              sx={{ fontWeight: 600 }}
            />
          </Stack>
        </Stack>

        {/* Source and Transparency Notice */}
        <Alert severity="info" sx={{ mb: 3, borderRadius: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {data.source_note}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Industry Peer Group: <strong>{data.industry}</strong>. Ratios adhere to strict point-in-time publication lag constraints.
          </Typography>
        </Alert>

        {/* Derived TTM Metrics & Peer Percentile Bars */}
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Derived Ratios & Industry Peer Percentiles
        </Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {data.metrics.map((m) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={m.metric_key}>
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  borderRadius: 2,
                  bgcolor: "action.hover",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <Box>
                  <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                      {getMetricTitle(m.metric_key)}
                    </Typography>
                    <Chip
                      label={m.status}
                      size="small"
                      color={
                        m.status === "computed"
                          ? "primary"
                          : m.status === "flagged"
                          ? "error"
                          : "default"
                      }
                      sx={{ height: 20, fontSize: "0.7rem", fontWeight: 700 }}
                    />
                  </Stack>
                  <Typography variant="h5" sx={{ fontWeight: 700, my: 0.5 }}>
                    {formatMetricVal(m.metric_key, m.value)}
                  </Typography>
                </Box>

                <Box sx={{ mt: 1.5 }}>
                  <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Peer Percentile
                    </Typography>
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      {m.peer_percentile !== null && m.peer_percentile !== undefined
                        ? `${m.peer_percentile.toFixed(0)}th pct`
                        : "N/A (peer size < 5)"}
                    </Typography>
                  </Stack>
                  <LinearProgress
                    variant="determinate"
                    value={m.peer_percentile ?? 0}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>

        {/* Quarterly Statements Table */}
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Published Quarterly Periods ({data.periods.length} quarters)
        </Typography>
        {data.periods.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            No quarterly disclosures recorded yet for this security.
          </Typography>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
            <Table size="small">
              <TableHead sx={{ bgcolor: "action.hover" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Period End</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Basis</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Revenue</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Operating Profit</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>PAT</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Total Debt</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Total Equity</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>CFO</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Published (Effective)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.periods.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell sx={{ fontWeight: 600 }}>{p.period_end}</TableCell>
                    <TableCell>
                      <Chip label={p.basis} size="small" variant="outlined" sx={{ fontSize: "0.75rem" }} />
                    </TableCell>
                    <TableCell align="right">{formatCr(p.revenue)}</TableCell>
                    <TableCell align="right">{formatCr(p.operating_profit)}</TableCell>
                    <TableCell align="right">{formatCr(p.pat)}</TableCell>
                    <TableCell align="right">{formatCr(p.total_debt)}</TableCell>
                    <TableCell align="right">{formatCr(p.total_equity)}</TableCell>
                    <TableCell align="right">{formatCr(p.cash_from_operations)}</TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                        <Typography variant="caption">{p.published_at.slice(0, 10)}</Typography>
                        {p.published_at_method === "estimated" && (
                          <Chip label="est" size="small" color="warning" sx={{ height: 18, fontSize: "0.65rem" }} />
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Limitations Transparency */}
        {data.limitations && data.limitations.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
              Methodology & Limitations:
            </Typography>
            <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: "0.8rem", color: "#64748b" }}>
              {data.limitations.map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
