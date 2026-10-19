import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  InputAdornment,
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
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

import AppShell from "./AppShell";
import { fetchJson } from "./api";
import type { Horizon, PipelineStatus, RankingsResponse } from "./types";

const bandColor = { normal: "default", moderate: "warning", strong: "error", extreme: "error" } as const;

type SortField = "divergence" | "magnitude" | "symbol" | "industry" | "percentile" | "interpretation";
type SortOrder = "asc" | "desc";
type FilterPreset = "all" | "positive" | "negative" | "outliers";

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [horizon, setHorizon] = useState<Horizon>(20);
  const [data, setData] = useState<RankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);

  // Search & Filter & Sort state
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("magnitude");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [filterPreset, setFilterPreset] = useState<FilterPreset>("all");

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<RankingsResponse>(
      `/sector-divergence/latest/rankings?horizon=${horizon}&limit=200`,
      controller.signal,
    )
      .then(setData)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Unable to load results");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [horizon]);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<PipelineStatus>("/pipeline/status", controller.signal)
      .then(setPipeline)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  // Distinct industries from current dataset
  const industries = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.results.map((r) => r.industry))).sort();
  }, [data]);

  // Handle column header clicks
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      // Default directions
      if (field === "divergence" || field === "magnitude" || field === "percentile") {
        setSortOrder("desc");
      } else {
        setSortOrder("asc");
      }
    }
  };

  // Filtered and sorted results
  const filteredResults = useMemo(() => {
    if (!data) return [];
    const q = searchQuery.toLowerCase().trim();

    return data.results
      .filter((item) => {
        // Stock symbol or industry search
        if (q) {
          const matchSymbol = item.symbol.toLowerCase().includes(q);
          const matchIndustry = item.industry.toLowerCase().includes(q);
          if (!matchSymbol && !matchIndustry) return false;
        }

        // Industry filter
        if (selectedIndustry !== "ALL" && item.industry !== selectedIndustry) {
          return false;
        }

        // Preset filter
        if (filterPreset === "positive" && item.divergence_value < 0) return false;
        if (filterPreset === "negative" && item.divergence_value >= 0) return false;
        if (filterPreset === "outliers" && item.interpretation !== "strong" && item.interpretation !== "extreme") {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        let comparison = 0;
        if (sortField === "divergence") {
          comparison = a.divergence_value - b.divergence_value;
        } else if (sortField === "magnitude") {
          comparison = Math.abs(a.divergence_value) - Math.abs(b.divergence_value);
        } else if (sortField === "symbol") {
          comparison = a.symbol.localeCompare(b.symbol);
        } else if (sortField === "industry") {
          comparison = a.industry.localeCompare(b.industry) || (b.divergence_value - a.divergence_value);
        } else if (sortField === "percentile") {
          comparison = a.industry_percentile - b.industry_percentile;
        } else if (sortField === "interpretation") {
          const rank = { extreme: 4, strong: 3, moderate: 2, normal: 1 };
          comparison = (rank[a.interpretation as keyof typeof rank] || 0) - (rank[b.interpretation as keyof typeof rank] || 0);
        }
        return sortOrder === "asc" ? comparison : -comparison;
      });
  }, [data, searchQuery, selectedIndustry, filterPreset, sortField, sortOrder]);

  const hasActiveFilters = searchQuery !== "" || selectedIndustry !== "ALL" || filterPreset !== "all" || sortField !== "magnitude";

  const resetFilters = () => {
    setSearchQuery("");
    setSelectedIndustry("ALL");
    setFilterPreset("all");
    setSortField("magnitude");
    setSortOrder("desc");
  };

  return (
    <AppShell>
      <Stack spacing={2.5}>
        {pipeline && (
          <Alert severity={pipeline.is_stale || pipeline.status === "failed" ? "warning" : "success"}>
            Pipeline: <strong>{pipeline.status}</strong>. Market data: {pipeline.latest_market_date ?? "unavailable"}; Layer 1: {pipeline.layer_1_date ?? "unavailable"}; Layer 2: {pipeline.layer_2_date ?? "unavailable"}.
            {pipeline.failed_stage && ` Failed stage: ${pipeline.failed_stage}.`}
            {pipeline.is_stale && " Displayed analysis is stale relative to stored market data."}
          </Alert>
        )}

        {/* ─── Top Header with Days Tracker ─── */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 2 }}
        >
          <Box>
            <Typography variant="h4" component="h2" sx={{ fontWeight: 700 }}>
              Sector divergence
            </Typography>
            <Typography color="text.secondary">
              Select a company to inspect its exact peer comparison.
            </Typography>
          </Box>
          <Box>
            <FormControl size="small" sx={{ minWidth: 190 }}>
              <InputLabel id="horizon-label">Days Tracker (Horizon)</InputLabel>
              <Select
                labelId="horizon-label"
                label="Days Tracker (Horizon)"
                value={horizon}
                onChange={(event) => {
                  setLoading(true);
                  setError(null);
                  setHorizon(event.target.value as Horizon);
                }}
              >
                <MenuItem value={1}>1 trading day</MenuItem>
                <MenuItem value={5}>5 trading days</MenuItem>
                <MenuItem value={20}>20 trading days</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Stack>

        {error && <Alert severity="warning">Results are not available ({error}).</Alert>}

        {data && (
          <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: 2 }}>
            <Paper sx={{ p: 2.5, flex: 1 }}>
              <Typography variant="overline" color="text.secondary">Market data through</Typography>
              <Typography variant="h6">{data.run.signal_date}</Typography>
            </Paper>
            <Paper sx={{ p: 2.5, flex: 1 }}>
              <Typography variant="overline" color="text.secondary">Calculated</Typography>
              <Typography variant="h6">{formatTimestamp(data.run.completed_at)}</Typography>
            </Paper>
            <Paper sx={{ p: 2.5, flex: 1 }}>
              <Typography variant="overline" color="text.secondary">Coverage</Typography>
              <Typography variant="h6">{data.run.score_count} scores</Typography>
              <Typography variant="body2" color="text.secondary">
                {data.run.exclusion_count} exclusions / {data.run.issue_count} issues
              </Typography>
            </Paper>
          </Stack>
        )}

        {/* ─── Condition-Responsive Methodology & Insights Explainer ─── */}
        <Paper
          sx={{
            p: 2.5,
            borderRadius: 0,
            border: "none",
            bgcolor: "#E3D7C4",
            boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
          }}
        >
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 1 }}>
              <Typography variant="subtitle1" component="div" sx={{ fontWeight: 700, color: "#292D2A" }}>
                💡 Understanding Peer Dispersion &amp; Horizon Dynamics ({horizon}-Day Horizon)
              </Typography>
              <Chip
                size="small"
                label={horizon === 1 ? "1D: Intraday Shock" : horizon === 5 ? "5D: Swing Momentum" : "20D: Monthly Structural"}
                sx={{
                  borderRadius: 0,
                  bgcolor: "#F9EBD7",
                  color: "#292D2A",
                  fontWeight: 700,
                  fontSize: "0.75rem",
                  boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                }}
              />
            </Stack>
            <Typography variant="body2" sx={{ color: "#4A4D46", lineHeight: 1.6 }}>
              {horizon === 1 && (
                <>
                  <strong style={{ color: "#292D2A" }}>1-Day Horizon:</strong> Isolates opening and closing price reactions from the latest trading session against each stock&apos;s industry median. Outliers highlight immediate earnings announcements, block deals, or sudden news shocks before sector-wide diffusion occurs.
                </>
              )}
              {horizon === 5 && (
                <>
                  <strong style={{ color: "#292D2A" }}>5-Day Horizon:</strong> Measures weekly swing momentum. Stocks with large positive residuals are breaking out from sector drag, while negative residuals highlight persistent weekly distribution.
                </>
              )}
              {horizon === 20 && (
                <>
                  <strong style={{ color: "#292D2A" }}>20-Day Horizon:</strong> Evaluates sustained monthly structural divergence. Accounts for multi-week capital rotation across NIFTY 200 sectors and isolates true idiosyncratic alpha from broad beta trends.
                </>
              )}
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ pt: 0.5 }}>
              <Box sx={{ flex: 1, p: 1.5, bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 2px 6px rgba(41,45,42,0.08)" }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "#046A38", textTransform: "uppercase", display: "block", mb: 0.5 }}>
                  📈 Positive Residual (+&sigma;)
                </Typography>
                <Typography variant="body2" sx={{ color: "#292D2A", fontSize: "0.82rem" }}>
                  The stock is outperforming its leave-one-out peer model, indicating business resilience, margin expansion, or institutional accumulation.
                </Typography>
              </Box>
              <Box sx={{ flex: 1, p: 1.5, bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 2px 6px rgba(41,45,42,0.08)" }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "#B8321A", textTransform: "uppercase", display: "block", mb: 0.5 }}>
                  📉 Negative Residual (-&sigma;)
                </Typography>
                <Typography variant="body2" sx={{ color: "#292D2A", fontSize: "0.82rem" }}>
                  The stock is lagging its industry benchmark, indicating relative valuation compression, guidance cuts, or operational headwinds.
                </Typography>
              </Box>
              <Box sx={{ flex: 1, p: 1.5, bgcolor: "#F9EBD7", borderRadius: 0, boxShadow: "0 2px 6px rgba(41,45,42,0.08)" }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "#8A5A00", textTransform: "uppercase", display: "block", mb: 0.5 }}>
                  ⚠️ Outlier Bands (|&sigma;| &ge; 1.5)
                </Typography>
                <Typography variant="body2" sx={{ color: "#292D2A", fontSize: "0.82rem" }}>
                  Statistically rare dislocations (top 13% of deviations). Useful for identifying decoupled leaders or mean-reversion candidates.
                </Typography>
              </Box>
            </Stack>
          </Stack>
        </Paper>

        {/* ─── Interactive Search, Filter, and Sort Controls ─── */}
        <Paper sx={{ p: 2.5, bgcolor: "#F9EBD7" }}>
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "center" } }}>
              {/* Search a particular stock */}
              <TextField
                size="small"
                placeholder="Search stock symbol or industry (e.g. RELIANCE, TCS, Banks)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                sx={{ flex: 2, minWidth: { sm: 280 } }}
                slotProps={{
                  input: {
                    startAdornment: <InputAdornment position="start">🔍</InputAdornment>,
                    endAdornment: searchQuery ? (
                      <InputAdornment position="end">
                        <Button size="small" onClick={() => setSearchQuery("")} sx={{ minWidth: 24, p: 0.5 }}>
                          ✕
                        </Button>
                      </InputAdornment>
                    ) : null,
                  },
                }}
              />

              {/* Sort By Preset Dropdown */}
              <FormControl size="small" sx={{ minWidth: 220, flex: 1 }}>
                <InputLabel id="sort-select-label">Sort Order</InputLabel>
                <Select
                  labelId="sort-select-label"
                  label="Sort Order"
                  value={
                    sortField === "divergence" && sortOrder === "desc"
                      ? "best-to-worst"
                      : sortField === "divergence" && sortOrder === "asc"
                      ? "worst-to-best"
                      : sortField === "industry" && sortOrder === "asc"
                      ? "industry-asc"
                      : sortField === "magnitude" && sortOrder === "desc"
                      ? "magnitude-desc"
                      : sortField === "symbol" && sortOrder === "asc"
                      ? "symbol-asc"
                      : "custom"
                  }
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "best-to-worst") {
                      setSortField("divergence");
                      setSortOrder("desc");
                    } else if (val === "worst-to-best") {
                      setSortField("divergence");
                      setSortOrder("asc");
                    } else if (val === "industry-asc") {
                      setSortField("industry");
                      setSortOrder("asc");
                    } else if (val === "magnitude-desc") {
                      setSortField("magnitude");
                      setSortOrder("desc");
                    } else if (val === "symbol-asc") {
                      setSortField("symbol");
                      setSortOrder("asc");
                    }
                  }}
                >
                  <MenuItem value="magnitude-desc">⚡ Most Extreme (|σ| magnitude)</MenuItem>
                  <MenuItem value="best-to-worst">📈 Best to Worst (Highest residual)</MenuItem>
                  <MenuItem value="worst-to-best">📉 Worst to Best (Lowest residual)</MenuItem>
                  <MenuItem value="industry-asc">🏭 Sort by Industry (A &rarr; Z)</MenuItem>
                  <MenuItem value="symbol-asc">🔤 Sort by Symbol (A &rarr; Z)</MenuItem>
                  <MenuItem value="custom" disabled>Custom column sort</MenuItem>
                </Select>
              </FormControl>

              {/* Filter by Industry Dropdown */}
              <FormControl size="small" sx={{ minWidth: 220, flex: 1 }}>
                <InputLabel id="industry-filter-label">Filter by Industry</InputLabel>
                <Select
                  labelId="industry-filter-label"
                  label="Filter by Industry"
                  value={selectedIndustry}
                  onChange={(e) => setSelectedIndustry(e.target.value)}
                >
                  <MenuItem value="ALL">All Industries ({data?.results.length ?? 0})</MenuItem>
                  {industries.map((ind) => {
                    const count = data?.results.filter((r) => r.industry === ind).length ?? 0;
                    return (
                      <MenuItem key={ind} value={ind}>
                        {ind} ({count})
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
            </Stack>

            {/* Quick Filter Presets and Status Bar */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 1.5, pt: 0.5 }}
            >
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                <Typography variant="body2" sx={{ fontWeight: 600, color: "text.secondary", mr: 0.5 }}>
                  Quick Filter:
                </Typography>
                <Chip
                  size="small"
                  label="All Stocks"
                  clickable
                  color={filterPreset === "all" ? "primary" : "default"}
                  variant={filterPreset === "all" ? "filled" : "outlined"}
                  onClick={() => setFilterPreset("all")}
                />
                <Chip
                  size="small"
                  label="📈 Positive Residuals"
                  clickable
                  color={filterPreset === "positive" ? "success" : "default"}
                  variant={filterPreset === "positive" ? "filled" : "outlined"}
                  onClick={() => setFilterPreset("positive")}
                />
                <Chip
                  size="small"
                  label="📉 Negative Residuals"
                  clickable
                  color={filterPreset === "negative" ? "error" : "default"}
                  variant={filterPreset === "negative" ? "filled" : "outlined"}
                  onClick={() => setFilterPreset("negative")}
                />
                <Chip
                  size="small"
                  label="⚠️ Outliers (Strong / Extreme)"
                  clickable
                  color={filterPreset === "outliers" ? "warning" : "default"}
                  variant={filterPreset === "outliers" ? "filled" : "outlined"}
                  onClick={() => setFilterPreset("outliers")}
                />
              </Stack>

              <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                <Typography variant="body2" color="text.secondary">
                  Showing <strong>{filteredResults.length}</strong> of {data?.results.length ?? 0} stocks
                </Typography>
                {hasActiveFilters && (
                  <Button size="small" variant="text" color="inherit" onClick={resetFilters} sx={{ textTransform: "none", fontSize: "0.82rem" }}>
                    Reset Filters
                  </Button>
                )}
              </Stack>
            </Stack>
          </Stack>
        </Paper>

        {/* ─── Sector Divergence Table with Clickable Sorting ─── */}
        <TableContainer component={Paper} sx={{ width: "100%", overflowX: "auto" }}>
          {loading && (
            <Box sx={{ display: "grid", placeItems: "center", py: 8 }}>
              <CircularProgress />
            </Box>
          )}
          {!loading && data && (
            <Table aria-label="sector divergence rankings">
              <TableHead>
                <TableRow>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === "symbol"}
                      direction={sortField === "symbol" ? sortOrder : "asc"}
                      onClick={() => handleSort("symbol")}
                      sx={{ fontWeight: 700 }}
                    >
                      Symbol
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === "industry"}
                      direction={sortField === "industry" ? sortOrder : "asc"}
                      onClick={() => handleSort("industry")}
                      sx={{ fontWeight: 700 }}
                    >
                      Industry
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right">
                    <TableSortLabel
                      active={sortField === "divergence" || sortField === "magnitude"}
                      direction={sortOrder}
                      onClick={() => handleSort("divergence")}
                      sx={{ fontWeight: 700 }}
                    >
                      Divergence (sigma)
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    Direction
                  </TableCell>
                  <TableCell align="right">
                    <TableSortLabel
                      active={sortField === "percentile"}
                      direction={sortField === "percentile" ? sortOrder : "desc"}
                      onClick={() => handleSort("percentile")}
                      sx={{ fontWeight: 700 }}
                    >
                      Industry Percentile
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === "interpretation"}
                      direction={sortField === "interpretation" ? sortOrder : "desc"}
                      onClick={() => handleSort("interpretation")}
                      sx={{ fontWeight: 700 }}
                    >
                      Band
                    </TableSortLabel>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredResults.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ textAlign: "center", py: 6, color: "text.secondary" }}>
                      No stocks found matching the active search or filters.
                      <Box sx={{ mt: 1 }}>
                        <Button
                          size="small"
                          onClick={resetFilters}
                          sx={{
                            borderRadius: 0,
                            border: "none",
                            bgcolor: "#E3D7C4",
                            color: "#292D2A",
                            fontWeight: 600,
                            boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                            "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                          }}
                        >
                          Clear All Filters
                        </Button>
                      </Box>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredResults.map((score) => (
                    <TableRow
                      key={score.symbol}
                      hover
                      tabIndex={0}
                      onClick={() => navigate(`/companies/${score.symbol}`)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") navigate(`/companies/${score.symbol}`);
                      }}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell sx={{ fontWeight: 700 }}>{score.symbol}</TableCell>
                      <TableCell>{score.industry}</TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontVariantNumeric: "tabular-nums",
                          color: score.divergence_value >= 0 ? "#046A38" : "#B8321A",
                          fontWeight: 700,
                        }}
                      >
                        {score.divergence_value > 0 ? "+" : ""}
                        {score.divergence_value.toFixed(2)}
                      </TableCell>
                      <TableCell align="right">
                        {score.divergence_value >= 0 ? "Positive residual" : "Negative residual"}
                      </TableCell>
                      <TableCell align="right">{score.industry_percentile.toFixed(1)}%</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={score.interpretation}
                          color={bandColor[score.interpretation]}
                          variant={score.interpretation === "normal" ? "outlined" : "filled"}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </TableContainer>

        <Alert severity="info" icon={false}>
          Daily opening-and-closing price analysis using persisted history and live provider data through {data?.run.signal_date}. Divergence is descriptive, not a forecast or investment recommendation.
        </Alert>
        <Typography variant="caption" color="text.secondary">
          PRISM does not provide investment advice.
        </Typography>
      </Stack>
    </AppShell>
  );
}
