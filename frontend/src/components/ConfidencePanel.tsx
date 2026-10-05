import { Alert, Card, CardContent, Chip, Grid, LinearProgress, Stack, Typography } from "@mui/material";

import type { ConfidenceFactor } from "../types";

const labels: Record<string, string> = {
  data_coverage: "Data coverage",
  data_freshness: "Data freshness",
  source_agreement: "Source agreement",
  signal_agreement: "Signal agreement",
  model_stability: "Model stability",
  evidence_volume: "Evidence volume",
};

interface ConfidencePanelProps {
  score: number;
  factors: Record<string, ConfidenceFactor>;
  caps?: string[];
}

export function ConfidencePanel({ score, factors, caps = [] }: ConfidencePanelProps) {
  return (
    <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
      <CardContent>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Confidence factors
          </Typography>
          <Chip label={`${score.toFixed(0)} / 100`} color={score >= 70 ? "primary" : "warning"} />
        </Stack>
        {caps.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Confidence cap applied: {caps.join(", ")}
          </Alert>
        )}
        <Grid container spacing={2}>
          {Object.entries(factors).map(([key, factor]) => (
            <Grid key={key} size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                {labels[key] ?? key.replace(/_/g, " ")}: {(factor.value * 100).toFixed(0)}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.max(0, Math.min(100, factor.value * 100))}
                sx={{ my: 1, height: 7, borderRadius: 4 }}
              />
              <Typography variant="caption" color="text.secondary">
                {factor.description}
              </Typography>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
}
