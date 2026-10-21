import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Container, FormControl, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Stack, Tooltip, Typography,
} from "@mui/material";

import { fetchJson, postJson } from "./api";
import AppShell from "./AppShell";

export interface Sentiment {
  label: "positive" | "negative" | "neutral" | "uncertain";
  score: number;
  confidence: number;
  probabilities: { positive: number; negative: number; neutral: number };
  model: string;
  chunks_analyzed: number;
  truncated: boolean;
}

export interface NewsFeed {
  status: {
    configured: boolean; model_ready: boolean; running: boolean; stale: boolean;
    last_success_at: string | null; next_refresh_at: string | null;
    error: string | null; warnings: string[]; sources: string[];
    credits_reserved_today: number; daily_credit_budget: number;
    refresh_minutes: number; auto_refresh: boolean; can_refresh: boolean;
  };
  articles: {
    url: string; title: string; publisher: string; published_at: string | null;
    retrieved_at: string; excerpt: string; sentiment: Sentiment;
    companies: Record<string, Sentiment>;
  }[];
}

function timestamp(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not available";
}

const color = { positive: "success", negative: "error", neutral: "default", uncertain: "warning" } as const;

export function NewsIntelligencePanel() {
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [symbol, setSymbol] = useState("all");
  const [sentiment, setSentiment] = useState("all");

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      let delay = 30000;
      try {
        const result = await fetchJson<NewsFeed>("/news", controller.signal);
        if (controller.signal.aborted) return;
        setFeed(result);
        setError(null);
        if (result.status.running) delay = 2000;
      } catch (reason) {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "News is unavailable");
      }
      timer = setTimeout(() => { void load(); }, delay);
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      await postJson("/news/refresh", {});
      setRevision(value => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to refresh news");
    } finally {
      setBusy(false);
    }
  }

  const state = feed?.status;
  const symbols = [...new Set(feed?.articles.flatMap(article => Object.keys(article.companies)) ?? [])].sort();
  const articles = (feed?.articles ?? []).filter(article => {
    const result = symbol === "all" ? article.sentiment : article.companies[symbol];
    return result && (sentiment === "all" || result.label === sentiment);
  });

  return <Stack spacing={3}>
    <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
      <Box>
        <Typography variant="overline" color="text.secondary">FINANCIAL NEWS · LOCAL SENTIMENT</Typography>
        <Typography component="h1" variant="h4" sx={{ fontWeight: 700 }}>News Intelligence</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          Financial reporting from multiple publishers, analyzed by FinBERT on your backend.
        </Typography>
      </Box>
      <Button variant="contained" disabled={!state?.can_refresh || busy} onClick={() => { void refresh(); }}
        sx={{ alignSelf: "center", minWidth: 155 }}>
        {state?.running || busy ? "Collecting news…" : "Refresh news"}
      </Button>
    </Stack>
    {error && <Alert severity="error">{error}</Alert>}
    {!feed && !error && <CircularProgress aria-label="Loading news" />}
    {state && <>
      <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap" }} spacing={1}>
        <Chip label={state.configured ? "Firecrawl connected" : "Firecrawl key needed"}
          color={state.configured ? "success" : "warning"} variant="outlined" />
        <Chip label={state.model_ready ? "FinBERT downloaded · local" : "FinBERT setup needed"}
          color={state.model_ready ? "success" : "warning"} variant="outlined" />
        <Chip label={`${feed.articles.length} unique articles`} variant="outlined" />
        <Chip label={state.auto_refresh ? `Auto refresh: ${state.refresh_minutes} min` : "Manual collection"} variant="outlined" />
      </Stack>
      {!state.configured && <Alert severity="info">
        Connect a Firecrawl API key on the backend to collect live news. Previously collected articles remain available.
      </Alert>}
      {!state.model_ready && <Alert severity="warning">Download the local FinBERT model before collecting news.</Alert>}
      {state.running && <Box><LinearProgress /><Typography sx={{ mt: 1 }} variant="body2">
        Collecting publisher articles and analyzing financial sentiment. You can leave this page while it runs.
      </Typography></Box>}
      {state.error && <Alert severity="warning">Last collection: {state.error}</Alert>}
      {state.warnings.map(warning => <Alert key={warning} severity="warning">{warning}</Alert>)}
      {state.stale && state.last_success_at && <Alert severity="info">
        Collection is older than the refresh window. Check article publication times before using the results.
      </Alert>}
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
          <Box sx={{ flex: 1 }}><Typography variant="caption" color="text.secondary">LAST SUCCESSFUL COLLECTION</Typography>
            <Typography>{timestamp(state.last_success_at)}</Typography></Box>
          <Box sx={{ flex: 1 }}><Typography variant="caption" color="text.secondary">NEXT REFRESH AVAILABLE</Typography>
            <Typography>{state.next_refresh_at ? timestamp(state.next_refresh_at) : "Ready after setup"}</Typography></Box>
          <Box sx={{ flex: 1 }}><Typography variant="caption" color="text.secondary">DAILY COLLECTION BUDGET</Typography>
            <Typography>{state.credits_reserved_today} / {state.daily_credit_budget} credits reserved</Typography>
            <Typography variant="caption" color="text.secondary">Conservative estimate; resets at UTC midnight.</Typography></Box>
        </Stack>
      </Paper>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <FormControl size="small" sx={{ minWidth: 200 }}><InputLabel id="news-company-label">Company</InputLabel>
          <Select labelId="news-company-label" label="Company" value={symbol} onChange={event => setSymbol(event.target.value)}>
            <MenuItem value="all">All market news</MenuItem>
            {symbols.map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
          </Select></FormControl>
        <FormControl size="small" sx={{ minWidth: 180 }}><InputLabel id="news-sentiment-label">Sentiment</InputLabel>
          <Select labelId="news-sentiment-label" label="Sentiment" value={sentiment} onChange={event => setSentiment(event.target.value)}>
            <MenuItem value="all">All sentiment</MenuItem>
            {["positive", "negative", "neutral", "uncertain"].map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
          </Select></FormControl>
      </Stack>
      {!articles.length && <Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
        <Typography variant="h6">{feed.articles.length ? "No articles match these filters" : "No news collected yet"}</Typography>
        <Typography color="text.secondary">{feed.articles.length ? "Try another company or sentiment." : "Once setup is complete, refresh to collect and analyze real publisher articles."}</Typography>
      </Paper>}
      {articles.map(article => {
        const result = symbol === "all" ? article.sentiment : article.companies[symbol];
        return <Paper component="article" key={article.url} variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
          <Stack spacing={1.5}>
            <Typography variant="caption" color="text.secondary">
              {article.publisher} · {article.published_at ? `Published ${timestamp(article.published_at)}` : "Publication time unavailable"}
            </Typography>
            <Typography component="h2" variant="h6">
              <a href={article.url} target="_blank" rel="noopener noreferrer" style={{ color: "inherit" }}>{article.title}</a>
            </Typography>
            <Typography color="text.secondary">{article.excerpt}</Typography>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
              <Chip color={color[result.label]} label={result.label.toUpperCase()} size="small" />
              <Tooltip title="Model probability for the most likely text-sentiment class. It is not a probability of a stock-price move.">
                <Typography variant="body2">Model confidence {(result.confidence * 100).toFixed(1)}%</Typography>
              </Tooltip>
              {Object.keys(article.companies).map(company => <Chip key={company} label={company} size="small" variant="outlined" onClick={() => setSymbol(company)} />)}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              Positive {(result.probabilities.positive * 100).toFixed(1)}% · Neutral {(result.probabilities.neutral * 100).toFixed(1)}% · Negative {(result.probabilities.negative * 100).toFixed(1)}%
              {symbol !== "all" ? ` · ${symbol} passages` : " · Article sentiment"}
              {result.truncated ? " · Long article: partial text analyzed" : ""}
            </Typography>
          </Stack>
        </Paper>;
      })}
      <Typography variant="body2" color="text.secondary">
        Sources: {state.sources.join(", ")}. English articles only; publisher availability varies.
        Sentiment describes the reporting and does not predict returns or change your fundamental score.
      </Typography>
    </>}
  </Stack>;
}

export default function NewsIntelligencePage() {
  return <AppShell subtitle="Financial news and local sentiment">
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <NewsIntelligencePanel />
    </Container>
  </AppShell>;
}
