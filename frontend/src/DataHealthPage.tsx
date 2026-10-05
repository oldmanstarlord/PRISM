import {
  Alert,
  Box,
  CircularProgress,
  Container,
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
import { useApi } from "./api";
import { FreshnessBadge, StatusChip } from "./components";
import type {
  CrosscheckLatestResponse,
  FreshnessResponse,
  OperationsFreshness,
  OperationsPipelineRun,
  QualitySummaryResponse,
} from "./types";

export default function DataHealthPage() {
  const {
    data: quality,
    isLoading: loadingQuality,
    error: qualityError,
  } = useApi<QualitySummaryResponse>("/data/quality/summary");

  const {
    data: freshness,
    isLoading: loadingFreshness,
    error: freshnessError,
  } = useApi<FreshnessResponse>("/data/freshness");

  const {
    data: crosscheck,
    isLoading: loadingCrosscheck,
    error: crosscheckError,
  } = useApi<CrosscheckLatestResponse>("/data/crosscheck/latest");
  const { data: sourceFreshness = [] } = useApi<OperationsFreshness[]>("/ops/freshness");
  const { data: pipelineRuns = [] } = useApi<OperationsPipelineRun[]>("/ops/pipeline-runs");

  const isLoading = loadingQuality || loadingFreshness || loadingCrosscheck;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={4}>
        <Box>
          <Typography variant="h4" component="h2" sx={{ fontWeight: 700, color: "#102b3a" }}>
            Data Health & Quality Surveillance
          </Typography>
          <Typography color="text.secondary">
            Continuous point-in-time auditing, freshness tracking, and multi-source price cross-checks.
          </Typography>
        </Box>

        {isLoading && (
          <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        )}

        <Box>
          <Typography variant="h6" sx={{ fontWeight: 650, mb: 1.5 }}>
            Source traffic lights
          </Typography>
          <Grid container spacing={2}>
            {sourceFreshness.map((item) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={item.source_key}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                    <Typography sx={{ fontWeight: 700 }}>{item.source_key}</Typography>
                    <StatusChip status={item.status} />
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    Last success: {item.last_success_at ? new Date(item.last_success_at).toLocaleString() : "Never"}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </Box>

        <Box>
          <Typography variant="h6" sx={{ fontWeight: 650, mb: 1.5 }}>Latest pipeline runs</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small"><TableHead><TableRow><TableCell>Workflow</TableCell><TableCell>Status</TableCell><TableCell>Started</TableCell><TableCell>Error</TableCell></TableRow></TableHead>
              <TableBody>{pipelineRuns.slice(0, 20).map((run) => <TableRow key={run.id}><TableCell>{run.workflow}</TableCell><TableCell><StatusChip status={run.status} /></TableCell><TableCell>{new Date(run.started_at).toLocaleString()}</TableCell><TableCell>{run.error_summary ?? "—"}</TableCell></TableRow>)}</TableBody>
            </Table>
          </TableContainer>
        </Box>

        {(qualityError || freshnessError || crosscheckError) && (
          <Alert severity="warning">
            Some data quality feeds are temporarily unavailable.
          </Alert>
        )}

        {/* 1. Freshness Overview */}
        {freshness && (
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 650, mb: 1.5 }}>
              Dataset Freshness & Timestamps
            </Typography>
            <Grid container spacing={2}>
              {freshness.datasets.map((item) => (
                <Grid size={{ xs: 12, sm: 6, md: 4 }} key={item.dataset}>
                  <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                    <Stack spacing={1}>
                      <Stack
                        direction="row"
                        sx={{ justifyContent: "space-between", alignItems: "center" }}
                      >
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "capitalize" }}>
                          {item.dataset.replace(/_/g, " ")}
                        </Typography>
                        <FreshnessBadge
                          dataThroughDate={item.latest_trade_date}
                          ageDays={item.age_days}
                        />
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        Latest Trade Date: <strong>{item.latest_trade_date ?? "N/A"}</strong>
                      </Typography>
                      {item.latest_ingested_at && (
                        <Typography variant="caption" color="text.secondary">
                          Ingested: {new Date(item.latest_ingested_at).toLocaleString()}
                        </Typography>
                      )}
                    </Stack>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* 2. Quality Summary & Counts */}
        {quality && (
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 650, mb: 1.5 }}>
              Data Coverage & Anomaly Counters
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                  <Typography variant="overline" color="text.secondary">
                    Active Securities
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    {quality.datasets.securities.active_count}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Universe: NIFTY 200 constituents
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                  <Typography variant="overline" color="text.secondary">
                    Price Observations
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    {quality.datasets.raw_prices.total_records.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Adjusted: {quality.datasets.adjusted_prices.total_records.toLocaleString()}
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                  <Typography variant="overline" color="text.secondary">
                    Derived Market Stats
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    {quality.datasets.derived_market_stats.total_records.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Traded value, ADV-20 & MCap
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                  <Typography variant="overline" color="text.secondary">
                    Liquidity Anomalies
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                    <Typography variant="h5" sx={{ fontWeight: 700, color: "warning.main" }}>
                      {quality.datasets.derived_market_stats.thin_trading_flagged}
                    </Typography>
                    <Typography variant="caption" sx={{ alignSelf: "center", color: "text.secondary" }}>
                      thin trading / {quality.datasets.derived_market_stats.zero_volume_flagged} zero-vol
                    </Typography>
                  </Stack>
                </Paper>
              </Grid>
            </Grid>

            <Paper variant="outlined" sx={{ p: 2.5, mt: 2, borderRadius: 2, bgcolor: "#f8fafb" }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                Quality Enforcement Policy
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {quality.quality_policy}
              </Typography>
            </Paper>
          </Box>
        )}

        {/* 3. Cross-Check Surveillance */}
        {crosscheck && (
          <Box>
            <Stack
              direction="row"
              sx={{ justifyContent: "space-between", alignItems: "center", mb: 1.5 }}
            >
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 650 }}>
                  Dual-Feed Price Cross-Check Surveillance
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Comparing primary feed ({crosscheck.sources.source_a}) against secondary feed ({crosscheck.sources.source_b}).
                </Typography>
              </Box>
              <StatusChip
                status={crosscheck.mismatch_count === 0 ? "match" : "warning"}
                label={`Mismatch rate: ${(crosscheck.mismatch_rate * 100).toFixed(2)}%`}
                size="medium"
              />
            </Stack>

            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
              <Table size="small" aria-label="price crosscheck table">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Trade Date</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Feed A Close</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Feed B Close</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Rel Diff %</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {crosscheck.worst_discrepancies.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} align="center" sx={{ py: 3, color: "text.secondary" }}>
                        No price discrepancies found in sampled check. All feeds agree within tolerance.
                      </TableCell>
                    </TableRow>
                  ) : (
                    crosscheck.worst_discrepancies.map((d, idx) => (
                      <TableRow key={`${d.symbol}-${d.trade_date}-${idx}`} hover>
                        <TableCell sx={{ fontWeight: 700 }}>{d.symbol}</TableCell>
                        <TableCell>{d.trade_date}</TableCell>
                        <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                          {d.close_a.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                          {d.close_b.toFixed(2)}
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontVariantNumeric: "tabular-nums",
                            fontWeight: 700,
                            color: d.rel_diff > 0.01 ? "error.main" : "warning.main",
                          }}
                        >
                          {(d.rel_diff * 100).toFixed(3)}%
                        </TableCell>
                        <TableCell>
                          <StatusChip status={d.status} />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </Stack>
    </Container>
  );
}
