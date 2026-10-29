import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
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
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";
import { Link, useSearchParams } from "react-router-dom";
import MarketOverview from "./MarketOverview";
import AppShell from "./AppShell";
import { ReviewDetails, ReviewHeading } from "./GuidedReview";
import { fetchJson } from "./api";
import type { Horizon, RankingsResponse, SectorRefreshStatus } from "./types";

const periods = [
  { value: 1, title: "Today", description: "1 trading session" },
  { value: 5, title: "One week", description: "5 trading sessions" },
  { value: 20, title: "One month", description: "20 trading sessions" },
] as const;
type SortField =
  "magnitude" | "symbol" | "industry" | "divergence" | "percentile";
export default function Dashboard() {
  const [params, setParams] = useSearchParams();
  const horizon: Horizon =
    params.get("horizon") === "1" ? 1 : params.get("horizon") === "5" ? 5 : 20;

  const [data, setData] = useState<RankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshStatus, setRefreshStatus] =
    useState<SectorRefreshStatus | null>(null);
  const [search, setSearch] = useState("");
  const [industry, setIndustry] = useState("ALL");
  const [direction, setDirection] = useState("all");
  const [sort, setSort] = useState<SortField>("magnitude");
  const [ascending, setAscending] = useState(false);
  const [page, setPage] = useState(0);
  const go = (nextStep: number, period = horizon) =>
    setParams({
      horizon: String(period),
      step: nextStep === 1 ? "companies" : "period",
    });
  const load = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true);
      void fetchJson<RankingsResponse>(
        `/sector-divergence/latest/rankings?horizon=${horizon}&limit=200`,
        signal,
      )
        .then((result) => {
          if (!signal?.aborted) {
            setData(result);
            setError(null);
          }
        })
        .catch((reason: unknown) => {
          if (!signal?.aborted)
            setError(
              reason instanceof Error
                ? reason.message
                : "Unable to load results",
            );
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
      void fetchJson<SectorRefreshStatus>(
        "/sector-divergence/refresh-status",
        signal,
      )
        .then((result) => {
          if (!signal?.aborted) setRefreshStatus(result);
        })
        .catch(() => {});
    },
    [horizon],
  );
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    const timer = setInterval(() => load(controller.signal), 60_000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [load]);
  const currentData = data?.horizon === horizon ? data : null;
  const industries = [
    ...new Set(currentData?.results.map((item) => item.industry) ?? []),
  ].sort();
  const results = useMemo(
    () =>
      (currentData?.results ?? [])
        .filter((item) => {
          const query = search.trim().toLowerCase();
          return (
            (!query ||
              `${item.symbol} ${item.industry}`
                .toLowerCase()
                .includes(query)) &&
            (industry === "ALL" || item.industry === industry) &&
            (direction !== "positive" || item.divergence_value >= 0) &&
            (direction !== "negative" || item.divergence_value < 0) &&
            (direction !== "outliers" ||
              ["strong", "extreme"].includes(item.interpretation))
          );
        })
        .sort((a, b) => {
          const diff =
            sort === "symbol" || sort === "industry"
              ? a[sort].localeCompare(b[sort])
              : sort === "magnitude"
                ? Math.abs(a.divergence_value) - Math.abs(b.divergence_value)
                : sort === "percentile"
                  ? a.industry_percentile - b.industry_percentile
                  : a.divergence_value - b.divergence_value;
          return ascending ? diff : -diff;
        }),
    [currentData, search, industry, direction, sort, ascending],
  );
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil(results.length / 15) - 1),
  );
  const changeSort = (field: SortField) => {
    setPage(0);
    setSort(field);
    setAscending(
      sort === field ? !ascending : field === "symbol" || field === "industry",
    );
  };
  const reset = () => {
    setPage(0);
    setSearch("");
    setIndustry("ALL");
    setDirection("all");
    setSort("magnitude");
    setAscending(false);
  };
  return (
    <AppShell>
      <Stack spacing={2.5} sx={{ width: "100%" }}>
        <ReviewHeading
          title="Explore the market"
          description="Compare companies with their industry peers, across the selected observation window."
        />
        {refreshStatus && (
          <Typography
            variant="body2"
            sx={{ pb: "var(--space-2)", borderBottom: "var(--border-width) solid", borderColor: "divider" }}
          >
            {!refreshStatus.enabled
              ? "Automatic recalculation is disabled."
              : refreshStatus.running
                ? "Updating market data and comparisons."
                : refreshStatus.market_open
                  ? "Market open · recalculates every 30 minutes."
                  : "Market closed · signals paused."}
            {currentData && ` Last signal: ${currentData.run.signal_date}.`}
          </Typography>
        )}
        {refreshStatus?.error && (
          <Alert severity="warning">{refreshStatus.error}</Alert>
        )}
        {refreshStatus?.calendar_warning && (
          <Alert severity="info">{refreshStatus.calendar_warning}</Alert>
        )}
        {currentData?.run.observation_basis ===
          "current_session_provisional" && (
          <Alert severity="info">Current-session prices are provisional.</Alert>
        )}
        <Stack
          direction="row"
          sx={{ gap: "var(--space-1)", alignItems: "center", flexWrap: "wrap" }}
        >
          <Typography variant="overline" sx={{ mr: "var(--space-2)" }}>
            Observation window
          </Typography>
          {periods.map((period) => (
            <Button
              key={period.value}
              variant={horizon === period.value ? "contained" : "outlined"}
              aria-pressed={horizon === period.value}
              onClick={() => {
                reset();
                go(1, period.value);
              }}
            >
              {period.title}
            </Button>
          ))}
        </Stack>
        <MarketOverview data={currentData} horizon={horizon} />{" "}
        <Stack spacing={3}>
          <ReviewHeading
            title="Review companies"
            level={2}
            description={`${horizon} trading ${horizon === 1 ? "session" : "sessions"} · Choose a company to open its peer comparison.`}
            action={
              <Button
                variant="outlined"
                onClick={() => load()}
                disabled={loading}
              >
                {loading ? "Refreshing…" : "Refresh results"}
              </Button>
            }
          />
          {error && (
            <Alert
              severity="warning"
              action={
                <Button onClick={() => load()} disabled={loading}>
                  Retry
                </Button>
              }
            >
              {currentData
                ? "Showing the last available results. "
                : "Results are unavailable. "}
              {error}
            </Alert>
          )}
          <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: "var(--space-2)" }}>
            <TextField
              label="Find a company or industry"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              sx={{ flex: 1 }}
            />
            <FormControl sx={{ minWidth: 190 }}>
              <InputLabel id="industry-label">Industry</InputLabel>
              <Select
                labelId="industry-label"
                label="Industry"
                value={industry}
                onChange={(e) => {
                  setIndustry(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="ALL">All industries</MenuItem>
                {industries.map((name) => (
                  <MenuItem value={name} key={name}>
                    {name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl sx={{ minWidth: 190 }}>
              <InputLabel id="direction-label">Peer difference</InputLabel>
              <Select
                labelId="direction-label"
                label="Peer difference"
                value={direction}
                onChange={(e) => {
                  setDirection(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All companies</MenuItem>
                <MenuItem value="positive">Above peer model</MenuItem>
                <MenuItem value="negative">Below peer model</MenuItem>
                <MenuItem value="outliers">Strong differences</MenuItem>
              </Select>
            </FormControl>
          </Stack>
          <Stack
            direction="row"
            sx={{ alignItems: "center", justifyContent: "space-between" }}
          >
            <Typography role="status" variant="body2">
              {results.length} {results.length === 1 ? "company" : "companies"}
            </Typography>
            {(search || industry !== "ALL" || direction !== "all") && (
              <Button onClick={reset}>Clear filters</Button>
            )}
          </Stack>
          {loading && !currentData ? (
            <Box sx={{ py: "var(--space-4)", textAlign: "center" }}>
              <CircularProgress aria-label="Loading companies" />
            </Box>
          ) : results.length > 0 ? (
            <TableContainer
              component={Paper}
              sx={{
                boxShadow: "none",
                border: "var(--border-width) solid",
                borderColor: "divider",
              }}
            >
              <Table aria-label="Companies compared with industry peers">
                <TableHead>
                  <TableRow>
                    {(
                      [
                        { field: "symbol", label: "Company" },
                        { field: "industry", label: "Industry" },
                        { field: "divergence", label: "Peer difference" },
                        { field: "percentile", label: "Industry percentile" },
                      ] as const
                    ).map((column) => (
                      <TableCell key={column.field}>
                        <TableSortLabel
                          active={sort === column.field}
                          direction={ascending ? "asc" : "desc"}
                          onClick={() => changeSort(column.field)}
                        >
                          {column.label}
                        </TableSortLabel>
                      </TableCell>
                    ))}
                    <TableCell>Review</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results
                    .slice(currentPage * 15, (currentPage + 1) * 15)
                    .map((item) => (
                      <TableRow key={item.symbol} hover>
                        <TableCell
                          component="th"
                          scope="row"
                          sx={{ fontWeight: 600 }}
                        >
                          {item.symbol}
                        </TableCell>
                        <TableCell>{item.industry}</TableCell>
                        <TableCell
                          sx={{
                            fontVariantNumeric: "tabular-nums",
                            color:
                              item.divergence_value >= 0
                                ? "primary.main"
                                : "error.dark",
                          }} align="right"
                        >
                          {item.divergence_value >= 0 ? "+" : ""}
                          {item.divergence_value.toFixed(2)}
                          <Typography
                            variant="caption"
                            sx={{ display: "block" }}
                          >
                            {item.interpretation}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          {item.industry_percentile.toFixed(0)}%
                        </TableCell>
                        <TableCell>
                          <Button
                            component={Link}
                            to={`/companies/${encodeURIComponent(item.symbol)}?horizon=${horizon}`}
                            aria-label={`Compare ${item.symbol}`}
                          >
                            Compare
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Paper sx={{ p: "var(--space-4)", boxShadow: "none", bgcolor: "var(--line)" }}>
              <Typography variant="h3">
                {currentData
                  ? "No companies match these filters"
                  : "No comparison data available"}
              </Typography>
              <Typography sx={{ mt: "var(--space-1)", display: "block" }}>
                {currentData
                  ? "Try another company name or clear your filters."
                  : "Refresh the results to try again."}
              </Typography>
              <Button
                onClick={currentData ? reset : () => load()}
                sx={{ mt: "var(--space-2)" }}
              >
                {currentData ? "Clear filters" : "Refresh results"}
              </Button>
            </Paper>
          )}
          {results.length > 15 && (
            <Stack
              direction="row"
              sx={{
                gap: "var(--space-2)",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <Typography variant="body2">
                Showing {currentPage * 15 + 1}–
                {Math.min((currentPage + 1) * 15, results.length)} of{" "}
                {results.length}
              </Typography>
              <Box>
                <Button
                  disabled={currentPage === 0}
                  onClick={() => setPage(currentPage - 1)}
                >
                  Previous companies
                </Button>
                <Button
                  disabled={(currentPage + 1) * 15 >= results.length}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Next companies
                </Button>
              </Box>
            </Stack>
          )}
        </Stack>
        <ReviewDetails title="How to read the comparison">
          <Typography variant="body2">
            Peer difference measures how far a company moved from its industry
            model over the selected period. Positive values are above the model;
            negative values are below it. The industry percentile describes its
            relative position. These signals describe recent behavior and do not
            predict returns.
          </Typography>
          {currentData && (
            <Typography variant="caption" sx={{ display: "block", mt: "var(--space-2)" }}>
              Signal date: {currentData.run.signal_date} · Data cutoff:{" "}
              {currentData.run.data_cutoff}
            </Typography>
          )}
        </ReviewDetails>
      </Stack>
    </AppShell>
  );
}
