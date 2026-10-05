import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  Divider,
  Grid,
  Stack,
  Typography,
} from "@mui/material";
import type { ResultEnvelope } from "../types";

export interface ExplainPanelProps {
  envelope: ResultEnvelope;
  defaultExpanded?: boolean;
  title?: string;
}

function formatTime(val?: string) {
  if (!val) return "N/A";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(val));
  } catch {
    return val;
  }
}

export function ExplainPanel({
  envelope,
  defaultExpanded = true,
  title = "Model Explanation & Methodology Envelope",
}: ExplainPanelProps) {
  const methodDisplay =
    envelope.method_version ??
    (envelope.method ? `${envelope.method} (${envelope.version ?? "v1"})` : "N/A");

  const fingerprint =
    envelope.input_fingerprint ??
    (envelope.inputs_ref?.fingerprint as string | undefined) ??
    "N/A";

  const lookbackDisplay =
    typeof envelope.lookback === "object" && envelope.lookback !== null
      ? `${envelope.lookback.start ?? ""} to ${envelope.lookback.end ?? ""} (${envelope.lookback.window_size ?? ""}d)`
      : envelope.lookback
        ? String(envelope.lookback)
        : "N/A";

  const confidenceValue =
    typeof envelope.confidence === "number"
      ? envelope.confidence
      : envelope.confidence?.score;

  const confidenceCaps =
    typeof envelope.confidence === "object" ? envelope.confidence.caps : undefined;

  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      sx={{
        border: "1px solid #d0dbe3",
        borderRadius: 2,
        boxShadow: "none",
        "&:before": { display: "none" },
        overflow: "hidden",
      }}
    >
      <AccordionSummary
        aria-controls="explain-panel-content"
        id="explain-panel-header"
        sx={{
          bgcolor: "#f0f4f8",
          minHeight: 48,
          "&.Mui-expanded": { minHeight: 48 },
        }}
      >
        <Stack
          direction="row"
          spacing={1.5}
          sx={{ width: "100%", pr: 2, alignItems: "center" }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 650, color: "#102b3a" }}>
            {title}
          </Typography>
          <Chip
            size="small"
            label={methodDisplay}
            color="primary"
            variant="outlined"
            sx={{ fontWeight: 600, ml: "auto" }}
          />
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ p: 3, bgcolor: "#ffffff" }}>
        <Stack spacing={2.5}>
          <Grid container spacing={2}>
            {envelope.subject && (
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Typography variant="overline" color="text.secondary">
                  Subject
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {envelope.subject}
                </Typography>
              </Grid>
            )}

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Typography variant="overline" color="text.secondary">
                Method & Version
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {methodDisplay}
              </Typography>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Typography variant="overline" color="text.secondary">
                Lookback Window
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {lookbackDisplay}
              </Typography>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Typography variant="overline" color="text.secondary">
                Computed At
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {formatTime(envelope.computed_at ?? envelope.effective_time)}
              </Typography>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 6 }}>
              <Typography variant="overline" color="text.secondary">
                Input Fingerprint
              </Typography>
              <Typography
                variant="caption"
                component="div"
                sx={{
                  fontFamily: "monospace",
                  bgcolor: "#f4f6f8",
                  p: 0.5,
                  borderRadius: 1,
                  wordBreak: "break-all",
                }}
              >
                {fingerprint}
              </Typography>
            </Grid>

            {confidenceValue !== undefined && (
              <Grid size={{ xs: 12, sm: 6, md: 6 }}>
                <Typography variant="overline" color="text.secondary">
                  Model Confidence
                </Typography>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {confidenceValue.toFixed(1)} / 100
                  </Typography>
                  {confidenceCaps && confidenceCaps.length > 0 && (
                    <Chip
                      size="small"
                      color="warning"
                      label={`Capped: ${confidenceCaps.join(", ")}`}
                    />
                  )}
                </Stack>
              </Grid>
            )}
          </Grid>

          {envelope.thresholds && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                Active Thresholds & Rules
              </Typography>
              <Box
                sx={{
                  bgcolor: "#f8fafb",
                  p: 1.5,
                  borderRadius: 1,
                  fontFamily: "monospace",
                  fontSize: "0.8125rem",
                }}
              >
                {typeof envelope.thresholds === "object"
                  ? JSON.stringify(envelope.thresholds, null, 2)
                  : String(envelope.thresholds)}
              </Box>
            </Box>
          )}

          {envelope.limitations && envelope.limitations.length > 0 && (
            <Box>
              <Divider sx={{ my: 1 }} />
              <Typography variant="overline" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                Limitations & Assumptions
              </Typography>
              <Stack spacing={0.75}>
                {envelope.limitations.map((lim, idx) => (
                  <Alert key={idx} severity="info" variant="outlined" sx={{ py: 0.5, px: 1.5 }}>
                    {lim}
                  </Alert>
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}
