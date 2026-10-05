import React, { Suspense, lazy, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
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
import TimelineIcon from "@mui/icons-material/Timeline";
import SecurityIcon from "@mui/icons-material/Security";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { useApi } from "./api";
import type {
  MacroSeriesDefinition,
  MacroSeriesDetail,
  MarketRegimeResponse,
  SectorMacroSensitivity,
} from "./types";

// Lazy-load Plotly to avoid canvas/webgl issues in test runners and bundle bloat
const Plot = lazy(() => import("react-plotly.js"));

function ChartLoadingFallback() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: 380,
        bgcolor: "#f8fafc",
        borderRadius: 2,
      }}
    >
      <CircularProgress size={32} />
    </Box>
  );
}

export default function MacroPage() {
  const [selectedSeriesKey, setSelectedSeriesKey] = useState<string>("crude_oil");
  const [selectedIndustry, setSelectedIndustry] = useState<string>("ALL");
  const [onlySignificant, setOnlySignificant] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [sortField, setSortField] = useState<"industry" | "beta" | "t_stat">("beta");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // API Calls
  const { data: regime, isLoading: regimeLoading } = useApi<MarketRegimeResponse>(
    "/macro/regime/latest"
  );
  const { data: seriesList = [] } = useApi<MacroSeriesDefinition[]>("/macro/series");
  const { data: seriesDetail, isLoading: seriesLoading } = useApi<MacroSeriesDetail>(
    `/macro/series/${selectedSeriesKey}`
  );
  const { data: allSensitivities = [], isLoading: sensitivitiesLoading } = useApi<
    SectorMacroSensitivity[]
  >("/macro/sensitivities");

  // Unique industries for filter dropdown
  const industries = useMemo(() => {
    const set = new Set<string>();
    allSensitivities.forEach((s) => set.add(s.industry));
    return Array.from(set).sort();
  }, [allSensitivities]);

  // Filtered and sorted sensitivities
  const filteredSensitivities = useMemo(() => {
    return allSensitivities
      .filter((s) => {
        if (selectedIndustry !== "ALL" && s.industry !== selectedIndustry) return false;
        if (onlySignificant && !s.is_significant) return false;
        if (searchTerm) {
          const term = searchTerm.toLowerCase();
          const matchInd = s.industry.toLowerCase().includes(term);
          const matchSer = (s.series_name || s.series_key).toLowerCase().includes(term);
          if (!matchInd && !matchSer) return false;
        }
        return true;
      })
      .sort((a, b) => {
        let diff = 0;
        if (sortField === "industry") {
          diff = a.industry.localeCompare(b.industry);
        } else if (sortField === "beta") {
          diff = Math.abs(a.beta) - Math.abs(b.beta);
        } else if (sortField === "t_stat") {
          diff = Math.abs(a.t_stat) - Math.abs(b.t_stat);
        }
        return sortOrder === "asc" ? diff : -diff;
      });
  }, [allSensitivities, selectedIndustry, onlySignificant, searchTerm, sortField, sortOrder]);

  const handleSort = (field: "industry" | "beta" | "t_stat") => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  // Plotly chart series observations
  const plotData = useMemo(() => {
    if (!seriesDetail?.observations || seriesDetail.observations.length === 0) {
      return [];
    }
    const dates = seriesDetail.observations.map((o) => o.obs_date);
    const values = seriesDetail.observations.map((o) => o.value);

    return [
      {
        x: dates,
        y: values,
        type: "scatter" as const,
        mode: "lines" as const,
        name: seriesDetail.series.name,
        line: { color: "#0284c7", width: 2 },
        hoverinfo: "x+y" as const,
      },
    ];
  }, [seriesDetail]);

  const currentSeries = seriesDetail?.series;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Page Title & Mission Header */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={1.5} sx={{ mb: 1, alignItems: "center" }}>
          <TimelineIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" component="h1" sx={{ fontWeight: 800 }}>
            Macroeconomic Series & Sector Sensitivity
          </Typography>
        </Stack>
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 900 }}>
          Rule-based market regime classification with 5-day exit hysteresis (FR-F4), point-in-time
          macroeconomic series tracking, and rolling 63-day OLS sector sensitivities. Strictly
          non-causal and transparent.
        </Typography>
      </Box>

      {/* Market Regime Status Card */}
      <Card variant="outlined" sx={{ mb: 4, borderRadius: 2, bgcolor: "#ffffff" }}>
        <CardContent sx={{ p: 3 }}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={2}
            sx={{
              mb: 2,
              justifyContent: "space-between",
              alignItems: { xs: "flex-start", sm: "center" },
            }}
          >
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <SecurityIcon color="primary" />
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Current Market Regime Classification
              </Typography>
            </Stack>
            {regime && (
              <Chip
                label={`STATE: ${regime.regime.toUpperCase()}`}
                color={
                  regime.regime === "stressed"
                    ? "error"
                    : regime.regime === "trending"
                    ? "warning"
                    : "success"
                }
                sx={{ fontWeight: 800, px: 1, py: 0.5, fontSize: "0.9rem" }}
              />
            )}
          </Stack>

          {regimeLoading ? (
            <CircularProgress size={24} />
          ) : regime ? (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                    REALISED VOLATILITY
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, mt: 0.5 }}>
                    {regime.features.realised_vol_percentile?.toFixed(1)}%ile
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    21-day rolling vs 252-day history
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                    PAIRWISE CORRELATION
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, mt: 0.5 }}>
                    {regime.features.correlation_percentile?.toFixed(1)}%ile
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Market-wide co-movement percentile
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                    INDIA VIX
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, mt: 0.5 }}>
                    {regime.features.india_vix !== undefined
                      ? regime.features.india_vix.toFixed(1)
                      : "N/A"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Implied vol index level
                  </Typography>
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                    REGIME MULTIPLIER
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 800, mt: 0.5, color: "primary.main" }}>
                    {regime.features.regime_multiplier?.toFixed(2)}x
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {regime.features.hysteresis_applied
                      ? "Hysteresis active (5d lock)"
                      : "Applied to macro risk points"}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          ) : (
            <Alert severity="info">No market regime data currently computed.</Alert>
          )}

          <Divider sx={{ my: 2 }} />
          <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
            As of: <strong>{regime?.as_of || "—"}</strong> • Config Version:{" "}
            <strong>{regime?.config_version || "—"}</strong> • Hysteresis: Stressed requires 5
            consecutive days below 75th percentile to exit back to trending/calm.
          </Typography>
        </CardContent>
      </Card>

      {/* Macro Series Interactive Chart */}
      <Card variant="outlined" sx={{ mb: 4, borderRadius: 2, bgcolor: "#ffffff" }}>
        <CardContent sx={{ p: 3 }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={2}
            sx={{
              mb: 3,
              justifyContent: "space-between",
              alignItems: { xs: "flex-start", md: "center" },
            }}
          >
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Macroeconomic Series Explorer
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Select an approved series to inspect historical values, update frequency, and data
                lineage.
              </Typography>
            </Box>

            {/* Series Selector */}
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
              {seriesList.map((s) => (
                <Chip
                  key={s.series_key}
                  label={s.name}
                  clickable
                  color={selectedSeriesKey === s.series_key ? "primary" : "default"}
                  variant={selectedSeriesKey === s.series_key ? "filled" : "outlined"}
                  onClick={() => setSelectedSeriesKey(s.series_key)}
                  sx={{ fontWeight: 600 }}
                />
              ))}
            </Stack>
          </Stack>

          {/* Metadata Bar */}
          {currentSeries && (
            <Paper
              variant="outlined"
              sx={{ p: 2, mb: 3, bgcolor: "#f8fafc", borderRadius: 2 }}
            >
              <Grid container spacing={2}>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    Source
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {currentSeries.source}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    Frequency / Unit
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {currentSeries.frequency.toUpperCase()} • {currentSeries.unit}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    Total Observations
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {seriesDetail?.total_observations || 0}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="caption" color="text.secondary">
                    Latest Value
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: "primary.main" }}>
                    {seriesDetail?.latest_observation
                      ? `${seriesDetail.latest_observation.value.toLocaleString()} (${seriesDetail.latest_observation.obs_date})`
                      : "—"}
                  </Typography>
                </Grid>
              </Grid>
            </Paper>
          )}

          {/* Interactive Plotly Chart */}
          <Box sx={{ width: "100%", height: 380 }} data-testid="macro-plotly-chart">
            <Suspense fallback={<ChartLoadingFallback />}>
              {seriesLoading ? (
                <ChartLoadingFallback />
              ) : plotData.length > 0 ? (
                <Plot
                  data={plotData}
                  layout={{
                    autosize: true,
                    margin: { l: 60, r: 20, t: 20, b: 40 },
                    xaxis: {
                      title: "Observation Date",
                      showgrid: true,
                      gridcolor: "#f1f5f9",
                    },
                    yaxis: {
                      title: currentSeries ? `${currentSeries.name} (${currentSeries.unit})` : "Value",
                      showgrid: true,
                      gridcolor: "#f1f5f9",
                    },
                    paper_bgcolor: "transparent",
                    plot_bgcolor: "transparent",
                  }}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                  config={{ responsive: true, displayModeBar: false }}
                />
              ) : (
                <Alert severity="info">No observations found for this series.</Alert>
              )}
            </Suspense>
          </Box>
        </CardContent>
      </Card>

      {/* Sector Macro Sensitivity Table */}
      <Card variant="outlined" sx={{ borderRadius: 2, bgcolor: "#ffffff" }}>
        <CardContent sx={{ p: 3 }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={2}
            sx={{
              mb: 3,
              justifyContent: "space-between",
              alignItems: { xs: "flex-start", md: "center" },
            }}
          >
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Sector Macro Sensitivity Matrix (Rolling 63d OLS)
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Equal-weighted industry returns regressed against changes in macro series.
              </Typography>
            </Box>

            <Stack direction="row" spacing={2} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <TextField
                size="small"
                placeholder="Filter industry/series..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                sx={{ width: 200 }}
              />
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel>Industry</InputLabel>
                <Select
                  value={selectedIndustry}
                  label="Industry"
                  onChange={(e) => setSelectedIndustry(e.target.value)}
                >
                  <MenuItem value="ALL">All Industries</MenuItem>
                  {industries.map((ind) => (
                    <MenuItem key={ind} value={ind}>
                      {ind}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControlLabel
                control={
                  <Switch
                    checked={onlySignificant}
                    onChange={(e) => setOnlySignificant(e.target.checked)}
                    color="primary"
                  />
                }
                label={
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    Significant Only (|t| ≥ 1.96)
                  </Typography>
                }
              />
            </Stack>
          </Stack>

          {/* Sensitivity Table */}
          {sensitivitiesLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress size={32} />
            </Box>
          ) : (
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: "#f8fafc" }}>
                  <TableRow>
                    <TableCell>
                      <TableSortLabel
                        active={sortField === "industry"}
                        direction={sortOrder}
                        onClick={() => handleSort("industry")}
                      >
                        Industry
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>Macro Factor</TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={sortField === "beta"}
                        direction={sortOrder}
                        onClick={() => handleSort("beta")}
                      >
                        Beta (Sensitivity)
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={sortField === "t_stat"}
                        direction={sortOrder}
                        onClick={() => handleSort("t_stat")}
                      >
                        t-Statistic
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">p-Value</TableCell>
                    <TableCell align="center">Significance</TableCell>
                    <TableCell align="right">Observations</TableCell>
                    <TableCell align="right">Window End</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredSensitivities.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} align="center" sx={{ py: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          No sensitivity records match the current filters.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredSensitivities.map((row) => (
                      <TableRow
                        key={`${row.industry}_${row.series_key}`}
                        hover
                        sx={{
                          bgcolor: row.is_significant ? "rgba(2, 132, 199, 0.04)" : "inherit",
                        }}
                      >
                        <TableCell sx={{ fontWeight: 700 }}>{row.industry}</TableCell>
                        <TableCell>{row.series_name || row.series_key}</TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontWeight: 700,
                            color:
                              row.beta > 0
                                ? "success.main"
                                : row.beta < 0
                                ? "error.main"
                                : "text.secondary",
                          }}
                        >
                          {row.beta > 0 ? `+${row.beta.toFixed(4)}` : row.beta.toFixed(4)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {row.t_stat.toFixed(2)}
                        </TableCell>
                        <TableCell align="right">{row.p_value.toFixed(4)}</TableCell>
                        <TableCell align="center">
                          <Chip
                            size="small"
                            label={row.is_significant ? "Significant" : "Insignificant"}
                            color={row.is_significant ? "primary" : "default"}
                            variant={row.is_significant ? "filled" : "outlined"}
                            sx={{ fontWeight: 700, fontSize: "0.75rem", height: 22 }}
                          />
                        </TableCell>
                        <TableCell align="right">{row.n_obs}</TableCell>
                        <TableCell align="right" sx={{ color: "text.secondary" }}>
                          {row.window_end}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Explanatory Callout */}
          <Alert severity="info" icon={<InfoOutlinedIcon />} sx={{ mt: 3, borderRadius: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
              Descriptive Exposure Policy (SRS D1, D3):
            </Typography>
            <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
              Only sensitivities meeting the statistical significance threshold (|t| ≥ 1.96, p ≤ 0.05)
              are incorporated into risk scoring. Insignificant sensitivities are assigned zero exposure,
              preventing spurious factor allocations. Historical beta coefficients represent statistical
              correlation, not causality.
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    </Container>
  );
}
