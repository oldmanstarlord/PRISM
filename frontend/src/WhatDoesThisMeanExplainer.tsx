import { useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import { METRIC_REGISTRY, type MetricDoc } from "./methodologyRegistry";

export interface ContributingHoldingInfo {
  symbol: string;
  weight?: number | string;
  contribution?: number | string;
}

export interface WhatDoesThisMeanExplainerProps {
  metricId: string;
  title?: string;
  currentValue?: string | number;
  units?: string;
  contributingHoldings?: Array<ContributingHoldingInfo | string>;
  dataCoverage?: {
    observations?: number;
    minRequired?: number;
    percent?: number;
    asOfDate?: string;
  };
  window?: string;
  whyItMatters?: string;
  defaultExpanded?: boolean;
}

/**
 * Reusable "What does this mean" expandable pattern for PRISM indicators.
 * Renders definition, investor significance, contributing holdings, window,
 * data coverage, underlying assumptions, and diagnostic limitations directly
 * from the authoritative methodology registry.
 */
export function WhatDoesThisMeanExplainer({
  metricId,
  title,
  currentValue,
  units,
  contributingHoldings,
  dataCoverage,
  window: customWindow,
  whyItMatters: customWhyItMatters,
  defaultExpanded = false,
}: WhatDoesThisMeanExplainerProps) {
  const [expanded, setExpanded] = useState<boolean>(defaultExpanded);

  const doc: MetricDoc | undefined = METRIC_REGISTRY[metricId];

  const displayTitle = title || doc?.name || metricId;
  const displayUnits = units || doc?.units || "";
  const displayWindow = customWindow || doc?.defaultWindow || "250 trading days (~1Y)";
  const definition = doc?.definition || "Quantitative risk indicator measured across portfolio holdings.";

  // Analytical interpretation for non-experts
  const defaultWhyItMatters =
    customWhyItMatters ||
    (metricId === "ANNUALIZED_VOLATILITY"
      ? "Volatility measures the annualized swing in portfolio value. Higher volatility indicates wider dispersion of daily returns and increased uncertainty over intermediate horizons."
      : metricId === "MAX_DRAWDOWN"
        ? "Maximum drawdown measures the steepest cumulative peak-to-trough drop in portfolio wealth. It reveals historical worst-case capital decline under real market stress."
        : metricId === "DIVERSIFICATION_RATIO" || metricId === "EFFECTIVE_HOLDINGS"
          ? "Measures whether your portfolio is genuinely spread out or heavily concentrated in a few correlated bets. Higher effective holdings reduce vulnerability to individual company shocks."
          : metricId === "PORTFOLIO_RISK_SCORE"
            ? "A multi-factor diagnostic composite combining volatility, downside risk, concentration, and beta into a single standardized 0-100 scale."
            : metricId === "HISTORICAL_VAR"
              ? "Value at Risk estimates the minimum loss expected on extreme trading days at a 95% or 99% confidence level based on empirical historical returns."
              : "Provides an objective statistical diagnosis of portfolio structure to help identify vulnerabilities before stress events occur.");

  const assumptions = doc?.assumptions || [
    "Evaluated on daily simple returns of portfolio holdings.",
    "Constant target asset weights rebalanced daily.",
    "Indian equity market calendar (252 trading sessions per calendar year).",
  ];

  const limitations = doc?.limitations || [
    "Reflects historical empirical data and does NOT predict future price movements or loss.",
    "Does not account for non-linear liquidity shocks or extreme gap-opening events.",
    "Measures co-movement and statistical association, NOT causal relationships.",
  ];

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, isExp) => setExpanded(isExp)}
      elevation={0}
      sx={{
        borderRadius: 0,
        bgcolor: "#F9EBD7",
        boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
        "&:before": { display: "none" },
        overflow: "hidden",
      }}
    >
      <AccordionSummary
        sx={{
          px: 2,
          py: 1,
          bgcolor: expanded ? "#E3D7C4" : "#F9EBD7",
          "&:hover": { bgcolor: "#E3D7C4" },
          "&:focus-visible": {
            boxShadow: "0 0 0 2px #046A38",
          },
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            width: "100%",
            gap: 1,
            pr: 1,
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
              What does this mean?
            </Typography>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 600 }}>
              — {displayTitle}
            </Typography>
          </Stack>

          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            {currentValue !== undefined && (
              <Chip
                size="small"
                label={`Current: ${currentValue}${displayUnits ? ` ${displayUnits}` : ""}`}
                sx={{
                  borderRadius: 0,
                  bgcolor: "#F9EBD7",
                  color: "#292D2A",
                  fontWeight: 700,
                  fontFamily: "JetBrains Mono",
                  fontSize: "0.875rem",
                  boxShadow: "0 1px 3px rgba(41,45,42,0.10)",
                }}
              />
            )}
            <Chip
              size="small"
              label={expanded ? "Hide Explanation ▲" : "Explain ▼"}
              sx={{
                borderRadius: 0,
                bgcolor: "#046A38",
                color: "#F9EBD7",
                fontWeight: 700,
                fontSize: "0.875rem",
              }}
            />
          </Stack>
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ p: 2.5, bgcolor: "#F9EBD7" }}>
        <Stack spacing={2}>
          {/* 1. What it measures */}
          <Box>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, textTransform: "uppercase" }}>
              What it measures
            </Typography>
            <Typography variant="body2" sx={{ color: "#292D2A", mt: 0.5, lineHeight: 1.6 }}>
              {definition}
            </Typography>
          </Box>

          {/* 2. Why it matters to an investor */}
          <Box sx={{ p: 1.5, bgcolor: "#E3D7C4", borderRadius: 0 }}>
            <Typography variant="caption" sx={{ color: "#292D2A", fontWeight: 700, textTransform: "uppercase" }}>
              Why it matters
            </Typography>
            <Typography variant="body2" sx={{ color: "#292D2A", mt: 0.5, lineHeight: 1.6 }}>
              {defaultWhyItMatters}
            </Typography>
          </Box>

          {/* 3. Window & Data Coverage */}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, textTransform: "uppercase" }}>
                Estimation Window & Units
              </Typography>
              <Typography variant="body2" sx={{ color: "#292D2A", mt: 0.5, fontFamily: "JetBrains Mono" }}>
                {displayWindow} {displayUnits ? `· Units: ${displayUnits}` : ""}
              </Typography>
            </Box>

            {dataCoverage && (
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, textTransform: "uppercase" }}>
                  Data Coverage & Freshness
                </Typography>
                <Typography variant="body2" sx={{ color: "#292D2A", mt: 0.5, fontFamily: "JetBrains Mono" }}>
                  {dataCoverage.observations !== undefined
                    ? `${dataCoverage.observations} observations (${dataCoverage.percent?.toFixed(1) ?? 100}% coverage)`
                    : "Full historical coverage"}{" "}
                  {dataCoverage.asOfDate ? `as of ${dataCoverage.asOfDate}` : ""}
                </Typography>
              </Box>
            )}
          </Stack>

          {/* 4. Contributing Holdings */}
          {contributingHoldings && contributingHoldings.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, textTransform: "uppercase", display: "block", mb: 0.75 }}>
                Contributing Holdings
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 0.75 }}>
                {contributingHoldings.map((item, idx) => {
                  if (typeof item === "string") {
                    return (
                      <Chip
                        key={idx}
                        size="small"
                        label={item}
                        sx={{
                          borderRadius: 0,
                          bgcolor: "#E3D7C4",
                          color: "#292D2A",
                          fontWeight: 600,
                          fontSize: "0.875rem",
                        }}
                      />
                    );
                  }
                  return (
                    <Chip
                      key={idx}
                      size="small"
                      label={`${item.symbol}${item.weight ? ` (${item.weight})` : ""}${item.contribution ? ` · Risk: ${item.contribution}` : ""}`}
                      sx={{
                        borderRadius: 0,
                        bgcolor: "#E3D7C4",
                        color: "#292D2A",
                        fontWeight: 600,
                        fontSize: "0.875rem",
                      }}
                    />
                  );
                })}
              </Stack>
            </Box>
          )}

          {/* 5. Assumptions & Limitations */}
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ pt: 1 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, textTransform: "uppercase", display: "block", mb: 0.5 }}>
                Assumptions
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5, color: "#686B64", fontSize: "0.875rem", lineHeight: 1.6 }}>
                {assumptions.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </Box>
            </Box>

            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "#8A5A00", fontWeight: 700, textTransform: "uppercase", display: "block", mb: 0.5 }}>
                Diagnostic Limitations & Warnings
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5, color: "#8A5A00", fontSize: "0.875rem", lineHeight: 1.6 }}>
                {limitations.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </Box>
            </Box>
          </Stack>
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}
