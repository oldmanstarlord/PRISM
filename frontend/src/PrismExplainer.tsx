import { useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Card,
  CardContent,
  Chip,
  Grid,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

/* ═══════════════════════════════════════════════════════════════════
   1. SECTOR DIVERGENCE EXPLAINER
   Explains why a stock is diverging from its peer group in real time
   ═══════════════════════════════════════════════════════════════════ */

export interface SectorDivergenceExplainerProps {
  symbol?: string;
  industry?: string;
  divergenceScore: number;
  horizon: number;
  peerCount?: number;
  stockReturn?: number;
  benchmarkReturn?: number;
  interpretation?: string;
}

export function SectorDivergenceExplainer({
  symbol = "This stock",
  industry = "its industry",
  divergenceScore,
  horizon,
  peerCount = 10,
  stockReturn,
  benchmarkReturn,
  interpretation,
}: SectorDivergenceExplainerProps) {
  const isPositive = divergenceScore >= 0;
  const absScore = Math.abs(divergenceScore);
  const band =
    interpretation ||
    (absScore >= 2.0
      ? "extreme"
      : absScore >= 1.5
      ? "strong"
      : absScore >= 1.0
      ? "moderate"
      : "normal");

  const horizonNarrative =
    horizon === 1
      ? "1-day horizon captures intraday and overnight earnings reactions, immediate news shocks, or high-frequency block deals."
      : horizon === 5
      ? "5-day horizon reflects weekly swing momentum, sector-level index rebalancing, and intermediate institutional positioning."
      : "20-day horizon measures persistent monthly structural divergence, separating secular multi-week alpha from short-term market noise.";

  const divergenceNarrative = isPositive
    ? `${symbol} is outperforming the leave-one-out median peer model by +${absScore.toFixed(
        2,
      )} standard deviations (σ). This signals idiosyncratic business strength, relative margin resilience, or targeted institutional accumulation that has not yet diffused across ${industry} peers.`
    : `${symbol} is underperforming the leave-one-out median peer model by -${absScore.toFixed(
        2,
      )} standard deviations (σ). This signals relative weakness, negative guidance, margin compression, or idiosyncratic headwind despite overall ${industry} peer momentum.`;

  const statisticalRarity =
    absScore >= 2.0
      ? "Extreme Outlier: A dislocation of this magnitude occurs in less than 5% of trading windows. This represents a significant decoupling from the peer model."
      : absScore >= 1.5
      ? "Strong Dislocation: In the top 13% of historical peer residuals. Suggests either an emerging fundamental breakout or an overextended mean-reversion opportunity."
      : absScore >= 1.0
      ? "Moderate Divergence: Notable deviation above typical peer dispersion, worth monitoring for follow-through momentum."
      : "Normal Range: Operating within expected peer beta variation (±1.0σ); movements are largely explained by common sector factors.";

  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 0,
        border: "none",
        bgcolor: "#F9EBD7",
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 1 }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                💡 Why is {symbol} Diverging?
              </Typography>
              <Chip
                size="small"
                label={`${band.toUpperCase()} (${absScore.toFixed(2)}σ)`}
                sx={{
                  borderRadius: 0,
                  fontWeight: 700,
                  bgcolor:
                    band === "extreme" || band === "strong"
                      ? isPositive
                        ? "#DCE9DE"
                        : "#F6D9CC"
                      : band === "moderate"
                      ? "#E3D7C4"
                      : "#F9EBD7",
                  color:
                    band === "extreme" || band === "strong"
                      ? isPositive
                        ? "#046A38"
                        : "#B8321A"
                      : band === "moderate"
                      ? "#8A5A00"
                      : "#292D2A",
                }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 600 }}>
              Active Horizon: {horizon} Trading Day{horizon > 1 ? "s" : ""}
            </Typography>
          </Stack>

          <Typography variant="body2" sx={{ color: "#292D2A", lineHeight: 1.65 }}>
            {divergenceNarrative}
          </Typography>

          {stockReturn !== undefined && benchmarkReturn !== undefined && (
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                borderRadius: 0,
                border: "none",
                bgcolor: "#F9EBD7",
                boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                display: "flex",
                flexWrap: "wrap",
                gap: 2,
                alignItems: "center",
              }}
            >
              <Typography variant="body2" sx={{ color: "#292D2A" }}>
                Actual {symbol} Return:{" "}
                <strong
                  style={{
                    color: stockReturn >= 0 ? "#046A38" : "#B8321A",
                    fontFamily: "JetBrains Mono, monospace",
                  }}
                >
                  {stockReturn >= 0 ? "+" : ""}
                  {stockReturn.toFixed(2)}%
                </strong>
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64" }}>
                vs
              </Typography>
              <Typography variant="body2" sx={{ color: "#292D2A" }}>
                Peer Median ({peerCount} peers):{" "}
                <strong
                  style={{
                    color: benchmarkReturn >= 0 ? "#046A38" : "#B8321A",
                    fontFamily: "JetBrains Mono, monospace",
                  }}
                >
                  {benchmarkReturn >= 0 ? "+" : ""}
                  {benchmarkReturn.toFixed(2)}%
                </strong>
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64" }}>
                Residual Alpha:{" "}
                <strong
                  style={{
                    color: stockReturn - benchmarkReturn >= 0 ? "#046A38" : "#B8321A",
                    fontFamily: "JetBrains Mono, monospace",
                  }}
                >
                  {stockReturn - benchmarkReturn >= 0 ? "+" : ""}
                  {(stockReturn - benchmarkReturn).toFixed(2)}%
                </strong>
              </Typography>
            </Paper>
          )}

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 1.75,
                  height: "100%",
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "#046A38", fontWeight: 700, mb: 0.5 }}>
                  📊 Statistical Context
                </Typography>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  {statisticalRarity}
                </Typography>
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 1.75,
                  height: "100%",
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "#292D2A", fontWeight: 700, mb: 0.5 }}>
                  ⏱️ Horizon Dynamics ({horizon}D)
                </Typography>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  {horizonNarrative}
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Stack>
      </CardContent>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   2. PORTFOLIO RISK SCORE EXPLAINER
   Explains why your portfolio risk score is Low/Moderate/High
   ═══════════════════════════════════════════════════════════════════ */

