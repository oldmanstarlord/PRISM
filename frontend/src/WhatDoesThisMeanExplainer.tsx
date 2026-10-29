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
        borderRadius: "var(--radius)",
        bgcolor: "var(--bg)",
        boxShadow: "none",
        "&:before": { display: "none" },
        overflow: "hidden",
      }}
    >
      <AccordionSummary
        sx={{
          px: "var(--space-2)",
          py: "var(--space-1)",
          bgcolor: expanded ? "var(--line)" : "var(--bg)",
          "&:hover": { bgcolor: "var(--line)" },
          "&:focus-visible": {
            boxShadow: "none",
          },
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            width: "100%",
            gap: "var(--space-1)",
            pr: "var(--space-1)",
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
              What does this mean?
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              — {displayTitle}
            </Typography>
          </Stack>

          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            {currentValue !== undefined && (
              <Chip
                size="small"
                label={`Current: ${currentValue}${displayUnits ? ` ${displayUnits}` : ""}`}
                sx={{
                  borderRadius: "var(--radius)",
                  bgcolor: "var(--bg)",
                  color: "var(--white)",
                  fontWeight: 600,
                  fontFamily: "var(--font-data)",
                  fontSize: "var(--text-title)",
                  boxShadow: "none",
                }}
              />
            )}
            <Chip
              size="small"
              label={expanded ? "Hide Explanation ▲" : "Explain ▼"}
              sx={{
                borderRadius: "var(--radius)",
                bgcolor: "var(--up)", color: "var(--line)",
                fontWeight: 600,
                fontSize: "var(--text-title)",
              }}
            />
          </Stack>
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ p: "var(--space-3)", bgcolor: "var(--bg)" }}>
        <Stack spacing={2}>
          {/* 1. What it measures */}
          <Box>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, textTransform: "uppercase" }}>
              What it measures
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)", lineHeight: "var(--leading)" }}>
              {definition}
            </Typography>
          </Box>

          {/* 2. Why it matters to an investor */}
          <Box sx={{ p: "var(--space-2)", bgcolor: "var(--line)", borderRadius: "var(--radius)" }}>
            <Typography variant="caption" sx={{ color: "var(--white)", fontWeight: 600, textTransform: "uppercase" }}>
              Why it matters
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)", lineHeight: "var(--leading)" }}>
              {defaultWhyItMatters}
            </Typography>
          </Box>

          {/* 3. Window & Data Coverage */}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, textTransform: "uppercase" }}>
                Estimation Window & Units
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)", fontFamily: "var(--font-data)" }}>
                {displayWindow} {displayUnits ? `· Units: ${displayUnits}` : ""}
              </Typography>
            </Box>

            {dataCoverage && (
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, textTransform: "uppercase" }}>
                  Data Coverage & Freshness
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--white)", mt: "var(--space-1)", fontFamily: "var(--font-data)" }}>
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
              <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, textTransform: "uppercase", display: "block", mb: "var(--space-1)" }}>
                Contributing Holdings
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                {contributingHoldings.map((item, idx) => {
                  if (typeof item === "string") {
                    return (
                      <Chip
                        key={idx}
                        size="small"
                        label={item}
                        sx={{
                          borderRadius: "var(--radius)",
                          bgcolor: "var(--line)",
                          color: "var(--white)",
                          fontWeight: 600,
                          fontSize: "var(--text-title)",
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
                        borderRadius: "var(--radius)",
                        bgcolor: "var(--line)",
                        color: "var(--white)",
                        fontWeight: 600,
                        fontSize: "var(--text-title)",
                      }}
                    />
                  );
                })}
              </Stack>
            </Box>
          )}

          {/* 5. Assumptions & Limitations */}
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ pt: "var(--space-1)" }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600, textTransform: "uppercase", display: "block", mb: "var(--space-1)" }}>
                Assumptions
              </Typography>
              <Box component="ul" sx={{ m: "var(--space-1)", pl: "var(--space-3)", color: "var(--gray)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                {assumptions.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </Box>
            </Box>

            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "var(--amber)", fontWeight: 600, textTransform: "uppercase", display: "block", mb: "var(--space-1)" }}>
                Diagnostic Limitations & Warnings
              </Typography>
              <Box component="ul" sx={{ m: "var(--space-1)", pl: "var(--space-3)", color: "var(--amber)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
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
