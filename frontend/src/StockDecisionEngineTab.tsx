import React, { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";

import type { PortfolioHolding } from "./PortfolioManager";
import { COLORS, SHADOWS } from "./theme";
import type {
  DecisionFlag,
  PortfolioDecisionResponse,
  StockDecision,
} from "./types";

interface Props {
  response: PortfolioDecisionResponse | null;
  loading: boolean;
  error: string | null;
  holdings: PortfolioHolding[];
  onRefresh: () => void;
}

export default function StockDecisionEngineTab({
  response,
  loading,
  error,
  holdings,
  onRefresh,
}: Props) {
  const [filterFlag, setFilterFlag] = useState<"ALL" | DecisionFlag>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<
    "final_score" | "weight" | "fundamental" | "sector" | "news" | "symbol"
  >("final_score");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  // Map holding weights for quick reference
  const holdingWeightMap = useMemo(() => {
    const totalVal = holdings.reduce(
      (sum, h) => sum + h.quantity * h.buyPrice,
      0
    );
    const map = new Map<string, number>();
    for (const h of holdings) {
      if (h.symbol) {
        const val = h.quantity * h.buyPrice;
        map.set(h.symbol.toUpperCase(), totalVal > 0 ? val / totalVal : 0);
      }
    }
    return map;
  }, [holdings]);

  const summary = response?.summary;
  const decisions = response?.decisions || [];

  // Filtered and sorted decisions
  const filteredDecisions = useMemo(() => {
    return decisions
      .filter((d) => {
        if (filterFlag !== "ALL" && d.decision !== filterFlag) return false;
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim();
          const symMatch = d.symbol.toLowerCase().includes(q);
          const nameMatch = d.company_name?.toLowerCase().includes(q) ?? false;
          const sectorMatch = d.sector?.toLowerCase().includes(q) ?? false;
          if (!symMatch && !nameMatch && !sectorMatch) return false;
        }
        return true;
      })
      .sort((a, b) => {
        let valA = 0;
        let valB = 0;
        if (sortField === "final_score") {
          valA = a.final_score;
          valB = b.final_score;
        } else if (sortField === "fundamental") {
          valA = a.fundamental.fundamental_strength_score;
          valB = b.fundamental.fundamental_strength_score;
        } else if (sortField === "sector") {
          valA = a.sector_strength.sector_strength_score;
          valB = b.sector_strength.sector_strength_score;
        } else if (sortField === "news") {
          valA = a.news.news_score;
          valB = b.news.news_score;
        } else if (sortField === "weight") {
          valA = holdingWeightMap.get(a.symbol.toUpperCase()) || 0;
          valB = holdingWeightMap.get(b.symbol.toUpperCase()) || 0;
        } else if (sortField === "symbol") {
          return sortOrder === "asc"
            ? a.symbol.localeCompare(b.symbol)
            : b.symbol.localeCompare(a.symbol);
        }
        return sortOrder === "asc" ? valA - valB : valB - valA;
      });
  }, [decisions, filterFlag, searchQuery, sortField, sortOrder, holdingWeightMap]);

  const getDecisionBadge = (flag: DecisionFlag) => {
    switch (flag) {
      case "HOLD":
        return {
          bg: "#046A38",
          color: "#F9EBD7",
          border: "#058b4a",
          label: "HOLD",
          icon: "✓",
          desc: "Strong or acceptable fundamentals with no major deterioration signals.",
        };
      case "WAIT & WATCH":
        return {
          bg: "#8A5A00",
          color: "#F9EBD7",
          border: "#b07400",
          label: "WAIT & WATCH",
          icon: "⏳",
          desc: "Mixed signals, uncertain conditions, or near decision thresholds.",
        };
      case "SELL":
        return {
          bg: "#E34222",
          color: "#F9EBD7",
          border: "#b8321a",
          label: "SELL",
          icon: "⚠",
          desc: "Significant evidence of financial weakness or downside risk.",
        };
    }
  };

  const getConfidenceBadge = (confidence: string) => {
    switch (confidence) {
      case "high":
        return { label: "High Confidence", color: "#046A38", bg: "#DCE9DE" };
      case "medium":
        return { label: "Medium Confidence", color: "#8A5A00", bg: "#FDF0D5" };
      case "low":
        return { label: "Low Confidence", color: "#686B64", bg: "#E3D7C4" };
      default:
        return { label: "Insufficient Data", color: "#E34222", bg: "#F6D9CC" };
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "#046A38";
    if (score >= 45) return "#8A5A00";
    return "#E34222";
  };

  return (
    <Stack spacing={3}>
      {/* Header Banner */}
      <Paper
        sx={{
          p: 2.5,
          borderRadius: 0,
          bgcolor: COLORS.deepCharcoal,
          color: COLORS.warmIvory,
          boxShadow: SHADOWS.card,
        }}
      >
        <Box
          sx={{
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            gap: 2,
          }}
        >
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  color: COLORS.warmIvory,
                  fontFamily: "Outfit, sans-serif",
                }}
              >
                STOCK DECISION ENGINE
              </Typography>
              <Chip
                label="3-Factor ML Synthesis"
                size="small"
                sx={{
                  bgcolor: "#046A38",
                  color: "#F9EBD7",
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  borderRadius: 0,
                }}
              />
            </Box>
            <Typography
              variant="body2"
              sx={{ color: COLORS.sandBeige, mt: 0.5, fontSize: "0.85rem" }}
            >
              Actionable flags (SELL / HOLD / WAIT & WATCH) combining Five-Factor
              Fundamental Strength (60%), Sector Divergence (25%), and News Sentiment (15%).
            </Typography>
          </Box>
          <Button
            variant="contained"
            size="small"
            onClick={onRefresh}
            disabled={loading || holdings.length === 0}
            startIcon={
              loading ? <CircularProgress size={16} color="inherit" /> : <span>↻</span>
            }
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              borderRadius: 0,
              textTransform: "none",
              fontWeight: 600,
              px: 2,
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            {loading ? "Analyzing..." : "Re-Analyze Decisions"}
          </Button>
        </Box>
      </Paper>

      {/* Error Alert */}
      {error && (
        <Alert
          severity="error"
          sx={{
            borderRadius: 0,
            bgcolor: "#F6D9CC",
            color: "#B8321A",
            border: "1px solid #E34222",
          }}
        >
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && !response && (
        <Paper
          sx={{
            p: 6,
            textAlign: "center",
            bgcolor: COLORS.warmIvory,
            borderRadius: 0,
            boxShadow: SHADOWS.card,
          }}
        >
          <CircularProgress sx={{ color: "#046A38", mb: 2 }} />
          <Typography variant="body1" sx={{ fontWeight: 600, color: COLORS.deepCharcoal }}>
            Synthesizing 5-Factor Risk, Sector Divergence, and News Sentiment...
          </Typography>
          <Typography variant="body2" sx={{ color: COLORS.mutedGrey, mt: 0.5 }}>
            Evaluating dynamic weight regimes and risk override triggers for each portfolio holding.
          </Typography>
        </Paper>
      )}

      {/* Summary KPI Cards */}
      {summary && (
        <Grid container spacing={2}>
          {/* Total Stocks */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: COLORS.warmIvory,
                border: "1px solid #E3D7C4",
                boxShadow: SHADOWS.control,
              }}
            >
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey, fontWeight: 600 }}>
                PORTFOLIO STOCKS
              </Typography>
              <Typography
                variant="h4"
                sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mt: 0.5 }}
              >
                {summary.total_stocks}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                {summary.unavailable_count > 0
                  ? `${summary.unavailable_count} unavailable`
                  : "All analyzed"}
              </Typography>
            </Paper>
          </Grid>

          {/* HOLD Count */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              onClick={() => setFilterFlag(filterFlag === "HOLD" ? "ALL" : "HOLD")}
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: filterFlag === "HOLD" ? "#DCE9DE" : COLORS.warmIvory,
                border: "1px solid #046A38",
                boxShadow: SHADOWS.control,
                cursor: "pointer",
                transition: "all 0.2s",
                "&:hover": { boxShadow: SHADOWS.card },
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Typography variant="caption" sx={{ color: "#046A38", fontWeight: 700 }}>
                  HOLD
                </Typography>
                <Chip
                  label="Healthy"
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: "0.65rem",
                    bgcolor: "#046A38",
                    color: "#F9EBD7",
                    borderRadius: 0,
                  }}
                />
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 700, color: "#046A38", mt: 0.5 }}>
                {summary.hold_count}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                {summary.total_stocks > 0
                  ? `${((summary.hold_count / summary.total_stocks) * 100).toFixed(0)}% of holdings`
                  : ""}
              </Typography>
            </Paper>
          </Grid>

          {/* WAIT & WATCH Count */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              onClick={() => setFilterFlag(filterFlag === "WAIT & WATCH" ? "ALL" : "WAIT & WATCH")}
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: filterFlag === "WAIT & WATCH" ? "#FDF0D5" : COLORS.warmIvory,
                border: "1px solid #8A5A00",
                boxShadow: SHADOWS.control,
                cursor: "pointer",
                transition: "all 0.2s",
                "&:hover": { boxShadow: SHADOWS.card },
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Typography variant="caption" sx={{ color: "#8A5A00", fontWeight: 700 }}>
                  WAIT & WATCH
                </Typography>
                <Chip
                  label="Mixed"
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: "0.65rem",
                    bgcolor: "#8A5A00",
                    color: "#F9EBD7",
                    borderRadius: 0,
                  }}
                />
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 700, color: "#8A5A00", mt: 0.5 }}>
                {summary.wait_and_watch_count}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                {summary.total_stocks > 0
                  ? `${((summary.wait_and_watch_count / summary.total_stocks) * 100).toFixed(0)}% of holdings`
                  : ""}
              </Typography>
            </Paper>
          </Grid>

          {/* SELL Count */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              onClick={() => setFilterFlag(filterFlag === "SELL" ? "ALL" : "SELL")}
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: filterFlag === "SELL" ? "#F6D9CC" : COLORS.warmIvory,
                border: "1px solid #E34222",
                boxShadow: SHADOWS.control,
                cursor: "pointer",
                transition: "all 0.2s",
                "&:hover": { boxShadow: SHADOWS.card },
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Typography variant="caption" sx={{ color: "#E34222", fontWeight: 700 }}>
                  SELL
                </Typography>
                <Chip
                  label="At Risk"
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: "0.65rem",
                    bgcolor: "#E34222",
                    color: "#F9EBD7",
                    borderRadius: 0,
                  }}
                />
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 700, color: "#E34222", mt: 0.5 }}>
                {summary.sell_count}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                {summary.total_stocks > 0
                  ? `${((summary.sell_count / summary.total_stocks) * 100).toFixed(0)}% of holdings`
                  : ""}
              </Typography>
            </Paper>
          </Grid>

          {/* Weighted Risk Exposure */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: COLORS.warmIvory,
                border: "1px solid #E3D7C4",
                boxShadow: SHADOWS.control,
              }}
            >
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey, fontWeight: 600 }}>
                RISK EXPOSURE
              </Typography>
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 700,
                  color: summary.portfolio_weighted_risk_exposure > 25 ? "#E34222" : COLORS.deepCharcoal,
                  mt: 0.5,
                }}
              >
                {summary.portfolio_weighted_risk_exposure.toFixed(1)}%
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Weighted SELL share
              </Typography>
            </Paper>
          </Grid>

          {/* Average Health Score */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Paper
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: COLORS.warmIvory,
                border: "1px solid #E3D7C4",
                boxShadow: SHADOWS.control,
              }}
            >
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey, fontWeight: 600 }}>
                AVG HEALTH SCORE
              </Typography>
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 700,
                  color: summary.average_final_score
                    ? getScoreColor(summary.average_final_score)
                    : COLORS.deepCharcoal,
                  mt: 0.5,
                }}
              >
                {summary.average_final_score ? summary.average_final_score.toFixed(1) : "—"}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                Out of 100 max
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Filter and Search Bar */}
      {decisions.length > 0 && (
        <Paper
          sx={{
            p: 2,
            borderRadius: 0,
            bgcolor: COLORS.warmIvory,
            border: "1px solid #E3D7C4",
            boxShadow: SHADOWS.control,
          }}
        >
          <Box
            sx={{
              display: "flex",
              flexDirection: { xs: "column", md: "row" },
              gap: 2,
              alignItems: { xs: "stretch", md: "center" },
              justifyContent: "space-between",
            }}
          >
            {/* Decision Filter Chips */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
              <Typography variant="caption" sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mr: 1 }}>
                FLAG:
              </Typography>
              {(["ALL", "HOLD", "WAIT & WATCH", "SELL"] as const).map((flag) => {
                const isSelected = filterFlag === flag;
                return (
                  <Chip
                    key={flag}
                    data-testid={`filter-chip-${flag}`}
                    label={flag}
                    onClick={() => setFilterFlag(flag)}
                    size="small"
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      bgcolor: isSelected
                        ? flag === "HOLD"
                          ? "#046A38"
                          : flag === "WAIT & WATCH"
                          ? "#8A5A00"
                          : flag === "SELL"
                          ? "#E34222"
                          : COLORS.deepCharcoal
                        : "#E3D7C4",
                      color: isSelected ? "#F9EBD7" : COLORS.deepCharcoal,
                      "&:hover": { opacity: 0.85 },
                    }}
                  />
                );
              })}
            </Box>

            {/* Search and Sort */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <TextField
                size="small"
                placeholder="Search symbol / company..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                sx={{
                  width: { xs: "100%", sm: 220 },
                  "& .MuiOutlinedInput-root": {
                    borderRadius: 0,
                    bgcolor: "#F9EBD7",
                    fontSize: "0.82rem",
                  },
                }}
              />
              <Select
                size="small"
                value={sortField}
                onChange={(e) => setSortField(e.target.value as typeof sortField)}
                sx={{
                  borderRadius: 0,
                  bgcolor: "#F9EBD7",
                  fontSize: "0.82rem",
                  minWidth: 140,
                }}
              >
                <MenuItem value="final_score">Final Score</MenuItem>
                <MenuItem value="weight">Portfolio Weight</MenuItem>
                <MenuItem value="fundamental">Fundamental Score</MenuItem>
                <MenuItem value="sector">Sector Strength</MenuItem>
                <MenuItem value="news">News Sentiment</MenuItem>
                <MenuItem value="symbol">Symbol</MenuItem>
              </Select>
              <IconButton
                size="small"
                onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
                sx={{
                  borderRadius: 0,
                  border: "1px solid #E3D7C4",
                  bgcolor: "#F9EBD7",
                  p: 0.75,
                }}
                title={sortOrder === "asc" ? "Ascending" : "Descending"}
              >
                {sortOrder === "asc" ? "↑" : "↓"}
              </IconButton>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Decision Cards List */}
      <Stack spacing={2}>
        {filteredDecisions.length === 0 && !loading && (
          <Paper
            sx={{
              p: 4,
              textAlign: "center",
              bgcolor: COLORS.warmIvory,
              borderRadius: 0,
              boxShadow: SHADOWS.card,
            }}
          >
            <Typography variant="body1" sx={{ color: COLORS.mutedGrey, fontWeight: 500 }}>
              {decisions.length === 0
                ? "No holdings in portfolio to analyze. Add holdings in the Dashboard tab."
                : "No stocks match the selected filter criteria."}
            </Typography>
          </Paper>
        )}

        {filteredDecisions.map((stock) => {
          const badge = getDecisionBadge(stock.decision);
          const conf = getConfidenceBadge(stock.confidence);
          const isExpanded = expandedSymbol === stock.symbol;
          const weight = holdingWeightMap.get(stock.symbol.toUpperCase());
          const hasRiskAlerts = stock.risk_alerts && stock.risk_alerts.length > 0;

          return (
            <Paper
              key={stock.symbol}
              data-testid={`stock-card-${stock.symbol}`}
              sx={{
                borderRadius: 0,
                bgcolor: COLORS.warmIvory,
                border: `1px solid ${hasRiskAlerts ? "#E34222" : "#E3D7C4"}`,
                boxShadow: isExpanded ? SHADOWS.card : SHADOWS.control,
                overflow: "hidden",
                transition: "all 0.2s",
              }}
            >
              {/* Card Header & Main Overview */}
              <Box sx={{ p: 2.5 }}>
                <Grid container spacing={2} sx={{ alignItems: "center" }}>
                  {/* Stock Identification */}
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Stack spacing={0.5}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Typography
                          variant="h6"
                          sx={{
                            fontWeight: 700,
                            color: COLORS.deepCharcoal,
                            fontFamily: "Outfit, sans-serif",
                          }}
                        >
                          {stock.symbol}
                        </Typography>
                        {weight !== undefined && weight > 0 && (
                          <Chip
                            label={`${(weight * 100).toFixed(1)}% weight`}
                            size="small"
                            sx={{
                              height: 20,
                              fontSize: "0.68rem",
                              borderRadius: 0,
                              bgcolor: "#E3D7C4",
                              color: COLORS.deepCharcoal,
                              fontWeight: 600,
                            }}
                          />
                        )}
                      </Box>
                      <Typography variant="body2" sx={{ color: COLORS.mutedGrey, fontSize: "0.82rem" }}>
                        {stock.company_name || stock.sector || "Equity"}
                      </Typography>
                      {stock.sector && (
                        <Typography variant="caption" sx={{ color: "#686B64", fontSize: "0.75rem" }}>
                          Sector: {stock.sector}
                        </Typography>
                      )}
                    </Stack>
                  </Grid>

                  {/* Decision Flag Badge */}
                  <Grid size={{ xs: 6, sm: 2.5 }}>
                    <Tooltip title={badge.desc} arrow>
                      <Box
                        sx={{
                          display: "inline-block",
                          p: "6px 14px",
                          bgcolor: badge.bg,
                          color: badge.color,
                          borderRadius: 0,
                          textAlign: "center",
                          boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
                        }}
                      >
                        <Typography
                          variant="subtitle2"
                          sx={{ fontWeight: 800, letterSpacing: "0.06em", fontSize: "0.88rem" }}
                        >
                          {badge.icon} {badge.label}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Box sx={{ mt: 0.75 }}>
                      <Chip
                        label={conf.label}
                        size="small"
                        sx={{
                          height: 18,
                          fontSize: "0.65rem",
                          borderRadius: 0,
                          bgcolor: conf.bg,
                          color: conf.color,
                          fontWeight: 600,
                        }}
                      />
                    </Box>
                  </Grid>

                  {/* Final Health Score Meter */}
                  <Grid size={{ xs: 6, sm: 2.5 }}>
                    <Stack spacing={0.5}>
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <Typography variant="caption" sx={{ color: COLORS.mutedGrey, fontWeight: 700 }}>
                          HEALTH SCORE
                        </Typography>
                        <Typography
                          variant="h6"
                          sx={{
                            fontWeight: 800,
                            color: getScoreColor(stock.final_score),
                            lineHeight: 1,
                          }}
                        >
                          {stock.final_score.toFixed(1)}
                          <Typography
                            component="span"
                            variant="caption"
                            sx={{ color: COLORS.mutedGrey, ml: 0.25 }}
                          >
                            /100
                          </Typography>
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={stock.final_score}
                        sx={{
                          height: 8,
                          borderRadius: 0,
                          bgcolor: "#E3D7C4",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: getScoreColor(stock.final_score),
                          },
                        }}
                      />
                      <Typography variant="caption" sx={{ color: COLORS.mutedGrey, fontSize: "0.7rem" }}>
                        Regime: {stock.applied_weights.regime} (
                        {Math.round(stock.applied_weights.fundamental * 100)}/
                        {Math.round(stock.applied_weights.sector * 100)}/
                        {Math.round(stock.applied_weights.news * 100)})
                      </Typography>
                    </Stack>
                  </Grid>

                  {/* 3-Factor Mini Pillars */}
                  <Grid size={{ xs: 12, sm: 3 }}>
                    <Stack spacing={0.75}>
                      {/* Fundamental */}
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Typography variant="caption" sx={{ color: COLORS.deepCharcoal, fontWeight: 600 }}>
                          Fundamental (60%)
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 700,
                            color: getScoreColor(stock.fundamental.fundamental_strength_score),
                          }}
                        >
                          {stock.fundamental.fundamental_strength_score.toFixed(0)}/100
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={stock.fundamental.fundamental_strength_score}
                        sx={{
                          height: 4,
                          borderRadius: 0,
                          bgcolor: "#E3D7C4",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: getScoreColor(stock.fundamental.fundamental_strength_score),
                          },
                        }}
                      />

                      {/* Sector */}
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Typography variant="caption" sx={{ color: COLORS.deepCharcoal, fontWeight: 600 }}>
                          Sector (25%)
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 700,
                            color: getScoreColor(stock.sector_strength.sector_strength_score),
                          }}
                        >
                          {stock.sector_strength.sector_strength_score.toFixed(0)}/100
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={stock.sector_strength.sector_strength_score}
                        sx={{
                          height: 4,
                          borderRadius: 0,
                          bgcolor: "#E3D7C4",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: getScoreColor(stock.sector_strength.sector_strength_score),
                          },
                        }}
                      />

                      {/* News */}
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <Typography variant="caption" sx={{ color: COLORS.deepCharcoal, fontWeight: 600 }}>
                          News (15%)
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 700,
                            color: getScoreColor(stock.news.news_score),
                          }}
                        >
                          {stock.news.news_score.toFixed(0)}/100
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={stock.news.news_score}
                        sx={{
                          height: 4,
                          borderRadius: 0,
                          bgcolor: "#E3D7C4",
                          "& .MuiLinearProgress-bar": {
                            bgcolor: getScoreColor(stock.news.news_score),
                          },
                        }}
                      />
                    </Stack>
                  </Grid>

                  {/* Expand / Collapse Button */}
                  <Grid size={{ xs: 12, sm: 1 }} sx={{ textAlign: "right" }}>
                    <Button
                      size="small"
                      onClick={() => setExpandedSymbol(isExpanded ? null : stock.symbol)}
                      sx={{
                        minWidth: 32,
                        p: "4px 8px",
                        borderRadius: 0,
                        textTransform: "none",
                        fontSize: "0.75rem",
                        color: COLORS.deepCharcoal,
                        border: "1px solid #E3D7C4",
                        "&:hover": { bgcolor: "#E3D7C4" },
                      }}
                    >
                      {isExpanded ? "Hide" : "Details"}
                    </Button>
                  </Grid>
                </Grid>

                {/* Risk Alerts Banner (always visible if present) */}
                {hasRiskAlerts && (
                  <Box sx={{ mt: 2 }}>
                    {stock.risk_alerts.map((alert, idx) => (
                      <Alert
                        key={idx}
                        severity="warning"
                        sx={{
                          borderRadius: 0,
                          mb: 0.5,
                          p: "4px 12px",
                          bgcolor: "#FDF0D5",
                          color: "#8A5A00",
                          border: "1px solid #8A5A00",
                          fontSize: "0.78rem",
                          "& .MuiAlert-icon": { color: "#8A5A00", py: 0 },
                        }}
                      >
                        {alert}
                      </Alert>
                    ))}
                  </Box>
                )}
              </Box>

              {/* Expandable Deep-Dive Details */}
              <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                <Divider sx={{ borderColor: "#E3D7C4" }} />
                <Box sx={{ p: 2.5, bgcolor: "#F5E6D0" }}>
                  <Grid container spacing={3}>
                    {/* Component 1: Fundamental Analysis */}
                    <Grid size={{ xs: 12, md: 4 }}>
                      <Paper
                        sx={{
                          p: 2,
                          borderRadius: 0,
                          bgcolor: COLORS.warmIvory,
                          border: "1px solid #E3D7C4",
                          height: "100%",
                        }}
                      >
                        <Stack spacing={1}>
                          <Typography
                            variant="subtitle2"
                            sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}
                          >
                            1. Fundamental Health (60%)
                          </Typography>
                          <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                            Source: 5-Factor Risk Score (Inverted)
                          </Typography>
                          <Divider sx={{ my: 0.5 }} />
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Strength Score:</strong>{" "}
                            {stock.fundamental.fundamental_strength_score.toFixed(1)} / 100
                          </Typography>
                          {stock.fundamental.raw_risk_score !== null &&
                            stock.fundamental.raw_risk_score !== undefined && (
                              <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                                <strong>Raw Risk Percentile:</strong>{" "}
                                {stock.fundamental.raw_risk_score.toFixed(1)} (lower = safer)
                              </Typography>
                            )}
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Classification:</strong>{" "}
                            {stock.fundamental.fundamental_classification}
                          </Typography>
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Anomaly ML Model:</strong>{" "}
                            {stock.fundamental.anomaly_flag ? (
                              <Chip
                                label="ANOMALY FLAGGED"
                                size="small"
                                sx={{
                                  height: 18,
                                  fontSize: "0.65rem",
                                  bgcolor: "#E34222",
                                  color: "#F9EBD7",
                                  borderRadius: 0,
                                }}
                              />
                            ) : (
                              "Normal behaviour"
                            )}
                          </Typography>
                          {stock.fundamental.failure_reason && (
                            <Typography variant="caption" sx={{ color: "#E34222" }}>
                              Note: {stock.fundamental.failure_reason}
                            </Typography>
                          )}
                        </Stack>
                      </Paper>
                    </Grid>

                    {/* Component 2: Sector Divergence */}
                    <Grid size={{ xs: 12, md: 4 }}>
                      <Paper
                        sx={{
                          p: 2,
                          borderRadius: 0,
                          bgcolor: COLORS.warmIvory,
                          border: "1px solid #E3D7C4",
                          height: "100%",
                        }}
                      >
                        <Stack spacing={1}>
                          <Typography
                            variant="subtitle2"
                            sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}
                          >
                            2. Sector Divergence (25%)
                          </Typography>
                          <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                            Source: 20-Day Sector Peer Residual
                          </Typography>
                          <Divider sx={{ my: 0.5 }} />
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Sector Strength:</strong>{" "}
                            {stock.sector_strength.sector_strength_score.toFixed(1)} / 100
                          </Typography>
                          {stock.sector_strength.divergence_value !== null &&
                            stock.sector_strength.divergence_value !== undefined && (
                              <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                                <strong>Divergence Z-Score:</strong>{" "}
                                {stock.sector_strength.divergence_value > 0 ? "+" : ""}
                                {stock.sector_strength.divergence_value.toFixed(2)}σ
                              </Typography>
                            )}
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Interpretation:</strong>{" "}
                            {stock.sector_strength.interpretation || "Industry Rank"}
                          </Typography>
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Horizon:</strong> {stock.sector_strength.horizon_days} trading days
                          </Typography>
                          {stock.sector_strength.failure_reason && (
                            <Typography variant="caption" sx={{ color: "#E34222" }}>
                              Note: {stock.sector_strength.failure_reason}
                            </Typography>
                          )}
                        </Stack>
                      </Paper>
                    </Grid>

                    {/* Component 3: News Sentiment */}
                    <Grid size={{ xs: 12, md: 4 }}>
                      <Paper
                        sx={{
                          p: 2,
                          borderRadius: 0,
                          bgcolor: COLORS.warmIvory,
                          border: "1px solid #E3D7C4",
                          height: "100%",
                        }}
                      >
                        <Stack spacing={1}>
                          <Typography
                            variant="subtitle2"
                            sx={{ fontWeight: 700, color: COLORS.deepCharcoal }}
                          >
                            3. News Intelligence (15%)
                          </Typography>
                          <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                            Source: FinBERT + News Classifier
                          </Typography>
                          <Divider sx={{ my: 0.5 }} />
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>News Score:</strong> {stock.news.news_score.toFixed(1)} / 100
                          </Typography>
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Dominant Sentiment:</strong>{" "}
                            <span style={{ textTransform: "capitalize" }}>{stock.news.sentiment}</span>
                          </Typography>
                          <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                            <strong>Articles Tracked (7d):</strong> {stock.news.articles_analyzed}
                          </Typography>
                          {stock.news.major_events && stock.news.major_events.length > 0 && (
                            <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                              <strong>Events:</strong> {stock.news.major_events.join(", ")}
                            </Typography>
                          )}
                          {stock.news.is_fallback_neutral && (
                            <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                              * Neutral fallback (insufficient recent articles)
                            </Typography>
                          )}
                        </Stack>
                      </Paper>
                    </Grid>

                    {/* Detailed Reasons & Explanation Narrative */}
                    <Grid size={{ xs: 12 }}>
                      <Paper
                        sx={{
                          p: 2,
                          borderRadius: 0,
                          bgcolor: COLORS.warmIvory,
                          border: "1px solid #E3D7C4",
                        }}
                      >
                        <Typography
                          variant="subtitle2"
                          sx={{ fontWeight: 700, color: COLORS.deepCharcoal, mb: 1 }}
                        >
                          Decision Rationale & Contributing Factors
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            color: COLORS.deepCharcoal,
                            fontSize: "0.84rem",
                            mb: 1.5,
                            lineHeight: 1.5,
                          }}
                        >
                          {stock.explanation}
                        </Typography>
                        {stock.reasons && stock.reasons.length > 0 && (
                          <Box component="ul" sx={{ pl: 2.5, m: 0 }}>
                            {stock.reasons.map((reason, rIdx) => (
                              <Typography
                                component="li"
                                key={rIdx}
                                variant="caption"
                                sx={{ color: COLORS.deepCharcoal, fontSize: "0.8rem", mb: 0.5 }}
                              >
                                {reason}
                              </Typography>
                            ))}
                          </Box>
                        )}
                        <Divider sx={{ my: 1.5 }} />
                        <Box
                          sx={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                            Weight Regime: <strong>{stock.applied_weights.regime}</strong> (
                            {stock.applied_weights.regime_reason || "Standard market conditions"})
                          </Typography>
                          <Typography variant="caption" sx={{ color: COLORS.mutedGrey }}>
                            Analyzed: {new Date(stock.analysis_timestamp).toLocaleString()}
                          </Typography>
                        </Box>
                      </Paper>
                    </Grid>
                  </Grid>
                </Box>
              </Collapse>
            </Paper>
          );
        })}
      </Stack>

      {/* Governance & Disclaimer Footer */}
      {response && (
        <Paper
          sx={{
            p: 2,
            borderRadius: 0,
            bgcolor: "#E3D7C4",
            color: COLORS.deepCharcoal,
            fontSize: "0.78rem",
          }}
        >
          <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 0.5 }}>
            GOVERNANCE & METHODOLOGY NOTICE
          </Typography>
          <Typography variant="caption" sx={{ color: "#686B64", display: "block", lineHeight: 1.4 }}>
            {response.governance_disclaimer}
          </Typography>
          <Typography variant="caption" sx={{ color: "#686B64", mt: 0.5, display: "block" }}>
            Methodology version: {response.methodology_version} | Weights: Fundamental (60%), Sector
            (25%), News Sentiment (15%). Dynamic adjustment triggered by material corporate events.
          </Typography>
        </Paper>
      )}
    </Stack>
  );
}
