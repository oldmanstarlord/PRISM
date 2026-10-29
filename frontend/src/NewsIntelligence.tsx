import { ReviewDetails } from "./GuidedReview";
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tooltip,
  Typography,
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
    configured: boolean;
    model_ready: boolean;
    running: boolean;
    stale: boolean;
    last_success_at: string | null;
    next_refresh_at: string | null;
    error: string | null;
    warnings: string[];
    sources: string[];
    credits_reserved_today: number;
    daily_credit_budget: number;
    refresh_minutes: number;
    auto_refresh: boolean;
    can_refresh: boolean;
    news_date?: string;
    timezone?: string;
    window_days?: number;
  };
  articles: {
    url: string;
    title: string;
    publisher: string;
    published_at: string | null;
    retrieved_at: string;
    excerpt: string;
    sentiment: Sentiment;
    companies: Record<string, Sentiment>;
    is_retained_context?: boolean;
    relevance_reason?: string | null;
    relevance_until?: string | null;
    related_article_url?: string | null;
  }[];
}

function timestamp(value: string | null) {
  return value
    ? `${new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST`
    : "Not available";
}

const NEWS_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

function publishedInWindow(value: string | null, now: Date) {
  if (!value || !/(Z|[+-]\d{2}:\d{2})$/i.test(value)) return false;
  const published = new Date(value);
  return (
    Number.isFinite(published.getTime()) &&
    published <= now &&
    published.getTime() >= now.getTime() - NEWS_WINDOW_MS
  );
}

const color = {
  positive: "success",
  negative: "error",
  neutral: "default",
  uncertain: "warning",
} as const;

