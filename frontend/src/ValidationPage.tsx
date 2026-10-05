import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Container,
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

import { useApi } from "./api";
import type { ValidationMetric, ValidationRunDetail, ValidationRunSummary } from "./types";

const DEFAULT_SURVIVORSHIP =
  "Historical validation uses current NIFTY 200 membership only; results contain survivorship bias.";

function value(metric: ValidationMetric) {
  return metric.value === null ? "Unavailable" : metric.value.toFixed(4);
}

export default function ValidationPage() {
  const { data: runPayload = [], isLoading, error } = useApi<ValidationRunSummary[]>(
    "/validation/runs"
  );
  const runs = Array.isArray(runPayload) ? runPayload : [];
  const latestId = runs[0]?.id;
  const { data: detail } = useApi<ValidationRunDetail>(
    `/validation/runs/${latestId ?? "none"}`,
    { enabled: Boolean(latestId) }
  );

  const results = detail?.results ?? [];
  const baselineRows = results.filter(
    (item) => item.metric_key.startsWith("beats_baseline:") && item.period === "all"
  );
  const ablations = results.filter(
    (item) => item.metric_key.startsWith("ablation_delta_spearman:") && item.period === "all"
  );
  const calibration = results.filter(
    (item) => item.metric_key.startsWith("calibration_rank_error:") && item.period === "all"
  );
  const layerBands = results.filter((item) => item.metric_key.startsWith("layer1_exceedance_"));
  const failures = detail?.notes.failures ?? [];
  const limitations = detail?.notes.limitations ?? [];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Stack spacing={1} sx={{ mb: 3 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 800 }}>
          Walk-Forward & Purged Validation
        </Typography>
        <Typography color="text.secondary">
          Honest descriptive-risk validation. Failures are retained and weights are never changed automatically.
        </Typography>
      </Stack>

      <Alert severity="warning" sx={{ mb: 2 }}>
        {detail?.notes.survivorship_warning ?? DEFAULT_SURVIVORSHIP}
      </Alert>
      <Alert severity="info" sx={{ mb: 3 }}>
        Short history and overlapping forward labels limit inference. These results are not a trading
        backtest, forecast, or investment advice.
      </Alert>

      {isLoading && <LinearProgress sx={{ mb: 3 }} />}
      {error && <Alert severity="error">Unable to load validation runs: {error.message}</Alert>}
      {!isLoading && runs.length === 0 && (
        <Alert severity="warning">No validation run exists. Score meaning remains unproven.</Alert>
      )}

      {detail && (
        <Stack spacing={3}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                <Chip label={detail.status.toUpperCase()} color={failures.length ? "error" : "success"} />
                <Chip label={detail.period} variant="outlined" />
                <Chip label={detail.notes.method_version ?? detail.kind} variant="outlined" />
                <Typography variant="body2" color="text.secondary">
                  {detail.notes.labelled_observation_count ?? 0} labelled observations from {detail.notes.evaluation_score_run_count ?? 0} evaluation runs in {detail.notes.walk_forward_fold_count ?? 0} time-ordered folds
                </Typography>
              </Stack>
            </CardContent>
          </Card>

          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Failures
            </Typography>
            {failures.length === 0 ? (
              <Alert severity="success">No recorded failure for this run.</Alert>
            ) : (
              <Stack spacing={1}>
                {failures.map((failure) => <Alert severity="error" key={failure}>{failure}</Alert>)}
              </Stack>
            )}
          </Box>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Baseline comparison</Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead><TableRow><TableCell>Target</TableCell><TableCell>Baseline</TableCell><TableCell>Baseline correlation</TableCell><TableCell>Outcome</TableCell><TableCell>N periods</TableCell></TableRow></TableHead>
                  <TableBody>
                    {baselineRows.map((row) => (
                      <TableRow key={`${row.metric_key}-${row.component_key}`}>
                        <TableCell>{row.metric_key.replace("beats_baseline:", "")}</TableCell>
                        <TableCell>{row.component_key}</TableCell>
                        <TableCell>{row.baseline_value?.toFixed(4) ?? "Unavailable"}</TableCell>
                        <TableCell><Chip size="small" color={row.value === 1 ? "success" : "error"} label={row.value === 1 ? "Beat" : "Did not beat"} /></TableCell>
                        <TableCell>{row.n}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Ablation changes</Typography>
              <Stack spacing={1.5}>
                {ablations.map((row) => {
                  const delta = row.value ?? 0;
                  return <Box key={row.component_key}>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <Typography variant="body2">
                        {row.component_key} · {row.metric_key.replace("ablation_delta_spearman:", "")}
                      </Typography>
                      <Typography variant="body2" color={delta > 0 ? "error.main" : "success.main"}>{delta >= 0 ? "+" : ""}{value(row)}</Typography>
                    </Stack>
                    <LinearProgress variant="determinate" color={delta > 0 ? "error" : "success"} value={Math.min(100, Math.abs(delta) * 500)} />
                  </Box>;
                })}
                {ablations.length === 0 && <Alert severity="info">No completed ablation evidence is available.</Alert>}
              </Stack>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Confidence calibration</Typography>
              <Table size="small">
                <TableHead><TableRow><TableCell>Target</TableCell><TableCell>Confidence bin</TableCell><TableCell>Rank error</TableCell><TableCell>N</TableCell></TableRow></TableHead>
                <TableBody>
                  {calibration.map((row) => (
                    <TableRow key={`${row.metric_key}-${row.component_key}`}>
                      <TableCell>
                        {row.metric_key.replace("calibration_rank_error:", "")}
                      </TableCell>
                      <TableCell>{row.component_key}</TableCell>
                      <TableCell>
                        <Stack spacing={0.5}>
                          <Typography variant="body2">{value(row)}</Typography>
                          <LinearProgress
                            aria-label={`${row.component_key} calibration rank error`}
                            color="warning"
                            variant="determinate"
                            value={Math.min(100, Math.max(0, (row.value ?? 0) * 100))}
                          />
                        </Stack>
                      </TableCell>
                      <TableCell>{row.n}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>Layer 1 empirical bands</Typography>
              <Table size="small">
                <TableHead><TableRow><TableCell>Horizon</TableCell><TableCell>Band</TableCell><TableCell>Observed exceedance</TableCell><TableCell>Normal reference</TableCell><TableCell>N</TableCell></TableRow></TableHead>
                <TableBody>{layerBands.map((row) => <TableRow key={`${row.metric_key}-${row.component_key}`}><TableCell>{row.component_key}</TableCell><TableCell>{row.metric_key}</TableCell><TableCell>{value(row)}</TableCell><TableCell>{row.baseline_value?.toFixed(4) ?? "TBD"}</TableCell><TableCell>{row.n}</TableCell></TableRow>)}</TableBody>
              </Table>
            </CardContent>
          </Card>

          <Stack spacing={1}>
            {[...limitations, detail.notes.multiple_testing].filter(Boolean).map((limitation) => <Alert severity="info" key={limitation}>{limitation}</Alert>)}
          </Stack>
        </Stack>
      )}
    </Container>
  );
}
