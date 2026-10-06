import { useState, type MouseEvent } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  Button,
  IconButton,
  Popover,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

import { useExplanation } from "../hooks/useExplain";
import type { ExplanationEvidence, ExplanationPayload } from "../types";

interface ExplainDrawerProps {
  open: boolean;
  symbol?: string;
  componentKey?: string;
  path?: string;
  onClose: () => void;
  payload?: ExplanationPayload;
}

export function ExplainDrawer({
  open,
  symbol,
  componentKey,
  path,
  onClose,
  payload: suppliedPayload,
}: ExplainDrawerProps) {
  const requestPath = path ?? (
    symbol && componentKey
      ? `/explain/component/${encodeURIComponent(symbol)}/${encodeURIComponent(componentKey)}`
      : ""
  );
  const query = useExplanation(requestPath, open && suppliedPayload === undefined);
  const payload = suppliedPayload ?? query.data;
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<ExplanationEvidence | null>(null);

  const openEvidence = (event: MouseEvent<HTMLElement>, item: ExplanationEvidence) => {
    setAnchor(event.currentTarget);
    setSelectedEvidence(item);
  };

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: { xs: 360, sm: 560 }, p: 3 }} role="dialog" aria-label="Explanation">
        <Stack spacing={2.5}>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
            <Box>
              <Typography variant="overline">Evidence-bound explanation</Typography>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {payload?.headline ?? "Loading explanation"}
              </Typography>
            </Box>
            <IconButton onClick={onClose} aria-label="Close explanation"><CloseIcon /></IconButton>
          </Stack>

          {query.isLoading && !payload && <CircularProgress />}
          {query.error && !payload && <Alert severity="error">{query.error.message}</Alert>}

          {payload && (
            <>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                <Chip label={`Confidence: ${payload.confidence.level}`} color={payload.confidence.level === "high" ? "success" : payload.confidence.level === "low" ? "warning" : "info"} />
                <Chip label={payload.data_age.days === null ? "Data age unavailable" : `Data age: ${payload.data_age.days}d`} variant="outlined" />
                <Chip label={`Template ${payload.template_version}`} variant="outlined" />
              </Stack>

              <Stack spacing={1}>
                {payload.summary_points.map((sentence, index) => (
                  <Typography key={`${sentence.text}-${index}`} variant="body1">{sentence.text}</Typography>
                ))}
              </Stack>

              {payload.sections.map((section) => (
                <Box key={section.key} data-section-key={section.key}>
                  <Typography variant="h6" sx={{ fontWeight: 650, mb: 1 }}>{section.title}</Typography>
                  <Stack spacing={1}>
                    {section.sentences.map((sentence, index) => (
                      <Typography key={`${sentence.text}-${index}`} variant="body2">{sentence.text}</Typography>
                    ))}
                  </Stack>
                  {section.chart_spec && <ChartSpec spec={section.chart_spec} />}
                </Box>
              ))}

              <Divider />
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Evidence</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                  {payload.evidence.map((item) => (
                    <Chip key={item.evidence_id} label={`${item.label}: ${String(item.value ?? "N/A")}`} onClick={(event) => openEvidence(event, item)} variant="outlined" />
                  ))}
                </Stack>
              </Box>

              <Alert severity="warning">
                <Typography variant="subtitle2">Limitations</Typography>
                {payload.limitations.map((item) => <Typography key={item} variant="body2">{item}</Typography>)}
              </Alert>
              <Alert severity="info">{payload.disclaimer}</Alert>
            </>
          )}
        </Stack>
      </Box>
      <Popover
        open={Boolean(anchor && selectedEvidence)}
        anchorEl={anchor}
        onClose={() => { setAnchor(null); setSelectedEvidence(null); }}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        {selectedEvidence && (
          <Stack spacing={0.5} sx={{ p: 2, maxWidth: 360 }}>
            <Typography variant="subtitle2">{selectedEvidence.label}</Typography>
            <Typography variant="body2">Source: {selectedEvidence.source_table} / {selectedEvidence.source_ref}</Typography>
            <Typography variant="body2">Window: {selectedEvidence.window ?? "Not applicable"}</Typography>
            <Typography variant="body2">As of: {selectedEvidence.as_of}</Typography>
          </Stack>
        )}
      </Popover>
    </Drawer>
  );
}

