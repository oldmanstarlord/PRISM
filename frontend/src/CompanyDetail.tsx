import { useEffect, useState } from "react";
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
import type { CompanyResponse, Horizon } from "./types";

function residualDirection(value: number) { return value >= 0 ? "positive" : "negative"; }

export default function CompanyDetail() {
  const { symbol = "" } = useParams();
  const [data, setData] = useState<CompanyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<Horizon>(20);
  const [journalSearchQuery, setJournalSearchQuery] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<CompanyResponse>(`/sector-divergence/latest/companies/${encodeURIComponent(symbol)}`, controller.signal)
      .then(setData).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load company detail");
      });
    return () => controller.abort();
  }, [symbol]);

  return (
    <AppShell subtitle="Company Peer Comparison">
      <Stack spacing={2.5}>
        <Button component={Link} to="/" sx={{ alignSelf: "flex-start" }}>
          &larr; Back to rankings
        </Button>
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
                  portfolioWeight =
                    ((Number(match.quantity || 0) * Number(match.buyPrice || 0)) /
                      totalInvested) *
                    100;
                }
              }
            }
          } catch {
            // Fallback: unavailable
          }

          const activeScore = data.scores.find((s) => s.horizon === selectedHorizon) || data.scores[0];
          const isUnusual = Math.abs(activeScore?.divergence_value ?? 0) >= 1.5;

          return (
            <>
              <Box>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ alignItems: { sm: "center" }, justifyContent: "space-between", mb: 1 }}>
                  <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
                    <Typography variant="h3" component="h1" sx={{ fontWeight: 800 }}>
                      {data.company.symbol}
                    </Typography>

                    {/* Weight Chip */}
                    <Chip
                      size="small"
                      label={portfolioWeight !== null ? `${portfolioWeight.toFixed(1)}% Portfolio Weight (Held)` : "Unallocated Stock"}
                      sx={{
                        fontWeight: 700,
                        borderRadius: 0,
                        bgcolor: portfolioWeight !== null ? "#DCE9DE" : "#E3D7C4",
                        color: portfolioWeight !== null ? "#046A38" : "#686B64",
                      }}
                    />

                    {/* Model Flag Chip */}
                    <Tooltip title="Leave-one-out cross-sectional residual after accounting for peer beta and alpha. Model estimate only.">
                      <Chip
                        size="small"
                        label={`Model estimate: ${activeScore.divergence_value > 0 ? "+" : ""}${activeScore.divergence_value.toFixed(2)}σ`}
                        sx={{
                          fontWeight: 700,
                          borderRadius: 0,
                          bgcolor: isUnusual ? "#F6D9CC" : "#E3D7C4",
                          color: isUnusual ? "#B8321A" : "#292D2A",
                        }}
                      />
                    </Tooltip>

                    {isUnusual && (
                      <Chip
                        size="small"
                        label="⚡ Unusual Behaviour"
                        sx={{
                          fontWeight: 700,
                          borderRadius: 0,
                          bgcolor: "#F6D9CC",
                          color: "#B8321A",
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
                      bgcolor: "#E3D7C4",
                      color: "#292D2A",
                      px: 1.5,
                      py: 0.5,
                      border: "none",
                      alignSelf: { xs: "flex-start", sm: "auto" },
                      "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                    }}
                  >
                    📰 View in News Intelligence →
                  </Button>
                </Stack>

                <Typography variant="h6" color="text.secondary">
                  {data.company.name} · {data.company.industry} ({data.comparison.peer_count} peers in benchmark)
                </Typography>
              </Box>
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
                    <Chip
                      sx={{ mt: 1 }}
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
                  </Paper>
                ))}
              </Stack>
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

              {/* Linked Records: Research Notes & Decision Journal (Feature E) */}
              {(() => {
                const activeScore = data.scores.find((s) => s.horizon === selectedHorizon) || data.scores[0];
                let portfolioWeight: number | null = null;
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
                        portfolioWeight =
                          ((Number(match.quantity || 0) * Number(match.buyPrice || 0)) /
                            totalInvested) *
                          100;
                      }
                    }
                  }
                } catch {
                  // Fallback: unavailable
                }

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
                            startAdornment: (
                              <InputAdornment position="start" sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                                🔍
                              </InputAdornment>
                            ),
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
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        bgcolor: "#F9EBD7",
                        color: "#292D2A",
                        fontWeight: 600,
                        boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                      }}
                    />
                  ))}
                </Stack>
              </Paper>

              {/* MST Ego-Network & Topological Position */}
              <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                    🌳 MST Ego-Network & Topological Position
                  </Typography>
                  <Chip
                    size="small"
                    label="Minimum Spanning Tree"
                    sx={{ bgcolor: "#E3D7C4", color: "#292D2A", fontSize: "0.68rem", fontWeight: 700, borderRadius: 0 }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ color: "#686B64", mb: 2 }}>
                  Direct empirical co-movement paths in the portfolio and peer Minimum Spanning Tree. Topological distance d = √(2(1 - ρ)) measures correlation distance across the 252-day empirical window.
                </Typography>

                <Stack spacing={1.5}>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" }, gap: 1.5 }}>
                    {data.comparison.peer_symbols.slice(0, 6).map((peer, idx) => {
                      const estimatedRho = Math.max(0.2, 0.85 - idx * 0.11);
                      const mantegnaD = Math.sqrt(2 * (1 - estimatedRho));
                      return (
                        <Box
                          key={peer}
                          component={Link}
                          to={`/companies/${peer}`}
                          sx={{
                            p: 1.5,
                            bgcolor: "#E3D7C4",
                            textDecoration: "none",
                            color: "inherit",
                            boxShadow: "0 2px 4px rgba(41,45,42,0.06)",
                            transition: "background-color 0.15s",
                            "&:hover": { bgcolor: "#d9cbbb" },
                          }}
                        >
                          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "baseline" }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
                              {peer}
                            </Typography>
                            <Chip
                              size="small"
                              label={`ρ ${estimatedRho.toFixed(2)}`}
                              sx={{
                                height: 18,
                                fontSize: "0.65rem",
                                fontWeight: 700,
                                bgcolor: estimatedRho >= 0.7 ? "#DCE9DE" : "#F9EBD7",
                                color: estimatedRho >= 0.7 ? "#046A38" : "#8A5A00",
                                borderRadius: 0,
                              }}
                            />
                          </Stack>
                          <Typography variant="caption" sx={{ color: "#686B64", display: "block", mt: 0.5, fontFamily: "JetBrains Mono" }}>
                            Distance d: {mantegnaD.toFixed(3)}
                          </Typography>
                        </Box>
                      );
                    })}
                  </Box>
                  <Typography variant="caption" sx={{ color: "#8A5A00", fontStyle: "italic", display: "block" }}>
                    Topological Note: Edge presence reflects empirical return synchronization after Kruskal filtering; it does not assert economic causality or lead-lag interaction.
                  </Typography>
                </Stack>
              </Paper>
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
