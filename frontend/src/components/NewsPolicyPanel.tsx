import React from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Link,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import PolicyIcon from "@mui/icons-material/Policy";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { useApi } from "../api";
import type { StockNewsResponse } from "../types";

interface NewsPolicyPanelProps {
  symbol: string;
}

export function NewsPolicyPanel({ symbol }: NewsPolicyPanelProps): React.ReactElement {
  const { data, isLoading, error } = useApi<StockNewsResponse>(
    `/stocks/${encodeURIComponent(symbol)}/news`
  );

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        Policy and news intelligence not currently available for {symbol}.
      </Alert>
    );
  }

  const { items = [], disclaimer, industry } = data;

  return (
    <Card
      variant="outlined"
      sx={{
        mb: 3,
        borderRadius: 2,
        bgcolor: "#ffffff",
        borderColor: "divider",
      }}
      data-testid="news-policy-panel"
    >
      <CardContent sx={{ p: 3 }}>
        {/* Header */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{
            mb: 2,
            alignItems: { sm: "center" },
            justifyContent: "space-between",
          }}
        >
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <PolicyIcon color="primary" sx={{ fontSize: 28 }} />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                Policy Press Releases & Sector Headwinds
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Deterministic policy-to-sector rules and regulatory disclosures for {symbol}{" "}
                {industry ? `(${industry})` : ""}
              </Typography>
            </Box>
          </Stack>
          <Chip
            size="small"
            label={`${items.length} Matched Item${items.length === 1 ? "" : "s"}`}
            color={items.length > 0 ? "primary" : "default"}
            variant="outlined"
          />
        </Stack>

        {/* Non-causal disclaimer */}
        <Alert
          severity="info"
          icon={<WarningAmberIcon fontSize="inherit" />}
          sx={{ mb: 3, fontSize: "0.825rem", py: 0.5 }}
        >
          {disclaimer}
        </Alert>

        {items.length === 0 ? (
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              textAlign: "center",
              bgcolor: "#fafafa",
              borderStyle: "dashed",
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No recent regulatory or policy headlines currently matched for {symbol} or industry{" "}
              {industry ?? "sector"}.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={2} divider={<Divider />}>
            {items.map((itemWrapper, idx) => {
              const { news_item, matched_events = [] } = itemWrapper;

              return (
                <Box key={news_item.id} sx={{ pt: idx > 0 ? 1 : 0 }}>
                  {/* Top line: Source, date, external link */}
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{
                      mb: 0.5,
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <Chip
                        label={news_item.source}
                        size="small"
                        sx={{
                          fontWeight: 700,
                          fontSize: "0.7rem",
                          bgcolor: "#e2e8f0",
                        }}
                      />
                      <Typography variant="caption" color="text.secondary">
                        {new Date(news_item.published_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </Typography>
                    </Stack>

                    <Link
                      href={news_item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        fontSize: "0.8rem",
                        textDecoration: "none",
                        color: "primary.main",
                        "&:hover": { textDecoration: "underline" },
                      }}
                    >
                      Official Source <OpenInNewIcon sx={{ fontSize: 14 }} />
                    </Link>
                  </Stack>

                  {/* Headline */}
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                    {news_item.headline}
                  </Typography>

                  {/* Matched Policy Events */}
                  {matched_events.length > 0 && (
                    <Stack spacing={1.5} sx={{ mt: 1 }}>
                      {matched_events.map((evt) => {
                        const isHeadwind = evt.direction === "headwind";
                        const isTailwind = evt.direction === "tailwind";

                        return (
                          <Paper
                            key={evt.id}
                            variant="outlined"
                            sx={{
                              p: 1.5,
                              bgcolor: isHeadwind
                                ? "#fff5f5"
                                : isTailwind
                                ? "#f0fdf4"
                                : "#f8fafc",
                              borderColor: isHeadwind
                                ? "#fed7d7"
                                : isTailwind
                                ? "#bbf7d0"
                                : "#e2e8f0",
                              borderRadius: 1.5,
                            }}
                          >
                            <Stack
                              direction={{ xs: "column", sm: "row" }}
                              spacing={1}
                              sx={{
                                mb: 1,
                                justifyContent: "space-between",
                                alignItems: { sm: "center" },
                              }}
                            >
                              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
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
                                  label={(evt.direction ?? "ambiguous").toUpperCase()}
                                  color={
                                    isHeadwind
                                      ? "error"
                                      : isTailwind
                                      ? "success"
                                      : "default"
                                  }
                                  sx={{ fontWeight: 700, fontSize: "0.7rem" }}
                                />
                                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                                  Rule: {evt.rule_key ?? "Policy Rule"}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  ({evt.affected_industry})
                                </Typography>
                              </Stack>

                              <Typography
                                variant="caption"
                                sx={{
                                  fontWeight: 700,
                                  color: isHeadwind ? "error.dark" : "text.secondary",
                                }}
                              >
                                Severity: {evt.severity.toFixed(1)} / 10.0
                              </Typography>
                            </Stack>

                            {/* Written Economic Rationale */}
                            {evt.rationale && (
                              <Box sx={{ pl: 1, borderLeft: "3px solid #cbd5e1" }}>
                                <Typography
                                  variant="caption"
                                  sx={{
                                    display: "block",
                                    color: "text.primary",
                                    fontStyle: "italic",
                                    fontSize: "0.8rem",
                                  }}
                                >
                                  <strong>Economic Transmission Rationale:</strong> {evt.rationale}
                                </Typography>
                              </Box>
                            )}
                          </Paper>
                        );
                      })}
                    </Stack>
                  )}
                </Box>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