function ChartSpec({ spec }: { spec: Record<string, unknown> }) {
  const [descending, setDescending] = useState(true);
  const type = String(spec.type ?? "unknown");
  if (type === "affected_stocks_table") {
    const sourceRows = Array.isArray(spec.rows) ? spec.rows : [];
    const rows = sourceRows
      .filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null)
      .sort((left, right) => (Number(right.exposure_score) - Number(left.exposure_score)) * (descending ? 1 : -1));
    return (
      <Box sx={{ overflowX: "auto", mt: 1 }}>
        <Button size="small" onClick={() => setDescending((value) => !value)}>
          Exposure {descending ? "highest first" : "lowest first"}
        </Button>
        <Table size="small">
          <TableHead><TableRow><TableCell>Stock / industry</TableCell><TableCell>Path</TableCell><TableCell>Direction</TableCell><TableCell>Exposure</TableCell><TableCell>Confidence</TableCell></TableRow></TableHead>
          <TableBody>{rows.map((row, index) => {
            const paths = Array.isArray(row.paths) ? row.paths : [];
            return <TableRow key={`${String(row.symbol ?? row.industry)}-${index}`}>
              <TableCell>{row.symbol ? <Button size="small" href={`/stocks/${encodeURIComponent(String(row.symbol))}`}>{String(row.symbol)}</Button> : String(row.industry)}</TableCell>
              <TableCell>{paths.map((path) => typeof path === "object" && path !== null ? String((path as Record<string, unknown>).path_type) : "").filter(Boolean).join(", ")}</TableCell>
              <TableCell>{String(row.direction)}</TableCell>
              <TableCell>{Number(row.exposure_score).toFixed(3)} ({String(row.exposure_band)})</TableCell>
              <TableCell>{Number(row.confidence).toFixed(2)}</TableCell>
            </TableRow>;
          })}</TableBody>
        </Table>
      </Box>
    );
  }
  if (type === "action_link") {
    return (
      <Button component="a" href={String(spec.href ?? "#")} sx={{ mt: 1 }}>
        {String(spec.label ?? "Open")}
      </Button>
    );
  }
  const rawPoints = Array.isArray(spec.points) ? spec.points : [];
  const points = rawPoints.filter(
    (point): point is Record<string, unknown> => typeof point === "object" && point !== null,
  );
  if (type === "rolling_correlation") {
    const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
    return (
      <Box data-chart-type={type} sx={{ mt: 1, p: 1.5, bgcolor: "grey.50", borderRadius: 1 }}>
        <Typography variant="caption">
          Rolling {String(spec.window ?? "")}‑day correlation · {values.length} points
        </Typography>
        <Typography variant="body2">
          {values.length ? `${Math.min(...values).toFixed(2)} to ${Math.max(...values).toFixed(2)}` : "No chart points"}
        </Typography>
      </Box>
    );
  }
  if (type === "returns_scatter") {
    return (
      <Box data-chart-type={type} sx={{ mt: 1, p: 1.5, bgcolor: "grey.50", borderRadius: 1 }}>
        <Typography variant="caption">
          Returns scatter: {String(spec.x_symbol)} vs {String(spec.y_symbol)} · {points.length} points
        </Typography>
      </Box>
    );
  }
  if (type === "stock_sector_rebased") {
    const markers = Array.isArray(spec.event_markers) ? spec.event_markers.length : 0;
    return (
      <Box data-chart-type={type} sx={{ mt: 1, p: 1.5, bgcolor: "grey.50", borderRadius: 1 }}>
        <Typography variant="caption">
          Stock and peer median rebased to {String(spec.indexed_to ?? 100)} · {points.length} points
        </Typography>
        <Typography variant="body2">
          Residual separation shaded · {markers} stored event markers
        </Typography>
      </Box>
    );
  }
  return null;
}
