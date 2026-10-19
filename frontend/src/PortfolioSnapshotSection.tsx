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
  Divider,
  FormControl,
  IconButton,
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
  Tooltip,
  Typography,
} from "@mui/material";
import {
  deletePortfolioSnapshot,
  getAllPortfolioSnapshots,
  type PortfolioSnapshot,
  savePortfolioSnapshot,
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

  // Save Modal
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [snapshotName, setSnapshotName] = useState("");
  const [snapshotDesc, setSnapshotDesc] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  // Comparison State
  const [compareIdA, setCompareIdA] = useState<string>("");
  const [compareIdB, setCompareIdB] = useState<string>("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

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

      // Calculation Meta
      const calculationMeta = {
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
        <Typography component="span" sx={{ color: "#8A5A00", fontStyle: "italic", fontSize: "0.78rem" }}>
          Not comparable (Horizon mismatch: {snapshotA?.calculationMeta.horizon}D vs {snapshotB?.calculationMeta.horizon}D)
        </Typography>
      );
    }
    if (valA === null || valA === undefined || valB === null || valB === undefined || isNaN(valA) || isNaN(valB)) {
      return (
        <Typography component="span" sx={{ color: "#686B64", fontStyle: "italic", fontSize: "0.78rem" }}>
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
          fontWeight: 700,
          color: isZero ? "#686B64" : isBetter ? "#046A38" : "#B8321A",
          fontSize: "0.82rem",
          fontFamily: "JetBrains Mono",
        }}
      >
        {diff >= 0 ? "+" : ""}{diff.toFixed(2)}{suffix}
      </Typography>
    );
  };

  const renderMetric = (val: number | null | undefined, suffix = "") => {
    if (val === null || val === undefined || isNaN(val)) {
      return (
        <Typography component="span" sx={{ color: "#686B64", fontStyle: "italic", fontSize: "0.8rem" }}>
          Unavailable
        </Typography>
      );
    }
    return `${val.toFixed(2)}${suffix}`;
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Header & Save Action */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          borderRadius: 0,
          bgcolor: "#F9EBD7",
          boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 2 }}
        >
          <Box>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                📸 Portfolio Snapshots & Audit Comparison
              </Typography>
              <Chip
                size="small"
                label={`${snapshots.length} ${snapshots.length === 1 ? "snapshot" : "snapshots"}`}
                sx={{ bgcolor: "#E3D7C4", color: "#292D2A", fontWeight: 700, borderRadius: 0 }}
              />
            </Stack>
            <Typography variant="body2" sx={{ color: "#686B64", mt: 0.5 }}>
              Capture immutable point-in-time portfolio allocations, risk metrics, and MST structures for historical comparison.
            </Typography>
          </Box>

          <Button
            variant="contained"
            onClick={handleOpenSave}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              "&:hover": { bgcolor: "#03532c" },
              textTransform: "none",
              fontWeight: 600,
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              px: 2,
            }}
          >
            + Save Snapshot Now
          </Button>
        </Stack>
      </Paper>

      {/* Snapshots Roster & Comparison Picker */}
      {snapshots.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center", bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
          <Typography variant="body2" sx={{ color: "#686B64", mb: 1.5 }}>
            No portfolio snapshots saved yet. Save a snapshot to compare portfolio states over time as weights, volatility, and market conditions shift.
          </Typography>
          <Button
            variant="contained"
            onClick={handleOpenSave}
            sx={{ textTransform: "none", fontSize: "0.85rem", bgcolor: "#046A38", color: "#F9EBD7", borderRadius: 0, boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}
          >
            Capture First Snapshot
          </Button>
        </Paper>
      ) : (
        <Card elevation={0} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 2 }}>
              Compare Any Two Snapshots
            </Typography>

            {/* Snapshot Selectors */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 3 }}>
              <FormControl size="small" sx={{ flex: 1 }}>
                <InputLabel id="snapshot-a-label">Baseline Snapshot (A)</InputLabel>
                <Select
                  labelId="snapshot-a-label"
                  label="Baseline Snapshot (A)"
                  value={compareIdA}
                  onChange={(e) => setCompareIdA(e.target.value)}
                  sx={{ borderRadius: 0 }}
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
                  sx={{ borderRadius: 0 }}
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
              <Box sx={{ borderRadius: 0, overflow: "hidden", boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}>
                <TableContainer>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>Metric</TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>
                          {snapshotA.name}
                          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
                            {new Date(snapshotA.createdAt).toLocaleDateString("en-IN")}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>
                          {snapshotB.name}
                          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
                            {new Date(snapshotB.createdAt).toLocaleDateString("en-IN")}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>Variance / Shift (B - A)</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {/* Calculation Horizon */}
                      <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Calculation Horizon</TableCell>
                        <TableCell>{snapshotA.calculationMeta.horizon} Days</TableCell>
                        <TableCell>{snapshotB.calculationMeta.horizon} Days</TableCell>
                        <TableCell>
                          {snapshotA.calculationMeta.horizon === snapshotB.calculationMeta.horizon ? (
                            <Chip size="small" label="Identical Horizon" sx={{ bgcolor: "#DCE9DE", color: "#046A38", height: 20, fontSize: "0.7rem", borderRadius: 0, fontWeight: 600 }} />
                          ) : (
                            <Chip size="small" label="Differing Horizon" sx={{ bgcolor: "#F6D9CC", color: "#B8321A", height: 20, fontSize: "0.7rem", borderRadius: 0, fontWeight: 600 }} />
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Portfolio Risk Score */}
                      <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Portfolio Risk Score</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>
                          {snapshotA.riskMetrics.portfolioRiskScore !== null
                            ? `${renderMetric(snapshotA.riskMetrics.portfolioRiskScore)} (${snapshotA.riskMetrics.portfolioClassification || "Normal"})`
                            : renderMetric(null)}
                        </TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>
                          {snapshotB.riskMetrics.portfolioRiskScore !== null
                            ? `${renderMetric(snapshotB.riskMetrics.portfolioRiskScore)} (${snapshotB.riskMetrics.portfolioClassification || "Normal"})`
                            : renderMetric(null)}
                        </TableCell>
                        <TableCell>
                          {renderDelta(snapshotA.riskMetrics.portfolioRiskScore, snapshotB.riskMetrics.portfolioRiskScore, "", false)}
                        </TableCell>
                      </TableRow>

                      {/* Annualized Volatility */}
                      <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Annualized Volatility</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotA.riskMetrics.annualizedVolatility ? snapshotA.riskMetrics.annualizedVolatility * 100 : null, "%")}</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotB.riskMetrics.annualizedVolatility ? snapshotB.riskMetrics.annualizedVolatility * 100 : null, "%")}</TableCell>
                        <TableCell>
                          {renderDelta(
                            snapshotA.riskMetrics.annualizedVolatility ? snapshotA.riskMetrics.annualizedVolatility * 100 : null,
                            snapshotB.riskMetrics.annualizedVolatility ? snapshotB.riskMetrics.annualizedVolatility * 100 : null,
                            "%"
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Max Drawdown */}
                      <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Max Drawdown</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotA.riskMetrics.maxDrawdown ? snapshotA.riskMetrics.maxDrawdown * 100 : null, "%")}</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotB.riskMetrics.maxDrawdown ? snapshotB.riskMetrics.maxDrawdown * 100 : null, "%")}</TableCell>
                        <TableCell>
                          {renderDelta(
                            snapshotA.riskMetrics.maxDrawdown ? snapshotA.riskMetrics.maxDrawdown * 100 : null,
                            snapshotB.riskMetrics.maxDrawdown ? snapshotB.riskMetrics.maxDrawdown * 100 : null,
                            "%"
                          )}
                        </TableCell>
                      </TableRow>

                      {/* Holding HHI Concentration */}
                      <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Holding Concentration (HHI)</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotA.diversification.holdingHhi)}</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotB.diversification.holdingHhi)}</TableCell>
                        <TableCell>{renderDelta(snapshotA.diversification.holdingHhi, snapshotB.diversification.holdingHhi, "", false)}</TableCell>
                      </TableRow>

                      {/* Effective Holdings */}
                      <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Effective Independent Bets (Neff)</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotA.diversification.effectiveHoldings)}</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotB.diversification.effectiveHoldings)}</TableCell>
                        <TableCell>{renderDelta(snapshotA.diversification.effectiveHoldings, snapshotB.diversification.effectiveHoldings, "", false)}</TableCell>
                      </TableRow>

                      {/* Holdings Count */}
                      <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>Total Holdings Count</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{snapshotA.holdings.length} stocks</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{snapshotB.holdings.length} stocks</TableCell>
                        <TableCell>{renderDelta(snapshotA.holdings.length, snapshotB.holdings.length, " stocks", false)}</TableCell>
                      </TableRow>

                      {/* MST Edges */}
                      <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                        <TableCell sx={{ color: "#292D2A", fontWeight: 600 }}>MST Graph Connected Edges</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotA.mstContext.edgeCount, " edges")}</TableCell>
                        <TableCell sx={{ fontFamily: "JetBrains Mono" }}>{renderMetric(snapshotB.mstContext.edgeCount, " edges")}</TableCell>
                        <TableCell>{renderDelta(snapshotA.mstContext.edgeCount, snapshotB.mstContext.edgeCount, " edges", false)}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Holdings Weight Delta Table */}
                <Box sx={{ p: 2.5, bgcolor: "#F9EBD7" }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 1.5 }}>
                    Asset Weight Changes Across Selected Snapshots
                  </Typography>
                  {(() => {
                    const symbolsSet = new Set([
                      ...snapshotA.holdings.map((h) => h.symbol),
                      ...snapshotB.holdings.map((h) => h.symbol),
                    ]);
                    const allSymbols = Array.from(symbolsSet).sort();

                    return (
                      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                        {allSymbols.map((sym) => {
                          const wtA = snapshotA.holdings.find((h) => h.symbol === sym)?.weight ?? 0;
                          const wtB = snapshotB.holdings.find((h) => h.symbol === sym)?.weight ?? 0;
                          const diff = wtB - wtA;
                          const isZero = Math.abs(diff) < 0.05;

                          return (
                            <Chip
                              key={sym}
                              size="small"
                              label={`${sym}: ${wtA.toFixed(1)}% → ${wtB.toFixed(1)}% (${diff >= 0 ? "+" : ""}${diff.toFixed(1)}%)`}
                              sx={{
                                fontSize: "0.75rem",
                                fontWeight: 600,
                                borderRadius: 0,
                                bgcolor: isZero ? "#E3D7C4" : diff > 0 ? "#DCE9DE" : "#F6D9CC",
                                color: isZero ? "#292D2A" : diff > 0 ? "#046A38" : "#B8321A",
                              }}
                            />
                          );
                        })}
                      </Stack>
                    );
                  })()}
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
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
              color: "#292D2A",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
          Save Portfolio Snapshot
          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
            Captures current holdings ({holdings.length} stocks), risk score, volatility, HHI, and MST topology.
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          {saveError && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 0 }} onClose={() => setSaveError(null)}>
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

            <Paper sx={{ p: 2, bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 2px 6px rgba(41,45,42,0.08)" }}>
              <Typography variant="caption" sx={{ fontWeight: 700, color: "#292D2A", display: "block", mb: 1 }}>
                Parameters Being Captured:
              </Typography>
              <Stack spacing={0.5} sx={{ fontSize: "0.8rem", color: "#292D2A" }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Total Capital:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>₹{totalInvested.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Positions:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>{holdings.length} stocks</span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Risk Score:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                    {comprehensiveRisk?.portfolio_profile?.portfolio_risk_score ?? monitoring?.portfolio_risk_score ?? "Unavailable"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Horizon:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>{analysis?.envelope?.requested_observations ?? 250} Days</span>
                </Stack>
              </Stack>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setSaveModalOpen(false)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveSnapshot}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#03532c" },
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
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
              color: "#292D2A",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: "#292D2A" }}>Delete Snapshot?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "#686B64" }}>
            Are you sure you want to delete this historical snapshot? This action is permanent.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, pb: 2 }}>
          <Button onClick={() => setDeleteConfirmId(null)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            sx={{
              bgcolor: "#E34222",
              color: "#F9EBD7",
              fontWeight: 700,
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#b8321a" },
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
