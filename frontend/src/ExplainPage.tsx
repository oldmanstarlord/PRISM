import { useState, useMemo } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Grid,
  IconButton,
  InputAdornment,
  Paper,
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
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import AutoStoriesIcon from "@mui/icons-material/AutoStories";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";

import { useApi } from "./api";
import { ExplainDrawer } from "./components/ExplainDrawer";
import type { ExplanationSearchResultItem, ExplanationSummaryItem } from "./types";

export default function ExplainPage() {
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [explainPath, setExplainPath] = useState<string>("");

  // Search API
  const searchUrl = query.trim().length > 0
    ? `/explain/search?query=${encodeURIComponent(query.trim())}&limit=20`
    : null;
  const { data: searchResults = [], isLoading: searchLoading } =
    useApi<ExplanationSearchResultItem[]>(searchUrl ?? "");

  // Recent Explanations API
  const { data: recentExplanations = [], isLoading: recentLoading, error: recentError } =
    useApi<ExplanationSummaryItem[]>("/explain/recent?limit=30");

  const filteredSearchResults = useMemo(() => {
    if (selectedCategory === "all") return searchResults;
    return searchResults.filter((r) => r.category.toLowerCase() === selectedCategory.toLowerCase());
  }, [searchResults, selectedCategory]);

  const filteredRecent = useMemo(() => {
    if (selectedCategory === "all") return recentExplanations;
    return recentExplanations.filter((r) => {
      const type = r.subject_type.toLowerCase();
      if (selectedCategory === "stock") return type.includes("risk") || type.includes("sector") || type.includes("score");
      if (selectedCategory === "pair") return type.includes("mst") || type.includes("pair");
      if (selectedCategory === "news") return type.includes("news");
      return true;
    });
  }, [recentExplanations, selectedCategory]);

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Stack spacing={1} sx={{ mb: 4 }}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <AutoStoriesIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h3" component="h1" sx={{ fontWeight: 800 }}>
            Explanation Index
          </Typography>
        </Stack>
        <Typography variant="body1" color="text.secondary">
          Evidence-bound, non-causal explanations for multidimensional stock risk, network tree connections, sector divergences, news transmission, and portfolio diversification.
        </Typography>
      </Stack>

      {/* Search & Filter Bar */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 4, borderRadius: 2 }}>
        <Stack spacing={2}>
          <TextField
            fullWidth
            placeholder="Search by stock symbol (e.g. TCS), pair (e.g. TCS-INFY), news topic, or risk condition..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
                endAdornment: query ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setQuery("")} aria-label="Clear search">
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              },
            }}
          />

          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1, alignItems: "center" }}>
            <Typography variant="caption" sx={{ fontWeight: 700, mr: 1 }}>
              Filter by entity:
            </Typography>
            {[
              { id: "all", label: "All" },
              { id: "stock", label: "Stocks" },
              { id: "pair", label: "Tree Pairs" },
              { id: "news", label: "News Impacts" },
            ].map((cat) => (
              <Chip
                key={cat.id}
                label={cat.label}
                clickable
                color={selectedCategory === cat.id ? "primary" : "default"}
                variant={selectedCategory === cat.id ? "filled" : "outlined"}
                onClick={() => setSelectedCategory(cat.id)}
                size="small"
              />
            ))}
          </Stack>
        </Stack>
      </Paper>

      {/* Search Results (Active when user types) */}
      {query.trim().length > 0 && (
        <Box sx={{ mb: 5 }}>
          <Typography variant="h5" sx={{ fontWeight: 750, mb: 2 }}>
            Search Results ({filteredSearchResults.length})
          </Typography>

          {searchLoading && (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {!searchLoading && filteredSearchResults.length === 0 && (
            <Alert severity="info" sx={{ borderRadius: 1.5 }}>
              No explanations found matching &ldquo;{query}&rdquo;. You can search by symbol (e.g. RELIANCE, TCS) or pair (TCS-INFY).
            </Alert>
          )}

          <Grid container spacing={2}>
            {filteredSearchResults.map((res, idx) => (
              <Grid size={{ xs: 12, md: 6 }} key={`${res.path}-${idx}`}>
                <Card
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    transition: "transform 0.15s, box-shadow 0.15s",
                    "&:hover": {
                      boxShadow: 2,
                      borderColor: "primary.main",
                    },
                  }}
                >
                  <CardContent>
                    <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
                      <Chip
                        size="small"
                        label={res.category.toUpperCase()}
                        color={
                          res.category === "stock"
                            ? "primary"
                            : res.category === "pair"
                            ? "secondary"
                            : res.category === "news"
                            ? "warning"
                            : "default"
                        }
                        sx={{ fontSize: "0.7rem", fontWeight: 700 }}
                      />
                      <Button
                        size="small"
                        variant="outlined"
                        endIcon={<OpenInNewIcon fontSize="small" />}
                        onClick={() => setExplainPath(res.path)}
                      >
                        Explain
                      </Button>
                    </Stack>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 1 }}>
                      {res.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {res.subtitle}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Recent Explanations Table */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" sx={{ fontWeight: 750, mb: 2 }}>
          Recent & Precomputed Explanations
        </Typography>

        {recentLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {recentError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Unable to load recent explanations: {recentError.message}
          </Alert>
        )}

        {!recentLoading && filteredRecent.length === 0 && (
          <Alert severity="info" sx={{ borderRadius: 1.5 }}>
            No recent explanations found in cache. Use the search bar above or click &ldquo;Why?&rdquo; on any dashboard signal to generate one on demand.
          </Alert>
        )}

        {!recentLoading && filteredRecent.length > 0 && (
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead sx={{ bgcolor: "action.hover" }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Subject</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Headline</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>As Of</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Confidence</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredRecent.map((item) => (
                  <TableRow
                    key={item.id}
                    hover
                    sx={{ cursor: "pointer" }}
                    onClick={() => setExplainPath(item.request_path)}
                  >
                    <TableCell>
                      <Chip
                        size="small"
                        label={item.subject_type.replace(/_/g, " ")}
                        variant="outlined"
                        sx={{ fontSize: "0.72rem", textTransform: "capitalize" }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>{item.subject_key}</TableCell>
                    <TableCell sx={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.headline}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>{item.as_of}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={item.confidence_level}
                        color={
                          item.confidence_level === "high"
                            ? "success"
                            : item.confidence_level === "low"
                            ? "warning"
                            : "info"
                        }
                        sx={{ fontSize: "0.72rem" }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        variant="text"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExplainPath(item.request_path);
                        }}
                      >
                        Explain
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {/* Global Shared Explain Drawer */}
      <ExplainDrawer
        open={Boolean(explainPath)}
        path={explainPath}
        onClose={() => setExplainPath("")}
      />
    </Container>
  );
}
