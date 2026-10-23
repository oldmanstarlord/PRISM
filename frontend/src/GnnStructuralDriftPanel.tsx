import { useEffect, useState } from "react";
import { Alert, Box, Chip, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import { Link } from "react-router-dom";

import { fetchJson, postJson } from "./api";
import { COLORS, SHADOWS } from "./theme";

interface GnnRun {
  status: "ready" | "research_only" | "stale" | "unavailable";
  production_eligible: boolean;
  model_version?: string;
  analysis_date?: string | null;
  latest_market_date?: string | null;
  selection_reason?: string | null;
  validation?: {
    selection?: {
      best_baseline_validation_auc?: number | null;
      gnn_beats_baseline?: boolean;
    };
    methods?: { gnn?: { auc?: number | null } };
  };
}

interface DriftResult {
  date: string;
  symbol: string;
  industry: string;
  embedding_drift: number;
  drift_percentile: number;
  alert_level: "normal" | "elevated" | "high";
  primary_driver?: string | null;
  driver_scope?: string | null;
}

interface PortfolioPayload {
  run: GnnRun;
  results: DriftResult[];
  missing_symbols?: string[];
  limitations?: string[];
  explainability?: ExplanationPayload;
}

interface StockEvidence {
  peer_comparison: { status: string; count: number; stock_return?: number; peer_median_return?: number; gap?: number; symbols?: string[]; start?: string; end?: string };
  persistence: { consecutive_elevated: number; window_snapshots: number; missing_snapshots: number; history: Array<{ date: string; percentile: number; alert_level: string }> };
}
interface ExplanationPayload {
  method: string;
  stocks: Record<string, StockEvidence>;
  diversification: { status: string; pairs: number; requested_pairs: number; prior?: number; current?: number; change?: number; method: string; prior_start?: string; prior_end?: string; current_start?: string; current_end?: string; largest_changes?: Array<{ symbols: string[]; prior: number; current: number; change: number }> };
}

function PortfolioEvidence({ data }: { data: ExplanationPayload }) {
  const d = data.diversification;
  return <Box sx={{ p: 2, bgcolor: "#F9EBD7" }}>
    <Typography sx={{ fontWeight: 800 }}>Are these holdings moving more alike?</Typography>
    <Typography variant="body2">{d.status === "available"
      ? `Average return correlation moved from ${d.prior!.toFixed(2)} to ${d.current!.toFixed(2)} (${d.change! >= 0 ? "+" : ""}${d.change!.toFixed(2)}). ${d.change! > 0 ? "The covered pairs moved more alike in the recent window." : d.change! < 0 ? "The covered pairs moved less alike in the recent window." : "Average correlation was unchanged."} This alone does not measure total portfolio risk.`
      : "Not enough overlapping price history to compare diversification."}</Typography>
    <Typography variant="caption">Coverage: {d.pairs} of {d.requested_pairs} holding pairs. Equal weight per pair.</Typography>
    <Box component="details" sx={{ mt: 1 }}><summary>See correlation evidence and method</summary>
      <Typography variant="body2">{d.method}</Typography>
      {d.status === "available" && <Typography variant="body2">Earlier: {d.prior_start} to {d.prior_end}. Recent: {d.current_start} to {d.current_end}.</Typography>}
      {d.largest_changes?.map(pair => <Typography variant="body2" key={pair.symbols.join("/")}>{pair.symbols.join(" / ")}: {pair.prior.toFixed(2)} → {pair.current.toFixed(2)}</Typography>)}
      <Typography variant="body2">{data.method}</Typography>
    </Box>
  </Box>;
}

function StockExplanation({ evidence }: { evidence: StockEvidence }) {
  const p = evidence.peer_comparison;
  const h = evidence.persistence;
  return <Box sx={{ mt: 1 }}>
    <Typography variant="body2">{p.status === "available"
      ? `Five-session return: ${(p.stock_return! * 100).toFixed(2)}%, versus ${(p.peer_median_return! * 100).toFixed(2)}% for the median of ${p.count} industry peers. Gap: ${p.gap! >= 0 ? "+" : ""}${(p.gap! * 100).toFixed(2)} percentage points.`
      : `Peer comparison unavailable: requires this stock's prices and at least three industry peers (${p.count} covered).`}</Typography>
    <Typography variant="body2">{h.consecutive_elevated > 0 ? `Elevated structural change persisted for at least ${h.consecutive_elevated} consecutive saved observation(s).` : "No ongoing elevated structural-change streak."} Checked {h.window_snapshots} snapshots; {h.missing_snapshots} missing for this stock.</Typography>
    <Box component="details"><summary>See peer group and GNN history</summary>
      {p.status === "available" && <Typography variant="body2">{p.start} to {p.end}. Peers excluding this stock: {p.symbols?.join(", ")}.</Typography>}
      {h.history.map(row => <Typography key={row.date} variant="body2">{row.date}: {(row.percentile * 100).toFixed(1)} percentile · {row.alert_level}</Typography>)}
      <Typography variant="caption">Elevated means above the training-period 95th-percentile drift threshold. Return gaps do not establish unusualness or explain the model's internal reasoning.</Typography>
    </Box>
  </Box>;
}

interface CompanyPayload {
  run: GnnRun;
  symbol: string;
  latest: DriftResult | null;
  history: DriftResult[];
}

interface MarketPayload {
  run: GnnRun;
  history: Array<{
    date: string;
    mean_drift: number;
    share_above_train_95pct: number;
    active_stocks: number;
  }>;
}

const driverLabel = (value?: string | null) =>
  value ? value.replaceAll("_", " ") : "No dominant observed driver";

const alertColors = (level: DriftResult["alert_level"]) =>
  level === "high"
    ? { background: COLORS.paleTerracotta, foreground: COLORS.vermilionText }
    : level === "elevated"
      ? { background: "#F4E6BC", foreground: "#8A5A00" }
      : { background: COLORS.paleSage, foreground: COLORS.emerald };

function RunNotice({ run }: { run: GnnRun }) {
  if (run.status === "ready") return null;
  return (
    <Alert severity={run.status === "stale" ? "warning" : "info"}>
      {run.status === "stale"
        ? `Structural-drift output is stale. Last graph: ${run.analysis_date ?? "unavailable"}; latest market data: ${run.latest_market_date ?? "unavailable"}.`
        : run.status === "research_only"
          ? `Research-only output: ${run.selection_reason ?? "production validation gates have not passed"}.`
          : "No persisted structural-drift analysis is available."}
    </Alert>
  );
}

function DriftCard({ item, linked = true, evidence }: { item: DriftResult; linked?: boolean; evidence?: StockEvidence }) {
  const colors = alertColors(item.alert_level);
  return (
    <Box sx={{ p: 1.5, bgcolor: "#F9EBD7", borderLeft: `4px solid ${colors.foreground}` }}>
      <Stack direction="row" spacing={1} sx={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
        <Typography
          component={linked ? Link : "span"}
          to={linked ? `/companies/${item.symbol}` : undefined}
          sx={{ fontWeight: 800, color: COLORS.deepCharcoal, textDecoration: "none" }}
        >
          {item.symbol}
        </Typography>
        <Chip
          size="small"
          label={`${item.alert_level.toUpperCase()} · ${(item.drift_percentile * 100).toFixed(1)}th percentile`}
          sx={{ borderRadius: 0, fontWeight: 800, bgcolor: colors.background, color: colors.foreground }}
        />
      </Stack>
      <Typography variant="body2" sx={{ color: COLORS.mutedGrey, mt: 0.5 }}>
        Largest observed input-change score: {driverLabel(item.primary_driver)} ({item.driver_scope ?? "unclassified"} context). This is not a causal attribution.
      </Typography>
      {evidence && <StockExplanation evidence={evidence} />}
    </Box>
  );
}

export function GnnPortfolioDriftPanel({ symbols }: { symbols: string[] }) {
  const [payload, setPayload] = useState<PortfolioPayload | null>(null);
  const [market, setMarket] = useState<MarketPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const symbolsKey = symbols.join("|");
  useEffect(() => {
    if (!symbolsKey) return;
    const controller = new AbortController();
    Promise.all([
      postJson<PortfolioPayload>(
        "/gnn/portfolio-drift",
        { symbols: symbolsKey.split("|") },
        controller.signal,
      ),
      fetchJson<MarketPayload>("/gnn/market-history?limit=20", controller.signal),
    ])
      .then(([portfolioPayload, marketPayload]) => {
        setPayload(portfolioPayload);
        setMarket(marketPayload);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => controller.abort();
  }, [symbolsKey]);
  return (
    <Paper sx={{ p: 2.5, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
      <Typography variant="h6" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
        Market-Network Structural Change
      </Typography>
      <Typography variant="body2" sx={{ color: COLORS.mutedGrey, mb: 2 }}>
        Weekly changes in each holding&apos;s learned market, peer and industry representation. This is not a loss probability, price forecast or trade signal.
      </Typography>
      {error && <Alert severity="error">{error}</Alert>}
      {!payload && !error && <CircularProgress size={22} />}
      {payload && (
        <Stack spacing={1.25}>
          <RunNotice run={payload.run} />
          {payload.run.analysis_date && (
            <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
              Analysis date: {payload.run.analysis_date}
            </Typography>
          )}
          {payload.explainability && <PortfolioEvidence data={payload.explainability} />}
          {payload.results.length ? payload.results.map((item) => <DriftCard key={item.symbol} item={item} evidence={payload.explainability?.stocks[item.symbol]} />) : payload.run.status !== "unavailable" ? (
            <Alert severity="info">No current GNN observations match these holdings.</Alert>
          ) : null}
          {market && market.history.length > 1 && (
            <Box sx={{ pt: 1 }}>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Market-wide share above the training-period 95th percentile
              </Typography>
              <Stack direction="row" spacing={0.4} sx={{ height: 56, alignItems: "flex-end", mt: 0.5 }}>
                {market.history.map((item) => (
                  <Box
                    key={item.date}
                    title={`${item.date}: ${(item.share_above_train_95pct * 100).toFixed(1)}% of ${item.active_stocks} stocks`}
                    sx={{
                      flex: 1,
                      minWidth: 3,
                      height: `${Math.max(4, item.share_above_train_95pct * 100)}%`,
                      bgcolor: item.share_above_train_95pct >= 0.1 ? COLORS.vermilionText : COLORS.emerald,
                    }}
                  />
                ))}
              </Stack>
            </Box>
          )}
          {payload.run.validation?.methods?.gnn?.auc != null && (
            <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
              Test adverse-change ranking AUC: {payload.run.validation.methods.gnn.auc.toFixed(3)} · best validation baseline: {payload.run.validation.selection?.best_baseline_validation_auc?.toFixed(3) ?? "unavailable"}.
            </Typography>
          )}
        </Stack>
      )}
    </Paper>
  );
}

export function GnnCompanyDriftPanel({ symbol }: { symbol: string }) {
  const [payload, setPayload] = useState<CompanyPayload | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<CompanyPayload>(`/gnn/companies/${encodeURIComponent(symbol)}`, controller.signal)
      .then(setPayload)
      .catch(() => undefined);
    return () => controller.abort();
  }, [symbol]);
  if (!payload) return null;
  const visible = payload.history.slice(-20);
  return (
    <Paper sx={{ p: 2.5, bgcolor: COLORS.sandBeige, borderRadius: 0, boxShadow: SHADOWS.card }}>
      <Typography variant="h6" sx={{ fontWeight: 800, color: COLORS.deepCharcoal }}>
        Market-Network Structural Change
      </Typography>
      <Typography variant="body2" sx={{ color: COLORS.mutedGrey, mb: 2 }}>
        Descriptive weekly embedding drift. It does not infer direction, causality or an investment action.
      </Typography>
      <Stack spacing={1.5}>
        <RunNotice run={payload.run} />
        {payload.latest ? <DriftCard item={payload.latest} linked={false} /> : <Alert severity="info">No GNN history is available for {symbol}.</Alert>}
        {visible.length > 1 && (
          <Box>
            <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>Recent drift percentile</Typography>
            <Stack direction="row" spacing={0.4} sx={{ height: 70, alignItems: "flex-end", mt: 0.5 }}>
              {visible.map((item) => {
                const colors = alertColors(item.alert_level);
                return (
                  <Box
                    key={item.date}
                    title={`${item.date}: ${(item.drift_percentile * 100).toFixed(1)}th percentile`}
                    sx={{ flex: 1, minWidth: 3, height: `${Math.max(4, item.drift_percentile * 100)}%`, bgcolor: colors.foreground }}
                  />
                );
              })}
            </Stack>
          </Box>
        )}
      </Stack>
    </Paper>
  );
}
