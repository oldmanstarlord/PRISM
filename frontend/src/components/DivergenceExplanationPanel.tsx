import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  Typography,
} from "@mui/material";

import { useExplanation } from "../hooks/useExplain";
import type { ExplanationSentence } from "../types";
import { ExplainDrawer } from "./ExplainDrawer";

export function DivergenceExplanationPanel({ symbol }: { symbol: string }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const path = `/explain/divergence/${encodeURIComponent(symbol)}`;
  const query = useExplanation(path, Boolean(symbol));

  if (query.isLoading) {
    return <CircularProgress size={24} aria-label="Loading divergence explanation" />;
  }
  if (query.error) {
    return <Alert severity="info">Divergence explanation unavailable: {query.error.message}</Alert>;
  }
  if (!query.data) return null;
  const payload = query.data;
  if (!Array.isArray(payload.evidence) || !Array.isArray(payload.sections)) {
    return <Alert severity="info">Divergence explanation payload is unavailable.</Alert>;
  }
  const evidence = Object.fromEntries(payload.evidence.map((item) => [item.evidence_id, item]));
  const sector = payload.sections.find((item) => item.key === "sector_trend");
  const stock = payload.sections.find((item) => item.key === "stock_trend");
  const flagged = payload.sections.find((item) => item.key === "why_flagged");
  const risk = payload.sections.find((item) => item.key === "risk_reading");
  const contribution = payload.sections.find((item) => item.key === "contribution");

  return (
    <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
      <CardContent>
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 1 }}>
          <Box>
            <Typography variant="overline">Layer 1 evidence-bound explanation</Typography>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>{payload.headline}</Typography>
          </Box>
          <Button onClick={() => setDrawerOpen(true)}>Inspect evidence</Button>
        </Stack>

        <Grid container spacing={2} sx={{ mt: 1 }}>
          <TrendCard
            title={sector?.title ?? "Peer trend"}
            trend={String(evidence.sector_trend_20?.value ?? "unavailable")}
            value={evidence.sector_return_20?.value}
          />
          <TrendCard
            title={stock?.title ?? "Stock trend"}
            trend={String(evidence.stock_trend_20?.value ?? "unavailable")}
            value={evidence.stock_return_20?.value}
          />
        </Grid>

        {sector?.chart_spec && <RebasedChart spec={sector.chart_spec} />}

        <Grid container spacing={2} sx={{ mt: 1 }}>
          <SentenceCard title={flagged?.title ?? "Why flagged"} sentences={flagged?.sentences ?? []} />
          <SentenceCard title={risk?.title ?? "Is it risky?"} sentences={risk?.sentences ?? []} />
          <SentenceCard title={contribution?.title ?? "How much it matters"} sentences={contribution?.sentences ?? []} />
        </Grid>

        <Alert severity="warning" sx={{ mt: 2 }}>
          {payload.limitations[0]}
        </Alert>
      </CardContent>
      <ExplainDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} payload={payload} />
    </Card>
  );
}

function TrendCard({ title, trend, value }: { title: string; trend: string; value: unknown }) {
  const numeric = Number(value);
  return (
    <Grid size={{ xs: 12, md: 6 }}>
      <Box sx={{ p: 2, bgcolor: "grey.50", borderRadius: 2, height: "100%" }}>
        <Typography variant="subtitle2">{title}</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: "center" }}>
          <Typography variant="h5" sx={{ fontWeight: 750 }}>
            {Number.isFinite(numeric) ? `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}%` : "N/A"}
          </Typography>
          <Chip label={trend} size="small" color={trend === "up" ? "success" : trend === "down" ? "warning" : "default"} />
        </Stack>
      </Box>
    </Grid>
  );
}

function SentenceCard({ title, sentences }: { title: string; sentences: ExplanationSentence[] }) {
  return (
    <Grid size={{ xs: 12, lg: 4 }}>
      <Box sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, height: "100%" }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>{title}</Typography>
        <Stack component="ul" spacing={0.75} sx={{ pl: 2, my: 0 }}>
          {sentences.map((sentence) => <Typography component="li" variant="body2" key={sentence.text}>{sentence.text}</Typography>)}
        </Stack>
      </Box>
    </Grid>
  );
}

function RebasedChart({ spec }: { spec: Record<string, unknown> }) {
  const raw = Array.isArray(spec.points) ? spec.points : [];
  const points = raw.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
  if (points.length < 2) return null;
  const width = 700;
  const height = 190;
  const stock = points.map((point) => Number(point.stock));
  const sector = points.map((point) => Number(point.sector));
  const all = [...stock, ...sector].filter(Number.isFinite);
  const minimum = Math.min(...all);
  const maximum = Math.max(...all);
  const range = Math.max(maximum - minimum, 0.0001);
  const coordinates = (values: number[]) => values.map((value, index) => {
    const x = (index / (values.length - 1)) * width;
    const y = height - ((value - minimum) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const stockPoints = coordinates(stock);
  const sectorPoints = coordinates(sector);
  const shade = [...stockPoints, ...sectorPoints.slice().reverse()].join(" ");
  return (
    <Box sx={{ mt: 2 }} data-chart-type="stock_sector_rebased">
      <Typography variant="subtitle2">Stock versus peer median, rebased to 100</Typography>
      <Box component="svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Rebased stock and sector trend with residual shaded" sx={{ width: "100%", height: 220, bgcolor: "grey.50", mt: 1 }}>
        <polygon points={shade} fill="rgba(156, 39, 176, 0.10)" />
        <polyline points={stockPoints.join(" ")} fill="none" stroke="#1565c0" strokeWidth="3" />
        <polyline points={sectorPoints.join(" ")} fill="none" stroke="#ef6c00" strokeWidth="3" />
      </Box>
      <Stack direction="row" spacing={2}>
        <Typography variant="caption" color="primary">Stock</Typography>
        <Typography variant="caption" color="warning.main">Peer median</Typography>
        <Typography variant="caption">Shading shows indexed separation, not the regression residual.</Typography>
      </Stack>
    </Box>
  );
}
