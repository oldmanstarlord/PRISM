import React, { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import AnnouncementIcon from "@mui/icons-material/Announcement";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import RemoveIcon from "@mui/icons-material/Remove";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import type { EventItem } from "../types";

export interface TimelinePricePoint {
  date: string;
  price: number;
}

export interface TimelineProps {
  events: EventItem[];
  pricePoints?: TimelinePricePoint[];
  symbol?: string;
  title?: string;
}

export function Timeline({
  events,
  pricePoints = [],
  symbol,
  title = "Corporate Announcements & Explainable Events",
}: TimelineProps) {
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedSentiment, setSelectedSentiment] = useState<string>("all");
  const [minImportance, setMinImportance] = useState<number>(0);
  const [highlightedEventId, setHighlightedEventId] = useState<string | null>(null);

  // Filter events based on selections
  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      if (selectedType !== "all" && ev.event_type !== selectedType) {
        return false;
      }
      if (selectedSentiment !== "all" && ev.sentiment !== selectedSentiment) {
        return false;
      }
      if (ev.importance < minImportance) {
        return false;
      }
      return true;
    });
  }, [events, selectedType, selectedSentiment, minImportance]);

  // Unique event types present in dataset
  const availableTypes = useMemo(() => {
    const set = new Set<string>();
    events.forEach((e) => set.add(e.event_type));
    return Array.from(set);
  }, [events]);

  const getSentimentChip = (sentiment?: string | null) => {
    switch (sentiment) {
      case "positive":
        return (
          <Chip
            size="small"
            icon={<TrendingUpIcon fontSize="small" />}
            label="Positive"
            color="success"
            variant="filled"
          />
        );
      case "negative":
        return (
          <Chip
            size="small"
            icon={<TrendingDownIcon fontSize="small" />}
            label="Negative"
            color="error"
            variant="filled"
          />
        );
      case "neutral":
      default:
        return (
          <Chip
            size="small"
            icon={<RemoveIcon fontSize="small" />}
            label="Neutral"
            variant="outlined"
          />
        );
    }
  };

  const getImportanceColor = (imp: number) => {
    if (imp >= 8.0) return "#d32f2f"; // red
    if (imp >= 5.0) return "#ed6c02"; // orange
    return "#0288d1"; // blue
  };

  // Synthetic price points if none provided, to establish a visual horizontal price/date axis
  const chartPoints = useMemo(() => {
    if (pricePoints.length > 0) return pricePoints;
    if (events.length === 0) return [];
    // Sort unique dates
    const dates = Array.from(
      new Set(events.map((e) => e.effective_trading_date))
    ).sort();
    return dates.map((d, idx) => ({
      date: d,
      price: 100 + (idx % 2 === 0 ? idx * 4 : -idx * 2),
    }));
  }, [pricePoints, events]);

  // Chart dimensions
  const svgWidth = 840;
  const svgHeight = 160;
  const padLeft = 50;
  const padRight = 40;
  const padTop = 30;
  const padBottom = 30;

  const prices = chartPoints.map((p) => p.price);
  const minPrice = prices.length ? Math.min(...prices) * 0.98 : 90;
  const maxPrice = prices.length ? Math.max(...prices) * 1.02 : 110;

  const getX = (index: number) => {
    if (chartPoints.length <= 1) return (svgWidth - padLeft - padRight) / 2 + padLeft;
    return padLeft + (index / (chartPoints.length - 1)) * (svgWidth - padLeft - padRight);
  };

  const getY = (price: number) => {
    return (
      padTop +
      ((maxPrice - price) / Math.max(maxPrice - minPrice, 1)) *
        (svgHeight - padTop - padBottom)
    );
  };

  const polylineStr = chartPoints
    .map((p, i) => `${getX(i)},${getY(p.price)}`)
    .join(" ");

  return (
    <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
      <CardContent>
        {/* Title & Market disclaimer notice */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1}
          sx={{
            mb: 2,
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <AnnouncementIcon color="primary" />
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              {title}
            </Typography>
            {symbol && (
              <Chip
                label={symbol}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 600 }}
              />
            )}
          </Stack>
        </Stack>

        <Alert
          severity="info"
          icon={<InfoOutlinedIcon fontSize="inherit" />}
          sx={{ mb: 3, fontSize: "0.85rem" }}
        >
          <strong>Note:</strong> Markets may have already priced this in. PRISM event
          signals quantify descriptive pressure and sentiment, not investment advice or
          directional forecasts.
        </Alert>

        {/* Interactive Filter Bar */}
        <Paper
          variant="outlined"
          sx={{ p: 2, mb: 3, backgroundColor: "#fafbfc", borderRadius: 2 }}
        >
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" },
              gap: 2,
              alignItems: "center",
            }}
          >
            <Box>
              <FormControl fullWidth size="small">
                <InputLabel id="event-type-filter-label">Event Type</InputLabel>
                <Select
                  labelId="event-type-filter-label"
                  id="event-type-filter"
                  value={selectedType}
                  label="Event Type"
                  onChange={(e) => setSelectedType(e.target.value)}
                >
                  <MenuItem value="all">All Types ({events.length})</MenuItem>
                  {availableTypes.map((t) => (
                    <MenuItem key={t} value={t}>
                      {t.replace(/_/g, " ").toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <Box>
              <FormControl fullWidth size="small">
                <InputLabel id="sentiment-filter-label">Sentiment</InputLabel>
                <Select
                  labelId="sentiment-filter-label"
                  id="sentiment-filter"
                  value={selectedSentiment}
                  label="Sentiment"
                  onChange={(e) => setSelectedSentiment(e.target.value)}
                >
                  <MenuItem value="all">All Sentiments</MenuItem>
                  <MenuItem value="positive">Positive</MenuItem>
                  <MenuItem value="negative">Negative</MenuItem>
                  <MenuItem value="neutral">Neutral</MenuItem>
                </Select>
              </FormControl>
            </Box>

            <Box>
              <FormControl fullWidth size="small">
                <InputLabel id="importance-filter-label">Min Importance</InputLabel>
                <Select
                  labelId="importance-filter-label"
                  id="importance-filter"
                  value={minImportance}
                  label="Min Importance"
                  onChange={(e) => setMinImportance(Number(e.target.value))}
                >
                  <MenuItem value={0}>All Levels (1.0 - 10.0)</MenuItem>
                  <MenuItem value={5}>Medium & High (&ge; 5.0)</MenuItem>
                  <MenuItem value={8}>High Impact Only (&ge; 8.0)</MenuItem>
                </Select>
              </FormControl>
            </Box>
          </Box>
        </Paper>

        {/* Visual Timeline Price Chart with Event Markers */}
        {chartPoints.length > 0 && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
              Price Context &amp; Announcement Distribution:
            </Typography>
            <Box
              component="svg"
              role="img"
              aria-label="Stock price line with overlaid announcement markers"
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              sx={{
                width: "100%",
                height: "auto",
                background: "#fcfdfe",
                border: "1px solid #e2e8f0",
                borderRadius: 1,
              }}
            >
              {/* Background horizontal guideline */}
              <line
                x1={padLeft}
                y1={svgHeight - padBottom}
                x2={svgWidth - padRight}
                y2={svgHeight - padBottom}
                stroke="#cbd5e1"
                strokeWidth="1"
              />

              {/* Price polyline */}
              {chartPoints.length > 1 && (
                <polyline
                  points={polylineStr}
                  fill="none"
                  stroke="#64748b"
                  strokeWidth="2"
                  strokeDasharray="4 2"
                />
              )}

              {/* Date ticks */}
              {chartPoints.length > 0 && (
                <>
                  <text
                    x={padLeft}
                    y={svgHeight - 10}
                    fontSize="11"
                    fill="#64748b"
                    textAnchor="start"
                  >
                    {chartPoints[0].date}
                  </text>
                  <text
                    x={svgWidth - padRight}
                    y={svgHeight - 10}
                    fontSize="11"
                    fill="#64748b"
                    textAnchor="end"
                  >
                    {chartPoints[chartPoints.length - 1].date}
                  </text>
                </>
              )}

              {/* Event pin markers */}
              {filteredEvents.map((ev) => {
                const dateIdx = chartPoints.findIndex(
                  (p) => p.date === ev.effective_trading_date
                );
                const cx = dateIdx >= 0 ? getX(dateIdx) : padLeft + 40;
                const cy = dateIdx >= 0 ? getY(chartPoints[dateIdx].price) : svgHeight / 2;

                const pinColor =
                  ev.sentiment === "negative"
                    ? "#ef4444"
                    : ev.sentiment === "positive"
                    ? "#10b981"
                    : "#64748b";

                const isHighlighted = highlightedEventId === ev.id;

                return (
                  <g
                    key={ev.id}
                    onClick={() => setHighlightedEventId(ev.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <line
                      x1={cx}
                      y1={cy}
                      x2={cx}
                      y2={svgHeight - padBottom}
                      stroke={pinColor}
                      strokeWidth={isHighlighted ? 2.5 : 1.2}
                      strokeDasharray="2 2"
                    />
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHighlighted ? 8 : 5.5}
                      fill={pinColor}
                      stroke="#ffffff"
                      strokeWidth={2}
                    />
                  </g>
                );
              })}
            </Box>
          </Box>
        )}

        {/* Filtered Event Cards List */}
        {filteredEvents.length === 0 ? (
          <Paper
            variant="outlined"
            sx={{ p: 4, textAlign: "center", borderRadius: 2, color: "text.secondary" }}
          >
            <Typography variant="body1">
              No corporate announcements match the selected criteria.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={2}>
            {filteredEvents.map((ev) => {
              const isHighlighted = highlightedEventId === ev.id;
              return (
                <Paper
                  key={ev.id}
                  id={`event-card-${ev.id}`}
                  variant="outlined"
                  sx={{
                    p: 2.5,
                    borderRadius: 2,
                    borderLeft: `5px solid ${getImportanceColor(ev.importance)}`,
                    transition: "box-shadow 0.2s, background-color 0.2s",
                    backgroundColor: isHighlighted ? "#f0fdf4" : "#ffffff",
                    "&:hover": {
                      boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                    },
                  }}
                >
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1}
                    sx={{
                      mb: 1,
                      justifyContent: "space-between",
                      alignItems: { xs: "flex-start", sm: "center" },
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={1}
                      sx={{ alignItems: "center", flexWrap: "wrap" }}
                    >
                      <Chip
                        label={ev.event_type.replace(/_/g, " ").toUpperCase()}
                        size="small"
                        sx={{ fontWeight: 700, backgroundColor: "#e2e8f0" }}
                      />
                      {getSentimentChip(ev.sentiment)}
                      <Chip
                        label={`Importance: ${ev.importance.toFixed(1)}/10`}
                        size="small"
                        variant="outlined"
                        sx={{
                          borderColor: getImportanceColor(ev.importance),
                          color: getImportanceColor(ev.importance),
                          fontWeight: 700,
                        }}
                      />
                      {ev.symbol && (
                        <Chip
                          label={ev.symbol}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      )}
                    </Stack>

                    <Typography variant="caption" color="text.secondary">
                      Trade Date:{" "}
                      <strong>{ev.effective_trading_date}</strong> (Pub:{" "}
                      {new Date(ev.published_at).toLocaleString()})
                    </Typography>
                  </Stack>

                  {/* Headline */}
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 600, color: "#1e293b", my: 1 }}
                  >
                    {ev.headline || "Corporate Announcement"}
                  </Typography>

                  {/* Evidence Text / Span */}
                  {ev.evidence_span && (
                    <Box
                      sx={{
                        p: 1.5,
                        my: 1,
                        backgroundColor: "#f8fafc",
                        borderLeft: "3px solid #94a3b8",
                        borderRadius: 1,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{ fontStyle: "italic", color: "#334155" }}
                      >
                        &ldquo;{ev.evidence_span}&rdquo;
                      </Typography>
                    </Box>
                  )}

                  {/* Metadata footer: Model details, confidence, and source link */}
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1}
                    sx={{
                      mt: 1.5,
                      pt: 1,
                      borderTop: "1px solid #f1f5f9",
                      justifyContent: "space-between",
                      alignItems: { xs: "flex-start", sm: "center" },
                    }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      Classification: <strong>{ev.event_type_method}</strong>
                      {ev.model_name && (
                        <>
                          {" "}&bull; Model: <strong>{ev.model_name}</strong>
                          {ev.model_version && ` (v${ev.model_version})`}
                        </>
                      )}
                      {ev.p_neg !== undefined && ev.p_neg !== null && (
                        <>
                          {" "}&bull; Probabilities: [pos: {(ev.p_pos ?? 0).toFixed(2)}, neg:{" "}
                          {(ev.p_neg ?? 0).toFixed(2)}, neu: {(ev.p_neu ?? 0).toFixed(2)}]
                        </>
                      )}
                    </Typography>

                    {ev.source_url && (
                      <Link
                        href={ev.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        variant="caption"
                        sx={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 0.5,
                          fontWeight: 600,
                        }}
                      >
                        Exchange Filing <OpenInNewIcon sx={{ fontSize: 13 }} />
                      </Link>
                    )}
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

export default Timeline;
