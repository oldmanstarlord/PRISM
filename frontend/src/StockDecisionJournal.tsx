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
        <Typography component="span" sx={{ color: "var(--gray)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
          Unavailable
        </Typography>
      );
    }
    return `${val > 0 && suffix.includes("σ") ? "+" : ""}${val.toFixed(2)}${suffix}`;
  };

  const renderStringValue = (val: string | null | undefined) => {
    if (!val || !val.trim()) {
      return (
        <Typography component="span" sx={{ color: "var(--gray)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
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
        bgcolor: "var(--bg)",
        borderRadius: "var(--radius)",
        boxShadow: "none",
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
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: "var(--text-title)", color: "var(--white)" }}>
             Investment Decision Journal
          </Typography>
          <Chip
            size="small"
            label={`${decisions.length} ${decisions.length === 1 ? "decision" : "decisions"}`}
            sx={{
              bgcolor: decisions.length > 0 ? "var(--line)" : "var(--line)",
              color: decisions.length > 0 ? "var(--up)" : "var(--white)",
              fontWeight: 600,
              fontSize: "var(--text-title)",
              borderRadius: "var(--radius)",
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
              bgcolor: "var(--up)", color: "var(--line)",
              fontSize: "var(--text-title)",
              py: "var(--space-1)",
              px: "var(--space-2)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--up)" },
            }}
          >
            + Record Decision
          </Button>
          <IconButton aria-label={expanded ? "Hide decision history" : "Show decision history"} aria-expanded={expanded} size="small" sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            {expanded ? "▲" : "▼"}
          </IconButton>
        </Stack>
      </Stack>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ mt: "var(--space-3)" }}>
          {loading ? (
            <Typography variant="body2" sx={{ color: "var(--gray)", py: "var(--space-2)" }}>
              Loading decision journal...
            </Typography>
          ) : decisions.length === 0 ? (
            <Box
              sx={{
                p: "var(--space-3)",
                textAlign: "center",
                bgcolor: "var(--bg)",
                borderRadius: "var(--radius)",
                boxShadow: "none",
              }}
            >
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-1)" }}>
                No investment decisions logged for {normSymbol} yet.
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--gray)", display: "block", mb: "var(--space-2)" }}>
                Recording a decision captures the current risk score, divergence, and portfolio weight at that point in time for future review.
              </Typography>
              <Button
                size="small"
                variant="contained"
                onClick={handleOpenCreate}
                sx={{ fontSize: "var(--text-title)", bgcolor: "var(--up)", color: "var(--line)", borderRadius: "var(--radius)", boxShadow: "none" }}
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
                  sx={{ "& .MuiInputBase-input": { fontSize: "var(--text-title)" } }}
                />
              )}

              {filteredDecisions.length === 0 ? (
                <Typography variant="body2" sx={{ color: "var(--gray)", py: "var(--space-2)", textAlign: "center" }}>
                  No decisions match "{effectiveQuery}".
                </Typography>
              ) : (
                filteredDecisions.map((decision) => {
                  const typeColors = {
                    Buy: { bg: "var(--line)", text: "var(--up)" },
                    Sell: { bg: "var(--gray)", text: "var(--down)" },
                    Hold: { bg: "var(--line)", text: "var(--white)" },
                    Review: { bg: "var(--bg)", text: "var(--amber)" },
                  }[decision.decisionType] || { bg: "var(--line)", text: "var(--white)" };

                  return (
                    <Paper
                      key={decision.id}
                      elevation={0}
                      sx={{
                        p: "var(--space-2)",
                        bgcolor: "var(--bg)",
                        borderRadius: "var(--radius)",
                        boxShadow: "none",
                      }}
                    >
                      {/* Top Bar: Type, Date, Tags, Delete */}
                      <Stack
                        direction="row"
                        sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: "var(--space-2)" }}
                      >
                        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                          <Chip
                            size="small"
                            label={decision.decisionType.toUpperCase()}
                            sx={{
                              fontWeight: 600,
                              fontSize: "var(--text-title)",
                              height: 24,
                              borderRadius: "var(--radius)",
                              bgcolor: typeColors.bg,
                              color: typeColors.text,
                            }}
                          />
                          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
                            {decision.decisionDate}
                          </Typography>
                          {decision.tags.map((tag) => (
                            <Chip
                              key={tag}
                              label={tag}
                              size="small"
                              sx={{ fontSize: "var(--text-title)", height: 20, borderRadius: "var(--radius)", bgcolor: "var(--line)", color: "var(--white)" }}
                            />
                          ))}
                        </Stack>

                        <Tooltip title="Delete decision entry">
                          <IconButton
                            size="small"
                            onClick={() => setDeleteConfirmId(decision.id)}
                            sx={{ color: "var(--gray)", borderRadius: "var(--radius)", "&:hover": { color: "var(--down)" }, fontSize: "var(--text-title)", fontWeight: 600 }}
                          >
                            Delete
                          </IconButton>
                        </Tooltip>
                      </Stack>

                      {/* Rationale */}
                      <Typography
                        variant="body2"
                        sx={{
                          whiteSpace: "pre-wrap",
                          color: "var(--white)",
                          lineHeight: "var(--leading)",
                          fontSize: "var(--text-title)",
                          mb: "var(--space-2)",
                        }}
                      >
                        {decision.rationale}
                      </Typography>

                      {/* Point-in-time Snapshot vs Current Metrics Comparison Table */}
                      <Box
                        sx={{
                          bgcolor: "var(--bg)",
                          borderRadius: "var(--radius)",
                          overflow: "hidden",
                          boxShadow: "none",
                        }}
                      >
                        <Box sx={{ px: "var(--space-2)", py: "var(--space-1)", bgcolor: "var(--line)" }}>
                          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)" }}>
                            Metrics Comparison: Snapshot at Decision vs. Current
                          </Typography>
                        </Box>
                        <Table size="small" sx={{ "& .MuiTableCell-root": { py: "var(--space-1)", px: "var(--space-2)", fontSize: "var(--text-title)", color: "var(--white)" } }}>
                          <TableHead>
                            <TableRow sx={{ bgcolor: "var(--bg)" }}>
                              <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>Metric</TableCell>
                              <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>At Decision ({decision.decisionDate})</TableCell>
                              <TableCell sx={{ fontWeight: 600, color: "var(--white)" }}>Current Condition</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                              <TableCell sx={{ color: "var(--gray)", fontWeight: 600 }}>Risk Score</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                                {decision.snapshot.riskScore !== null ? (
                                  <>
                                    {decision.snapshot.riskScore}{" "}
                                    {decision.snapshot.riskLabel && `(${decision.snapshot.riskLabel})`}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
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

                            <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                              <TableCell sx={{ color: "var(--gray)", fontWeight: 600 }}>Sector Divergence</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                                {decision.snapshot.sectorDivergenceScore !== null ? (
                                  <>
                                    {renderMetricValue(decision.snapshot.sectorDivergenceScore, "σ")}
                                    {decision.snapshot.sectorDivergenceHorizon && (
                                      <Typography component="span" variant="caption" sx={{ ml: "var(--space-1)", color: "var(--gray)" }}>
                                        ({decision.snapshot.sectorDivergenceHorizon}D)
                                      </Typography>
                                    )}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                                {currentMetrics?.sectorDivergenceScore !== null && currentMetrics?.sectorDivergenceScore !== undefined ? (
                                  <>
                                    {renderMetricValue(currentMetrics.sectorDivergenceScore, "σ")}
                                    {currentMetrics.sectorDivergenceHorizon && (
                                      <Typography component="span" variant="caption" sx={{ ml: "var(--space-1)", color: "var(--gray)" }}>
                                        ({currentMetrics.sectorDivergenceHorizon}D)
                                      </Typography>
                                    )}
                                  </>
                                ) : (
                                  renderMetricValue(null)
                                )}
                              </TableCell>
                            </TableRow>

                            <TableRow sx={{ "&:hover": { bgcolor: "var(--line)" } }}>
                              <TableCell sx={{ color: "var(--gray)", fontWeight: 600 }}>Portfolio Weight</TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                                {renderMetricValue(decision.snapshot.portfolioWeight, "%")}
                              </TableCell>
                              <TableCell sx={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                                {renderMetricValue(currentMetrics?.portfolioWeight, "%")}
                              </TableCell>
                            </TableRow>

                            <TableRow sx={{ bgcolor: "var(--bg)", "&:hover": { bgcolor: "var(--line)" } }}>
                              <TableCell sx={{ color: "var(--gray)", fontWeight: 600 }}>MST Cluster Context</TableCell>
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
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, pb: "var(--space-1)", color: "var(--white)" }}>
          Record Investment Decision: {normSymbol}
          <Typography variant="caption" sx={{ display: "block", color: "var(--gray)", fontWeight: 400 }}>
            Captures current market metrics alongside your thesis. This entry is separate from portfolio trades and will not alter your holdings.
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: "var(--space-1)" }}>
          {errorMsg && (
            <Alert severity="error" sx={{ mb: "var(--space-2)", borderRadius: "var(--radius)" }} onClose={() => setErrorMsg(null)}>
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
                  sx={{ borderRadius: "var(--radius)" }}
                >
                  <MenuItem value="Buy"> Buy</MenuItem>
                  <MenuItem value="Hold"> Hold</MenuItem>
                  <MenuItem value="Sell"> Sell</MenuItem>
                  <MenuItem value="Review"> Review</MenuItem>
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
              sx={{ "& .MuiInputBase-input": { fontSize: "var(--text-title)", lineHeight: "var(--leading)" } }}
            />

            {/* Optional Tags */}
            <Box>
              <Typography variant="caption" sx={{ color: "var(--white)", fontWeight: 600, display: "block", mb: "var(--space-1)" }}>
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
                  sx={{ bgcolor: "var(--up)", color: "var(--line)", borderRadius: "var(--radius)", boxShadow: "none" }}
                >
                  Add
                </Button>
              </Stack>
              {tags.length > 0 && (
                <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: "var(--space-1)", mt: "var(--space-1)" }}>
                  {tags.map((t) => (
                    <Chip key={t} label={t} size="small" onDelete={() => handleRemoveTag(t)} sx={{ height: 24, borderRadius: "var(--radius)", bgcolor: "var(--line)", color: "var(--white)" }} />
                  ))}
                </Stack>
              )}
            </Box>

            {/* Live Snapshot Preview */}
            <Paper sx={{ p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)", boxShadow: "none" }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--white)", display: "block", mb: "var(--space-1)" }}>
                Snapshot Being Captured Right Now:
              </Typography>
              <Stack spacing={0.5} sx={{ fontSize: "var(--text-title)", color: "var(--white)" }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Risk Score:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                    {currentMetrics?.riskScore !== null && currentMetrics?.riskScore !== undefined
                      ? `${currentMetrics.riskScore} (${currentMetrics.riskLabel || "Standard"})`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Sector Divergence:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                    {currentMetrics?.sectorDivergenceScore !== null && currentMetrics?.sectorDivergenceScore !== undefined
                      ? `${currentMetrics.sectorDivergenceScore > 0 ? "+" : ""}${currentMetrics.sectorDivergenceScore.toFixed(2)}σ`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>Portfolio Weight:</span>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-data)" }}>
                    {currentMetrics?.portfolioWeight !== null && currentMetrics?.portfolioWeight !== undefined
                      ? `${currentMetrics.portfolioWeight.toFixed(2)}%`
                      : "Unavailable (stored as null)"}
                  </span>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <span style={{ color: "var(--gray)" }}>MST Cluster:</span>
                  <span style={{ fontWeight: 600 }}>
                    {currentMetrics?.mstCluster || "Unavailable (stored as null)"}
                  </span>
                </Stack>
              </Stack>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: "var(--space-3)", py: "var(--space-2)" }}>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: "var(--gray)", borderRadius: "var(--radius)" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveDecision}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              borderRadius: "var(--radius)",
              boxShadow: "none",
              "&:hover": { bgcolor: "var(--up)" },
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
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, color: "var(--white)" }}>Delete Decision Record?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: "var(--gray)" }}>
            Are you sure you want to remove this journal decision entry? This action cannot be undone.
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
    </Paper>
  );
}
