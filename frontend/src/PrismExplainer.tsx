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
  Tooltip,
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
                Why is {symbol} Diverging?
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
                  Statistical Context
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
                  Horizon Dynamics ({horizon}D)
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
                Why is your Portfolio Risk Score rated &ldquo;{riskLabel}&rdquo;?
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
                  Primary Risk Anchor
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
                  Effective Independent Bets
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
                  Sector Concentration
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

export function getIndustryMacroProfile(industry?: string): {
  icon: string;
  headline: string;
  macroDrivers: string[];
  shockTransmission: string;
} {
  const norm = (industry || "").toLowerCase();
  if (norm.includes("tech") || norm.includes("information")) {
    return {
      icon: "",
      headline: "Global Enterprise IT Budgets & Currency Exposure",
      macroDrivers: [
        "Over 70% of enterprise revenues originate from North American and European corporate clients (especially BFSI and Retail).",
        "USD/INR exchange rate movements directly influence operating margins and cross-border billing realization.",
        "Global interest rate cycles and enterprise digital transformation / AI capex cycles dictate contract order flow synchronously.",
      ],
      shockTransmission:
        "When US/EU corporate IT budgets contract or FX shifts abruptly, valuation multiples across tech stocks compress in unison (high intra-sector co-movement).",
    };
  }
  if (norm.includes("financ") || norm.includes("bank") || norm.includes("insur")) {
    return {
      icon: "",
      headline: "Monetary Policy Transmission & Domestic Credit Cycle",
      macroDrivers: [
        "Reserve Bank of India (RBI) repo rate decisions directly dictate bank Net Interest Margins (NIM) and NBFC cost of funds.",
        "Systemic credit growth, deposit mobilization competition, and retail/SME delinquency cycles affect all lenders simultaneously.",
        "Foreign Institutional Investors (FIIs) trade high-liquidity financial stocks as the primary liquid proxy for India's macroeconomic GDP trajectory.",
      ],
      shockTransmission:
        "Financial institutions act as central capital arteries; stress or liquidity shocks in the banking corridor cascade into capital goods, auto financing, and real estate.",
    };
  }
  if (norm.includes("auto")) {
    return {
      icon: "",
      headline: "Retail Financing Conditions & Input Commodity Inflation",
      macroDrivers: [
        "Retail vehicle purchase volumes heavily depend on bank/NBFC vehicle financing rates and consumer credit availability.",
        "Input costs are tied directly to industrial commodities: automotive-grade sheet steel, aluminum, and rubber prices.",
        "Rural agricultural income (for 2-wheelers and tractors) alongside urban replacement demand cycles dictate sales seasonality.",
      ],
      shockTransmission:
        "Automakers connect closely with metal producers (input cost supply chain) and retail financiers (demand credit channel).",
    };
  }
  if (norm.includes("capital goods") || norm.includes("construction") || norm.includes("industrial")) {
    return {
      icon: "",
      headline: "Public Infrastructure Outlays & Private Capex Cycle",
      macroDrivers: [
        "Central and State government capital expenditure budgets for roads, railways, energy transition, and urban mobility.",
        "Private sector manufacturing capacity utilization rates determining new plant and equipment expansion cycles.",
        "Long gestation contract execution timelines, raw material escalation clauses, and working capital financing costs.",
      ],
      shockTransmission:
        "Capital Goods stocks act as economic barometers, transmitting industrial momentum between raw materials (metals/energy) and financing hubs.",
    };
  }
  if (norm.includes("oil") || norm.includes("gas") || norm.includes("fuel") || norm.includes("energy")) {
    return {
      icon: "",
      headline: "Global Crude Benchmarks & Refining Crack Spreads",
      macroDrivers: [
        "International Brent crude price benchmarks and Singapore Gross Refining Margins (GRM) dictate upstream and downstream profitability.",
        "Domestic government excise duty adjustments, windfall profit taxes, and retail auto-fuel pricing policies.",
        "Global LNG supply-demand balances and shipping freight tariffs for imported hydrocarbon feedstocks.",
      ],
      shockTransmission:
        "Oil & Gas giants represent systemic market weight; oil price swings transmit inflationary shocks across transport, chemicals, and consumer goods.",
    };
  }
  if (norm.includes("metal") || norm.includes("mining")) {
    return {
      icon: "",
      headline: "LME Global Commodity Pricing & Chinese Industrial Demand",
      macroDrivers: [
        "London Metal Exchange (LME) spot prices and Chinese manufacturing purchasing managers' indices (PMI) dictate domestic realization prices.",
        "Imported coking coal and domestic iron ore pricing parity create operating cost swings.",
        "Domestic construction, automotive, and infrastructure demand provide baseline volume consumption.",
      ],
      shockTransmission:
        "Metals stocks exhibit cyclical beta; shifts in global commodity demand rapidly feed into construction materials and industrial manufacturing.",
    };
  }
  if (norm.includes("health") || norm.includes("pharma")) {
    return {
      icon: "",
      headline: "US FDA Regulatory Oversight & Generic Pricing Dynamics",
      macroDrivers: [
        "Regulatory compliance, inspection outcomes, and Form 483 issuance by the US FDA for export-oriented manufacturing plants.",
        "Price erosion in the US generic pharmaceuticals market versus high-margin complex injectables and biosimilar pipelines.",
        "Resilient, non-cyclical growth in domestic Indian formulations driven by chronic therapy prescription adoption.",
      ],
      shockTransmission:
        "Pharma operates with defensive, lower correlation to domestic interest rate cycles, frequently acting as a portfolio hedge during cyclical drawdowns.",
    };
  }
  if (norm.includes("consumer goods") || norm.includes("fmcg") || norm.includes("durables")) {
    return {
      icon: "",
      headline: "Agricultural Monsoon Distribution & Household Purchasing Power",
      macroDrivers: [
        "Southwest monsoon spatial distribution directly drives rural farm income and staple consumer goods volume off-take.",
        "Agricultural raw material price volatility (crude palm oil, wheat, sugar, packaging materials) dictating gross margins.",
        "Urban premiumization trends versus mass rural volume recovery determining top-line growth trajectory.",
      ],
      shockTransmission:
        "FMCG stocks exhibit lower systemic beta; they serve as structural anchors in the MST with strong intra-sector coherence.",
    };
  }
  if (norm.includes("power") || norm.includes("utilit")) {
    return {
      icon: "",
      headline: "Grid Peak Load Demand & DISCOM Health",
      macroDrivers: [
        "National peak power demand driven by industrial electrification, seasonal heatwaves, and air conditioning penetration.",
        "Power Purchase Agreement (PPA) realization rates, coal linkage availability, and renewable capacity deployment.",
        "State distribution company (DISCOM) financial solvency and timely payment settlements under central schemes.",
      ],
      shockTransmission:
        "Power stocks connect heavy industry to public utilities, anchoring industrial energy demand in the empirical network.",
    };
  }
  if (norm.includes("realt")) {
    return {
      icon: "",
      headline: "Mortgage Rates, Land Acquisition & Residential Absorption",
      macroDrivers: [
        "Retail home loan interest rates and banking liquidity driving residential presales velocity.",
        "Urban land parcel acquisitions, regulatory approvals (RERA), and construction milestone completion rates.",
        "Consolidation toward organized, tier-1 branded developers with strong balance sheets.",
      ],
      shockTransmission:
        "Realty co-moves closely with banking and housing finance NBFCs, forming a sensitive interest-rate transmission corridor.",
    };
  }
  if (norm.includes("telecom")) {
    return {
      icon: "",
      headline: "Industry ARPU Trajectory & 5G Infrastructure Monetization",
      macroDrivers: [
        "Average Revenue Per User (ARPU) headline tariff increase cycles across the 3-player private oligopoly.",
        "Capital expenditure amortization for 5G network rollout, fiber backhaul, and spectrum auction liabilities.",
        "Data consumption growth per subscriber and enterprise cloud connectivity services.",
      ],
      shockTransmission:
        "Telecom connects capital-intensive infrastructure with digital consumer services, serving as an independent digital conduit.",
    };
  }
  if (norm.includes("chemic")) {
    return {
      icon: "",
      headline: "Petrochemical Feedstocks & Global Supply Chain Diversification",
      macroDrivers: [
        "Global chemical cycle demand, particularly European and American agrochemical and specialty chemical destocking.",
        "Crude oil and natural gas derivative feedstock costs dictating intermediate chemical manufacturing margins.",
        "Global 'China + 1' manufacturing diversification contracts and domestic import substitution incentives.",
      ],
      shockTransmission:
        "Chemicals link energy refining inputs to pharmaceutical, agrochemical, and automotive applications.",
    };
  }

  return {
    icon: "",
    headline: "Sector Operational Dynamics & Macro Sensitivities",
    macroDrivers: [
      `Companies in ${industry || "this sector"} share direct sensitivity to domestic GDP growth rates, inflation, and sovereign yield curves.`,
      "Co-movement is driven by synchronized demand conditions, capital access, and collective institutional investor asset allocation baskets.",
      "Regulatory frameworks and tax structures impacting this industry create synchronous valuation adjustments across peers.",
    ],
    shockTransmission:
      "Shocks in this industry propagate across empirical spanning tree edges to closely correlated supplier, customer, and financing nodes.",
  };
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
    let roleColor = "#3F5B7A";
    let roleBg = "#DCE9DE";
    if (degree >= 5) {
      roleLabel = `Systemic Market Hub (${degree} Connections)`;
      roleColor = "#046A38";
      roleBg = "#DCE9DE";
    } else if (degree >= 2 && hasCrossSector) {
      roleLabel = `Cross-Sector Transmission Bridge (${degree} Connections)`;
      roleColor = "#8A5A00";
      roleBg = "#F9EBD7";
    } else if (degree >= 2) {
      roleLabel = `Sector Cluster Core (${degree} Connections)`;
      roleColor = "#1F6F78";
      roleBg = "#DCE9DE";
    }

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
          <Stack spacing={2.5}>
            {/* Header & Active Selection Strip */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", alignItems: { sm: "flex-start" }, gap: 1.5 }}
            >
              <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: 0.5 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                    {macro.icon} {symbol}: Empirical Network Position & Drivers
                  </Typography>
                  <Chip
                    size="small"
                    label={roleLabel}
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: roleBg,
                      color: roleColor,
                      fontSize: "0.75rem",
                    }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
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
                      borderRadius: 0,
                      textTransform: "none",
                      color: "#292D2A",
                      borderColor: "rgba(41,45,42,0.25)",
                      fontSize: "0.76rem",
                      "&:hover": { borderColor: "#292D2A", bgcolor: "rgba(41,45,42,0.04)" },
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
                    borderRadius: 0,
                    textTransform: "none",
                    fontSize: "0.76rem",
                    bgcolor: "#046A38",
                    color: "#F9EBD7",
                    "&:hover": { bgcolor: "#034d28" },
                  }}
                >
                  Open {symbol} Detail →
                </Button>
              </Stack>
            </Stack>

            {/* Quick Metrics Bar */}
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                bgcolor: "#E3D7C4",
                borderRadius: 0,
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                gap: 1.5,
              }}
            >
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Stock Symbol
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  {symbol}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Sector / Industry
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  {industry}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  MST Degree
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#046A38" }}>
                  {degree} direct link{degree === 1 ? "" : "s"}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Observations
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  {selectedItem.observations_used ?? 120} days
                </Typography>
              </Box>
            </Paper>

            {/* Real Connected MST Neighbors Table */}
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 1 }}>
                Direct Spanning Tree Neighbors ({neighbors.length})
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1.5 }}>
                These are the only {neighbors.length} stock{neighbors.length === 1 ? "" : "s"} in the entire market with
                direct minimum-distance spanning edges to <strong>{symbol}</strong>. Shocks travel directly across these links.
              </Typography>

              {neighbors.length === 0 ? (
                <Paper sx={{ p: 2, bgcolor: "#E3D7C4", borderRadius: 0, textAlign: "center" }}>
                  <Typography variant="body2" sx={{ color: "#686B64" }}>
                    No direct edges recorded in the active calculation window.
                  </Typography>
                </Paper>
              ) : (
                <TableContainer
                  component={Paper}
                  elevation={0}
                  sx={{
                    borderRadius: 0,
                    bgcolor: "#F9EBD7",
                    border: "1px solid rgba(41,45,42,0.12)",
                  }}
                >
                  <Table size="small">
                    <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }}>
                          Connected Stock
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }}>
                          Industry
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }} align="right">
                          Correlation (ρ)
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }} align="right">
                          Mantegna Distance (d)
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }} align="center">
                          Edge Rank
                        </TableCell>
                        <TableCell sx={{ fontWeight: 700, color: "#292D2A", fontSize: "0.75rem" }}>
                          Link Nature
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {neighbors.map((neighbor) => (
                        <TableRow key={neighbor.symbol} hover sx={{ "&:last-child td, &:last-child th": { border: 0 } }}>
                          <TableCell sx={{ py: 1 }}>
                            {onSelectSymbol ? (
                              <Button
                                size="small"
                                onClick={() => onSelectSymbol(neighbor.symbol)}
                                sx={{
                                  p: 0,
                                  minWidth: 0,
                                  fontWeight: 700,
                                  color: "#046A38",
                                  textTransform: "none",
                                  fontSize: "0.82rem",
                                  "&:hover": { textDecoration: "underline", bgcolor: "transparent" },
                                }}
                              >
                                {neighbor.symbol}
                              </Button>
                            ) : (
                              <strong>{neighbor.symbol}</strong>
                            )}
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.8rem", color: "#686B64" }}>{neighbor.industry}</TableCell>
                          <TableCell sx={{ fontSize: "0.8rem", fontWeight: 700, color: "#046A38" }} align="right">
                            +{neighbor.correlation.toFixed(3)}
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.8rem", color: "#292D2A" }} align="right">
                            {neighbor.distance.toFixed(3)}
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.75rem", color: "#686B64" }} align="center">
                            #{neighbor.edge_rank}
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={neighbor.isCrossSector ? "Cross-Sector Conduit" : "Intra-Sector Peer"}
                              sx={{
                                borderRadius: 0,
                                fontSize: "0.7rem",
                                fontWeight: 600,
                                bgcolor: neighbor.isCrossSector ? "#F6D9CC" : "#DCE9DE",
                                color: neighbor.isCrossSector ? "#B8321A" : "#046A38",
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
                p: 2,
                borderRadius: 0,
                bgcolor: "#F9EBD7",
                border: "1px solid rgba(41,45,42,0.12)",
                boxShadow: "0 3px 8px rgba(41,45,42,0.06)",
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 0.5 }}>
                Fundamental Macro Drivers: {macro.headline}
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1.5 }}>
                Why does <strong>{symbol}</strong> co-move with its empirical neighbors? Its return correlation is structurally driven by:
              </Typography>
              <Stack spacing={1} sx={{ pl: 1, mb: 1.5 }}>
                {macro.macroDrivers.map((driver, idx) => (
                  <Stack key={idx} direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
                    <Typography sx={{ color: "#046A38", fontWeight: 700, fontSize: "0.85rem", lineHeight: 1.5 }}>
                      •
                    </Typography>
                    <Typography variant="body2" sx={{ color: "#292D2A", lineHeight: 1.55 }}>
                      {driver}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
              <Divider sx={{ my: 1.5, borderColor: "rgba(41,45,42,0.10)" }} />
              <Typography variant="body2" sx={{ color: "#686B64", lineHeight: 1.55 }}>
                <strong style={{ color: "#292D2A" }}>Network Stress Transmission:</strong> {macro.shockTransmission}
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
    const macroB = getIndustryMacroProfile(indB);

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
          <Stack spacing={2.5}>
            {/* Header & Badges */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              sx={{ justifyContent: "space-between", alignItems: { sm: "flex-start" }, gap: 1.5 }}
            >
              <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap", mb: 0.5 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
                    Link Dynamics: {symA} ↔ {symB}
                  </Typography>
                  <Chip
                    size="small"
                    label={isSameSector ? "Intra-Sector Empirical Anchor" : "Cross-Sector Structural Bridge"}
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: isSameSector ? "#DCE9DE" : "#F6D9CC",
                      color: isSameSector ? "#046A38" : "#B8321A",
                      fontSize: "0.75rem",
                    }}
                  />
                </Stack>
                <Typography variant="body2" sx={{ color: "#686B64" }}>
                  Empirical Minimum Spanning Tree backbone link connecting {symA} ({indA}) and {symB} ({indB}).
                </Typography>
              </Box>

              {onClearSelection && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={onClearSelection}
                  sx={{
                    borderRadius: 0,
                    textTransform: "none",
                    color: "#292D2A",
                    borderColor: "rgba(41,45,42,0.25)",
                    fontSize: "0.76rem",
                    flexShrink: 0,
                    "&:hover": { borderColor: "#292D2A", bgcolor: "rgba(41,45,42,0.04)" },
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
                p: 1.5,
                bgcolor: "#E3D7C4",
                borderRadius: 0,
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                gap: 1.5,
              }}
            >
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Pearson Correlation
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#046A38" }}>
                  ρ = +{corr.toFixed(3)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Mantegna Distance
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  d = {dist.toFixed(3)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Market Edge Rank
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  Rank #{rank} in tree
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "#686B64", textTransform: "uppercase", fontWeight: 700 }}>
                  Paired Returns
                </Typography>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A" }}>
                  {selectedItem.paired_observations ?? 120} trading days
                </Typography>
              </Box>
            </Paper>

            {/* Structural Rationale */}
            <Paper
              elevation={0}
              sx={{
                p: 2,
                borderRadius: 0,
                bgcolor: "#F9EBD7",
                border: "1px solid rgba(41,45,42,0.12)",
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: "#292D2A", mb: 0.75 }}>
                Why Did Kruskal&apos;s Algorithm Select This Exact Edge?
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64", lineHeight: 1.65 }}>
                Out of all 19,701 possible pairwise relationships in the NIFTY 200 universe, Kruskal&apos;s algorithm selected this
                link with a Mantegna distance of <strong>d = {dist.toFixed(3)}</strong> (correlation <strong>ρ = {corr.toFixed(3)}</strong>).
                In an acyclic spanning tree, this edge is indispensable: cutting it would mathematically partition their respective subtrees.
                {isSameSector ? (
                  <> Both companies operate in <strong>{indA}</strong>, reflecting shared exposure to: {macroA.headline.toLowerCase()}.</>
                ) : (
                  <> This forms a systemic cross-sector conduit between <strong>{indA}</strong> and <strong>{indB}</strong>, allowing capital and volatility shocks to transmit across industries.</>
                )}
              </Typography>

              <Stack direction="row" spacing={1.5} sx={{ mt: 2 }}>
                {onSelectSymbol && (
                  <>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => onSelectSymbol(symA)}
                      sx={{
                        borderRadius: 0,
                        textTransform: "none",
                        color: "#046A38",
                        borderColor: "#046A38",
                        fontSize: "0.78rem",
                        "&:hover": { bgcolor: "rgba(4,106,56,0.06)", borderColor: "#034d28" },
                      }}
                    >
                      Focus {symA} ({indA}) →
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => onSelectSymbol(symB)}
                      sx={{
                        borderRadius: 0,
                        textTransform: "none",
                        color: "#046A38",
                        borderColor: "#046A38",
                        fontSize: "0.78rem",
                        "&:hover": { bgcolor: "rgba(4,106,56,0.06)", borderColor: "#034d28" },
                      }}
                    >
                      Focus {symB} ({indB}) →
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
        borderRadius: 0,
        border: "none",
        bgcolor: "#F9EBD7",
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2.5}>
          {/* Main Title & Guiding Note */}
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A" }}>
              Why Do These Stocks Correlate? Structural Macro Drivers
            </Typography>
            <Typography variant="body2" sx={{ color: "#686B64", mt: 0.5 }}>
              Correlation is not accidental—it reflects shared exposure to regulatory policies, currency fluctuations,
              interest rate cycles, and global supply chains.
            </Typography>
          </Box>

          {/* Interactive Instruction Banner */}
          <Paper
            elevation={0}
            sx={{
              p: 1.75,
              borderRadius: 0,
              bgcolor: "#DCE9DE",
              borderLeft: "4px solid #046A38",
            }}
          >
            <Typography variant="body2" sx={{ color: "#046A38", fontWeight: 600 }}>
              <strong>Interactive Tree:</strong> Click any stock node or connection line above, or search for a symbol,
              to inspect its real-time correlation drivers, connected neighbors, and transmission pathways.
            </Typography>
          </Paper>

          {/* Real Empirical Market Hubs (Computed dynamically from MST API) */}
          {topHubs.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 1, textTransform: "uppercase", fontSize: "0.76rem" }}>
                Top Empirical Market Hubs (Highest Spanning Tree Degree)
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1.5, fontSize: "0.82rem" }}>
                These stocks act as structural backbone anchors in the empirical tree, connecting multiple branches and transmitting systemic market shocks:
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                {topHubs.map((hub) => (
                  <Button
                    key={hub.symbol}
                    size="small"
                    variant="outlined"
                    onClick={() => onSelectSymbol?.(hub.symbol)}
                    sx={{
                      borderRadius: 0,
                      textTransform: "none",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                      color: "#292D2A",
                      borderColor: "rgba(41,45,42,0.22)",
                      bgcolor: "#E3D7C4",
                      "&:hover": { borderColor: "#046A38", bgcolor: "#d5c7b2" },
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
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 1, textTransform: "uppercase", fontSize: "0.76rem" }}>
                Strongest Co-Movement Links in the Market
              </Typography>
              <Typography variant="body2" sx={{ color: "#686B64", mb: 1.5, fontSize: "0.82rem" }}>
                These pairs exhibit the lowest statistical distance in the entire NIFTY 200 universe (highest return synchronization):
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                {topCorrelations.map((pair) => (
                  <Button
                    key={`${pair.symbol_a}-${pair.symbol_b}`}
                    size="small"
                    variant="outlined"
                    onClick={() => onSelectEdge?.(pair.symbol_a, pair.symbol_b)}
                    sx={{
                      borderRadius: 0,
                      textTransform: "none",
                      fontSize: "0.78rem",
                      fontWeight: 600,
                      color: "#046A38",
                      borderColor: "rgba(4,106,56,0.30)",
                      bgcolor: "#DCE9DE",
                      "&:hover": { borderColor: "#046A38", bgcolor: "#cde0d0" },
                    }}
                  >
                    {pair.symbol_a} ↔ {pair.symbol_b} (ρ = +{pair.correlation.toFixed(2)})
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          {/* Sector Macroeconomic Driver Encyclopedia */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 1, textTransform: "uppercase", fontSize: "0.76rem" }}>
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
                      borderRadius: 0,
                      border: "none",
                      bgcolor: "#F9EBD7",
                      boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
                      "&:before": { display: "none" },
                    }}
                  >
                    <AccordionSummary>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", width: "100%", pr: 2 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A" }}>
                          {sectorName}
                        </Typography>
                        <Chip
                          size="small"
                          label={profile.headline}
                          sx={{
                            borderRadius: 0,
                            fontWeight: 600,
                            fontSize: "0.72rem",
                            bgcolor: "#E3D7C4",
                            color: "#292D2A",
                          }}
                        />
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: 0 }}>
                      <Stack spacing={1}>
                        {profile.macroDrivers.map((d, i) => (
                          <Typography key={i} variant="body2" sx={{ color: "#686B64", lineHeight: 1.55 }}>
                            • {d}
                          </Typography>
                        ))}
                        <Typography variant="body2" sx={{ color: "#046A38", fontWeight: 600, mt: 0.5 }}>
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
