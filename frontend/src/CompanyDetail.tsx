import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { Link, useParams, useSearchParams } from "react-router-dom";
import AppShell from "./AppShell";
import { GuidedSteps, ReviewDetails } from "./GuidedReview";
import { fetchJson } from "./api";
import ComparisonChart from "./ComparisonChart";
import StockDecisionJournal from "./StockDecisionJournal";
import StockResearchNotes from "./StockResearchNotes";
import { GnnCompanyDriftPanel } from "./GnnStructuralDriftPanel";
import type {
  CompanyResponse,
  Horizon,
  LiveQuote,
  RankingsResponse,
} from "./types";

const signed = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
export default function CompanyDetail() {
  const { symbol = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const horizon: Horizon =
    params.get("horizon") === "1" ? 1 : params.get("horizon") === "5" ? 5 : 20;
  const [data, setData] = useState<CompanyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<LiveQuote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [peerRankings, setPeerRankings] = useState<RankingsResponse | null>(
    null,
  );
  const [journalSearch, setJournalSearch] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    void fetchJson<CompanyResponse>(
      `/sector-divergence/latest/companies/${encodeURIComponent(symbol)}`,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to load comparison",
          );
      });
    return () => controller.abort();
  }, [symbol, attempt]);
  const refreshQuote = useCallback(
    async (force = false, signal?: AbortSignal) => {
      setQuoteLoading(true);
      try {
        const result = await fetchJson<LiveQuote>(
          `/market-data/quote/${encodeURIComponent(symbol)}${force ? "?force_refresh=true" : ""}`,
          signal,
        );
        if (!signal?.aborted) setQuote(result);
      } catch {
        /* Keep the last available quote. */
      } finally {
        if (!signal?.aborted) setQuoteLoading(false);
      }
    },
    [symbol],
  );
  useEffect(() => {
    const controller = new AbortController();
    void refreshQuote(false, controller.signal);
    const timer = setInterval(() => {
      void refreshQuote(false, controller.signal);
    }, 15_000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [refreshQuote]);
  useEffect(() => {
    const controller = new AbortController();
    void fetchJson<RankingsResponse>(
      `/sector-divergence/latest/rankings?horizon=${horizon}&limit=200`,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setPeerRankings(result);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [horizon]);
  const current =
    data?.company.symbol.toUpperCase() === symbol.toUpperCase() ? data : null;
  const currentQuote =
    quote?.symbol?.toUpperCase() === symbol.toUpperCase() ? quote : null;
  const score = current?.scores.find((item) => item.horizon === horizon);
  const points = current?.comparison.points.slice(-(horizon + 1)) ?? [];
  const first = points[0];
  const last = points.at(-1);
  const stockReturn =
    first && last ? (last.stock_index / first.stock_index - 1) * 100 : null;
  const peerReturn =
    first && last
      ? (last.benchmark_index / first.benchmark_index - 1) * 100
      : null;
  const peers =
    peerRankings?.horizon === horizon
      ? peerRankings.results
          .filter(
            (item) =>
              item.industry === current?.company.industry &&
              item.symbol !== symbol,
          )
          .sort((a, b) => b.divergence_value - a.divergence_value)
      : [];
  let portfolioWeight: number | null = null;
  try {
    const holdings = JSON.parse(
      localStorage.getItem("prism_portfolio_holdings") ?? "[]",
    ) as { symbol: string; quantity: number; buyPrice: number }[];
    const total = holdings.reduce(
      (sum, holding) => sum + holding.quantity * holding.buyPrice,
      0,
    );
    const held = holdings.find(
      (item) => item.symbol.toUpperCase() === symbol.toUpperCase(),
    );
    if (held && total > 0)
      portfolioWeight = ((held.quantity * held.buyPrice) / total) * 100;
  } catch {
    /* Portfolio context is optional. */
  }
  return (
    <AppShell>
      <Stack spacing={3}>
        <GuidedSteps
          activeStep={2}
          steps={[
            { label: "Choose period", to: `/?step=period&horizon=${horizon}` },
            {
              label: "Review companies",
              to: `/?step=companies&horizon=${horizon}`,
            },
            { label: "Compare" },
          ]}
        />
        <Stack
          direction="row"
          sx={{ justifyContent: "space-between", flexWrap: "wrap", gap: 1 }}
        >
          <Button component={Link} to={`/?step=companies&horizon=${horizon}`}>
            Back to companies
          </Button>
          <Button
            onClick={() => void refreshQuote(true)}
            disabled={quoteLoading}
          >
            {quoteLoading ? "Refreshing price…" : "Refresh price"}
          </Button>
        </Stack>
        {error && (
          <Alert
            severity="error"
            action={
              <Button onClick={() => setAttempt((value) => value + 1)}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        )}
        {!current && !error && (
          <Box sx={{ textAlign: "center", py: 6 }}>
            <CircularProgress aria-label="Loading company comparison" />
          </Box>
        )}
        {current && (
          <>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", gap: 2 }}
            >
              <Box>
                <Typography variant="h1">{current.company.symbol}</Typography>
                <Typography sx={{ mt: 1, color: "text.secondary" }}>
                  {current.company.name} · {current.company.industry}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {portfolioWeight === null
                    ? "Not in your portfolio"
                    : `${portfolioWeight.toFixed(1)}% of your portfolio by invested cost`}{" "}
                  ·{" "}
                  <Link to="/portfolio" style={{ color: "#046A38" }}>
                    View portfolio
                  </Link>
                </Typography>
              </Box>
              {currentQuote?.latest_price != null && (
                <Box>
                  <Typography variant="caption">Latest price</Typography>
                  <Typography variant="h2">
                    ₹
                    {currentQuote.latest_price.toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </Typography>
                  <Typography variant="body2">
                    {currentQuote.change_percent != null &&
                      `${signed(currentQuote.change_percent)}% · `}
                    {currentQuote.as_of?.split("T")[0]}
                  </Typography>
                </Box>
              )}
            </Stack>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{
                gap: 2,
                alignItems: { sm: "center" },
                justifyContent: "space-between",
              }}
            >
              <Typography variant="body2">Comparison period</Typography>
              <Stack
                direction="row"
                role="group"
                aria-label="Comparison period"
                sx={{ gap: 1, flexWrap: "wrap" }}
              >
                {(
                  [
                    { value: 1, label: "Today" },
                    { value: 5, label: "One week" },
                    { value: 20, label: "One month" },
                  ] as const
                ).map((period) => (
                  <Button
                    key={period.value}
                    aria-pressed={horizon === period.value}
                    onClick={() => setParams({ horizon: String(period.value) })}
                    sx={{
                      bgcolor:
                        horizon === period.value ? "primary.main" : "#E3D7C4",
                      color:
                        horizon === period.value ? "#F9EBD7" : "text.primary",
                      px: 3,
                      "&:hover": {
                        bgcolor:
                          horizon === period.value ? "primary.dark" : "#d8cabc",
                      },
                    }}
                  >
                    {period.label}
                  </Button>
                ))}
              </Stack>
            </Stack>
            {current.run.observation_basis ===
              "current_session_provisional" && (
              <Alert severity="info">
                Current-session prices are provisional.
              </Alert>
            )}
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" },
                gap: 2,
              }}
            >
              <Paper sx={{ p: 2.5, bgcolor: "#E3D7C4", boxShadow: "none" }}>
                <Typography variant="body2">Peer difference</Typography>
                <Typography
                  variant="h3"
                  sx={{
                    mt: 1,
                    color:
                      (score?.divergence_value ?? 0) >= 0
                        ? "primary.main"
                        : "error.dark",
                  }}
                >
                  {score ? `${signed(score.divergence_value)}σ` : "Unavailable"}
                </Typography>
                {score && (
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {score.divergence_value >= 0 ? "positive" : "negative"}{" "}
                    residual versus peer model
                  </Typography>
                )}
              </Paper>
              {[
                { label: "Company return", value: stockReturn },
                { label: "Peer return", value: peerReturn },
              ].map((stat) => (
                <Paper
                  key={stat.label}
                  sx={{ p: 2.5, bgcolor: "#E3D7C4", boxShadow: "none" }}
                >
                  <Typography variant="body2">{stat.label}</Typography>
                  <Typography variant="h3" sx={{ mt: 1 }}>
                    {stat.value === null
                      ? "Unavailable"
                      : `${signed(stat.value)}%`}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {horizon} trading {horizon === 1 ? "session" : "sessions"}
                  </Typography>
                </Paper>
              ))}
            </Box>
            <Paper
              sx={{
                p: { xs: 2, sm: 3 },
                boxShadow: "none",
                border: "1px solid",
                borderColor: "divider",
              }}
            >
              <Typography variant="h2">
                {horizon}-day actual performance
              </Typography>
              <Typography variant="body2" sx={{ mt: 1, mb: 3 }}>
                Both lines start at 100. The benchmark uses{" "}
                {current.comparison.peer_count} industry peers and excludes{" "}
                {current.company.symbol}.
              </Typography>
              {points.length > 0 ? (
                <ComparisonChart
                  points={points}
                  symbol={current.company.symbol}
                />
              ) : (
                <Alert severity="info">
                  No paired performance observations are available.
                </Alert>
              )}
            </Paper>
            <ReviewDetails title="How to read this comparison">
              <Typography variant="body2">
                The chart shows indexed returns. The sigma score measures a
                standardized difference from the peer model after accounting for
                estimated alpha and beta. It may differ from the gap between the
                lines. These signals describe behavior and do not explain the
                cause of a move or predict returns.
              </Typography>
              {score && (
                <Typography variant="body2" sx={{ mt: 2 }}>
                  Difference: {score.interpretation} · Industry percentile:{" "}
                  {score.industry_percentile.toFixed(0)} ·{" "}
                  {score.observations_used} observations.
                </Typography>
              )}
            </ReviewDetails>
            <ReviewDetails title="Compare other companies in this industry">
              {peers.length ? (
                <TableContainer sx={{ boxShadow: "none", maxHeight: 420 }}>
                  <Table stickyHeader aria-label="Industry peer comparisons">
                    <TableHead>
                      <TableRow>
                        <TableCell>Company</TableCell>
                        <TableCell>Peer difference</TableCell>
                        <TableCell>Industry percentile</TableCell>
                        <TableCell>Review</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {peers.map((peer) => (
                        <TableRow key={peer.symbol}>
                          <TableCell>{peer.symbol}</TableCell>
                          <TableCell>
                            {signed(peer.divergence_value)}σ
                          </TableCell>
                          <TableCell>
                            {peer.industry_percentile.toFixed(0)}%
                          </TableCell>
                          <TableCell>
                            <Button
                              component={Link}
                              to={`/companies/${encodeURIComponent(peer.symbol)}?horizon=${horizon}`}
                              aria-label={`Compare ${peer.symbol}`}
                            >
                              Compare
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2">
                  Other company comparisons are currently unavailable.
                </Typography>
              )}
            </ReviewDetails>
            <ReviewDetails title="Peer set and data details">
              <Typography variant="h3">Exact peer set</Typography>
              <Typography variant="body2" sx={{ mt: 1, mb: 2 }}>
                These companies formed the benchmark; {current.company.symbol}{" "}
                was excluded from its own comparison.
              </Typography>
              <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
                {current.comparison.peer_symbols.map((peer) => (
                  <Chip
                    key={peer}
                    component={Link}
                    to={`/companies/${encodeURIComponent(peer)}?horizon=${horizon}`}
                    clickable
                    label={peer}
                  />
                ))}
              </Stack>
              <Typography variant="body2" sx={{ mt: 2 }}>
                Signal date: {current.run.signal_date} · Data cutoff:{" "}
                {current.run.data_cutoff ?? "Unavailable"} · Benchmark:{" "}
                {current.comparison.basis}.
              </Typography>
              {currentQuote && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Price source: {currentQuote.source} · Day range: ₹
                  {currentQuote.day_low ?? "—"}–₹{currentQuote.day_high ?? "—"}{" "}
                  · Open: ₹{currentQuote.day_open ?? "—"} · Volume:{" "}
                  {currentQuote.volume?.toLocaleString("en-IN") ?? "—"}
                </Typography>
              )}
              {current.limitations.map((item) => (
                <Typography key={item} variant="body2" sx={{ mt: 1 }}>
                  {item}
                </Typography>
              ))}
            </ReviewDetails>
            <ReviewDetails title="GNN research signal">
              <GnnCompanyDriftPanel symbol={current.company.symbol} />
            </ReviewDetails>
            <Box>
              <Typography variant="h2">Your notes & decisions</Typography>
              <Typography variant="body2" sx={{ mt: 1, mb: 2 }}>
                Keep your research and decision history for{" "}
                {current.company.symbol}.
              </Typography>
              <TextField
                label="Search notes and decisions"
                value={journalSearch}
                onChange={(event) => setJournalSearch(event.target.value)}
                fullWidth
                sx={{ mb: 2 }}
              />
              <Stack spacing={2}>
                <StockResearchNotes
                  key={`notes-${symbol}`}
                  symbol={current.company.symbol}
                  companyName={current.company.name}
                  defaultExpanded={false}
                  externalSearchQuery={journalSearch}
                />
                <StockDecisionJournal
                  key={`journal-${symbol}`}
                  symbol={current.company.symbol}
                  defaultExpanded={false}
                  externalSearchQuery={journalSearch}
                  currentMetrics={{
                    riskScore: null,
                    riskLabel: null,
                    sectorDivergenceScore: score?.divergence_value ?? null,
                    sectorDivergenceHorizon: horizon,
                    portfolioWeight,
                    mstCluster: current.company.industry,
                  }}
                />
              </Stack>
            </Box>
          </>
        )}
      </Stack>
    </AppShell>
  );
}