export interface PortfolioRiskExplainerProps {
  riskScore: number;
  riskLabel: string;
  annualizedVolatility: number;
  effectiveHoldings: number;
  totalHoldings: number;
  effectiveIndustries?: number;
  topRiskContributor?: {
    symbol: string;
    riskContribution: number;
    weight: number;
    sector?: string;
  };
  historicalTrend?: "Elevating" | "Stabilizing" | "Cooling";
}

export function PortfolioRiskExplainer({
  riskScore,
  riskLabel,
  annualizedVolatility,
  effectiveHoldings,
  totalHoldings,
  effectiveIndustries = 5,
  topRiskContributor,
  historicalTrend = "Stabilizing",
}: PortfolioRiskExplainerProps) {
  const volPct = annualizedVolatility * 100;

  const scoreReason =
    riskScore === 1
      ? `Rated Low Risk because weighted annualized volatility (${volPct.toFixed(
          1,
        )}%) is below 15%. The portfolio is well-anchored by defensive assets with low beta and stable cash flows.`
      : riskScore === 2
      ? `Rated Moderate Risk because annualized volatility (${volPct.toFixed(
          1,
        )}%) is in the healthy 15%–25% corridor. Growth assets (e.g., Tech and Cyclicals) are balanced by steady anchors (FMCG, Pharma, Construction).`
      : riskScore === 3
      ? `Rated High Risk because annualized volatility (${volPct.toFixed(
          1,
        )}%) is between 25%–35%. Multiple high-beta assets co-move together, amplifying swings during market pullbacks.`
      : `Rated Very High Risk (${volPct.toFixed(
          1,
        )}% volatility). Capital is heavily tilted toward volatile, highly correlated securities that experience steep drawdowns during stress.`;

  const diversificationBenefit =
    effectiveHoldings >= totalHoldings * 0.75
      ? `Strong diversification protection: With ${effectiveHoldings.toFixed(
          1,
        )} effective independent bets out of ${totalHoldings} holdings, idiosyncratic risk is heavily dispersed.`
      : `Moderate concentration: Although you hold ${totalHoldings} stocks, correlation clustering reduces your effective bets to ${effectiveHoldings.toFixed(
          1,
        )}. Some holdings act as mutual amplifiers.`;

  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 0,
        border: "none",
        bgcolor: "#F9EBD7",
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: 1 }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                🛡️ Why is your Portfolio Risk Score rated &ldquo;{riskLabel}&rdquo;?
              </Typography>
              <Chip
                label={`Score ${riskScore}/4 · ${riskLabel}`}
                sx={{
                  borderRadius: 0,
                  fontWeight: 700,
                  bgcolor:
                    riskScore === 1
                      ? "#DCE9DE"
                      : riskScore === 2
                      ? "#E3D7C4"
                      : "#F6D9CC",
                  color:
                    riskScore === 1
                      ? "#046A38"
                      : riskScore === 2
                      ? "#8A5A00"
                      : "#B8321A",
                }}
                size="small"
              />
            </Stack>
            <Chip
              size="small"
              label={`Risk Trend: ${historicalTrend}`}
              sx={{
                borderRadius: 0,
                fontWeight: 700,
                bgcolor: historicalTrend === "Elevating" ? "#F6D9CC" : "#DCE9DE",
                color: historicalTrend === "Elevating" ? "#B8321A" : "#046A38",
              }}
            />
          </Stack>

          <Typography variant="body2" sx={{ color: "#292D2A", lineHeight: 1.65 }}>
            {scoreReason}
          </Typography>

          <Grid container spacing={2}>
            {/* Driver 1: Volatility & Top Contributor */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  height: "100%",
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "#292D2A", fontWeight: 700, mb: 0.5 }}>
                  🎯 Primary Risk Anchor
                </Typography>
                {topRiskContributor ? (
                  <Typography variant="body2" sx={{ color: "#686B64" }}>
                    <strong style={{ color: "#292D2A" }}>{topRiskContributor.symbol}</strong> ({topRiskContributor.sector || "Holding"}) contributes{" "}
                    <strong style={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                      {(topRiskContributor.riskContribution * 100).toFixed(1)}%
                    </strong>{" "}
                    of total portfolio variance while representing{" "}
                    <span style={{ fontFamily: "JetBrains Mono, monospace" }}>{(topRiskContributor.weight * 100).toFixed(1)}%</span> of capital.
                  </Typography>
                ) : (
                  <Typography variant="body2" sx={{ color: "#686B64" }}>
                    Risk is evenly distributed across your constituent assets without severe single-stock concentration.
                  </Typography>
                )}
              </Paper>
            </Grid>

            {/* Driver 2: Effective Bets & Diversification */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  height: "100%",
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "#046A38", fontWeight: 700, mb: 0.5 }}>
                  🎲 Effective Independent Bets
                </Typography>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  {diversificationBenefit}
                </Typography>
              </Paper>
            </Grid>

            {/* Driver 3: Sector Breadth */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  height: "100%",
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#F9EBD7",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "#8A5A00", fontWeight: 700, mb: 0.5 }}>
                  🏭 Sector Concentration
                </Typography>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  Spread across <strong style={{ color: "#292D2A" }}>{effectiveIndustries.toFixed(1)} effective industries</strong>. Having exposure in
                  both cyclicals (Auto, Construction) and defensives (FMCG, Pharma) cushions banking/tech drawdowns.
                </Typography>
              </Paper>
            </Grid>
          </Grid>
        </Stack>
      </CardContent>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   3. CORRELATION & MST STRUCTURAL EXPLAINER
   Explains why stocks correlate and how stress travels across the tree
   ═══════════════════════════════════════════════════════════════════ */

export interface CorrelationMstExplainerProps {
  topClusters?: Array<{
    clusterId: string;
    symbols: string[];
    avgCorrelation: number;
    weight: number;
  }>;
  bridgeStocks?: string[];
}

export function CorrelationMstExplainer({
  topClusters = [
    {
      clusterId: "TECH",
      symbols: ["INFY", "TCS", "HCLTECH", "TECHM", "WIPRO"],
      avgCorrelation: 0.72,
      weight: 26.1,
    },
    {
      clusterId: "FINANCIALS",
      symbols: ["ICICIBANK", "HDFCBANK", "SBIN", "AXISBANK", "KOTAKBANK", "BAJFINANCE"],
      avgCorrelation: 0.55,
      weight: 32.3,
    },
    {
      clusterId: "CYCLICAL_GROWTH",
      symbols: ["LT", "MARUTI", "TITAN", "RELIANCE"],
      avgCorrelation: 0.48,
      weight: 28.5,
    },
  ],
  bridgeStocks = ["SHRIRAMFIN", "LT", "RELIANCE"],
}: CorrelationMstExplainerProps) {
  const [expanded, setExpanded] = useState<string | false>("cluster-tech");

  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 0,
        border: "none",
        bgcolor: "#F9EBD7",
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
              🕸️ Why Do These Stocks Correlate? Structural Macro Drivers
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64", mt: 0.5 }}>
              Correlation is not accidental—it reflects shared exposure to regulatory policies, currency fluctuations,
              interest rate cycles, and global supply chains.
            </Typography>
          </Box>

          <Box>
            <Accordion
              expanded={expanded === "cluster-tech"}
              onChange={(_, isExp) => setExpanded(isExp ? "cluster-tech" : false)}
              elevation={0}
              sx={{
                mb: 1.5,
                borderRadius: 0,
                border: "none",
                bgcolor: "#F9EBD7",
                boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", width: "100%", pr: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                    💻 Technology Cluster ({topClusters[0]?.symbols.join(", ")})
                  </Typography>
                  <Chip
                    size="small"
                    label={`High Co-movement (ρ ≈ ${topClusters[0]?.avgCorrelation.toFixed(2)})`}
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: "#DCE9DE",
                      color: "#046A38",
                    }}
                  />
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <Typography variant="body2" sx={{ color: "#686B64", lineHeight: 1.65 }}>
                  <strong style={{ color: "#292D2A" }}>Underlying Driver:</strong> Indian IT giants share nearly identical macroeconomic sensitivities:
                  (1) Over 70% of revenue originates from North American and European enterprise clients; (2) They are
                  equally impacted by USD/INR foreign exchange fluctuations; and (3) Enterprise tech spending budgets in
                  Banking/Financial Services (BFSI) dictate their order pipelines simultaneously. As a result, when global
                  tech spending contracts or expands, their valuations move in unison (ρ &gt; 0.70).
                </Typography>
              </AccordionDetails>
            </Accordion>

            <Accordion
              expanded={expanded === "cluster-fin"}
              onChange={(_, isExp) => setExpanded(isExp ? "cluster-fin" : false)}
              elevation={0}
              sx={{
                mb: 1.5,
                borderRadius: 0,
                border: "none",
                bgcolor: "#F9EBD7",
                boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", width: "100%", pr: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#046A38" }}>
                    🏦 Financial Services & Banking Cluster ({topClusters[1]?.symbols.join(", ")})
                  </Typography>
                  <Chip
                    size="small"
                    label={`Moderate-High Co-movement (ρ ≈ ${topClusters[1]?.avgCorrelation.toFixed(2)})`}
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: "#E3D7C4",
                      color: "#8A5A00",
                    }}
                  />
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <Typography variant="body2" sx={{ color: "#686B64", lineHeight: 1.65 }}>
                  <strong style={{ color: "#292D2A" }}>Underlying Driver:</strong> Commercial banks and NBFCs are bound to the domestic credit cycle:
                  (1) Reserve Bank of India (RBI) repo rate decisions directly dictate their Net Interest Margins (NIM);
                  (2) Deposit competition and retail lending growth affect all lenders synchronously; and (3) Foreign
                  Institutional Investors (FIIs) trade Indian financials as a primary liquidity proxy for India's GDP.
                </Typography>
              </AccordionDetails>
            </Accordion>

            <Accordion
              expanded={expanded === "cluster-bridges"}
              onChange={(_, isExp) => setExpanded(isExp ? "cluster-bridges" : false)}
              elevation={0}
              sx={{
                borderRadius: 0,
                border: "none",
                bgcolor: "#F9EBD7",
                boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", width: "100%", pr: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#8A5A00" }}>
                    🌉 Bridge Stocks & Stress Transmission ({bridgeStocks.join(", ")})
                  </Typography>
                  <Chip
                    size="small"
                    label="Systemic Transmission Nodes"
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: "#F6D9CC",
                      color: "#B8321A",
                    }}
                  />
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <Typography variant="body2" sx={{ color: "#686B64", lineHeight: 1.65 }}>
                  <strong style={{ color: "#292D2A" }}>Underlying Driver:</strong> Bridge stocks serve as critical connectors in the Minimum Spanning Tree,
                  linking distinct macroeconomic clusters. When market stress occurs, volatility transmits through these hubs first before reaching more isolated nodes.
                </Typography>
              </AccordionDetails>
            </Accordion>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
