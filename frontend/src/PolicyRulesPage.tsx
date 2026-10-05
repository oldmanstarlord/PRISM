import React, { useMemo, useState } from "react";
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
  InputAdornment,
  MenuItem,
  OutlinedInput,
  Paper,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import PolicyIcon from "@mui/icons-material/Policy";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import VerifiedUserIcon from "@mui/icons-material/VerifiedUser";

import { useApi } from "./api";
import type { PolicyRule } from "./types";

export default function PolicyRulesPage(): React.ReactElement {
  const { data: rules = [], isLoading, error } = useApi<PolicyRule[]>("/policy/rules");

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [activeFilter, setActiveFilter] = useState<string>("ALL");

  // Extract unique categories
  const categories = useMemo(() => {
    const set = new Set<string>();
    rules.forEach((r) => {
      if (r.match_category) set.add(r.match_category);
    });
    return Array.from(set).sort();
  }, [rules]);

  // Filter rules
  const filteredRules = useMemo(() => {
    return rules.filter((rule) => {
      // Category filter
      if (selectedCategory !== "ALL" && rule.match_category !== selectedCategory) {
        return false;
      }
      // Active filter
      if (activeFilter === "ACTIVE" && !rule.active) return false;
      if (activeFilter === "DRAFT" && rule.active) return false;

      // Search term
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchesKey = rule.rule_key.toLowerCase().includes(query);
        const matchesDesc = rule.description.toLowerCase().includes(query);
        const matchesRationale = rule.rationale.toLowerCase().includes(query);
        const matchesReviewer = rule.reviewer.toLowerCase().includes(query);
        const matchesKeywords = rule.match_keywords.some((kw) =>
          kw.toLowerCase().includes(query)
        );
        const matchesIndustries = rule.affected_industries.some((ind) =>
          ind.toLowerCase().includes(query)
        );

        return (
          matchesKey ||
          matchesDesc ||
          matchesRationale ||
          matchesReviewer ||
          matchesKeywords ||
          matchesIndustries
        );
      }

      return true;
    });
  }, [rules, selectedCategory, activeFilter, searchTerm]);

  return (
    <Container maxWidth="lg" sx={{ py: 4 }} data-testid="policy-rules-page">
      {/* Title & Header */}
      <Stack spacing={1} sx={{ mb: 3 }}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <PolicyIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" component="h1" sx={{ fontWeight: 800 }}>
            Policy & Regulatory Sector Rules
          </Typography>
        </Stack>
        <Typography variant="body1" color="text.secondary">
          Explainable, deterministic transmission rules mapping government, central bank, and
          regulatory press releases to sector headwinds with written economic rationales and
          versioned reviewer accountability (D1, D3).
        </Typography>
      </Stack>

      {/* Non-Causal Regulatory Disclaimer */}
      <Alert
        severity="info"
        icon={<WarningAmberIcon fontSize="inherit" />}
        sx={{ mb: 4, borderRadius: 2 }}
      >
        <strong>Descriptive Risk Disclaimer:</strong> Markets may have already priced this in. PRISM
        policy rules are deterministic descriptive filters mapping regulatory announcements to sector
        headwinds, not trading recommendations, investment advice, or price predictions.
      </Alert>

      {/* Filter Toolbar */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3, borderRadius: 2 }}>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "2fr 1fr 1fr" },
            gap: 2,
            alignItems: "center",
          }}
        >
          <Box>
            <OutlinedInput
              fullWidth
              size="small"
              placeholder="Search rules, keywords, industries, rationales..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              startAdornment={
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              }
            />
          </Box>

          <Box>
            <FormControl fullWidth size="small">
              <Select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                displayEmpty
              >
                <MenuItem value="ALL">All Categories ({rules.length})</MenuItem>
                {categories.map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat.toUpperCase()} (
                    {rules.filter((r) => r.match_category === cat).length})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Box>
            <FormControl fullWidth size="small">
              <Select
                value={activeFilter}
                onChange={(e) => setActiveFilter(e.target.value)}
              >
                <MenuItem value="ALL">All Statuses (Active & Draft)</MenuItem>
                <MenuItem value="ACTIVE">Active Only</MenuItem>
                <MenuItem value="DRAFT">Draft / Under Review</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>
      </Paper>

      {/* Content Area */}
      {isLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load policy rules. Please check backend connection.
        </Alert>
      ) : filteredRules.length === 0 ? (
        <Paper
          variant="outlined"
          sx={{ p: 4, textAlign: "center", bgcolor: "#fafafa", borderRadius: 2 }}
        >
          <Typography variant="subtitle1" color="text.secondary">
            No policy rules matched the active search filters.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={3}>
          {filteredRules.map((rule) => {
            const isHeadwind = rule.direction === "headwind";
            const isTailwind = rule.direction === "tailwind";

            return (
              <Card
                key={rule.id}
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                  "&:hover": { boxShadow: "0 4px 12px rgba(0,0,0,0.08)" },
                  transition: "box-shadow 0.2s ease-in-out",
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  {/* Top Bar: Rule Key, Direction, Severity, Version, Status */}
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1.5}
                    sx={{
                      mb: 1.5,
                      justifyContent: "space-between",
                      alignItems: { sm: "center" },
                    }}
                  >
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                      <Typography
                        variant="subtitle1"
                        sx={{ fontWeight: 800, fontFamily: "monospace" }}
                      >
                        {rule.rule_key}
                      </Typography>
                      <Chip
                        size="small"
                        icon={
                          isHeadwind ? (
                            <WarningAmberIcon />
                          ) : isTailwind ? (
                            <TrendingUpIcon />
                          ) : (
                            <InfoOutlinedIcon />
                          )
                        }
                        label={rule.direction.toUpperCase()}
                        color={
                          isHeadwind ? "error" : isTailwind ? "success" : "default"
                        }
                        sx={{ fontWeight: 700, fontSize: "0.72rem" }}
                      />
                      <Chip
                        size="small"
                        label={`v${rule.version}`}
                        variant="outlined"
                        sx={{ fontWeight: 600, fontSize: "0.72rem" }}
                      />
                      <Chip
                        size="small"
                        label={rule.active ? "ACTIVE" : "DRAFT"}
                        color={rule.active ? "success" : "warning"}
                        variant={rule.active ? "filled" : "outlined"}
                        sx={{ fontWeight: 700, fontSize: "0.72rem" }}
                      />
                    </Stack>

                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 700,
                        color: isHeadwind ? "error.main" : "text.secondary",
                      }}
                    >
                      Severity: {rule.severity.toFixed(1)} / 10.0
                    </Typography>
                  </Stack>

                  {/* Description */}
                  <Typography variant="body1" sx={{ mb: 2, fontWeight: 500 }}>
                    {rule.description}
                  </Typography>

                  {/* Affected Industries & Keywords */}
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                      gap: 2,
                      mb: 2.5,
                    }}
                  >
                    <Box>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", display: "block", mb: 0.5 }}>
                        AFFECTED INDUSTRIES
                      </Typography>
                      <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
                        {rule.affected_industries.map((ind) => (
                          <Chip
                            key={ind}
                            label={ind}
                            size="small"
                            sx={{ bgcolor: "#edf2f7", fontSize: "0.75rem" }}
                          />
                        ))}
                      </Stack>
                    </Box>

                    <Box>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", display: "block", mb: 0.5 }}>
                        MATCH KEYWORDS
                      </Typography>
                      <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
                        {rule.match_keywords.map((kw) => (
                          <Chip
                            key={kw}
                            label={kw}
                            size="small"
                            variant="outlined"
                            sx={{ fontFamily: "monospace", fontSize: "0.72rem" }}
                          />
                        ))}
                      </Stack>
                    </Box>
                  </Box>

                  {/* Mandatory Economic Rationale Callout Box */}
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      bgcolor: "#f8fafc",
                      borderColor: "#e2e8f0",
                      borderLeft: "4px solid #3182ce",
                      borderRadius: 1.5,
                      mb: 2,
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{ fontWeight: 800, color: "#2b6cb0", display: "block", mb: 0.5, letterSpacing: 0.5 }}
                    >
                      MANDATORY ECONOMIC TRANSMISSION RATIONALE
                    </Typography>
                    <Typography variant="body2" sx={{ color: "text.primary", lineHeight: 1.6 }}>
                      {rule.rationale}
                    </Typography>
                  </Paper>

                  <Divider sx={{ my: 1.5 }} />

                  {/* Audit Trail Footer */}
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1}
                    sx={{
                      justifyContent: "space-between",
                      alignItems: { sm: "center" },
                    }}
                  >
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <VerifiedUserIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                      <Typography variant="caption" color="text.secondary">
                        Reviewer: <strong>{rule.reviewer}</strong>
                      </Typography>
                      {rule.match_category && (
                        <Typography variant="caption" color="text.secondary">
                          • Category: <strong>{rule.match_category}</strong>
                        </Typography>
                      )}
                    </Stack>

                    <Typography variant="caption" color="text.disabled">
                      Created: {new Date(rule.created_at).toLocaleDateString()}
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      )}
    </Container>
  );
}
