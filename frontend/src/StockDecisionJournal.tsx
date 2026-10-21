import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  DecisionContextSnapshot,
  DecisionType,
  deleteDecision,
  getDecisionsBySymbol,
  InvestmentDecision,
  saveDecision,
} from "./journalStorage";

export interface CurrentMetricsContext {
  riskScore?: number | null;
  riskLabel?: string | null;
  sectorDivergenceScore?: number | null;
  sectorDivergenceHorizon?: number | null;
  portfolioWeight?: number | null;
  mstCluster?: string | null;
}

export interface StockDecisionJournalProps {
  symbol: string;
  currentMetrics?: CurrentMetricsContext;
  defaultExpanded?: boolean;
  onDecisionsCountChange?: (count: number) => void;
  externalSearchQuery?: string;
}

export default function StockDecisionJournal({
  symbol,
  currentMetrics,
  defaultExpanded = true,
  onDecisionsCountChange,
  externalSearchQuery,
}: StockDecisionJournalProps) {
  const normSymbol = symbol.trim().toUpperCase();
  const [decisions, setDecisions] = useState<InvestmentDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Dialog State
  const [dialogOpen, setDialogOpen] = useState(false);
  const [decisionType, setDecisionType] = useState<DecisionType>("Hold");
  const [decisionDate, setDecisionDate] = useState(() => new Date().toISOString().substring(0, 10));
  const [rationale, setRationale] = useState("");
  const [customTagInput, setCustomTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Delete State
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Search filter
  const [searchQuery, setSearchQuery] = useState("");
  const effectiveQuery = (externalSearchQuery !== undefined ? externalSearchQuery : searchQuery).trim().toLowerCase();
  const filteredDecisions = useMemo(() => {
    return decisions.filter((d) => {
      if (!effectiveQuery) return true;
      return (
        d.rationale.toLowerCase().includes(effectiveQuery) ||
        d.tags.some((t) => t.toLowerCase().includes(effectiveQuery)) ||
        d.decisionType.toLowerCase().includes(effectiveQuery)
      );
    });
  }, [decisions, effectiveQuery]);

  const loadDecisions = async () => {
    setLoading(true);
    try {
      const data = await getDecisionsBySymbol(normSymbol);
      setDecisions(data);
      if (onDecisionsCountChange) {
        onDecisionsCountChange(data.length);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDecisions();
  }, [normSymbol]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleOpenCreate = () => {
    setDecisionType("Hold");
    setDecisionDate(new Date().toISOString().substring(0, 10));
    setRationale("");
    setTags([]);
    setCustomTagInput("");
    setErrorMsg(null);
    setDialogOpen(true);
  };

  const handleAddTag = () => {
    const trimmed = customTagInput.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags((prev) => [...prev, trimmed]);
      setCustomTagInput("");
    }
  };

  const handleRemoveTag = (t: string) => {
    setTags((prev) => prev.filter((item) => item !== t));
  };

  const handleSaveDecision = async () => {
    if (!rationale.trim()) {
      setErrorMsg("Please provide an investment thesis or rationale for this decision.");
      return;
    }

    try {
      // Capture context snapshot at creation time.
      // Strict rule: Use null for any unavailable value. Never substitute current values for missing history. Never store unavailable as 0.
      const snapshot: DecisionContextSnapshot = {
        riskScore: typeof currentMetrics?.riskScore === "number" ? currentMetrics.riskScore : null,
        riskLabel: currentMetrics?.riskLabel || null,
        sectorDivergenceScore:
          typeof currentMetrics?.sectorDivergenceScore === "number"
            ? currentMetrics.sectorDivergenceScore
            : null,
        sectorDivergenceHorizon:
          typeof currentMetrics?.sectorDivergenceHorizon === "number"
            ? currentMetrics.sectorDivergenceHorizon
            : null,
        portfolioWeight:
          typeof currentMetrics?.portfolioWeight === "number"
            ? currentMetrics.portfolioWeight
            : null,
        mstCluster: currentMetrics?.mstCluster || null,
        capturedAt: new Date().toISOString(),
      };

      await saveDecision({
        symbol: normSymbol,
        decisionType,
        decisionDate,
        rationale: rationale.trim(),
        tags,
        snapshot,
      });

      setDialogOpen(false);
      await loadDecisions();
    } catch {
      setErrorMsg("Failed to save investment decision. Please try again.");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDecision(id);
      setDeleteConfirmId(null);
      await loadDecisions();
    } catch {
      // Graceful fallback
    }
  };

  const renderMetricValue = (val: number | null | undefined, suffix = "") => {
    if (val === null || val === undefined || isNaN(val)) {
      return (
        <Typography component="span" sx={{ color: "#686B64", fontStyle: "italic", fontSize: "0.8rem" }}>
          Unavailable
        </Typography>
      );
    }
    return `${val > 0 && suffix.includes("σ") ? "+" : ""}${val.toFixed(2)}${suffix}`;
  };

  const renderStringValue = (val: string | null | undefined) => {
    if (!val || !val.trim()) {
      return (
        <Typography component="span" sx={{ color: "#686B64", fontStyle: "italic", fontSize: "0.8rem" }}>
          Unavailable
        </Typography>
      );
    }
    return val;
  };

  return (
    <Paper
      id="decision-journal-section"
      elevation={0}
      sx={{
        p: { xs: 2, sm: 2.5 },
        bgcolor: "#F9EBD7",
        borderRadius: 0,
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
      }}
    >
      {/* Header */}
      <Stack
        direction="row"
        sx={{
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1.05rem", color: "#292D2A" }}>
            📓 Investment Decision Journal
          </Typography>
          <Chip
            size="small"
            label={`${decisions.length} ${decisions.length === 1 ? "decision" : "decisions"}`}
            sx={{
              bgcolor: decisions.length > 0 ? "#DCE9DE" : "#E3D7C4",
              color: decisions.length > 0 ? "#046A38" : "#292D2A",
              fontWeight: 700,
              fontSize: "0.75rem",
              borderRadius: 0,
            }}
          />
        </Stack>

        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Button
            size="small"
            variant="contained"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(true);
              handleOpenCreate();
            }}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              fontSize: "0.8rem",
              py: 0.5,
              px: 1.5,
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            + Record Decision
          </Button>
          <IconButton size="small" sx={{ color: "#686B64", borderRadius: 0 }}>
            {expanded ? "▲" : "▼"}
          </IconButton>
        </Stack>
      </Stack>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ mt: 2.5 }}>
          {loading ? (
            <Typography variant="body2" sx={{ color: "#686B64", py: 2 }}>
              Loading decision journal...
            </Typography>
          ) : decisions.length === 0 ? (
            <Box
              sx={{
                p: 3,
                textAlign: "center",
                bgcolor: "#F9EBD7",
                borderRadius: 0,
                boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
              }}
            >
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1 }}>
                No investment decisions logged for {normSymbol} yet.
              </Typography>
              <Typography variant="caption" sx={{ color: "#686B64", display: "block", mb: 1.5 }}>
                Recording a decision captures the current risk score, divergence, and portfolio weight at that point in time for future review.
              </Typography>
              <Button
                size="small"
                variant="contained"
                onClick={handleOpenCreate}
                sx={{ fontSize: "0.8rem", bgcolor: "#046A38", color: "#F9EBD7", borderRadius: 0, boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}
              >
                Log First Decision
              </Button>
            </Box>
          ) : (
            <Stack spacing={2}>
              {externalSearchQuery === undefined && decisions.length > 0 && (
                <TextField
                  size="small"
                  placeholder={`Search decisions & rationale for ${normSymbol}...`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  sx={{ "& .MuiInputBase-input": { fontSize: "0.85rem" } }}
                  slotProps={{
                    input: {
                      startAdornment: (
                        <InputAdornment position="start" sx={{ color: "#686B64", fontSize: "0.85rem" }}>
                          🔍
                        </InputAdornment>
                      ),
                    },
                  }}
                />
              )}

              {filteredDecisions.length === 0 ? (
                <Typography variant="body2" sx={{ color: "#686B64", py: 2, textAlign: "center" }}>
                  No decisions match "{effectiveQuery}".
                </Typography>
              ) : (
                filteredDecisions.map((decision) => {
                  const typeColors = {
                    Buy: { bg: "#DCE9DE", text: "#046A38" },
                    Sell: { bg: "#F6D9CC", text: "#B8321A" },
                    Hold: { bg: "#E3D7C4", text: "#292D2A" },
                    Review: { bg: "#F9EBD7", text: "#8A5A00" },
                  }[decision.decisionType] || { bg: "#E3D7C4", text: "#292D2A" };

                  return (
                    <Paper
                      key={decision.id}
                      elevation={0}
                      sx={{
                        p: 2,
                        bgcolor: "#F9EBD7",
                        borderRadius: 0,
                        boxShadow: "0 3px 8px rgba(41,45,42,0.08)",
                      }}
                    >
                      {/* Top Bar: Type, Date, Tags, Delete */}
                      <Stack
                        direction="row"
                        sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 1.5 }}
                      >
                        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                          <Chip
                            size="small"
                            label={decision.decisionType.toUpperCase()}
                            sx={{
                              fontWeight: 700,
                              fontSize: "0.75rem",
                              height: 24,
                              borderRadius: 0,
                              bgcolor: typeColors.bg,
                              color: typeColors.text,
                            }}
                          />
                          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
                            {decision.decisionDate}
                          </Typography>
                          {decision.tags.map((tag) => (
                            <Chip
                              key={tag}
                              label={tag}
                              size="small"
                              sx={{ fontSize: "0.7rem", height: 20, borderRadius: 0, bgcolor: "#E3D7C4", color: "#292D2A" }}
                            />
                          ))}
                        </Stack>

                        <Tooltip title="Delete decision entry">
                          <IconButton
                            size="small"
                            onClick={() => setDeleteConfirmId(decision.id)}
                            sx={{ color: "#686B64", borderRadius: 0, "&:hover": { color: "#B8321A" } }}
                          >
                            <span style={{ fontSize: "0.85rem" }}>🗑️</span>
                          </IconButton>
                        </Tooltip>
                      </Stack>

                      {/* Rationale */}
                      <Typography
                        variant="body2"
                        sx={{
                          whiteSpace: "pre-wrap",
                          color: "#292D2A",
                          lineHeight: 1.6,
                          fontSize: "0.9rem",
                          mb: 2,
                        }}
                      >
                        {decision.rationale}
                      </Typography>

                      {/* Point-in-time Snapshot vs Current Metrics Comparison Table */}
                      <Box
                        sx={{
                          bgcolor: "#F9EBD7",
                          borderRadius: 0,
                          overflow: "hidden",
                          boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
                        }}
                      >
                        <Box sx={{ px: 1.5, py: 0.8, bgcolor: "#E3D7C4" }}>
                          <Typography variant="caption" sx={{ fontWeight: 700, color: "#292D2A" }}>
                            📊 Metrics Comparison: Snapshot at Decision vs. Current
                          </Typography>
                        </Box>
                        <Table size="small" sx={{ "& .MuiTableCell-root": { py: 0.8, px: 1.5, fontSize: "0.8rem", color: "#292D2A" } }}>
                          <TableHead>
                            <TableRow sx={{ bgcolor: "#F9EBD7" }}>
                              <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>Metric</TableCell>
                              <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>At Decision ({decision.decisionDate})</TableCell>
                              <TableCell sx={{ fontWeight: 700, color: "#292D2A" }}>Current Condition</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                              <TableCell sx={{ color: "#686B64", fontWeight: 600 }}>Risk Score</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {decision.snapshot.riskScore !== null ? (
                                  <>
                                    {decision.snapshot.riskScore}{" "}
                                    {decision.snapshot.riskLabel && `(${decision.snapshot.riskLabel})`}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {currentMetrics?.riskScore !== null && currentMetrics?.riskScore !== undefined ? (
                                  <>
                                    {currentMetrics.riskScore}{" "}
                                    {currentMetrics.riskLabel && `(${currentMetrics.riskLabel})`}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                            </TableRow>

                            <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                              <TableCell sx={{ color: "#686B64", fontWeight: 600 }}>Sector Divergence</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {decision.snapshot.sectorDivergenceScore !== null ? (
                                  <>
                                    {renderMetricValue(decision.snapshot.sectorDivergenceScore, "σ")}
                                    {decision.snapshot.sectorDivergenceHorizon && (
                                      <Typography component="span" variant="caption" sx={{ ml: 0.5, color: "#686B64" }}>
                                        ({decision.snapshot.sectorDivergenceHorizon}D)
                                      </Typography>
                                    )}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {currentMetrics?.sectorDivergenceScore !== null && currentMetrics?.sectorDivergenceScore !== undefined ? (
                                  <>
                                    {renderMetricValue(currentMetrics.sectorDivergenceScore, "σ")}
                                    {currentMetrics.sectorDivergenceHorizon && (
                                      <Typography component="span" variant="caption" sx={{ ml: 0.5, color: "#686B64" }}>
                                        ({currentMetrics.sectorDivergenceHorizon}D)
                                      </Typography>
                                    )}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                            </TableRow>

                            <TableRow sx={{ "&:hover": { bgcolor: "#E3D7C4" } }}>
                              <TableCell sx={{ color: "#686B64", fontWeight: 600 }}>Portfolio Weight</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {renderMetricValue(decision.snapshot.portfolioWeight, "%")}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                                {renderMetricValue(currentMetrics?.portfolioWeight, "%")}
                              </TableCell>
                            </TableRow>

                            <TableRow sx={{ bgcolor: "#F9EBD7", "&:hover": { bgcolor: "#E3D7C4" } }}>
                              <TableCell sx={{ color: "#686B64", fontWeight: 600 }}>MST Cluster Context</TableCell>
                              <TableCell sx={{ fontWeight: 600 }}>
                                {renderStringValue(decision.snapshot.mstCluster)}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600 }}>
                                {renderStringValue(currentMetrics?.mstCluster)}
                              </TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                      </Box>
                    </Paper>
                  );
                })
              )}
            </Stack>
          )}
        </Box>
      </Collapse>

      {/* Record Decision Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
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
          Record Investment Decision: {normSymbol}
          <Typography variant="caption" sx={{ display: "block", color: "#686B64", fontWeight: 400 }}>
            Captures current market metrics alongside your thesis. This entry is separate from portfolio trades and will not alter your holdings.
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 0 }} onClose={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          <Stack spacing={2.5}>
            {/* Decision Type & Date in a row */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="decision-type-label">Decision Type</InputLabel>
                <Select
                  labelId="decision-type-label"
                  label="Decision Type"
                  value={decisionType}
                  onChange={(e) => setDecisionType(e.target.value as DecisionType)}
                  sx={{ borderRadius: 0 }}
                >
                  <MenuItem value="Buy">🟢 Buy</MenuItem>
                  <MenuItem value="Hold">🔵 Hold</MenuItem>
                  <MenuItem value="Sell">🔴 Sell</MenuItem>
                  <MenuItem value="Review">🟡 Review</MenuItem>
                </Select>
              </FormControl>

              <TextField
                size="small"
                label="Decision Date"
                type="date"
                value={decisionDate}
                onChange={(e) => setDecisionDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ flex: 1 }}
              />
            </Stack>

            {/* Rationale multiline */}
            <TextField
              multiline
              rows={4}
              label="Investment Rationale & Thesis"
              placeholder="Detail your reasons for this decision (e.g. valuation multiple discount, divergence exhaustion, balance sheet strength)..."
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              sx={{ "& .MuiInputBase-input": { fontSize: "0.9rem", lineHeight: 1.6 } }}
            />

            {/* Optional Tags */}
            <Box>
              <Typography variant="caption" sx={{ color: "#292D2A", fontWeight: 700, display: "block", mb: 0.5 }}>
                Decision Tags (Optional)
              </Typography>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <TextField
                  size="small"
                  placeholder="e.g. Quarterly Rebalance, Stop Loss, High Conviction..."
                  value={customTagInput}
                  onChange={(e) => setCustomTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                  sx={{ flex: 1 }}
                />
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleAddTag}
                  disabled={!customTagInput.trim()}
                  sx={{ bgcolor: "#046A38", color: "#F9EBD7", borderRadius: 0, boxShadow: "0 3px 8px rgba(41,45,42,0.10)" }}
                >
                  Add
                </Button>
              </Stack>
              {tags.length > 0 && (
                <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mt: 1 }}>
                  {tags.map((t) => (
                    <Chip key={t} label={t} size="small" onDelete={() => handleRemoveTag(t)} sx={{ height: 24, borderRadius: 0, bgcolor: "#E3D7C4", color: "#292D2A" }} />
                  ))}
                </Stack>
              )}
            </Box>

            {/* Live Snapshot Preview */}
            <Paper sx={{ p: 2, bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 2px 6px rgba(41,45,42,0.08)" }}>
              <Typography variant="caption" sx={{ fontWeight: 700, color: "#292D2A", display: "block", mb: 1 }}>
                📸 Snapshot Being Captured Right Now:
              </Typography>
              <Stack spacing={0.5} sx={{ fontSize: "0.8rem", color: "#292D2A" }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Risk Score:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                    {currentMetrics?.riskScore !== null && currentMetrics?.riskScore !== undefined
                      ? `${currentMetrics.riskScore} (${currentMetrics.riskLabel || "Standard"})`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Sector Divergence:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                    {currentMetrics?.sectorDivergenceScore !== null && currentMetrics?.sectorDivergenceScore !== undefined
                      ? `${currentMetrics.sectorDivergenceScore > 0 ? "+" : ""}${currentMetrics.sectorDivergenceScore.toFixed(2)}σ`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>Portfolio Weight:</span>
                  <span style={{ fontWeight: 600, fontFamily: "JetBrains Mono" }}>
                    {currentMetrics?.portfolioWeight !== null && currentMetrics?.portfolioWeight !== undefined
                      ? `${currentMetrics.portfolioWeight.toFixed(2)}%`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "#686B64" }}>MST Cluster:</span>
                  <span style={{ fontWeight: 600 }}>
                    {currentMetrics?.mstCluster || "Unavailable (stored as null)"}
                  </span>
                </Stack>
              </Stack>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveDecision}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              borderRadius: 0,
              boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            Record Decision
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
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
        <DialogTitle sx={{ fontWeight: 700, color: "#292D2A" }}>Delete Decision Record?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "#686B64" }}>
            Are you sure you want to remove this journal decision entry? This action cannot be undone.
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
    </Paper>
  );
}
