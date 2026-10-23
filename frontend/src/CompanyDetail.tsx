import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { Link, useParams } from "react-router-dom";

import AppShell from "./AppShell";
import { fetchJson } from "./api";
import ComparisonChart from "./ComparisonChart";
import { SectorDivergenceExplainer } from "./PrismExplainer";
import StockDecisionJournal from "./StockDecisionJournal";
import StockResearchNotes from "./StockResearchNotes";
import { GnnCompanyDriftPanel } from "./GnnStructuralDriftPanel";
import type { CompanyResponse, Horizon, LiveQuote, RankingsResponse } from "./types";

function residualDirection(value: number) { return value >= 0 ? "positive" : "negative"; }

export default function CompanyDetail() {
  const { symbol = "" } = useParams();
  const [data, setData] = useState<CompanyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<Horizon>(20);
  const [journalSearchQuery, setJournalSearchQuery] = useState("");

  // Live market quote stream state
  const [liveQuote, setLiveQuote] = useState<LiveQuote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [lastQuoteSync, setLastQuoteSync] = useState<string | null>(null);

  // Peer rankings state
  const [peerRankings, setPeerRankings] = useState<RankingsResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<CompanyResponse>(`/sector-divergence/latest/companies/${encodeURIComponent(symbol)}`, controller.signal)
      .then(setData).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load company detail");
      });
    return () => controller.abort();
  }, [symbol]);

  // Live quote fetching with 15s polling
  const fetchLiveQuote = useCallback(async (force = false) => {
    if (!symbol) return;
    try {
      setQuoteLoading(true);
      const url = `/market-data/quote/${encodeURIComponent(symbol)}${force ? "?force_refresh=true" : ""}`;
      const q = await fetchJson<LiveQuote>(url, new AbortController().signal);
      setLiveQuote(q);
      setLastQuoteSync(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } catch {
      // Graceful fallback
    } finally {
      setQuoteLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    void fetchLiveQuote(false);
    const interval = setInterval(() => {
      void fetchLiveQuote(false);
    }, 15_000);
    return () => clearInterval(interval);
  }, [fetchLiveQuote]);

  // Peer rankings for the selected horizon
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<RankingsResponse>(`/sector-divergence/latest/rankings?horizon=${selectedHorizon}&limit=200`, controller.signal)
      .then(setPeerRankings)
      .catch(() => undefined);
    return () => controller.abort();
  }, [selectedHorizon]);

  return (
    <AppShell subtitle="Company Peer Comparison">
      <Stack spacing={2.5}>
        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
          <Button component={Link} to="/" sx={{ alignSelf: "flex-start" }}>
            &larr; Back to rankings
          </Button>

          {/* Live Data Status & Sync Button */}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Tooltip title="Data feeds are polled and refreshed automatically every 15 seconds. Click to force instant live quote refresh.">
              <Chip
                size="small"
                icon={
                  quoteLoading ? (
                    <CircularProgress size={12} sx={{ color: "#046A38" }} />
                  ) : (
                    <Box
                      component="span"
                      sx={{
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        bgcolor: "#046A38",
                        display: "inline-block",
                        ml: 1,
                      }}
                    />
                  )
                }
                label={lastQuoteSync ? `Live Feed (${lastQuoteSync})` : "Connecting live feed…"}
                onClick={() => void fetchLiveQuote(true)}
                sx={{
                  fontWeight: 700,
                  fontSize: "0.74rem",
                  bgcolor: "#DCE9DE",
                  color: "#046A38",
                  cursor: "pointer",
                }}
              />
            </Tooltip>
            <Button
              size="small"
              onClick={() => void fetchLiveQuote(true)}
              disabled={quoteLoading}
              sx={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "#292D2A",
                bgcolor: "#E3D7C4",
                "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
              }}
            >
              Sync Live Quote
            </Button>
          </Stack>
        </Stack>

        {!data && !error && (
          <Box sx={{ display: "grid", placeItems: "center", py: 10 }}>
            <CircularProgress />
          </Box>
        )}
        {error && <Alert severity="error">{error}</Alert>}
        {data && (() => {
          const chartPoints = data.comparison.points.slice(-(selectedHorizon + 1));
          const first = chartPoints[0];
          const last = chartPoints.at(-1);
          const stockReturn = first && last ? (last.stock_index / first.stock_index - 1) * 100 : 0;
          const benchmarkReturn = first && last ? (last.benchmark_index / first.benchmark_index - 1) * 100 : 0;

          // Compute portfolio weight & holding status
          let portfolioWeight: number | null = null;
          let heldQuantity = 0;
          let avgCost = 0;
          try {
            const raw = localStorage.getItem("prism_portfolio_holdings");
            if (raw) {
              const holdings = JSON.parse(raw);
              if (Array.isArray(holdings) && holdings.length > 0) {
                const totalInvested = holdings.reduce(
                  (sum: number, h: { quantity: number; buyPrice: number }) =>
                    sum + Number(h.quantity || 0) * Number(h.buyPrice || 0),
                  0,
                );
                const match = holdings.find(
                  (h: { symbol: string }) =>
                    h.symbol?.toUpperCase() === data.company.symbol.toUpperCase(),
                );
                if (match && totalInvested > 0) {
                  heldQuantity = Number(match.quantity || 0);
                  avgCost = Number(match.buyPrice || 0);
                  portfolioWeight =
                    ((heldQuantity * avgCost) / totalInvested) * 100;
                }
              }
            }
          } catch {
            // Fallback: unavailable
          }

          const activeScore = data.scores.find((s) => s.horizon === selectedHorizon) || data.scores[0];
          const isUnusual = Math.abs(activeScore?.divergence_value ?? 0) >= 1.5;

          // Sector peer companies for the selected horizon
          const peerItems = peerRankings?.results
            ? peerRankings.results
              .filter(
                (r) =>
                  r.industry === data.company.industry &&
                  r.symbol.toUpperCase() !== data.company.symbol.toUpperCase(),
              )
              .sort((a, b) => b.divergence_value - a.divergence_value)
            : [];

          const quotePrice = liveQuote?.latest_price;
          const quoteChange = liveQuote?.change;
          const quoteChangePct = liveQuote?.change_percent;
          const isQuoteUp = (quoteChange ?? 0) >= 0;

          return (
            <>
              {/* ─── Hero Header & Live Quote Banner ─── */}
              <Paper
                sx={{
                  p: { xs: 2, sm: 3 },
                  bgcolor: "#292D2A",
                  color: "#F9EBD7",
                  boxShadow: "0 8px 24px rgba(41,45,42,0.18)",
                }}
              >
                <Stack spacing={2}>
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={2}
                    sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}
                  >
                    <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
                      <Typography variant="h3" component="h1" sx={{ fontWeight: 800, color: "#F9EBD7" }}>
                        {data.company.symbol}
                      </Typography>

                      <Chip
                        size="small"
                        label={portfolioWeight !== null ? `${portfolioWeight.toFixed(1)}% Portfolio Weight (Held: ${heldQuantity} shares)` : "Unallocated in Portfolio"}
                        sx={{
                          fontWeight: 700,
                          borderRadius: 0,
                          bgcolor: portfolioWeight !== null ? "#046A38" : "rgba(227, 215, 196, 0.2)",
                          color: "#F9EBD7",
                        }}
                      />

                      <Tooltip title="Statistical divergence residual against the peer median model after controlling for sector beta.">
                        <Chip
                          size="small"
                          label={`Model residual: ${activeScore.divergence_value > 0 ? "+" : ""}${activeScore.divergence_value.toFixed(2)}σ`}
                          sx={{
                            fontWeight: 700,
                            borderRadius: 0,
                            bgcolor: isUnusual ? "#B8321A" : "rgba(227, 215, 196, 0.2)",
                            color: "#F9EBD7",
                          }}
                        />
                      </Tooltip>

                      {isUnusual && (
                        <Chip
                          size="small"
                          label="Statistical Dislocation"
                          sx={{
                            fontWeight: 700,
                            borderRadius: 0,
                            bgcolor: "#B8321A",
                            color: "#F9EBD7",
                          }}
                        />
                      )}
                    </Stack>

                    <Button
                      component={Link}
                      to="/portfolio"
                      size="small"
                      sx={{
                        borderRadius: 0,
                        textTransform: "none",
                        fontSize: "0.80rem",
                        fontWeight: 700,
                        bgcolor: "#046A38",
                        color: "#F9EBD7",
                        px: 1.5,
                        py: 0.5,
                        border: "none",
                        alignSelf: { xs: "flex-start", sm: "auto" },
                        "&:hover": { bgcolor: "#034d28" },
                      }}
                    >
                      View in Portfolio Intelligence →
                    </Button>
                  </Stack>

                  <Typography variant="subtitle1" sx={{ color: "#E3D7C4" }}>
                    {data.company.name} · {data.company.industry} ({data.comparison.peer_count} peers in benchmark)
                  </Typography>

                  {/* Real-time Live Price & Intraday Stats Bar */}
                  <Stack
                    direction={{ xs: "column", md: "row" }}
                    spacing={2.5}
                    sx={{
                      pt: 1.5,
                      borderTop: "1px solid rgba(227, 215, 196, 0.15)",
                      alignItems: { md: "center" },
                      flexWrap: "wrap",
                    }}
                  >
                    <Box>
                      <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block", textTransform: "uppercase", fontSize: "0.70rem" }}>
                        Live Market Price
                      </Typography>
                      {quotePrice != null ? (
                        <Stack direction="row" spacing={1} sx={{ alignItems: "baseline" }}>
                          <Typography variant="h4" sx={{ fontWeight: 800, color: "#F9EBD7", fontFamily: "monospace" }}>
                            ₹{quotePrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </Typography>
                          {quoteChange != null && (
                            <Chip
                              size="small"
                              label={`${isQuoteUp ? "+" : ""}₹${quoteChange.toFixed(2)} (${isQuoteUp ? "+" : ""}${quoteChangePct?.toFixed(2)}%)`}
                              sx={{
                                fontWeight: 800,
                                bgcolor: isQuoteUp ? "#046A38" : "#B8321A",
                                color: "#F9EBD7",
                                borderRadius: "2px",
                              }}
                            />
                          )}
                        </Stack>
                      ) : (
                        <Typography variant="h6" sx={{ color: "#E3D7C4" }}>
                          Connecting quote feed…
                        </Typography>
                      )}
                    </Box>

                    {liveQuote && (
                      <Stack direction="row" spacing={3} sx={{ flexWrap: "wrap", gap: 1.5 }}>
                        <Box>
                          <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block" }}>Day Range</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "monospace" }}>
                            ₹{liveQuote.day_low?.toLocaleString("en-IN") ?? "—"} – ₹{liveQuote.day_high?.toLocaleString("en-IN") ?? "—"}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block" }}>Day Open</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "monospace" }}>
                            ₹{liveQuote.day_open?.toLocaleString("en-IN") ?? "—"}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block" }}>Volume</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: "monospace" }}>
                            {liveQuote.volume != null ? liveQuote.volume.toLocaleString("en-IN") : "—"}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block" }}>Feed Lineage</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: "#DCE9DE" }}>
                            {liveQuote.source === "yfinance" ? "Live NSE Feed" : "Persisted EOD"} ({liveQuote.as_of ? liveQuote.as_of.split("T")[0] : "verified"})
                          </Typography>
                        </Box>
                      </Stack>
                    )}
                  </Stack>
                </Stack>
              </Paper>

              {/* ─── Horizon Selector Cards ─── */}
              <Stack direction={{ xs: "column", md: "row" }} sx={{ gap: 2 }}>
                {data.scores.map((score) => (
                  <Paper
                    key={score.horizon}
                    onClick={() => setSelectedHorizon(score.horizon)}
                    sx={{
                      p: 2.5,
                      flex: 1,
                      cursor: "pointer",
                      borderRadius: 0,
                      border: "none",
                      bgcolor: selectedHorizon === score.horizon ? "#F9EBD7" : "#E3D7C4",
                      boxShadow: selectedHorizon === score.horizon ? "0 8px 20px rgba(4,106,56,0.20)" : "0 6px 16px rgba(41,45,42,0.14)",
                      transition: "transform 0.15s ease-in-out, box-shadow 0.15s",
                      "&:hover": {
                        boxShadow: "0 10px 28px rgba(41,45,42,0.18)",
                        transform: "translateY(-2px)",
                      },
                    }}
                  >
                    <Typography variant="overline">{score.horizon}-day divergence</Typography>
                    <Typography
                      variant="h4"
                      sx={{
                        fontWeight: 700,
                        color: score.divergence_value >= 0 ? "#046A38" : "#B8321A",
                      }}
                    >
                      {score.divergence_value > 0 ? "+" : ""}
                      {score.divergence_value.toFixed(2)} sigma
                    </Typography>
                    <Typography>{residualDirection(score.divergence_value)} residual versus peer model</Typography>
                    <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: "center" }}>
                      <Chip
                        size="small"
                        label={score.interpretation}
                        color={
                          score.interpretation === "normal"
                            ? "default"
                            : score.interpretation === "moderate"
                              ? "warning"
                              : "error"
                        }
                      />
                      <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600 }}>
                        {score.industry_percentile.toFixed(0)}th percentile in {data.company.industry}
                      </Typography>
                    </Stack>
                  </Paper>
                ))}
              </Stack>

              <GnnCompanyDriftPanel symbol={data.company.symbol} />

              {/* ─── Actual Performance vs Leave-One-Out Benchmark ─── */}
              <Paper sx={{ p: { xs: 2, md: 3 } }}>
                <Typography variant="h5" sx={{ fontWeight: 650, mb: 0.5 }}>
                  {selectedHorizon}-day actual performance
                </Typography>
                <Typography sx={{ mb: 0.5 }}>
                  <strong>{data.company.symbol}: {stockReturn >= 0 ? "+" : ""}{stockReturn.toFixed(2)}%</strong> / Peer benchmark: {benchmarkReturn >= 0 ? "+" : ""}{benchmarkReturn.toFixed(2)}%
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                  Both lines start at 100 for the selected horizon. The peer line is the daily leave-one-out median of {data.comparison.peer_count} eligible {data.company.industry} peers.
                </Typography>
                <ComparisonChart points={chartPoints} symbol={data.company.symbol} />
              </Paper>

              {/* Dynamic Condition Explainer */}
              {(() => {
                const activeScore = data.scores.find((s) => s.horizon === selectedHorizon) || data.scores[0];
                return (
                  <SectorDivergenceExplainer
                    symbol={data.company.symbol}
                    industry={data.company.industry}
                    divergenceScore={activeScore?.divergence_value ?? 0}
                    horizon={selectedHorizon}
                    peerCount={data.comparison.peer_count}
                    stockReturn={stockReturn}
                    benchmarkReturn={benchmarkReturn}
                    interpretation={activeScore?.interpretation}
                  />
                );
              })()}

              {/* ─── Real Peer Roster with Divergence Scores ─── */}
              {peerItems.length > 0 && (
                <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A", mb: 0.5 }}>
                    Full {data.company.industry} Peer Universe ({peerItems.length} peers)
                  </Typography>
                  <Typography variant="body2" sx={{ color: "#686B64", mb: 2 }}>
                    Real divergence scores for all active peers in this sector at the {selectedHorizon}-day horizon. Click any peer to navigate to its full comparison.
                  </Typography>

                  <TableContainer component={Paper} sx={{ bgcolor: "#F9EBD7", borderRadius: 0, maxHeight: 340 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow sx={{ bgcolor: "#E3D7C4" }}>
                          <TableCell sx={{ fontWeight: 700, bgcolor: "#E3D7C4" }}>Peer Symbol</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, bgcolor: "#E3D7C4" }}>{selectedHorizon}D Divergence</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, bgcolor: "#E3D7C4" }}>Percentile Rank</TableCell>
                          <TableCell align="center" sx={{ fontWeight: 700, bgcolor: "#E3D7C4" }}>Rarity Classification</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, bgcolor: "#E3D7C4" }}>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {peerItems.map((peer) => {
                          const isPeerPos = peer.divergence_value >= 0;
                          return (
                            <TableRow key={peer.symbol} hover>
                              <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>
                                {peer.symbol}
                              </TableCell>
                              <TableCell align="right" sx={{ fontWeight: 800, color: isPeerPos ? "#046A38" : "#B8321A", fontFamily: "monospace" }}>
                                {isPeerPos ? "+" : ""}{peer.divergence_value.toFixed(2)}σ
                              </TableCell>
                              <TableCell align="right" sx={{ fontWeight: 600 }}>
                                {peer.industry_percentile.toFixed(0)}th
                              </TableCell>
                              <TableCell align="center">
                                <Chip
                                  size="small"
                                  label={peer.interpretation}
                                  sx={{
                                    height: 20,
                                    fontSize: "0.68rem",
                                    fontWeight: 700,
                                    borderRadius: 0,
                                    bgcolor: peer.interpretation === "extreme" || peer.interpretation === "strong"
                                      ? (isPeerPos ? "#DCE9DE" : "#F6D9CC")
                                      : "#E3D7C4",
                                    color: peer.interpretation === "extreme" || peer.interpretation === "strong"
                                      ? (isPeerPos ? "#046A38" : "#B8321A")
                                      : "#292D2A",
                                  }}
                                />
                              </TableCell>
                              <TableCell align="right">
                                <Button
                                  component={Link}
                                  to={`/companies/${peer.symbol}`}
                                  size="small"
                                  sx={{ fontSize: "0.72rem", textTransform: "none", fontWeight: 700 }}
                                >
                                  Inspect →
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              )}

              {/* ─── Exact Peer Set Summary Chips ─── */}
              <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>Exact peer set</Typography>
                <Typography sx={{ color: "#686B64", mb: 2 }}>
                  These companies formed the benchmark; {data.company.symbol} was excluded from its own comparison.
                </Typography>
                <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
                  {data.comparison.peer_symbols.map((peer) => (
                    <Chip
                      key={peer}
                      label={peer}
                      component={Link}
                      to={`/companies/${peer}`}
                      clickable
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        bgcolor: "#E3D7C4",
                        color: "#292D2A",
                        fontWeight: 600,
                        boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                        "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                      }}
                    />
                  ))}
                </Stack>
              </Paper>



              {/* ─── Linked Records: Notes & Decisions ─── */}
              {(() => {
                const activeScore = data.scores.find((s) => s.horizon === selectedHorizon) || data.scores[0];
                const currentMetrics = {
                  riskScore: null,
                  riskLabel: null,
                  sectorDivergenceScore: activeScore?.divergence_value ?? null,
                  sectorDivergenceHorizon: selectedHorizon,
                  portfolioWeight,
                  mstCluster: data.company.industry || null,
                };

                return (
                  <Paper
                    sx={{
                      p: 2.5,
                      borderRadius: 0,
                      border: "none",
                      bgcolor: "#F9EBD7",
                      boxShadow: "0 10px 28px rgba(41,45,42,0.18)",
                    }}
                  >
                    <Stack
                      direction={{ xs: "column", sm: "row" }}
                      sx={{
                        justifyContent: "space-between",
                        alignItems: { xs: "stretch", sm: "center" },
                        gap: 1.5,
                        mb: 2,
                      }}
                    >
                      <Box>
                        <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A", fontSize: "1.05rem" }}>
                          Linked Records: Notes & Decisions
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          All qualitative thesis, tags, and decision rationale linked to canonical ticker {data.company.symbol}.
                        </Typography>
                      </Box>
                      <TextField
                        size="small"
                        placeholder={`Filter notes, tags, & decisions for ${data.company.symbol}...`}
                        value={journalSearchQuery}
                        onChange={(e) => setJournalSearchQuery(e.target.value)}
                        sx={{ minWidth: { sm: 300 }, "& .MuiInputBase-input": { fontSize: "0.85rem" } }}
                        slotProps={{
                          input: {
                            endAdornment: journalSearchQuery ? (
                              <IconButton size="small" onClick={() => setJournalSearchQuery("")}>
                                ✕
                              </IconButton>
                            ) : undefined,
                          },
                        }}
                      />
                    </Stack>

                    <Stack spacing={2.5}>
                      <StockResearchNotes
                        symbol={data.company.symbol}
                        companyName={data.company.name}
                        defaultExpanded={true}
                        externalSearchQuery={journalSearchQuery}
                      />

                      <StockDecisionJournal
                        symbol={data.company.symbol}
                        currentMetrics={currentMetrics}
                        defaultExpanded={true}
                        externalSearchQuery={journalSearchQuery}
                      />
                    </Stack>
                  </Paper>
                );
              })()}

              <Alert severity="info" sx={{ borderRadius: 0, bgcolor: "#F9EBD7", color: "#292D2A", border: "none", boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}>
                <strong style={{ color: "#292D2A" }}>Interpretation:</strong> the chart shows raw indexed performance. The sigma score is a standardized model residual after accounting for estimated alpha and beta, so it is not simply the vertical distance between the two lines. It does not establish a cause or predict what happens next. Data through {data.run.signal_date}.
              </Alert>
            </>
          );
        })()}
      </Stack>
    </AppShell>
  );
}

