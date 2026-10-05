import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Pagination,
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
import SearchIcon from "@mui/icons-material/Search";
import ShieldIcon from "@mui/icons-material/Shield";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { useApi } from "./api";
import type { StockScoresResponse } from "./types";
import { FreshnessBadge } from "./components/FreshnessBadge";

export default function StocksPage() {
  const [industryFilter, setIndustryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("risk");
  const [sortOrder, setSortOrder] = useState<string>("desc");
  const [page, setPage] = useState<number>(1);
  const pageSize = 25;

  const queryPath = `/stocks/scores/latest?sort_by=${sortBy}&sort_order=${sortOrder}&page=${page}&page_size=${pageSize}${
    industryFilter !== "all" ? `&industry=${encodeURIComponent(industryFilter)}` : ""
  }`;

  const { data, isLoading, error } = useApi<StockScoresResponse>(queryPath);

  // Filter items by client search query if present
  const items = (data?.items || []).filter((item) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.symbol.toLowerCase().includes(q) ||
      item.company_name.toLowerCase().includes(q) ||
      item.industry.toLowerCase().includes(q)
    );
  });

  // Calculate industry list from items
  const industries = Array.from(
    new Set((data?.items || []).map((i) => i.industry).filter(Boolean))
  ).sort();

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", px: { xs: 2, sm: 3 }, py: 3 }}>
      {/* Page Header */}
      <Stack spacing={1} sx={{ mb: 3 }}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <ShieldIcon color="primary" sx={{ fontSize: 32 }} />
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>
            Multi-Dimensional Stock Risk Explorer & Screener
          </Typography>
        </Stack>
        <Typography variant="body1" color="text.secondary">
          Dynamic multi-component risk synthesis across 8 dimensions. Empirical peer percentiles,
          coverage tracking, and confidence envelopes (D1–D6).
        </Typography>
        {data?.as_of_date && (
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", pt: 0.5 }}>
            <FreshnessBadge
              asOf={data.as_of_date}
              label={`Run As Of: ${data.as_of_date}`}
            />
            <Chip
              label={`Config v${data.config_version}`}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 600 }}
            />
            <Chip
              label={`${data.total_items} Securities Scored`}
              size="small"
              color="primary"
              variant="filled"
            />
          </Stack>
        )}
      </Stack>

      {/* Disclaimers Alert */}
      <Alert severity="info" sx={{ mb: 3 }} icon={<InfoOutlinedIcon />}>
        <strong>Descriptive Risk Assessment:</strong> PRISM provides risk synthesis and peer
        decoupling analysis, <em>not price prediction</em> and <em>not investment advice</em>. High
        scores reflect elevated composite risk factors relative to empirical peer distributions.
      </Alert>

      {/* Filter and Control Bar */}
      <Card variant="outlined" sx={{ mb: 3, p: 2, borderRadius: 2 }}>
        <Grid container spacing={2} sx={{ alignItems: "center" }}>
          <Grid size={{ xs: 12, sm: 4, md: 3 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search symbol or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              slotProps={{
                input: {
                  startAdornment: <SearchIcon fontSize="small" sx={{ mr: 1, color: "text.secondary" }} />,
                },
              }}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 4, md: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel id="industry-filter-label">Industry Group</InputLabel>
              <Select
                labelId="industry-filter-label"
                value={industryFilter}
                label="Industry Group"
                onChange={(e) => {
                  setIndustryFilter(e.target.value);
                  setPage(1);
                }}
              >
                <MenuItem value="all">All Industries</MenuItem>
                {industries.map((ind) => (
                  <MenuItem key={ind} value={ind}>
                    {ind}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 6, sm: 2, md: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel id="sort-by-label">Sort By</InputLabel>
              <Select
                labelId="sort-by-label"
                value={sortBy}
                label="Sort By"
                onChange={(e) => setSortBy(e.target.value)}
              >
                <MenuItem value="risk">Risk Score</MenuItem>
                <MenuItem value="confidence">Confidence</MenuItem>
                <MenuItem value="coverage">Data Coverage</MenuItem>
                <MenuItem value="symbol">Symbol</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 6, sm: 2, md: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel id="sort-order-label">Order</InputLabel>
              <Select
                labelId="sort-order-label"
                value={sortOrder}
                label="Order"
                onChange={(e) => setSortOrder(e.target.value)}
              >
                <MenuItem value="desc">Highest First</MenuItem>
                <MenuItem value="asc">Lowest First</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 12, md: 2 }} sx={{ textAlign: { md: "right" } }}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setSearchQuery("");
                setIndustryFilter("all");
                setSortBy("risk");
                setSortOrder("desc");
                setPage(1);
              }}
            >
              Reset Filters
            </Button>
          </Grid>
        </Grid>
      </Card>

      {/* Loading & Error States */}
      {isLoading && (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center", borderRadius: 2 }}>
          <CircularProgress size={40} sx={{ mb: 2 }} />
          <Typography color="text.secondary">Synthesizing multi-dimensional risk scores...</Typography>
        </Paper>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load stock risk scores: {error.message}
        </Alert>
      )}

      {/* Screener Table */}
      {!isLoading && !error && (
        <>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
            <Table aria-label="stock risk screener table" size="medium">
              <TableHead sx={{ bgcolor: "action.hover" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Symbol & Company</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Industry</TableCell>
                  <TableCell sx={{ fontWeight: 700, minWidth: 160 }}>Risk Score (0–100)</TableCell>
                  <TableCell sx={{ fontWeight: 700, minWidth: 130 }}>Confidence</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Coverage</TableCell>
                  <TableCell sx={{ fontWeight: 700, minWidth: 260 }}>Primary Risk Driver</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} sx={{ textAlign: "center", py: 4 }}>
                      <Typography color="text.secondary">
                        No stocks matched the specified filter criteria.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((row) => {
                    const score = row.total_score;
                    const conf = row.confidence;
                    const covPct = Math.round(row.data_coverage * 100);

                    // Risk score color: green < 40, orange 40-70, red >= 70
                    const riskColor =
                      score >= 70
                        ? "error"
                        : score >= 45
                        ? "warning"
                        : "success";

                    return (
                      <TableRow key={row.symbol} hover>
                        <TableCell>
                          <RouterLink
                            to={`/stocks/${row.symbol}`}
                            style={{ textDecoration: "none", color: "inherit" }}
                          >
                            <Typography
                              variant="subtitle2"
                              sx={{
                                fontWeight: 700,
                                color: "primary.main",
                                "&:hover": { textDecoration: "underline" },
                              }}
                            >
                              {row.symbol}
                            </Typography>
                          </RouterLink>
                          <Typography variant="caption" color="text.secondary">
                            {row.company_name}
                          </Typography>
                        </TableCell>

                        <TableCell>
                          <Typography variant="body2">{row.industry}</Typography>
                        </TableCell>

                        <TableCell>
                          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                            <Chip
                              label={score.toFixed(1)}
                              color={riskColor}
                              size="small"
                              sx={{ fontWeight: 700, minWidth: 50 }}
                            />
                            <Box sx={{ width: 80 }}>
                              <LinearProgress
                                variant="determinate"
                                value={score}
                                color={riskColor}
                                sx={{ height: 6, borderRadius: 3 }}
                              />
                            </Box>
                          </Stack>
                        </TableCell>

                        <TableCell>
                          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                            <Chip
                              label={`${conf.toFixed(0)}%`}
                              size="small"
                              variant="outlined"
                              color={conf >= 70 ? "primary" : conf >= 50 ? "warning" : "error"}
                              sx={{ fontWeight: 600 }}
                            />
                          </Stack>
                        </TableCell>

                        <TableCell>
                          <Tooltip title={`${covPct}% of potential dimension weight available`}>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {covPct}%
                            </Typography>
                          </Tooltip>
                        </TableCell>

                        <TableCell sx={{ maxWidth: 320 }}>
                          {row.top_reason ? (
                            <Typography variant="body2" color="text.secondary">
                              {row.top_reason.text}
                            </Typography>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              Uniform peer alignment.
                            </Typography>
                          )}
                        </TableCell>

                        <TableCell align="right">
                          <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
                            <Button
                              component={RouterLink}
                              to={`/stocks/${row.symbol}`}
                              size="small"
                              variant="contained"
                              sx={{ textTransform: "none" }}
                            >
                              Details
                            </Button>
                            <Button
                              component={RouterLink}
                              to={`/companies/${row.symbol}`}
                              size="small"
                              variant="outlined"
                              sx={{ textTransform: "none" }}
                              title="Layer 1 Sector Divergence"
                            >
                              L1 Peer
                            </Button>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination */}
          {data && data.total_items > pageSize && (
            <Stack direction="row" sx={{ justifyContent: "center", mt: 2 }}>
              <Pagination
                count={Math.ceil(data.total_items / pageSize)}
                page={page}
                onChange={(_, val) => setPage(val)}
                color="primary"
              />
            </Stack>
          )}
        </>
      )}
    </Box>
  );
}
