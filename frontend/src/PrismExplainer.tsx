import { getIndustryMacroProfile } from "./industryMacroProfile";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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
        borderRadius: "var(--radius)",
        border: "none",
        bgcolor: "var(--bg)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-1)" }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                Why is {symbol} Diverging?
              </Typography>
              <Chip
                size="small"
                label={`${band.toUpperCase()} (${absScore.toFixed(2)}σ)`}
                sx={{
                  borderRadius: "var(--radius)",
                  fontWeight: 600,
                  bgcolor:
                    band === "extreme" || band === "strong"
                      ? isPositive
                        ? "var(--line)"
                        : "var(--gray)"
                      : band === "moderate"
                        ? "var(--line)"
                        : "var(--bg)",
                  color:
                    band === "extreme" || band === "strong"
                      ? isPositive
                        ? "var(--up)"
                        : "var(--down)"
                      : band === "moderate"
                        ? "var(--amber)"
                        : "var(--white)",
                }}
              />
            </Stack>
            <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
              Active Horizon: {horizon} Trading Day{horizon > 1 ? "s" : ""}
            </Typography>
          </Stack>

          <Typography variant="body2" sx={{ color: "var(--white)", lineHeight: "var(--leading)" }}>
            {divergenceNarrative}
          </Typography>

          {stockReturn !== undefined && benchmarkReturn !== undefined && (
            <Paper
              elevation={0}
              sx={{
                p: "var(--space-2)",
                borderRadius: "var(--radius)",
                border: "none",
                bgcolor: "var(--bg)",
                boxShadow: "none",
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-2)",
                alignItems: "center",
              }}
            >
              <Typography variant="body2" sx={{ color: "var(--white)" }}>
                Actual {symbol} Return:{" "}
                <strong
                  style={{
                    color: stockReturn >= 0 ? "var(--up)" : "var(--down)",
                    fontFamily: "var(--font-data)",
                  }}
                >
                  {stockReturn >= 0 ? "+" : ""}
                  {stockReturn.toFixed(2)}%
                </strong>
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                vs
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--white)" }}>
                Peer Median ({peerCount} peers):{" "}
                <strong
                  style={{
                    color: benchmarkReturn >= 0 ? "var(--up)" : "var(--down)",
                    fontFamily: "var(--font-data)",
                  }}
                >
                  {benchmarkReturn >= 0 ? "+" : ""}
                  {benchmarkReturn.toFixed(2)}%
                </strong>
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                Residual Alpha:{" "}
                <strong
                  style={{
                    color: stockReturn - benchmarkReturn >= 0 ? "var(--up)" : "var(--down)",
                    fontFamily: "var(--font-data)",
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
                  p: "var(--space-2)",
                  height: "100%",
                  borderRadius: "var(--radius)",
                  border: "none",
                  bgcolor: "var(--bg)",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "var(--up)", fontWeight: 600, mb: "var(--space-1)" }}>
                  Statistical Context
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                  {statisticalRarity}
                </Typography>
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper
                elevation={0}
                sx={{
                  p: "var(--space-2)",
                  height: "100%",
                  borderRadius: "var(--radius)",
                  border: "none",
                  bgcolor: "var(--bg)",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "var(--white)", fontWeight: 600, mb: "var(--space-1)" }}>
                  Horizon Dynamics ({horizon}D)
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
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
        borderRadius: "var(--radius)",
        border: "none",
        bgcolor: "var(--bg)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, gap: "var(--space-1)" }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                Why is your Portfolio Risk Score rated &ldquo;{riskLabel}&rdquo;?
              </Typography>
              <Chip
                label={`Score ${riskScore}/4 · ${riskLabel}`}
                sx={{
                  borderRadius: "var(--radius)",
                  fontWeight: 600,
                  bgcolor:
                    riskScore === 1
                      ? "var(--line)"
                      : riskScore === 2
                        ? "var(--line)"
                        : "var(--gray)",
                  color:
                    riskScore === 1
                      ? "var(--up)"
                      : riskScore === 2
                        ? "var(--amber)"
                        : "var(--down)",
                }}
                size="small"
              />
            </Stack>
            <Chip
              size="small"
              label={`Risk Trend: ${historicalTrend}`}
              sx={{
                borderRadius: "var(--radius)",
                fontWeight: 600,
                bgcolor: historicalTrend === "Elevating" ? "var(--gray)" : "var(--line)",
                color: historicalTrend === "Elevating" ? "var(--down)" : "var(--up)",
              }}
            />
          </Stack>

          <Typography variant="body2" sx={{ color: "var(--white)", lineHeight: "var(--leading)" }}>
            {scoreReason}
          </Typography>

          <Grid container spacing={2}>
            {/* Driver 1: Volatility & Top Contributor */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: "var(--space-2)",
                  height: "100%",
                  borderRadius: "var(--radius)",
                  border: "none",
                  bgcolor: "var(--bg)",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "var(--white)", fontWeight: 600, mb: "var(--space-1)" }}>
                  Primary Risk Anchor
                </Typography>
                {topRiskContributor ? (
                  <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                    <strong style={{ color: "var(--white)" }}>{topRiskContributor.symbol}</strong> ({topRiskContributor.sector || "Holding"}) contributes{" "}
                    <strong style={{ color: "var(--white)", fontFamily: "var(--font-data)" }}>
                      {(topRiskContributor.riskContribution * 100).toFixed(1)}%
                    </strong>{" "}
                    of total portfolio variance while representing{" "}
                    <span style={{ fontFamily: "var(--font-data)" }}>{(topRiskContributor.weight * 100).toFixed(1)}%</span> of capital.
                  </Typography>
                ) : (
                  <Typography variant="body2" sx={{ color: "var(--gray)" }}>
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
                  p: "var(--space-2)",
                  height: "100%",
                  borderRadius: "var(--radius)",
                  border: "none",
                  bgcolor: "var(--bg)",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "var(--up)", fontWeight: 600, mb: "var(--space-1)" }}>
                  Effective Independent Bets
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                  {diversificationBenefit}
                </Typography>
              </Paper>
            </Grid>

            {/* Driver 3: Sector Breadth */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: "var(--space-2)",
                  height: "100%",
                  borderRadius: "var(--radius)",
                  border: "none",
                  bgcolor: "var(--bg)",
                  boxShadow: "none",
                }}
              >
                <Typography variant="subtitle2" sx={{ color: "var(--amber)", fontWeight: 600, mb: "var(--space-1)" }}>
                  Sector Concentration
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                  Spread across <strong style={{ color: "var(--white)" }}>{effectiveIndustries.toFixed(1)} effective industries</strong>. Having exposure in
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

