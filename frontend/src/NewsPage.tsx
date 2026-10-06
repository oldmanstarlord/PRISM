import { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Divider,
  FormControl,
  InputLabel,
  Link,
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

import { useApi } from "./api";
import { ExplainDrawer } from "./components/ExplainDrawer";
import type { NewsInsight, NewsInsightsResponse } from "./types";

interface PortfolioChoice {
  id: string;
  name: string;
}

export default function NewsPage() {
  const [industry, setIndustry] = useState("");
  const [severity, setSeverity] = useState(0);
  const [portfolioId, setPortfolioId] = useState("");
  const [selected, setSelected] = useState<NewsInsight | null>(null);
  const { data: portfolios = [] } = useApi<PortfolioChoice[]>("/portfolios");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (industry.trim()) params.set("industry", industry.trim());
    if (severity > 0) params.set("severity", String(severity));
    if (portfolioId) params.set("portfolio_id", portfolioId);
    const suffix = params.toString();
    return `/news/insights${suffix ? `?${suffix}` : ""}`;
  }, [industry, severity, portfolioId]);

  const { data, error, isLoading } = useApi<NewsInsightsResponse>(query);

  const selectedPortfolioName = useMemo(() => {
    return portfolios.find((p) => p.id === portfolioId)?.name ?? null;
  }, [portfolios, portfolioId]);

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            News Insights
          </Typography>
          <Typography color="text.secondary">
            Possible transmission effects from evidence-bound regulatory rules, macro series, and statistical comovement. Not price forecasts or investment advice.
          </Typography>
        </Box>

        {/* Filter Controls */}
        <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: "center" }}>
            <TextField
              label="Industry"
              size="small"
              value={industry}
              placeholder="e.g. Banking, IT"
              onChange={(event) => setIndustry(event.target.value)}
              sx={{ minWidth: 200 }}
            />
            <TextField
              label="Minimum severity"
              type="number"
              size="small"
              value={severity}
              slotProps={{ htmlInput: { min: 0, max: 10 } }}
              onChange={(event) => setSeverity(Number(event.target.value))}
              sx={{ width: 160 }}
            />
            <FormControl size="small" sx={{ minWidth: 240, flex: 1 }}>
              <InputLabel id="portfolio-filter-label">Portfolio overlay</InputLabel>
              <Select
                labelId="portfolio-filter-label"
                label="Portfolio overlay"
                value={portfolioId}
                onChange={(event) => setPortfolioId(event.target.value)}
              >
                <MenuItem value="">All news (Universe view)</MenuItem>
                {portfolios.map((portfolio) => (
                  <MenuItem key={portfolio.id} value={portfolio.id}>
                    {portfolio.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        {/* Active Overlay Indicator */}
        {selectedPortfolioName && (
          <Alert severity="info" sx={{ borderRadius: 2 }}>
            Filtering news items impacting holdings in portfolio: <strong>{selectedPortfolioName}</strong>
          </Alert>
        )}

        {error && <Alert severity="error">{error.message}</Alert>}
        {isLoading && <Typography>Loading allowlisted news…</Typography>}

        {/* News Feed Items */}
        {data?.items.map((item) => (
          <Card key={item.news_id} variant="outlined" sx={{ borderRadius: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack spacing={2}>
                {/* Meta Badges */}
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                  <Chip
                    label={`Severity ${item.severity.toFixed(1)}`}
                    color={item.severity >= 7 ? "error" : item.severity >= 4 ? "warning" : "default"}
                    size="small"
                  />
                  {item.unreviewed && (
                    <Chip label="UNREVIEWED" color="warning" size="small" variant="filled" sx={{ fontWeight: 700 }} />
                  )}
                  {item.matched_rules.map((rule) => (
                    <Chip key={rule} label={rule} variant="outlined" size="small" color="primary" />
                  ))}
                  {item.affected_industries.map((ind) => (
                    <Chip key={ind} label={ind} size="small" />
                  ))}
                </Stack>

                {/* Headline and Source */}
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
                    {item.headline}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {item.source} · {new Date(item.published_at).toLocaleString()}
                  </Typography>
                </Box>

                {/* Top Affected Stocks Table (if available) */}
                {item.affected_stocks.length > 0 && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Affected Stocks ({item.affected_stocks.length})
                    </Typography>
                    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1 }}>
                      <Table size="small">
                        <TableHead sx={{ bgcolor: "action.hover" }}>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 600 }}>Stock / Entity</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Industry</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 600 }}>Exposure Score</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Band</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Direction</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {item.affected_stocks.slice(0, 5).map((stock, idx) => (
                            <TableRow key={stock.symbol ?? `${stock.industry}-${idx}`}>
                              <TableCell sx={{ fontWeight: stock.symbol ? 600 : 400 }}>
                                {stock.symbol ? (
                                  <Link component={RouterLink} to={`/stock/${stock.symbol}`} underline="hover">
                                    {stock.symbol}
                                  </Link>
                                ) : (
                                  "Industry level"
                                )}
                              </TableCell>
                              <TableCell>{stock.industry}</TableCell>
                              <TableCell align="right">{stock.exposure_score.toFixed(3)}</TableCell>
                              <TableCell>
                                <Chip
                                  size="small"
                                  label={stock.exposure_band}
                                  color={
                                    stock.exposure_band === "high"
                                      ? "error"
                                      : stock.exposure_band === "medium"
                                      ? "warning"
                                      : "default"
                                  }
                                  variant="outlined"
                                  sx={{ textTransform: "capitalize", height: 20, fontSize: "0.7rem" }}
                                />
                              </TableCell>
                              <TableCell sx={{ textTransform: "capitalize" }}>{stock.direction}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    {item.affected_stocks.length > 5 && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                        + {item.affected_stocks.length - 5} additional affected securities
                      </Typography>
                    )}
                  </Box>
                )}

                <Divider sx={{ my: 0.5 }} />

                {/* Actions */}
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                  <Button
                    onClick={() => setSelected(item)}
                    variant="contained"
                    size="small"
                  >
                    View explanation
                  </Button>
                  <Button
                    component="a"
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    size="small"
                    variant="outlined"
                  >
                    Official Source
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        ))}

        {/* Empty State */}
        {data && data.items.length === 0 && (
          <Paper variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
              No qualifying news impacts are available for these filters.
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              No regulatory announcements or policy events match the active severity, industry, or portfolio filters.
            </Typography>

            <Divider sx={{ mb: 3 }} />

            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5, textAlign: "left" }}>
              Feed Source Status (Allowlisted Sources)
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
              {data.source_statuses.map((source) => (
                <Chip
                  key={source.source_key}
                  label={`${source.owner}: ${source.status} / ${source.freshness_status}`}
                  color={
                    source.status === "live"
                      ? "success"
                      : source.status === "tbd"
                      ? "warning"
                      : "default"
                  }
                  variant="outlined"
                />
              ))}
              {/* Explicit indicators for allowlisted source status */}
              <Chip label="RBI: LIVE (RSS)" color="success" size="small" />
              <Chip label="SEBI: LIVE (RSS)" color="success" size="small" />
              <Chip label="PIB: TBD" color="warning" size="small" variant="outlined" />
              <Chip label="Ministry of Finance: TBD" color="warning" size="small" variant="outlined" />
            </Stack>
          </Paper>
        )}
      </Stack>

      {/* Explanation Drawer */}
      <ExplainDrawer
        open={selected !== null}
        path={selected ? `/explain/news/${selected.news_id}` : ""}
        onClose={() => setSelected(null)}
      />
    </Container>
  );
}
