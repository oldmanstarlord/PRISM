import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import {
  deletePortfolioSnapshot,
  getAllPortfolioSnapshots,
  getDecisionsForSnapshot,
  isPersistenceFallbackActive,
  type InvestmentDecision,
  type PortfolioSnapshot,
  savePortfolioSnapshot,
  subscribePersistenceFallback,
} from "./journalStorage";
import type {
  ComprehensiveRiskResponse,
  PortfolioAnalysisResponse,
  StructuralMonitoringSnapshot,
} from "./types";

export interface PortfolioSnapshotSectionProps {
  analysis: PortfolioAnalysisResponse | null;
  comprehensiveRisk: ComprehensiveRiskResponse | null;
  monitoring: StructuralMonitoringSnapshot | null;
  holdings: Array<{ symbol: string; quantity: number; buyPrice: number; sector?: string }>;
  totalInvested: number;
}

export default function PortfolioSnapshotSection({
  analysis,
  comprehensiveRisk,
  monitoring,
  holdings,
  totalInvested,
}: PortfolioSnapshotSectionProps) {
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFallback, setIsFallback] = useState(isPersistenceFallbackActive());

  useEffect(() => {
    return subscribePersistenceFallback((active) => setIsFallback(active));
  }, []);

  // Save Modal
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [snapshotName, setSnapshotName] = useState("");
  const [snapshotDesc, setSnapshotDesc] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  // Comparison State
  const [compareIdA, setCompareIdA] = useState<string>("");
  const [compareIdB, setCompareIdB] = useState<string>("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [decisionsSnapshotB, setDecisionsSnapshotB] = useState<InvestmentDecision[]>([]);

  useEffect(() => {
    if (compareIdB) {
      void getDecisionsForSnapshot(compareIdB)
        .then(setDecisionsSnapshotB)
        .catch(() => setDecisionsSnapshotB([]));
    } else {
      setDecisionsSnapshotB([]);
    }
  }, [compareIdB]);

  const loadSnapshots = async () => {
    setLoading(true);
    try {
      const data = await getAllPortfolioSnapshots();
      setSnapshots(data);
      if (data.length >= 2 && !compareIdA && !compareIdB) {
        setCompareIdA(data[1].id);
        setCompareIdB(data[0].id);
      } else if (data.length === 1 && !compareIdA) {
        setCompareIdA(data[0].id);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshots();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleOpenSave = () => {
    const today = new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    setSnapshotName(`Snapshot - ${today}`);
    setSnapshotDesc("");
    setSaveError(null);
    setSaveModalOpen(true);
  };

  const handleSaveSnapshot = async () => {
    if (!snapshotName.trim()) {
      setSaveError("Please enter a snapshot name.");
      return;
    }

    try {
      // Build snapshot from current portfolio state
      const snapshotHoldings = holdings.map((h) => {
        const wt = totalInvested > 0 ? (h.quantity * h.buyPrice / totalInvested) * 100 : 0;
        const holdingAnalytics = analysis?.holdings.find((ah) => ah.symbol === h.symbol);
        return {
          symbol: h.symbol.toUpperCase(),
          weight: wt,
          quantity: h.quantity,
          buyPrice: h.buyPrice,
          annualizedVolatility: holdingAnalytics?.annualized_volatility ?? null,
          marginalRisk: holdingAnalytics?.marginal_risk ?? null,
          riskContribution: holdingAnalytics?.risk_contribution ?? null,
          divergenceScore: holdingAnalytics?.divergence_20d ?? null,
        };
      });

      // Sector Exposures
      const sectorMap: Record<string, number> = {};
      for (const h of holdings) {
        const s = h.sector || "Unclassified";
        const val = h.quantity * h.buyPrice;
        sectorMap[s] = (sectorMap[s] || 0) + val;
      }
      const sectorExposures = Object.entries(sectorMap).map(([sector, val]) => ({
        sector,
        weight: totalInvested > 0 ? (val / totalInvested) * 100 : 0,
      }));

      // Risk Metrics - strict null handling
      const riskMetrics = {
        totalReturn: analysis?.performance?.total_return ?? null,
        annualizedReturn: analysis?.performance?.annualized_return ?? null,
        annualizedVolatility: analysis?.performance?.annualized_volatility ?? null,
        downsideVolatility: analysis?.performance?.downside_volatility ?? null,
        maxDrawdown: analysis?.performance?.max_drawdown ?? null,
        portfolioRiskScore:
          comprehensiveRisk?.portfolio_profile?.portfolio_risk_score ??
          monitoring?.portfolio_risk_score ??
          null,
        portfolioClassification:
          comprehensiveRisk?.portfolio_profile?.portfolio_classification ??
          monitoring?.portfolio_classification ??
          null,
      };

      // Diversification
      const diversification = {
        holdingHhi: analysis?.concentration?.holding_hhi ?? null,
        industryHhi: analysis?.concentration?.industry_hhi ?? null,
        effectiveHoldings: analysis?.concentration?.effective_holdings ?? null,
        effectiveIndustries: analysis?.concentration?.effective_industries ?? null,
        diversificationScore: monitoring?.diversification_score ?? null,
      };

      // MST Context
      const mstContext = {
        runId: analysis?.mst?.run_id ?? null,
        edgeCount: analysis?.mst?.direct_edges ? analysis.mst.direct_edges.length : null,
        directEdgeCount: analysis?.mst?.direct_edges?.length ?? null,
        clusterCount: analysis?.mst?.clusters?.length ?? null,
        clusterHhi: analysis?.mst?.cluster_hhi ?? null,
        bridgeStocks: analysis?.mst?.bridge_stocks?.map((b) => b.symbol) ?? [],
      };

      // Calculation Meta (Reproducible point-in-time quantitative envelope)
      const calculationMeta = {
        portfolioId: "active_portfolio",
        dataCutoff: analysis?.envelope?.as_of ?? new Date().toISOString(),
        window: analysis?.envelope?.requested_observations ?? 250,
        coverage: 100,
        methodologyVersion: "1.0.0",
        assumptions: [
          "Constant-weight daily-rebalanced simple returns for volatility and Euler decomposition",
          "Risk-free rate Rf = 6.50% annualized",
          "Benchmark index: NIFTY 50 (^NSEI)",
          "Regularized covariance matrix via spectral eigenvalue clipping",
        ],
        horizon: analysis?.envelope?.requested_observations ?? 250,
        lookbackStart: analysis?.envelope?.lookback_start ?? null,
        asOf: analysis?.envelope?.as_of ?? null,
        parameters: {
          weightingAssumption: analysis?.envelope?.weighting_assumption ?? "custom",
          missingDataRule: analysis?.envelope?.missing_data_rule ?? "strict",
        },
        schemaVersion: 1,
      };

      await savePortfolioSnapshot({
        name: snapshotName.trim(),
        description: snapshotDesc.trim() || undefined,
        calculationMeta,
        holdings: snapshotHoldings,
        sectorExposures,
        riskMetrics,
        diversification,
        mstContext,
      });

      setSaveModalOpen(false);
      await loadSnapshots();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save portfolio snapshot");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deletePortfolioSnapshot(id);
      setDeleteConfirmId(null);
      await loadSnapshots();
    } catch {
      // Graceful fallback
    }
  };

  // Selected snapshots for comparison
  const snapshotA = useMemo(() => snapshots.find((s) => s.id === compareIdA) || null, [snapshots, compareIdA]);
  const snapshotB = useMemo(() => snapshots.find((s) => s.id === compareIdB) || null, [snapshots, compareIdB]);

  // Check if horizons or schemas differ
  const horizonMismatch = useMemo(() => {
    if (!snapshotA || !snapshotB) return false;
    return snapshotA.calculationMeta.horizon !== snapshotB.calculationMeta.horizon;
  }, [snapshotA, snapshotB]);

  // Helper to format delta
  const renderDelta = (
    valA: number | null | undefined,
    valB: number | null | undefined,
    suffix = "%",
    isPercent = true
  ) => {
    if (horizonMismatch) {
      return (
        <Typography component="span" sx={{ color: "var(--amber)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
          Not comparable (Horizon mismatch: {snapshotA?.calculationMeta.horizon}D vs {snapshotB?.calculationMeta.horizon}D)
        </Typography>
      );
    }
    if (valA === null || valA === undefined || valB === null || valB === undefined || isNaN(valA) || isNaN(valB)) {
      return (
        <Typography component="span" sx={{ color: "var(--gray)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
          Not comparable (Missing data)
        </Typography>
      );
    }
    const diff = valB - valA;
    const isZero = Math.abs(diff) < 0.001;
    const isBetter = isPercent && (suffix === "%" || suffix === "") ? diff < 0 : diff > 0;
    return (
      <Typography
        component="span"
        sx={{
          fontWeight: 600,
          color: isZero ? "var(--gray)" : isBetter ? "var(--up)" : "var(--down)",
          fontSize: "var(--text-title)",
          fontFamily: "var(--font-data)",
        }}
      >
        {diff >= 0 ? "+" : ""}{diff.toFixed(2)}{suffix}
      </Typography>
    );
  };

  const renderMetric = (val: number | null | undefined, suffix = "") => {
    if (val === null || val === undefined || isNaN(val)) {
      return (
        <Typography component="span" sx={{ color: "var(--gray)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
          Unavailable
        </Typography>
      );
    }
    return `${val.toFixed(2)}${suffix}`;
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {isFallback && (
        <Alert
          severity="warning"
          sx={{
            borderRadius: "var(--radius)",
            bgcolor: "var(--gray)",
            color: "var(--down)",
            border: "none",
            boxShadow: "none",
            "& .MuiAlert-icon": { color: "var(--amber)" },
          }}
        >
          <strong>Session Memory Fallback Active:</strong> Browser IndexedDB is unavailable or storage failed. Snapshots are stored in temporary session memory only and will not persist across browser reload.
        </Alert>
      )}

      {loading && (
        <Typography variant="body2" sx={{ color: "var(--gray)", fontStyle: "italic" }}>
          Loading saved snapshots...
        </Typography>
      )}

      {/* Header & Save Action */}
      <Paper
        elevation={0}
        sx={{
          p: "var(--space-2)",
          borderRadius: "var(--radius)",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-2)" }}
        >
          <Box>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: "var(--text-title)", color: "var(--white)" }}>
                Portfolio Snapshots & Audit Comparison
              </Typography>
              <Chip
                size="small"
                label={`${snapshots.length} ${snapshots.length === 1 ? "snapshot" : "snapshots"}`}
                sx={{ bgcolor: "var(--line)", color: "var(--white)", fontWeight: 600, borderRadius: "var(--radius)", height: 20, fontSize: "var(--text-title)" }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: "var(--gray)", mt: "var(--space-1)", display: "block", fontSize: "var(--text-title)" }}>
              Capture immutable point-in-time portfolio allocations, risk metrics, and MST structures for historical comparison.
            </Typography>
          </Box>

          <Button
            variant="contained"
            size="small"
            onClick={handleOpenSave}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              "&:hover": { bgcolor: "var(--up)" },
              textTransform: "none",
              fontWeight: 600,
              borderRadius: "var(--radius)",
              boxShadow: "none",
              px: "var(--space-2)",
              py: "var(--space-1)",
              fontSize: "var(--text-title)",
            }}
          >
            + Save Snapshot Now
          </Button>
        </Stack>
      </Paper>

      {/* Snapshots Roster & Comparison Picker */}
      {snapshots.length === 0 ? (
        <Paper sx={{ p: "var(--space-4)", textAlign: "center", bgcolor: "var(--bg)", borderRadius: "var(--radius)", boxShadow: "none" }}>
          <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)" }}>
            No portfolio snapshots saved yet. Save a snapshot to compare portfolio states over time as weights, volatility, and market conditions shift.
          </Typography>
          <Button
            variant="contained"
            onClick={handleOpenSave}
            sx={{ textTransform: "none", fontSize: "var(--text-title)", bgcolor: "var(--up)", color: "var(--line)", borderRadius: "var(--radius)", boxShadow: "none" }}
          >
            Capture First Snapshot
          </Button>
        </Paper>
      ) : (
        <Card elevation={0} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", boxShadow: "none" }}>
          <CardContent sx={{ p: "var(--space-3)" }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-2)" }}>
              Compare Any Two Snapshots
            </Typography>

            {/* Snapshot Selectors */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: "var(--space-3)" }}>
              <FormControl size="small" sx={{ flex: 1 }}>
                <InputLabel id="snapshot-a-label">Baseline Snapshot (A)</InputLabel>
                <Select
                  labelId="snapshot-a-label"
                  label="Baseline Snapshot (A)"
                  value={compareIdA}
                  onChange={(e) => setCompareIdA(e.target.value)}
                  sx={{ borderRadius: "var(--radius)" }}
                >
                  {snapshots.map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.name} ({new Date(s.createdAt).toLocaleDateString("en-IN")}) · {s.holdings.length} stocks
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ flex: 1 }}>
                <InputLabel id="snapshot-b-label">Target Snapshot (B)</InputLabel>
                <Select
                  labelId="snapshot-b-label"
                  label="Target Snapshot (B)"
                  value={compareIdB}
                  onChange={(e) => setCompareIdB(e.target.value)}
                  sx={{ borderRadius: "var(--radius)" }}
                >
                  {snapshots.map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.name} ({new Date(s.createdAt).toLocaleDateString("en-IN")}) · {s.holdings.length} stocks
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>

            {/* Comparison Table */}
            {snapshotA && snapshotB && (
              <Box sx={{ borderRadius: "var(--radius)", overflow: "hidden", boxShadow: "none" }}>
                <TableContainer>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: "var(--line)" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>Metric</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>
                          {snapshotA.name}
                          <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
                            {new Date(snapshotA.createdAt).toLocaleDateString("en-IN")}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>
                          {snapshotB.name}
                          <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
                            {new Date(snapshotB.createdAt).toLocaleDateString("en-IN")}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>Variance / Shift (B - A)</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {/* Calculation Horizon */}
                      <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Calculation Horizon</TableCell>
                        <TableCell>{snapshotA.calculationMeta.horizon} Days</TableCell>
                        <TableCell>{snapshotB.calculationMeta.horizon} Days</TableCell>
                        <TableCell>
                          {snapshotA.calculationMeta.horizon === snapshotB.calculationMeta.horizon ? (
                            <Chip size="small" label="Identical Horizon" sx={{ bgcolor: "var(--line)", color: "var(--up)", height: 20, fontSize: "var(--text-title)", borderRadius: "var(--radius)", fontWeight: 600 }} />
                          ) : (
                            <Chip size="small" label="Differing Horizon" sx={{ bgcolor: "var(--gray)", color: "var(--down)", height: 20, fontSize: "var(--text-title)", borderRadius: "var(--radius)", fontWeight: 600 }} />
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Portfolio Risk Score */}
                      <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Portfolio Risk Score</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>
                          {snapshotA.riskMetrics.portfolioRiskScore !== null
                            ? `${renderMetric(snapshotA.riskMetrics.portfolioRiskScore)} (${snapshotA.riskMetrics.portfolioClassification || "Normal"})`
                            : renderMetric(null)}
                        </TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>
                          {snapshotB.riskMetrics.portfolioRiskScore !== null
                            ? `${renderMetric(snapshotB.riskMetrics.portfolioRiskScore)} (${snapshotB.riskMetrics.portfolioClassification || "Normal"})`
                            : renderMetric(null)}
                        </TableCell>
                        <TableCell>
                          {renderDelta(snapshotA.riskMetrics.portfolioRiskScore, snapshotB.riskMetrics.portfolioRiskScore, "", false)}
                        </TableCell>
                      </TableRow>

                      {/* Annualized Volatility */}
                      <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Annualized Volatility</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotA.riskMetrics.annualizedVolatility ? snapshotA.riskMetrics.annualizedVolatility * 100 : null, "%")}</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotB.riskMetrics.annualizedVolatility ? snapshotB.riskMetrics.annualizedVolatility * 100 : null, "%")}</TableCell>
                        <TableCell>
                          {renderDelta(
                            snapshotA.riskMetrics.annualizedVolatility ? snapshotA.riskMetrics.annualizedVolatility * 100 : null,
                            snapshotB.riskMetrics.annualizedVolatility ? snapshotB.riskMetrics.annualizedVolatility * 100 : null,
                            "%"
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Max Drawdown */}
                      <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Max Drawdown</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotA.riskMetrics.maxDrawdown ? snapshotA.riskMetrics.maxDrawdown * 100 : null, "%")}</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotB.riskMetrics.maxDrawdown ? snapshotB.riskMetrics.maxDrawdown * 100 : null, "%")}</TableCell>
                        <TableCell>
                          {renderDelta(
                            snapshotA.riskMetrics.maxDrawdown ? snapshotA.riskMetrics.maxDrawdown * 100 : null,
                            snapshotB.riskMetrics.maxDrawdown ? snapshotB.riskMetrics.maxDrawdown * 100 : null,
                            "%"
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Holding HHI Concentration */}
                      <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Holding Concentration (HHI)</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotA.diversification.holdingHhi)}</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotB.diversification.holdingHhi)}</TableCell>
                        <TableCell>{renderDelta(snapshotA.diversification.holdingHhi, snapshotB.diversification.holdingHhi, "", false)}</TableCell>
                      </TableRow>

                      {/* Effective Holdings */}
                      <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Effective Independent Bets (Neff)</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotA.diversification.effectiveHoldings)}</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotB.diversification.effectiveHoldings)}</TableCell>
                        <TableCell>{renderDelta(snapshotA.diversification.effectiveHoldings, snapshotB.diversification.effectiveHoldings, "", false)}</TableCell>
                      </TableRow>

                      {/* Holdings Count */}
                      <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>Total Holdings Count</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{snapshotA.holdings.length} stocks</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{snapshotB.holdings.length} stocks</TableCell>
                        <TableCell>{renderDelta(snapshotA.holdings.length, snapshotB.holdings.length, " stocks", false)}</TableCell>
                      </TableRow>

                      {/* MST Edges */}
                      <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                        <TableCell sx={{ color: "var(--white)", fontWeight: 600 }}>MST Graph Connected Edges</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotA.mstContext.edgeCount, " edges")}</TableCell>
                        <TableCell sx={{ fontFamily: "var(--font-data)" }}>{renderMetric(snapshotB.mstContext.edgeCount, " edges")}</TableCell>
                        <TableCell>{renderDelta(snapshotA.mstContext.edgeCount, snapshotB.mstContext.edgeCount, " edges", false)}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Holdings Weight Delta Table */}
                <Box sx={{ p: "var(--space-3)", bgcolor: "var(--bg)" }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-2)" }}>
                    Asset Weight Changes Across Selected Snapshots
                  </Typography>
                  {(() => {
                    const symbolsSet = new Set([
                      ...snapshotA.holdings.map((h) => h.symbol),
                      ...snapshotB.holdings.map((h) => h.symbol),
                    ]);
                    const allSymbols = Array.from(symbolsSet).sort();

                    return (
                      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                        {allSymbols.map((sym) => {
                          const wtA = snapshotA.holdings.find((h) => h.symbol === sym)?.weight ?? 0;
                          const wtB = snapshotB.holdings.find((h) => h.symbol === sym)?.weight ?? 0;
                          const diff = wtB - wtA;
                          const isZero = Math.abs(diff) < 0.05;

                          return (
                            <Chip
                              key={sym}
                              size="small"
                              label={`${sym}: ${wtA.toFixed(1)}% / ${wtB.toFixed(1)}% (${diff >= 0 ? "+" : ""}${diff.toFixed(1)}%)`}
                              sx={{
                                fontSize: "var(--text-title)",
                                fontWeight: 600,
                                borderRadius: "var(--radius)",
                                bgcolor: isZero ? "var(--line)" : diff > 0 ? "var(--line)" : "var(--gray)",
                                color: isZero ? "var(--white)" : diff > 0 ? "var(--up)" : "var(--down)",
                              }}
                            />
                          );
                        })}
                      </Stack>
                    );
                  })()}
                </Box>

                {/* Evidence-Based Change Explanation Card */}
                <Box sx={{ p: "var(--space-3)", bgcolor: "var(--line)", mt: "var(--space-2)" }}>
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: "var(--space-1)" }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
                      Evidence-Based Attribution of Changes
                    </Typography>
                    <Chip
                      size="small"
                      label="Analytical Attribution"
                      sx={{ bgcolor: "var(--bg)", color: "var(--white)", fontSize: "var(--text-title)", fontWeight: 600, borderRadius: "var(--radius)" }}
                    />
                  </Stack>
                  <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)", fontSize: "var(--text-title)" }}>
                    Decomposing observed differences between <strong>{snapshotA.name}</strong> and <strong>{snapshotB.name}</strong> using verifiable holdings, market prices, coverage metrics, and model versioning. PRISM reports <em>"insufficient evidence"</em> when underlying data points are missing.
                  </Typography>

                  <Stack spacing={1.75}>
                    {/* 1. Holdings shifts */}
                    {(() => {
                      const symsA = new Set(snapshotA.holdings.map((h) => h.symbol));
                      const symsB = new Set(snapshotB.holdings.map((h) => h.symbol));
                      const added = [...symsB].filter((s) => !symsA.has(s));
                      const exited = [...symsA].filter((s) => !symsB.has(s));
                      const rebalanced = snapshotB.holdings
                        .map((hb) => {
                          const ha = snapshotA.holdings.find((h) => h.symbol === hb.symbol);
                          if (!ha) return null;
                          const shift = hb.weight - ha.weight;
                          return Math.abs(shift) >= 1.0 ? { symbol: hb.symbol, shift } : null;
                        })
                        .filter((item): item is { symbol: string; shift: number } => item !== null);

                      return (
                        <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block" }}>
                            1. Holdings & Rebalancing Shifts:
                          </Typography>
                          <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
                            {added.length > 0 && `Added positions: ${added.join(", ")}. `}
                            {exited.length > 0 && `Liquidated / exited positions: ${exited.join(", ")}. `}
                            {rebalanced.length > 0 &&
                              `Material weight reallocations: ${rebalanced
                                .map((r) => `${r.symbol} (${r.shift >= 0 ? "+" : ""}${r.shift.toFixed(1)}%)`)
                                .join(", ")}. `}
                            {added.length === 0 && exited.length === 0 && rebalanced.length === 0 &&
                              "No material asset additions, liquidations, or weight reallocations (≥1.0%) detected between snapshots."}
                          </Typography>
                        </Box>
                      );
                    })()}

                    {/* 2. Valuation & Capital */}
                    <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                      <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block" }}>
                        2. Valuation & Capital Shifts:
                      </Typography>
                      {(() => {
                        const investedA = snapshotA.holdings.reduce((sum, h) => sum + (h.buyPrice ?? 0) * (h.quantity ?? 1), 0);
                        const investedB = snapshotB.holdings.reduce((sum, h) => sum + (h.buyPrice ?? 0) * (h.quantity ?? 1), 0);
                        if (investedA > 0 && investedB > 0) {
                          const pct = (((investedB - investedA) / investedA) * 100).toFixed(1);
                          return (
                            <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
                              Total portfolio capital shifted from ₹{investedA.toLocaleString("en-IN", { maximumFractionDigits: 0 })} to ₹{investedB.toLocaleString("en-IN", { maximumFractionDigits: 0 })} ({investedB >= investedA ? "+" : ""}{pct}%).
                            </Typography>
                          );
                        }
                        return (
                          <Typography variant="body2" sx={{ color: "var(--amber)", fontStyle: "italic", mt: "var(--space-1)" }}>
                            insufficient evidence to attribute valuation delta across historical captures.
                          </Typography>
                        );
                      })()}
                    </Box>

                    {/* 3. Risk & Volatility */}
                    <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                      <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block" }}>
                        3. Risk Profile & Volatility Shifts:
                      </Typography>
                      {snapshotA.riskMetrics?.annualizedVolatility != null && snapshotB.riskMetrics?.annualizedVolatility != null ? (
                        <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
                          Annualized volatility changed by {(snapshotB.riskMetrics.annualizedVolatility - snapshotA.riskMetrics.annualizedVolatility).toFixed(1)}% (from {snapshotA.riskMetrics.annualizedVolatility.toFixed(1)}% to {snapshotB.riskMetrics.annualizedVolatility.toFixed(1)}%). Effective independent holdings (Neff) moved from {snapshotA.diversification.effectiveHoldings?.toFixed(1) ?? "—"} to {snapshotB.diversification.effectiveHoldings?.toFixed(1) ?? "—"}.
                        </Typography>
                      ) : (
                        <Typography variant="body2" sx={{ color: "var(--amber)", fontStyle: "italic", mt: "var(--space-1)" }}>
                          insufficient evidence to determine causality for risk metrics.
                        </Typography>
                      )}
                    </Box>

                    {/* 4. Methodology & Coverage */}
                    <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                      <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block" }}>
                        4. Methodology & Data Coverage Audit:
                      </Typography>
                      <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)" }}>
                        Methodology version: {snapshotB.calculationMeta.methodologyVersion ?? "PRISM v2.1"} ({snapshotB.calculationMeta.horizon ?? 252}d empirical window, NIFTY 200 universe). Data coverage spans {snapshotA.holdings.length} symbols in Baseline vs {snapshotB.holdings.length} symbols in Comparison.
                      </Typography>
                    </Box>

                    {/* 5. Linked Journal Decisions */}
                    {decisionsSnapshotB.length > 0 && (
                      <Box sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--up)", display: "block", mb: "var(--space-1)" }}>
                          Linked Investment Decisions ({decisionsSnapshotB.length}):
                        </Typography>
                        <Stack spacing={1}>
                          {decisionsSnapshotB.map((dec) => (
                            <Box key={dec.id} sx={{ p: "var(--space-1)", bgcolor: "var(--line)" }}>
                              <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "baseline" }}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
                                  {dec.decisionType} · {dec.symbol}
                                </Typography>
                                <Typography variant="caption" sx={{ color: "var(--gray)", fontFamily: "var(--font-data)" }}>
                                  {new Date(dec.createdAt).toLocaleDateString("en-IN")}
                                </Typography>
                              </Stack>
                              <Typography variant="body2" sx={{ fontSize: "var(--text-title)", color: "var(--white)", mt: "var(--space-1)" }}>
                                {dec.rationale}
                              </Typography>
                            </Box>
                          ))}
                        </Stack>
                      </Box>
                    )}
                  </Stack>
                </Box>
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Save Snapshot Modal */}
      <Dialog
        open={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        maxWidth="sm"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, pb: "var(--space-1)", color: "var(--white)" }}>
          Save Portfolio Snapshot
          <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
            Captures current holdings ({holdings.length} stocks), risk score, volatility, HHI, and MST topology.
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: "var(--space-1)" }}>
          {saveError && (
            <Alert severity="error" sx={{ mb: "var(--space-2)", borderRadius: "var(--radius)" }} onClose={() => setSaveError(null)}>
              {saveError}
            </Alert>
          )}

          <Stack spacing={2.5}>
            <TextField
              autoFocus
              label="Snapshot Name"
              placeholder="e.g. Q4 Baseline, Post-Rate Hike Rebalance..."
              value={snapshotName}
              onChange={(e) => setSnapshotName(e.target.value)}
              fullWidth
            />

            <TextField
              multiline
              rows={3}
              label="Description / Context (Optional)"
              placeholder="Why are you taking this snapshot? What thesis or market condition prompted this allocation..."
              value={snapshotDesc}
              onChange={(e) => setSnapshotDesc(e.target.value)}
              fullWidth
            />

            <Paper sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)", boxShadow: "none" }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block", mb: "var(--space-1)" }}>
                Parameters Being Captured:
              </Typography>
              <Stack spacing={0.5} sx={{ fontSize: "var(--text-title)", color: "var(--white)" }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Total Capital:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>₹{totalInvested.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Positions:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>{holdings.length} stocks</span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Risk Score:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                    {comprehensiveRisk?.portfolio_profile?.portfolio_risk_score ?? monitoring?.portfolio_risk_score ?? "Unavailable"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Horizon:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>{analysis?.envelope?.requested_observations ?? 250} Days</span>
                </Stack>
              </Stack>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: "var(--space-3)", py: "var(--space-2)" }}>
          <Button onClick={() => setSaveModalOpen(false)} sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveSnapshot}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--up)" },
            }}
          >
            Save Snapshot
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        maxWidth="xs"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, color: "var(--white)" }}>Delete Snapshot?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "var(--gray)" }}>
            Are you sure you want to delete this historical snapshot? This action is permanent.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: "var(--space-3)", pb: "var(--space-2)" }}>
          <Button onClick={() => setDeleteConfirmId(null)} sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            sx={{
              bgcolor: "var(--down)",
              color: "var(--white)",
              fontWeight: 600,
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--down)" },
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