export interface DynamicMstNeighbor {
  symbol: string;
  industry: string;
  correlation: number;
  distance: number;
  edge_rank: number;
  paired_observations?: number;
  isCrossSector: boolean;
}

export interface DynamicMstItem {
  type: "node" | "edge";
  symbol?: string;
  industry?: string;
  degree?: number;
  observations_used?: number;
  neighbors?: DynamicMstNeighbor[];
  symbol_a?: string;
  symbol_b?: string;
  industry_a?: string;
  industry_b?: string;
  correlation?: number;
  distance?: number;
  paired_observations?: number;
  edge_rank?: number;
}

export interface CorrelationMstExplainerProps {
  selectedItem?: DynamicMstItem | null;
  topHubs?: Array<{ symbol: string; industry: string; degree: number }>;
  topCorrelations?: Array<{
    symbol_a: string;
    symbol_b: string;
    industry_a?: string;
    industry_b?: string;
    correlation: number;
    distance: number;
    edge_rank: number;
  }>;
  onSelectSymbol?: (symbol: string) => void;
  onSelectEdge?: (symbolA: string, symbolB: string) => void;
  onClearSelection?: () => void;
  topClusters?: Array<{
    clusterId: string;
    symbols: string[];
    avgCorrelation: number;
    weight: number;
  }>;
  bridgeStocks?: string[];
}


