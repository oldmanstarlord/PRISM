import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { useApi } from "./api";
import { ExplainDrawer } from "./components/ExplainDrawer";
import type { NewsInsight, NewsInsightsResponse } from "./types";

interface PortfolioChoice {
  id: string;
  name: string;
}

export default function NewsPage() {
  const [industry, setIndustry] = useState("");
  const [severity, setSeverity] = useState(0);
  const [portfolioId, setPortfolioId] = useState("");
  const [selected, setSelected] = useState<NewsInsight | null>(null);
  const { data: portfolios = [] } = useApi<PortfolioChoice[]>("/portfolios");
  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (industry.trim()) params.set("industry", industry.trim());
    if (severity > 0) params.set("severity", String(severity));
    if (portfolioId) params.set("portfolio_id", portfolioId);
    const suffix = params.toString();
    return `/news/insights${suffix ? `?${suffix}` : ""}`;
  }, [industry, severity, portfolioId]);
  const { data, error, isLoading } = useApi<NewsInsightsResponse>(query);

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>News insights</Typography>
          <Typography color="text.secondary">
            Possible effects from evidence-bound rules and statistical paths, not predictions.
          </Typography>
        </Box>

        <Paper sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField label="Industry" value={industry} onChange={(event) => setIndustry(event.target.value)} />
            <TextField label="Minimum severity" type="number" value={severity} inputProps={{ min: 0, max: 10 }} onChange={(event) => setSeverity(Number(event.target.value))} />
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel id="portfolio-filter">Portfolio overlay</InputLabel>
              <Select labelId="portfolio-filter" label="Portfolio overlay" value={portfolioId} onChange={(event) => setPortfolioId(event.target.value)}>
                <MenuItem value="">All news</MenuItem>
                {portfolios.map((portfolio) => <MenuItem key={portfolio.id} value={portfolio.id}>{portfolio.name}</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        {error && <Alert severity="error">{error.message}</Alert>}
        {isLoading && <Typography>Loading allowlisted news…</Typography>}
        {data?.items.map((item) => (
          <Paper key={item.news_id} sx={{ p: 2.5 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                <Chip label={`Severity ${item.severity.toFixed(1)}`} color={item.severity >= 7 ? "error" : item.severity >= 4 ? "warning" : "default"} />
                {item.unreviewed && <Chip label="UNREVIEWED" color="warning" />}
                {item.matched_rules.map((rule) => <Chip key={rule} label={rule} variant="outlined" />)}
                {item.affected_industries.map((value) => <Chip key={value} label={value} size="small" />)}
              </Stack>
              <Typography variant="h6">{item.headline}</Typography>
              <Typography variant="body2" color="text.secondary">
                {item.source} · {new Date(item.published_at).toLocaleString()}
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button onClick={() => setSelected(item)} variant="contained">View explanation</Button>
                <Button component="a" href={item.url} target="_blank" rel="noreferrer">Official source</Button>
              </Stack>
            </Stack>
          </Paper>
        ))}

        {data && data.items.length === 0 && (
          <Alert severity="info">
            <Typography>No qualifying news impacts are available for these filters.</Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap", gap: 1 }}>
              {data.source_statuses.map((source) => (
                <Chip key={source.source_key} label={`${source.owner}: ${source.status} / ${source.freshness_status}`} color={source.status === "live" ? "success" : source.status === "tbd" ? "warning" : "default"} />
              ))}
            </Stack>
          </Alert>
        )}
      </Stack>
      <ExplainDrawer open={selected !== null} path={selected ? `/explain/news/${selected.news_id}` : ""} onClose={() => setSelected(null)} />
    </Container>
  );
}