export function NewsIntelligencePanel({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [symbol, setSymbol] = useState("all");
  const [sentiment, setSentiment] = useState("all");
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    // Expire cards by publication time even when this tab is offline.
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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
        setError(
          reason instanceof Error ? reason.message : "News is unavailable",
        );
      }
      timer = setTimeout(() => {
        void load();
      }, delay);
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [revision]);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      await postJson("/news/refresh", {});
      setRevision((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to refresh news",
      );
    } finally {
      setBusy(false);
    }
  }

  const state = feed?.status;
  const recentArticles = (feed?.articles ?? []).filter((article) =>
    publishedInWindow(article.published_at, now),
  );
  const activeArticles = (feed?.articles ?? []).filter((article) => {
    if (publishedInWindow(article.published_at, now)) return true;
    const published = article.published_at
      ? new Date(article.published_at)
      : null;
    const until = article.relevance_until
      ? new Date(article.relevance_until)
      : null;
    return (
      article.is_retained_context &&
      published &&
      published <= now &&
      until &&
      until > now &&
      recentArticles.some(
        (recent) => recent.url === article.related_article_url,
      )
    );
  });
  const contextCount = activeArticles.length - recentArticles.length;
  const symbols = [
    ...new Set(
      activeArticles.flatMap((article) => Object.keys(article.companies)),
    ),
  ].sort();
  const articles = activeArticles.filter((article) => {
    const result =
      symbol === "all" ? article.sentiment : article.companies[symbol];
    return result && (sentiment === "all" || result.label === sentiment);
  });

  return (
    <Stack spacing={3}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        sx={{ justifyContent: "space-between", gap: "var(--space-2)" }}
      >
        <Box>
          <Typography
            component={embedded ? "h2" : "h1"}
            variant={embedded ? "h2" : "h1"}
            sx={{ fontWeight: 600 }}
          >
            News
          </Typography>

        </Box>
        <Button
          variant="contained"
          disabled={!state?.can_refresh || busy}
          onClick={() => {
            void refresh();
          }}
          sx={{ alignSelf: "center", minWidth: 155 }}
        >
          {state?.running || busy ? "Collecting news…" : "Refresh news"}
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {!feed && !error && <CircularProgress aria-label="Loading news" />}
      {state && (
        <>
          <Stack
            direction="row"
            useFlexGap
            sx={{ flexWrap: "wrap" }}
            spacing={1}
          >
            <Chip
              label={`${recentArticles.length} article${recentArticles.length === 1 ? "" : "s"} · last 7 days`}
              variant="outlined"
            />
            {contextCount > 0 && (
              <Chip
                label={`${contextCount} older relevant ${contextCount === 1 ? "story" : "stories"}`}
                variant="outlined"
              />
            )}
            <Chip
              label={
                state.auto_refresh
                  ? `Auto refresh: ${state.refresh_minutes} min`
                  : "Manual collection"
              }
              variant="outlined"
            />
          </Stack>
          {!state.configured && (
            <Alert severity="info">
              Live news collection needs setup. Available articles remain
              visible. Open Collection details for setup status.
            </Alert>
          )}
          {!state.model_ready && (
            <Alert severity="warning">
              Sentiment analysis needs setup before news can be collected. Open
              Collection details for setup status.
            </Alert>
          )}
          {state.running && (
            <Box>
              <LinearProgress />
              <Typography sx={{ mt: "var(--space-1)" }} variant="body2">
                Collecting publisher articles and analyzing financial sentiment.
                You can leave this page while it runs.
              </Typography>
            </Box>
          )}
          {state.error && (
            <Alert severity="warning">Last collection: {state.error}</Alert>
          )}
          {state.stale && state.last_success_at && (
            <Alert severity="info">
              A fresh collection is due. Available news from the last 7 days
              remains visible while new articles are collected.
            </Alert>
          )}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="news-company-label">Company</InputLabel>
              <Select
                labelId="news-company-label"
                label="Company"
                value={symbol}
                onChange={(event) => setSymbol(event.target.value)}
              >
                <MenuItem value="all">All market news</MenuItem>
                {symbols.map((value) => (
                  <MenuItem key={value} value={value}>
                    {value}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="news-sentiment-label">Sentiment</InputLabel>
              <Select
                labelId="news-sentiment-label"
                label="Sentiment"
                value={sentiment}
                onChange={(event) => setSentiment(event.target.value)}
              >
                <MenuItem value="all">All sentiment</MenuItem>
                {["positive", "negative", "neutral", "uncertain"].map(
                  (value) => (
                    <MenuItem key={value} value={value}>
                      {value}
                    </MenuItem>
                  ),
                )}
              </Select>
            </FormControl>
          </Stack>
          {(symbol !== "all" || sentiment !== "all") && (
            <Box>
              <Button
                onClick={() => {
                  setSymbol("all");
                  setSentiment("all");
                }}
              >
                Clear filters
              </Button>
            </Box>
          )}
          {!articles.length && (
            <Paper variant="outlined" sx={{ p: "var(--space-4)", textAlign: "left" }}>
              <Typography variant="h6">
                {activeArticles.length
                  ? "NO MATCHES"
                  : "NO DATA / 7D"}
              </Typography>
            </Paper>
          )}
          <Box sx={{ display: "grid", gridTemplateColumns: "minmax(0,1fr)", gap: "var(--space-2)" }}>
          {articles.map((article) => {
            const result =
              symbol === "all" ? article.sentiment : article.companies[symbol];
            return (
              <Paper
                component="article"
                key={article.url}
                variant="outlined"
                className="terminal-news-article" sx={{ p: "var(--space-2)" }}
              >
                <Stack spacing={1}>
                  {article.is_retained_context &&
                    !publishedInWindow(article.published_at, now) && (
                      <Alert severity="info">
                        <strong>Older relevant context.</strong>{" "}
                        {article.relevance_reason} This story is excluded from
                        7-day sentiment averages.
                        {article.related_article_url && (
                          <>
                            {" "}
                            <a
                              href={article.related_article_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              View recent related report
                            </a>
                            .
                          </>
                        )}
                      </Alert>
                    )}
                  <Typography variant="caption" color="text.secondary">
                    {article.publisher} ·{" "}
                    {article.published_at
                      ? `Published ${timestamp(article.published_at)}`
                      : "Publication time unavailable"}
                  </Typography>
                  <Typography component="h2" variant="h6">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "inherit" }}
                    >
                      {article.title}
                    </a>
                  </Typography>
                  <Stack
                    direction="row"
                    spacing={1}
                    useFlexGap
                    sx={{ flexWrap: "wrap", alignItems: "center" }}
                  >
                    <Chip
                      color={color[result.label]}
                      label={result.label.toUpperCase()}
                      size="small"
                    />
                    <Tooltip title="Model probability for the most likely text-sentiment class. It is not a probability of a stock-price move.">
                      <Typography variant="body2">
                        Model confidence {(result.confidence * 100).toFixed(1)}%
                      </Typography>
                    </Tooltip>
                  </Stack>
                  <ReviewDetails title="Sentiment details">
                    <Stack
                      direction="row"
                      sx={{ gap: "var(--space-1)", flexWrap: "wrap", mb: "var(--space-2)" }}
                    >
                      {Object.keys(article.companies).map((company) => (
                        <Chip
                          key={company}
                          label={company}
                          size="small"
                          variant="outlined"
                          onClick={() => setSymbol(company)}
                        />
                      ))}
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      Positive{" "}
                      {(result.probabilities.positive * 100).toFixed(1)}% ·
                      Neutral {(result.probabilities.neutral * 100).toFixed(1)}%
                      · Negative{" "}
                      {(result.probabilities.negative * 100).toFixed(1)}%
                      {symbol !== "all"
                        ? ` · ${symbol} passages`
                        : " · Article sentiment"}
                      {result.truncated
                        ? " · Long article: partial text analyzed"
                        : ""}
                    </Typography>
                  </ReviewDetails>
                </Stack>
              </Paper>
            );
          })}</Box>
          <ReviewDetails title="Collection details">
            {state.warnings.map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}

            <Typography variant="body2" sx={{ mb: "var(--space-2)" }}>
              {state.configured
                ? "Firecrawl connected"
                : "Firecrawl API key needed on the backend"}{" "}
              ·{" "}
              {state.model_ready
                ? "FinBERT ready"
                : "FinBERT model download needed"}
            </Typography>
            <Paper variant="outlined" sx={{ p: "var(--space-3)" }}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    LAST SUCCESSFUL COLLECTION
                  </Typography>
                  <Typography>{timestamp(state.last_success_at)}</Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    NEXT REFRESH AVAILABLE
                  </Typography>
                  <Typography>
                    {state.next_refresh_at
                      ? timestamp(state.next_refresh_at)
                      : "Ready after setup"}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    DAILY COLLECTION BUDGET
                  </Typography>
                  <Typography>
                    {state.credits_reserved_today} / {state.daily_credit_budget}{" "}
                    credits reserved
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Conservative estimate; resets at UTC midnight.
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          </ReviewDetails>
          <Typography variant="body2" color="text.secondary">
            Sources: {state.sources.join(", ")}. English articles only;
            publisher availability varies. Sentiment describes the reporting and
            does not predict returns or change your fundamental score.
          </Typography>
        </>
      )}
    </Stack>
  );
}

export default function NewsIntelligencePage() {
  return (
    <AppShell subtitle="Financial news and local sentiment">
      <NewsIntelligencePanel />
    </AppShell>
  );
}