export function CorrelationMstExplainer({
  selectedItem,
  topHubs = [],
  topCorrelations = [],
  onSelectSymbol,
  onSelectEdge,
  onClearSelection,
}: CorrelationMstExplainerProps) {
  const [expandedSector, setExpandedSector] = useState<string | false>("Financial Services");

  // CASE 1: A stock node is selected
  if (selectedItem?.type === "node" && selectedItem.symbol) {
    const symbol = selectedItem.symbol;
    const industry = selectedItem.industry || "Market Universe";
    const degree = selectedItem.degree ?? 0;
    const neighbors = selectedItem.neighbors ?? [];
    const macro = getIndustryMacroProfile(industry);

    const hasCrossSector = neighbors.some((n) => n.isCrossSector);
    let roleLabel = "Peripheral Leaf Node";
    let roleColor = "var(--cyan)";
    let roleBg = "var(--line)";
    if (degree >= 5) {
      roleLabel = `Systemic Market Hub (${degree} Connections)`;
      roleColor = "var(--up)";
      roleBg = "var(--line)";
    } else if (degree >= 2 && hasCrossSector) {
      roleLabel = `Cross-Sector Transmission Bridge (${degree} Connections)`;
      roleColor = "var(--amber)";
      roleBg = "var(--bg)";
    } else if (degree >= 2) {
      roleLabel = `Sector Cluster Core (${degree} Connections)`;
      roleColor = "var(--cyan)";
      roleBg = "var(--line)";
    }

    return (
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={2.5}>
            {/* Header & Active Selection Strip */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", alignItems: { sm: "flex-start" }, gap: "var(--space-2)" }}
            >
              <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: "var(--space-1)" }}>
                  <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                    {macro.icon} {symbol}: Empirical Network Position & Drivers
                  </Typography>
                  <Chip
                    size="small"
                    label={roleLabel}
                    sx={{
                      borderRadius: "var(--radius)",
                      fontWeight: 600,
                      bgcolor: roleBg,
                      color: roleColor,
                      fontSize: "var(--text-title)",
                    }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                  Real 120-day return co-movement and topology for <strong>{symbol}</strong> in the NIFTY 200 empirical tree.
                </Typography>
              </Box>

              <Stack direction="row" spacing={1} sx={{ flexShrink: 0 }}>
                {onClearSelection && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={onClearSelection}
                    sx={{
                      borderRadius: "var(--radius)",
                      textTransform: "none",
                      color: "var(--white)",
                      borderColor: "var(--gray)",
                      fontSize: "var(--text-title)",
                      "&:hover": { borderColor: "var(--white)", bgcolor: "var(--gray)" },
                    }}
                  >
                    Clear Filter
                  </Button>
                )}
                <Button
                  component={Link}
                  to={`/companies/${symbol}`}
                  size="small"
                  variant="contained"
                  sx={{
                    borderRadius: "var(--radius)",
                    textTransform: "none",
                    fontSize: "var(--text-title)",
                    bgcolor: "var(--up)", color: "var(--line)",
                    "&:hover": { bgcolor: "var(--up)" },
                  }}
                >
                  Open {symbol} Detail /
                </Button>
              </Stack>
            </Stack>

            {/* Quick Metrics Bar */}
            <Paper
              elevation={0}
              sx={{
                p: "var(--space-2)",
                bgcolor: "var(--line)",
                borderRadius: "var(--radius)",
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                gap: "var(--space-2)",
              }}
            >
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Stock Symbol
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  {symbol}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Sector / Industry
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  {industry}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  MST Degree
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--up)" }}>
                  {degree} direct link{degree === 1 ? "" : "s"}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Observations
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  {selectedItem.observations_used ?? 120} days
                </Typography>
              </Box>
            </Paper>

            {/* Real Connected MST Neighbors Table */}
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)" }}>
                Direct Spanning Tree Neighbors ({neighbors.length})
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)" }}>
                These are the only {neighbors.length} stock{neighbors.length === 1 ? "" : "s"} in the entire market with
                direct minimum-distance spanning edges to <strong>{symbol}</strong>. Shocks travel directly across these links.
              </Typography>

              {neighbors.length === 0 ? (
                <Paper sx={{ p: "var(--space-2)", bgcolor: "var(--line)", borderRadius: "var(--radius)", textAlign: "center" }}>
                  <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                    No direct edges recorded in the active calculation window.
                  </Typography>
                </Paper>
              ) : (
                <TableContainer
                  component={Paper}
                  elevation={0}
                  sx={{
                    borderRadius: "var(--radius)",
                    bgcolor: "var(--bg)",
                    border: "var(--border-width) solid var(--cyan)",
                  }}
                >
                  <Table size="small">
                    <TableHead sx={{ bgcolor: "var(--line)" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }}>
                          Connected Stock
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }}>
                          Industry
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }} align="right">
                          Correlation (ρ)
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }} align="right">
                          Mantegna Distance (d)
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }} align="center">
                          Edge Rank
                        </TableCell>
                        <TableCell sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }}>
                          Link Nature
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {neighbors.map((neighbor) => (
                        <TableRow key={neighbor.symbol} hover sx={{ "&:last-child td, &:last-child th": { border: 0 } }}>
                          <TableCell sx={{ py: "var(--space-1)" }}>
                            {onSelectSymbol ? (
                              <Button
                                size="small"
                                onClick={() => onSelectSymbol(neighbor.symbol)}
                                sx={{
                                  p: "var(--space-1)",
                                  minWidth: 0,
                                  fontWeight: 600,
                                  color: "var(--up)",
                                  textTransform: "none",
                                  fontSize: "var(--text-title)",
                                  "&:hover": { textDecoration: "underline", bgcolor: "transparent" },
                                }}
                              >
                                {neighbor.symbol}
                              </Button>
                            ) : (
                              <strong>{neighbor.symbol}</strong>
                            )}
                          </TableCell>
                          <TableCell sx={{ fontSize: "var(--text-title)", color: "var(--gray)" }}>{neighbor.industry}</TableCell>
                          <TableCell sx={{ fontSize: "var(--text-title)", fontWeight: 600, color: "var(--up)" }} align="right">
                            +{neighbor.correlation.toFixed(3)}
                          </TableCell>
                          <TableCell sx={{ fontSize: "var(--text-title)", color: "var(--white)" }} align="right">
                            {neighbor.distance.toFixed(3)}
                          </TableCell>
                          <TableCell sx={{ fontSize: "var(--text-title)", color: "var(--gray)" }} align="center">
                            #{neighbor.edge_rank}
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={neighbor.isCrossSector ? "Cross-Sector Conduit" : "Intra-Sector Peer"}
                              sx={{
                                borderRadius: "var(--radius)",
                                fontSize: "var(--text-title)",
                                fontWeight: 600,
                                bgcolor: neighbor.isCrossSector ? "var(--gray)" : "var(--line)",
                                color: neighbor.isCrossSector ? "var(--down)" : "var(--up)",
                              }}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>

            {/* Macroeconomic Structural Drivers for this specific Industry */}
            <Paper
              elevation={0}
              sx={{
                p: "var(--space-2)",
                borderRadius: "var(--radius)",
                bgcolor: "var(--bg)",
                border: "var(--border-width) solid var(--cyan)",
                boxShadow: "none",
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)" }}>
                Fundamental Macro Drivers: {macro.headline}
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)" }}>
                Why does <strong>{symbol}</strong> co-move with its empirical neighbors? Its return correlation is structurally driven by:
              </Typography>
              <Stack spacing={1} sx={{ pl: "var(--space-1)", mb: "var(--space-2)" }}>
                {macro.macroDrivers.map((driver, idx) => (
                  <Stack key={idx} direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
                    <Typography sx={{ color: "var(--up)", fontWeight: 600, fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                      •
                    </Typography>
                    <Typography variant="body2" sx={{ color: "var(--white)", lineHeight: "var(--leading)" }}>
                      {driver}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
              <Divider sx={{ my: "var(--space-2)", borderColor: "var(--gray)" }} />
              <Typography variant="body2" sx={{ color: "var(--gray)", lineHeight: "var(--leading)" }}>
                <strong style={{ color: "var(--white)" }}>Network Stress Transmission:</strong> {macro.shockTransmission}
              </Typography>
            </Paper>
          </Stack>
        </CardContent>
      </Card>
    );
  }

  // CASE 2: An edge is selected
  if (selectedItem?.type === "edge" && selectedItem.symbol_a && selectedItem.symbol_b) {
    const symA = selectedItem.symbol_a;
    const symB = selectedItem.symbol_b;
    const indA = selectedItem.industry_a || "Market";
    const indB = selectedItem.industry_b || "Market";
    const corr = selectedItem.correlation ?? 0;
    const dist = selectedItem.distance ?? 0;
    const rank = selectedItem.edge_rank ?? 0;
    const isSameSector = indA === indB;

    const macroA = getIndustryMacroProfile(indA);

    return (
      <Card
        elevation={0}
        sx={{
          borderRadius: "var(--radius)",
          border: "none",
          bgcolor: "var(--bg)",
          boxShadow: "none",
        }}
      >
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={2.5}>
            {/* Header & Badges */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", alignItems: { sm: "flex-start" }, gap: "var(--space-2)" }}
            >
              <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: "var(--space-1)" }}>
                  <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
                    Link Dynamics: {symA} / {symB}
                  </Typography>
                  <Chip
                    size="small"
                    label={isSameSector ? "Intra-Sector Empirical Anchor" : "Cross-Sector Structural Bridge"}
                    sx={{
                      borderRadius: "var(--radius)",
                      fontWeight: 600,
                      bgcolor: isSameSector ? "var(--line)" : "var(--gray)",
                      color: isSameSector ? "var(--up)" : "var(--down)",
                      fontSize: "var(--text-title)",
                    }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ color: "var(--gray)" }}>
                  Empirical Minimum Spanning Tree backbone link connecting {symA} ({indA}) and {symB} ({indB}).
                </Typography>
              </Box>

              {onClearSelection && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={onClearSelection}
                  sx={{
                    borderRadius: "var(--radius)",
                    textTransform: "none",
                    color: "var(--white)",
                    borderColor: "var(--gray)",
                    fontSize: "var(--text-title)",
                    flexShrink: 0,
                    "&:hover": { borderColor: "var(--white)", bgcolor: "var(--gray)" },
                  }}
                >
                  Clear Filter
                </Button>
              )}
            </Stack>

            {/* Link Statistics Metric Cards */}
            <Paper
              elevation={0}
              sx={{
                p: "var(--space-2)",
                bgcolor: "var(--line)",
                borderRadius: "var(--radius)",
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                gap: "var(--space-2)",
              }}
            >
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Pearson Correlation
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--up)" }}>
                  ρ = +{corr.toFixed(3)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Mantegna Distance
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  d = {dist.toFixed(3)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Market Edge Rank
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  Rank #{rank} in tree
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "var(--gray)", textTransform: "uppercase", fontWeight: 600 }}>
                  Paired Returns
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                  {selectedItem.paired_observations ?? 120} trading days
                </Typography>
              </Box>
            </Paper>

            {/* Structural Rationale */}
            <Paper
              elevation={0}
              sx={{
                p: "var(--space-2)",
                borderRadius: "var(--radius)",
                bgcolor: "var(--bg)",
                border: "var(--border-width) solid var(--cyan)",
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)" }}>
                Why Did Kruskal&apos;s Algorithm Select This Exact Edge?
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", lineHeight: "var(--leading)" }}>
                Out of all 19,701 possible pairwise relationships in the NIFTY 200 universe, Kruskal&apos;s algorithm selected this
                link with a Mantegna distance of <strong>d = {dist.toFixed(3)}</strong> (correlation <strong>ρ = {corr.toFixed(3)}</strong>).
                In an acyclic spanning tree, this edge is indispensable: cutting it would mathematically partition their respective subtrees.
                {isSameSector ? (
                  <> Both companies operate in <strong>{indA}</strong>, reflecting shared exposure to: {macroA.headline.toLowerCase()}.</>
                ) : (
                  <> This forms a systemic cross-sector conduit between <strong>{indA}</strong> and <strong>{indB}</strong>, allowing capital and volatility shocks to transmit across industries.</>
                )}
              </Typography>

              <Stack direction="row" spacing={1.5} sx={{ mt: "var(--space-2)" }}>
                {onSelectSymbol && (
                  <>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => onSelectSymbol(symA)}
                      sx={{
                        borderRadius: "var(--radius)",
                        textTransform: "none",
                        color: "var(--up)",
                        borderColor: "var(--up)",
                        fontSize: "var(--text-title)",
                        "&:hover": { bgcolor: "var(--up)", borderColor: "var(--up)" },
                      }}
                    >
                      Focus {symA} ({indA}) /
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => onSelectSymbol(symB)}
                      sx={{
                        borderRadius: "var(--radius)",
                        textTransform: "none",
                        color: "var(--up)",
                        borderColor: "var(--up)",
                        fontSize: "var(--text-title)",
                        "&:hover": { bgcolor: "var(--up)", borderColor: "var(--up)" },
                      }}
                    >
                      Focus {symB} ({indB}) /
                    </Button>
                  </>
                )}
              </Stack>
            </Paper>
          </Stack>
        </CardContent>
      </Card>
    );
  }

  // CASE 3: Default state when nothing is selected
  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: "var(--radius)",
        border: "none",
        bgcolor: "var(--bg)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2.5}>
          {/* Main Title & Guiding Note */}
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)" }}>
              Why Do These Stocks Correlate? Structural Macro Drivers
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--gray)", mt: "var(--space-1)" }}>
              Correlation is not accidental—it reflects shared exposure to regulatory policies, currency fluctuations,
              interest rate cycles, and global supply chains.
            </Typography>
          </Box>

          {/* Interactive Instruction Banner */}
          <Paper
            elevation={0}
            sx={{
              p: "var(--space-2)",
              borderRadius: "var(--radius)",
              bgcolor: "var(--line)",
              borderLeft: "var(--border-width) solid var(--up)",
            }}
          >
            <Typography variant="body2" sx={{ color: "var(--up)", fontWeight: 600 }}>
              <strong>Interactive Tree:</strong> Click any stock node or connection line above, or search for a symbol,
              to inspect its real-time correlation drivers, connected neighbors, and transmission pathways.
            </Typography>
          </Paper>

          {/* Real Empirical Market Hubs (Computed dynamically from MST API) */}
          {topHubs.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)", textTransform: "uppercase", fontSize: "var(--text-title)" }}>
                Top Empirical Market Hubs (Highest Spanning Tree Degree)
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)", fontSize: "var(--text-title)" }}>
                These stocks act as structural backbone anchors in the empirical tree, connecting multiple branches and transmitting systemic market shocks:
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                {topHubs.map((hub) => (
                  <Button
                    key={hub.symbol}
                    size="small"
                    variant="outlined"
                    onClick={() => onSelectSymbol?.(hub.symbol)}
                    sx={{
                      borderRadius: "var(--radius)",
                      textTransform: "none",
                      fontSize: "var(--text-title)",
                      fontWeight: 600,
                      color: "var(--white)",
                      borderColor: "var(--gray)",
                      bgcolor: "var(--line)",
                      "&:hover": { borderColor: "var(--up)", bgcolor: "var(--amber)" },
                    }}
                  >
                    <strong>{hub.symbol}</strong> ({hub.degree} links · {hub.industry})
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          {/* Real Top Correlation Links (Computed dynamically from MST API) */}
          {topCorrelations.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)", textTransform: "uppercase", fontSize: "var(--text-title)" }}>
                Strongest Co-Movement Links in the Market
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)", fontSize: "var(--text-title)" }}>
                These pairs exhibit the lowest statistical distance in the entire NIFTY 200 universe (highest return synchronization):
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: "var(--space-1)" }}>
                {topCorrelations.map((pair) => (
                  <Button
                    key={`${pair.symbol_a}-${pair.symbol_b}`}
                    size="small"
                    variant="outlined"
                    onClick={() => onSelectEdge?.(pair.symbol_a, pair.symbol_b)}
                    sx={{
                      borderRadius: "var(--radius)",
                      textTransform: "none",
                      fontSize: "var(--text-title)",
                      fontWeight: 600,
                      color: "var(--up)",
                      borderColor: "var(--up)",
                      bgcolor: "var(--line)",
                      "&:hover": { borderColor: "var(--up)", bgcolor: "var(--white)" },
                    }}
                  >
                    {pair.symbol_a} / {pair.symbol_b} (ρ = +{pair.correlation.toFixed(2)})
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          {/* Sector Macroeconomic Driver Encyclopedia */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)", mb: "var(--space-1)", textTransform: "uppercase", fontSize: "var(--text-title)" }}>
              Macroeconomic Sensitivity Profiles by Sector
            </Typography>
            <Stack spacing={1}>
              {[
                "Financial Services",
                "Information Technology",
                "Automobile and Auto Components",
                "Capital Goods",
                "Oil Gas & Consumable Fuels",
                "Metals & Mining",
                "Healthcare",
                "Fast Moving Consumer Goods",
              ].map((sectorName) => {
                const profile = getIndustryMacroProfile(sectorName);
                return (
                  <Accordion
                    key={sectorName}
                    expanded={expandedSector === sectorName}
                    onChange={(_, isExp) => setExpandedSector(isExp ? sectorName : false)}
                    elevation={0}
                    sx={{
                      borderRadius: "var(--radius)",
                      border: "none",
                      bgcolor: "var(--bg)",
                      boxShadow: "none",
                      "&:before": { display: "none" },
                    }}
                  >
                    <AccordionSummary>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", width: "100%", pr: "var(--space-2)" }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "var(--white)" }}>
                          {sectorName}
                        </Typography>
                        <Chip
                          size="small"
                          label={profile.headline}
                          sx={{
                            borderRadius: "var(--radius)",
                            fontWeight: 600,
                            fontSize: "var(--text-title)",
                            bgcolor: "var(--line)",
                            color: "var(--white)",
                          }}
                        />
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: "var(--space-1)" }}>
                      <Stack spacing={1}>
                        {profile.macroDrivers.map((d, i) => (
                          <Typography key={i} variant="body2" sx={{ color: "var(--gray)", lineHeight: "var(--leading)" }}>
                            • {d}
                          </Typography>
                        ))}
                        <Typography variant="body2" sx={{ color: "var(--up)", fontWeight: 600, mt: "var(--space-1)" }}>
                          Transmission Dynamics: {profile.shockTransmission}
                        </Typography>
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                );
              })}
            </Stack>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}
