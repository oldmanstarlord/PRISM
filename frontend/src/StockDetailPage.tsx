import { useMemo } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Breadcrumbs,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Link,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import ShieldIcon from "@mui/icons-material/Shield";

import { useApi } from "./api";
import type { BreakdownItem, StockEventsResponse, StockRiskEnvelope } from "./types";
import { BreakdownBars } from "./components/BreakdownBars";
import { ExplainPanel } from "./components/ExplainPanel";
import { FreshnessBadge } from "./components/FreshnessBadge";
import { FundamentalsPanel } from "./components/FundamentalsPanel";
import { GovernancePanel } from "./components/GovernancePanel";
import { MacroPanel } from "./components/MacroPanel";
import { NewsPolicyPanel } from "./components/NewsPolicyPanel";
import { Timeline } from "./components/Timeline";

export default function StockDetailPage() {
  const { symbol = "" } = useParams<{ symbol: string }>();
  const upperSymbol = symbol.toUpperCase();

  const { data: envelope, isLoading, error } = useApi<StockRiskEnvelope>(
    `/stocks/${encodeURIComponent(upperSymbol)}/risk/latest`
  );

  const { data: history = [] } = useApi<
    Array<{
      as_of_date: string;
      total_score: number;
      confidence: number;
      data_coverage: number;
    }>
  >(`/stocks/${encodeURIComponent(upperSymbol)}/risk/history?limit=10`);

  const { data: stockEvents } = useApi<StockEventsResponse>(
    `/stocks/${encodeURIComponent(upperSymbol)}/events`
  );

  // Transform generic components array from API into BreakdownItems (D2, D5)
  const breakdownItems: BreakdownItem[] = useMemo(() => {
    if (!envelope?.components) return [];
    return envelope.components.map((c) => {
      const isMissingOrInactive = c.status === "missing" || c.status === "inactive";
      return {
        key: c.component_id,
        dimension: c.dimension,
        display_name: c.name,
        percentile: c.percentile_rank !== null ? c.percentile_rank : undefined,
        risk_points: c.points !== null ? c.points : undefined,
        weight: 1.0,
        status: isMissingOrInactive ? "not yet available" : c.status,
        data_age_days: c.data_age_days !== null ? c.data_age_days : undefined,
        reason:
          c.raw_value !== null
            ? `Raw: ${c.raw_value} (${c.direction.replace(/_/g, " ")})`
            : "Not yet available in current data release.",
      };
    });
  }, [envelope]);

  if (isLoading) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "60vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !envelope) {
    return (
      <Box sx={{ maxWidth: 1200, mx: "auto", px: 3, py: 4 }}>
        <Button
          component={RouterLink}
          to="/stocks"
          startIcon={<ArrowBackIcon />}
          sx={{ mb: 2 }}
        >
          Back to Stock Screener
        </Button>
        <Alert severity="error">
          Failed to load risk result for {upperSymbol}: {error?.message || "Not found"}
        </Alert>
      </Box>
    );
  }

  const score = envelope.total_score;
  const confidenceScore =
    typeof envelope.confidence === "number"
      ? envelope.confidence
      : envelope.confidence?.score ?? 50.0;
  const covPct = Math.round((envelope.data_coverage || 0) * 100);

  const riskColor =
    score >= 70 ? "error" : score >= 45 ? "warning" : "success";

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, sm: 3 }, py: 3 }}>
      {/* Navigation Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link component={RouterLink} to="/stocks" color="inherit">
          Stocks Screener
        </Link>
        <Typography color="text.primary">{upperSymbol}</Typography>
      </Breadcrumbs>

      {/* Header and Action Links */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        sx={{
          justifyContent: "space-between",
          alignItems: { sm: "center" },
          mb: 3,
        }}
      >
        <Box>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <ShieldIcon color="primary" sx={{ fontSize: 36 }} />
            <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>
              {envelope.symbol}
            </Typography>
            <Chip label={envelope.industry} size="small" variant="outlined" />
          </Stack>
          <Typography variant="subtitle1" color="text.secondary">
            {envelope.company_name}
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <FreshnessBadge
            asOf={envelope.effective_time || envelope.computed_at}
            label={`As of: ${envelope.effective_time || "N/A"}`}
          />
          <Button
            component={RouterLink}
            to={`/companies/${upperSymbol}`}
            variant="outlined"
            startIcon={<ShowChartIcon />}
          >
            Layer 1 Peer Divergence
          </Button>
        </Stack>
      </Stack>

      {/* Top Gauge Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* Risk Score Gauge */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2, height: "100%", borderRadius: 2 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 700 }}>
                Synthesized Multi-Dimensional Risk Score
              </Typography>
              <Stack direction="row" spacing={2} sx={{ alignItems: "baseline", mt: 1, mb: 2 }}>
                <Typography variant="h2" sx={{ fontWeight: 800 }}>
                  {score.toFixed(1)}
                </Typography>
                <Typography variant="h5" color="text.secondary">
                  / 100
                </Typography>
                <Chip
                  label={score >= 70 ? "Elevated Risk" : score >= 45 ? "Moderate Risk" : "Low Risk"}
                  color={riskColor}
                  sx={{ fontWeight: 700 }}
                />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={score}
                color={riskColor}
                sx={{ height: 10, borderRadius: 5, mb: 2 }}
              />
              <Typography variant="caption" color="text.secondary">
                Point score synthesized across 8 risk dimensions using empirical peer rankings.
                Renormalised for available dimension weights.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Confidence Gauge */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2, height: "100%", borderRadius: 2 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 700 }}>
                Confidence & Evidence Quality
              </Typography>
              <Stack direction="row" spacing={2} sx={{ alignItems: "baseline", mt: 1, mb: 2 }}>
                <Typography variant="h2" sx={{ fontWeight: 800 }}>
                  {confidenceScore.toFixed(0)}%
                </Typography>
                <Chip
                  label={
                    confidenceScore >= 70
                      ? "High Confidence"
                      : confidenceScore >= 50
                      ? "Moderate Confidence"
                      : "Low / Capped Confidence"
                  }
                  color={
                    confidenceScore >= 70 ? "primary" : confidenceScore >= 50 ? "warning" : "error"
                  }
                  sx={{ fontWeight: 700 }}
                />
                <Chip
                  label={`${covPct}% Coverage`}
                  variant="outlined"
                  size="small"
                  sx={{ fontWeight: 600 }}
                />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={confidenceScore}
                color={confidenceScore >= 70 ? "primary" : "warning"}
                sx={{ height: 10, borderRadius: 5, mb: 2 }}
              />
              <Typography variant="caption" color="text.secondary">
                Synthesized across 6 factors: Coverage, Calendar Freshness, Redundant Source
                Cross-Checks, Signal Concordance, and Model Stability.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Top Risk Drivers / Reasons */}
      {envelope.component_contributions && envelope.component_contributions.length > 0 && (
        <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Top Risk Drivers & Explanations
            </Typography>
            <Grid container spacing={2}>
              {envelope.component_contributions.map((reason, idx) => (
                <Grid size={{ xs: 12, md: 4 }} key={reason.component_id || idx}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      bgcolor: "action.hover",
                      borderRadius: 2,
                      height: "100%",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                    }}
                  >
                    <Box>
                      <Stack direction="row" sx={{ justifyContent: "space-between", mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          #{idx + 1} {reason.name}
                        </Typography>
                        <Chip
                          label={`+${reason.contribution.toFixed(1)} pts`}
                          size="small"
                          color="warning"
                          sx={{ fontWeight: 700 }}
                        />
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {reason.text}
                      </Typography>
                    </Box>
                    <Typography
                      variant="caption"
                      color="primary.main"
                      sx={{ mt: 1.5, fontWeight: 600 }}
                    >
                      Dimension: {reason.dimension.toUpperCase()}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* BreakdownBars: Driven purely by the API array (D5) */}
      <Box sx={{ mb: 3 }}>
        <BreakdownBars
          items={breakdownItems}
          title="Dynamic Component Breakdown & Directional Rank"
        />
      </Box>

      {/* Fundamentals Panel: Quarterly table, TTM metrics, and peer percentiles (Step 7) */}
      <FundamentalsPanel symbol={upperSymbol} />

      {/* Governance Panel: Shareholding pattern, pledge trend, insider trades (Step 8) */}
      <GovernancePanel symbol={upperSymbol} />

      {/* Macroeconomic Sensitivity Panel (Step 9) */}
      <MacroPanel symbol={upperSymbol} />

      {/* Corporate Announcements & Events Timeline (Step 10, Dimension: Events) */}
      {stockEvents?.events && stockEvents.events.length > 0 && (
        <Timeline
          events={stockEvents.events}
          symbol={upperSymbol}
          title="Corporate Announcements & Explainable Events (Dimension: Events)"
        />
      )}

      {/* Policy Press Releases & Sector Headwinds (Step 11, Dimension: Macro/Events) */}
      <NewsPolicyPanel symbol={upperSymbol} />

      {/* History Trajectory Card */}
      {history.length > 1 && (
        <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Recent Score Trajectory (Trailing Calculations)
            </Typography>
            <Stack direction="row" spacing={2} sx={{ overflowX: "auto", pb: 1 }}>
              {history.map((pt) => (
                <Paper
                  key={pt.as_of_date}
                  variant="outlined"
                  sx={{ p: 1.5, minWidth: 120, textAlign: "center", borderRadius: 2 }}
                >
                  <Typography variant="caption" color="text.secondary">
                    {pt.as_of_date}
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700, my: 0.5 }}>
                    {pt.total_score.toFixed(1)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Conf: {pt.confidence.toFixed(0)}%
                  </Typography>
                </Paper>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* Model Explanation & Result Envelope (D3) */}
      <ExplainPanel
        envelope={envelope}
        title="Stock Risk Model Envelope & Method Transparency"
        defaultExpanded={true}
      />
    </Box>
  );
}
