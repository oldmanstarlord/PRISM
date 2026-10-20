/**
 * Authoritative Frontend Methodology Registry
 *
 * Synchronized with backend `backend/app/portfolio_analytics/methodology_registry.py`.
 * Provides definitions, formulas, units, windows, and limitations for all metrics.
 * Powers tooltips, info popups, and the methodology documentation panel in the UI.
 */

export interface MetricDoc {
  id: string;
  name: string;
  label?: string;
  category: string;
  definition: string;
  formulaLatex: string;
  formulaPlain: string;
  formula?: string;
  units: string;
  defaultWindow: string;
  window?: string;
  minObservations: number;
  min_observations?: number;
  returnType: "simple" | "log" | "ratio";
  assumptions: string[];
  limitations: string[];
}

export interface AlertThresholdDef {
  id: string;
  name: string;
  defaultWarning: number;
  defaultCritical: number | null;
  minAllowed: number;
  maxAllowed: number;
  unit: string;
  description: string;
}

export interface AlertThresholdConfig {
  id: string;
  title: string;
  defaultValue: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  description: string;
}

export const METHODOLOGY_VERSION = "2026.1";
export const ANNUALISATION_FACTOR = 252;
export const DEFAULT_RISK_FREE_RATE = 0.065; // 6.5% annualized

export const METRIC_REGISTRY: Record<string, MetricDoc> = {
  ANNUALIZED_VOLATILITY: {
    id: "ANNUALIZED_VOLATILITY",
    name: "Annualized Volatility",
    category: "Risk",
    definition:
      "Sample standard deviation of daily portfolio returns annualized by the square root of 252 trading sessions.",
    formulaLatex:
      "\\sigma_{ann} = \\sqrt{252} \\cdot \\sqrt{\\frac{1}{N-1}\\sum_{t=1}^N (R_{p,t} - \\bar{R}_p)^2}",
    formulaPlain: "sigma_ann = sqrt(252) * std(R_p, ddof=1)",
    units: "% annualized",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "252 trading sessions per calendar year in Indian equity markets.",
      "Constant target portfolio asset weights rebalanced daily.",
      "Finite variance in underlying daily return series.",
    ],
    limitations: [
      "Assumes stationary return variance over the estimation lookback.",
      "Does not distinguish between upside and downside return variance.",
      "Underestimates tail risk under fat-tailed (leptokurtic) distributions.",
    ],
  },
  DOWNSIDE_VOLATILITY: {
    id: "DOWNSIDE_VOLATILITY",
    name: "Downside Semi-Volatility",
    category: "Risk",
    definition:
      "Annualized root-mean-square of negative returns relative to a zero target, measuring only unfavorable downside volatility.",
    formulaLatex:
      "\\sigma_{down} = \\sqrt{252} \\cdot \\sqrt{\\frac{1}{N}\\sum_{t=1}^N \\min(R_{p,t}, 0)^2}",
    formulaPlain: "sigma_down = sqrt(252) * sqrt(mean(min(R_p, 0)^2))",
    units: "% annualized",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Target minimum acceptable return (MAR) is fixed at 0.0.",
      "Constant target portfolio asset weights.",
    ],
    limitations: [
      "Sample size of down sessions is strictly smaller than total sessions.",
      "Path-independent within the lookback window.",
    ],
  },
  MAX_DRAWDOWN: {
    id: "MAX_DRAWDOWN",
    name: "Maximum Drawdown (MDD)",
    category: "Risk",
    definition:
      "Peak-to-trough maximum observed capital decline across the cumulative wealth path within the estimation window.",
    formulaLatex:
      "\\text{MDD} = \\max_{\\tau \\in [0, T]} \\left( \\frac{\\max_{s \\le \\tau} W_s - W_\\tau}{\\max_{s \\le \\tau} W_s} \\right)",
    formulaPlain: "MDD = max( (Peak(s<=t) - W_t) / Peak(s<=t) )",
    units: "% decline",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "ratio",
    assumptions: [
      "Constructed from discrete compounded portfolio wealth series W_t = W_0 * prod(1 + R_p).",
      "Values strictly bounded in [-1.0, 0.0] (or 0% to 100% loss).",
    ],
    limitations: [
      "Highly path-dependent and sensitive to estimation window start/end dates.",
      "Does not capture drawdown duration or recovery speed.",
    ],
  },
  HISTORICAL_VAR_95: {
    id: "HISTORICAL_VAR_95",
    name: "Historical Value at Risk (95% 1-Day)",
    category: "Tail Risk",
    definition:
      "Negative 5th percentile of empirical daily returns, estimating the loss exceeded on 5% of trading days.",
    formulaLatex: "\\text{VaR}_{0.95} = - Q_{0.05}(R_p)",
    formulaPlain: "VaR_95 = -quantile(R_p, 0.05)",
    units: "% 1-day",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 60,
    returnType: "simple",
    assumptions: [
      "Historical sample distribution is representative of forward short-term risk.",
      "1-day holding horizon without active intraday liquidation.",
    ],
    limitations: [
      "Historical estimate, not a guaranteed loss ceiling.",
      "Provides no information on the magnitude of losses beyond the 95th percentile.",
    ],
  },
  HISTORICAL_VAR_99: {
    id: "HISTORICAL_VAR_99",
    name: "Historical Value at Risk (99% 1-Day)",
    category: "Tail Risk",
    definition:
      "Negative 1st percentile of empirical daily returns, estimating the loss exceeded on 1% of trading sessions (~2.5 days/year).",
    formulaLatex: "\\text{VaR}_{0.99} = - Q_{0.01}(R_p)",
    formulaPlain: "VaR_99 = -quantile(R_p, 0.01)",
    units: "% 1-day",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 100,
    returnType: "simple",
    assumptions: [
      "Historical sample distribution is representative of tail extremes.",
      "Monotonically greater than or equal to 95% VaR: VaR_99 >= VaR_95.",
    ],
    limitations: [
      "High sample variance when N < 250 observations.",
      "Historical estimate, not a guaranteed maximum loss.",
    ],
  },
  HISTORICAL_ES_95: {
    id: "HISTORICAL_ES_95",
    name: "Expected Shortfall / CVaR (95% 1-Day)",
    category: "Tail Risk",
    definition:
      "Expected loss conditional on the portfolio loss exceeding the 95% VaR threshold (average of tail losses).",
    formulaLatex: "\\text{ES}_{0.95} = - \\mathbb{E}[R_p \\mid R_p \\le -\\text{VaR}_{0.95}]",
    formulaPlain: "ES_95 = -mean(R_p[R_p <= -VaR_95])",
    units: "% 1-day",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 60,
    returnType: "simple",
    assumptions: [
      "Coherent risk measure satisfying subadditivity (Artzner et al. 1999).",
      "Monotonically greater than or equal to VaR: ES_95 >= VaR_95.",
    ],
    limitations: [
      "Requires sufficient observations in the tail.",
      "Sensitive to extreme historical outliers in small samples.",
    ],
  },
  HISTORICAL_ES_99: {
    id: "HISTORICAL_ES_99",
    name: "Expected Shortfall / CVaR (99% 1-Day)",
    category: "Tail Risk",
    definition:
      "Expected loss conditional on the portfolio loss exceeding the 99% VaR threshold.",
    formulaLatex: "\\text{ES}_{0.99} = - \\mathbb{E}[R_p \\mid R_p \\le -\\text{VaR}_{0.99}]",
    formulaPlain: "ES_99 = -mean(R_p[R_p <= -VaR_99])",
    units: "% 1-day",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 100,
    returnType: "simple",
    assumptions: [
      "Coherent risk measure; ES_99 >= VaR_99 and ES_99 >= ES_95.",
    ],
    limitations: [
      "In 250 days, the 1% tail contains only 2-3 observations.",
    ],
  },
  PARAMETRIC_VAR_95: {
    id: "PARAMETRIC_VAR_95",
    name: "Parametric Gaussian VaR (95% 1-Day)",
    category: "Tail Risk",
    definition:
      "Analytic VaR derived assuming portfolio returns follow a normal distribution with empirical mean and standard deviation.",
    formulaLatex: "\\text{VaR}_{0.95}^{param} = - (\\mu_p - 1.64485 \\cdot \\sigma_p)",
    formulaPlain: "VaR_param_95 = -(mean(R_p) - 1.64485 * std(R_p))",
    units: "% 1-day",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Normal (Gaussian) distribution of daily portfolio returns.",
      "z-score for 95% one-tailed confidence is 1.644853.",
    ],
    limitations: [
      "Underestimates actual losses when returns exhibit negative skewness and excess kurtosis.",
    ],
  },
  EULER_MARGINAL_RISK: {
    id: "EULER_MARGINAL_RISK",
    name: "Marginal Risk Contribution (Euler)",
    category: "Decomposition",
    definition:
      "Partial derivative of portfolio volatility with respect to holding weight: d(sigma_p)/d(w_i).",
    formulaLatex: "\\frac{\\partial \\sigma_p}{\\partial w_i} = \\frac{(\\Sigma w)_i}{\\sigma_p}",
    formulaPlain: "marginal_risk_i = (Sigma @ w)_i / sigma_p",
    units: "% volatility / weight",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Portfolio volatility is a linearly homogeneous function of degree 1: f(lambda*w) = lambda*f(w).",
      "Sample covariance matrix Sigma is positive semi-definite.",
    ],
    limitations: [
      "Negative marginal risk is legitimate and indicates a hedging position.",
    ],
  },
  EULER_COMPONENT_RISK: {
    id: "EULER_COMPONENT_RISK",
    name: "Component Risk Contribution (Euler)",
    category: "Decomposition",
    definition:
      "Absolute volatility contributed by holding i: C_i = w_i * d(sigma_p)/d(w_i). By Euler's theorem, sum(C_i) == sigma_p.",
    formulaLatex: "C_i = w_i \\frac{\\partial \\sigma_p}{\\partial w_i} = \\frac{w_i (\\Sigma w)_i}{\\sigma_p}",
    formulaPlain: "C_i = w_i * (Sigma @ w)_i / sigma_p",
    units: "% volatility",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Sum of all component contributions equals total portfolio volatility: sum(C_i) == sigma_p.",
      "Negative contributions indicate hedging assets reducing overall portfolio volatility.",
    ],
    limitations: [
      "Reflects marginal incremental changes; does not predict non-linear rebalancing impacts.",
    ],
  },
  EULER_RISK_SHARE: {
    id: "EULER_RISK_SHARE",
    name: "Percentage Risk Contribution Share",
    category: "Decomposition",
    definition:
      "Fraction of portfolio risk variance explained by holding i: RC%_i = C_i / sigma_p. Sum of all shares identically equals 100%.",
    formulaLatex: "\\text{RC}\\%_i = \\frac{w_i (\\Sigma w)_i}{\\sigma_p^2} \\times 100\\%",
    formulaPlain: "RC%_i = (w_i * (Sigma @ w)_i / sigma_p^2) * 100",
    units: "%",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Identically sums to 100.0%: sum(RC%_i) == 100.0%.",
      "Negative percentages represent hedging benefits.",
    ],
    limitations: [
      "Shares can exceed 100% when other positions provide negative hedging offsets.",
    ],
  },
  MARKET_BETA: {
    id: "MARKET_BETA",
    name: "Market Beta (NIFTY 50)",
    category: "Systematic Risk",
    definition:
      "Slope coefficient of OLS regression of asset returns against the benchmark (NIFTY 50 ^NSEI).",
    formulaLatex: "\\beta = \\frac{\\text{Cov}(R_i, R_m)}{\\text{Var}(R_m)}",
    formulaPlain: "beta = cov(R_i, R_m) / var(R_m)",
    units: "Sensitivity ratio",
    defaultWindow: "252 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Benchmark is NIFTY 50 (^NSEI), ingested into the local database.",
      "Asset and benchmark returns aligned strictly on common valid dates.",
    ],
    limitations: [
      "Assumes stable linear co-movement; unreliable below 30 common observations.",
      "Survivorship bias: benchmark constituents change over time.",
    ],
  },
  JENSENS_ALPHA: {
    id: "JENSENS_ALPHA",
    name: "Jensen's Alpha",
    category: "Systematic Risk",
    definition:
      "Annualized excess return above CAPM expected return using a 6.5% risk-free rate assumption.",
    formulaLatex: "\\alpha = 252 \\cdot \\left[ (\\bar{R}_i - R_f) - \\beta (\\bar{R}_m - R_f) \\right]",
    formulaPlain: "alpha = 252 * ((mean(R_i) - R_f_daily) - beta * (mean(R_m) - R_f_daily))",
    units: "% annualized",
    defaultWindow: "252 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Risk-free rate assumed at 6.5% annualized (RBI 91-day T-bill reference).",
      "Single-factor CAPM linear relation.",
    ],
    limitations: [
      "Diagnostic historical estimate; past alpha is not predictive of future outperformance.",
    ],
  },
  DIVERSIFICATION_RATIO: {
    id: "DIVERSIFICATION_RATIO",
    name: "Diversification Ratio (Choueifaty)",
    category: "Diversification",
    definition:
      "Ratio of weighted average individual asset volatilities to total portfolio volatility.",
    formulaLatex: "\\text{DR} = \\frac{\\sum_{i=1}^N w_i \\sigma_i}{\\sigma_p}",
    formulaPlain: "DR = sum(w_i * sigma_i) / sigma_p",
    units: "Ratio (>= 1.0)",
    defaultWindow: "250 trading days (~1Y)",
    minObservations: 30,
    returnType: "simple",
    assumptions: [
      "Always greater than or equal to 1.0 (Cauchy-Schwarz inequality): DR >= 1.0.",
      "DR = 1.0 if and only if all assets are perfectly positively correlated (rho = 1.0).",
    ],
    limitations: ["Assumes asset volatilities are estimated without error."],
  },
  HOLDING_HHI: {
    id: "HOLDING_HHI",
    name: "Holding Concentration (HHI)",
    category: "Concentration",
    definition: "Sum of squared capital weights across all holdings: HHI = sum(w_i^2).",
    formulaLatex: "\\text{HHI}_{holding} = \\sum_{i=1}^N w_i^2",
    formulaPlain: "HHI = sum(w_i^2)",
    units: "decimal (0 to 1)",
    defaultWindow: "Current Portfolio Allocation",
    minObservations: 1,
    returnType: "ratio",
    assumptions: [
      "Weights sum to 1.0: sum(w_i) == 1.0.",
      "Range: [1/N, 1.0]. Equal-weight gives 1/N; single monopoly position gives 1.0.",
    ],
    limitations: ["Does not account for correlations between holdings."],
  },
  EFFECTIVE_HOLDINGS: {
    id: "EFFECTIVE_HOLDINGS",
    name: "Effective Number of Holdings (N_eff)",
    category: "Concentration",
    definition: "Inverse of Holding HHI: N_eff = 1 / HHI.",
    formulaLatex: "N_{eff} = \\frac{1}{\\sum_{i=1}^N w_i^2}",
    formulaPlain: "N_eff = 1 / sum(w_i^2)",
    units: "Effective count",
    defaultWindow: "Current Portfolio Allocation",
    minObservations: 1,
    returnType: "ratio",
    assumptions: ["Range: [1.0, N]. Equals N for equal-weighted portfolio."],
    limitations: ["Measures capital concentration only, not risk concentration."],
  },
  SECTOR_HHI: {
    id: "SECTOR_HHI",
    name: "Sector Concentration (Sector HHI & S_eff)",
    category: "Concentration",
    definition:
      "Sum of squared aggregate sector weights: HHI_sector = sum(s_j^2). S_eff = 1 / HHI_sector.",
    formulaLatex: "\\text{HHI}_{sector} = \\sum_{j=1}^M s_j^2, \\quad S_{eff} = \\frac{1}{\\sum_{j=1}^M s_j^2}",
    formulaPlain: "HHI_sec = sum(s_j^2), S_eff = 1 / sum(s_j^2)",
    units: "Effective sector count",
    defaultWindow: "Current Portfolio Allocation",
    minObservations: 1,
    returnType: "ratio",
    assumptions: [
      "Each security mapped to exactly one primary industry sector from SecurityMaster.",
    ],
    limitations: [
      "Conglomerates and diversified businesses mapped to single sector.",
    ],
  },
  MANTEGNA_MST_DISTANCE: {
    id: "MANTEGNA_MST_DISTANCE",
    name: "Mantegna MST Metric Distance",
    category: "Network",
    definition:
      "Non-linear distance transform mapping pairwise correlation rho into Euclidean metric space: d_ij = sqrt(2 * (1 - rho_ij)).",
    formulaLatex: "d_{ij} = \\sqrt{2 (1 - \\rho_{ij})}",
    formulaPlain: "d_ij = sqrt(2 * (1 - rho_ij))",
    units: "Metric distance [0, 2]",
    defaultWindow: "120 trading days",
    minObservations: 100,
    returnType: "ratio",
    assumptions: [
      "Satisfies metric axioms: d_ii = 0, d_ij >= 0, d_ij = d_ji, and triangle inequality.",
      "Bounded in [0, 2]. rho=1 -> d=0; rho=-1 -> d=2.",
    ],
    limitations: [
      "Minimum Spanning Tree discards (N-1)(N-2)/2 edges; tree topology does not prove causation.",
    ],
  },
  STOCK_RISK_SCORE_HEURISTIC: {
    id: "STOCK_RISK_SCORE_HEURISTIC",
    name: "5-Factor Heuristic Stock Risk Score",
    category: "Scoring (Heuristic)",
    definition:
      "Heuristic 0–100 composite synthesizing 5 normalized risk dimensions: Volatility (30%), Downside (25%), Drawdown (20%), Beta (15%), and Instability (10%).",
    formulaLatex:
      "S = 0.30 S_{vol} + 0.25 S_{down} + 0.20 S_{mdd} + 0.15 S_{\\beta} + 0.10 S_{instab}",
    formulaPlain:
      "Score = 0.30*S_vol + 0.25*S_down + 0.20*S_mdd + 0.15*S_beta + 0.10*S_instab",
    units: "Score (0–100)",
    defaultWindow: "252 trading days (or 126d fallback)",
    minObservations: 30,
    returnType: "ratio",
    assumptions: [
      "Normalized to [0, 100] via fixed empirical calibration bounds.",
      "Labelled HEURISTIC: diagnostic synthesis, not an ML prediction or buy/sell signal.",
    ],
    limitations: [
      "Fixed normalization parameters; full historical calibration scheduled for Phase 4.",
    ],
  },
  PORTFOLIO_RISK_SCORE_HEURISTIC: {
    id: "PORTFOLIO_RISK_SCORE_HEURISTIC",
    name: "Portfolio Diagnostic Risk Score",
    category: "Scoring (Heuristic)",
    definition:
      "Heuristic 0–100 composite evaluating overall portfolio covariance risk: Portfolio Volatility (35%), Downside Volatility (25%), Max Drawdown (25%), and Weighted Beta (15%).",
    formulaLatex:
      "S_p = 0.35 S_{\\sigma_p} + 0.25 S_{down_p} + 0.25 S_{\\text{MDD}_p} + 0.15 S_{\\beta_p}",
    formulaPlain:
      "Score = 0.35*S_vol + 0.25*S_down + 0.25*S_mdd + 0.15*S_beta",
    units: "Score (0–100)",
    defaultWindow: "250 trading days",
    minObservations: 30,
    returnType: "ratio",
    assumptions: [
      "Evaluates true portfolio covariance (w^T Sigma w), not simple average of stock scores.",
      "Labelled HEURISTIC until Phase 4 empirical calibration.",
    ],
    limitations: [
      "Fixed prudential bounds [vol: 0.10-0.35, down: 0.06-0.25, mdd: 0.08-0.38, beta: 50+(beta-1)*55].",
    ],
  },
};

export const STOCK_RISK_FACTOR_WEIGHTS: Record<string, number> = {
  annualized_volatility: 0.30,
  downside_volatility: 0.25,
  max_drawdown: 0.20,
  beta: 0.15,
  instability: 0.10,
};

export const PORTFOLIO_RISK_FACTOR_WEIGHTS: Record<string, number> = {
  annualized_volatility: 0.35,
  downside_volatility: 0.25,
  max_drawdown: 0.25,
  weighted_beta: 0.15,
};

// Add backward-compatible lowercase aliases with label, window, min_observations, formula
const aliases: Record<string, string> = {
  portfolio_risk_score: "PORTFOLIO_RISK_SCORE_HEURISTIC",
  portfolio_volatility: "ANNUALIZED_VOLATILITY",
  downside_volatility: "DOWNSIDE_VOLATILITY",
  max_drawdown: "MAX_DRAWDOWN",
  portfolio_beta: "MARKET_BETA",
  var_historical_95: "HISTORICAL_VAR_95",
  cvar_historical_95: "HISTORICAL_ES_95",
  euler_contribution: "EULER_COMPONENT_RISK",
};
for (const [alias, canonical] of Object.entries(aliases)) {
  if (METRIC_REGISTRY[canonical]) {
    const orig = METRIC_REGISTRY[canonical];
    orig.label = orig.name;
    orig.window = orig.defaultWindow;
    orig.min_observations = orig.minObservations;
    orig.formula = orig.formulaPlain;
    METRIC_REGISTRY[alias] = {
      ...orig,
      id: alias,
    };
  }
}
for (const orig of Object.values(METRIC_REGISTRY)) {
  if (!orig.label) orig.label = orig.name;
  if (!orig.window) orig.window = orig.defaultWindow;
  if (orig.min_observations === undefined) orig.min_observations = orig.minObservations;
  if (!orig.formula) orig.formula = orig.formulaPlain;
}

export const ALERT_THRESHOLD_DEFAULTS: Record<string, AlertThresholdDef> = {
  risk_score: {
    id: "risk_score",
    name: "Portfolio Risk Score",
    defaultWarning: 60.0,
    defaultCritical: 80.0,
    minAllowed: 10.0,
    maxAllowed: 95.0,
    unit: "pts (0-100)",
    description: "Overall heuristic portfolio risk score.",
  },
  sector_ceiling: {
    id: "sector_ceiling",
    name: "Top Sector Allocation Ceiling",
    defaultWarning: 25.0,
    defaultCritical: 35.0,
    minAllowed: 10.0,
    maxAllowed: 80.0,
    unit: "% capital",
    description: "Prudential maximum weight for any single industry sector.",
  },
  holding_concentration: {
    id: "holding_concentration",
    name: "Single-Stock Capital Concentration",
    defaultWarning: 20.0,
    defaultCritical: 30.0,
    minAllowed: 5.0,
    maxAllowed: 60.0,
    unit: "% capital",
    description: "Maximum capital allocation to any single holding.",
  },
  effective_holdings: {
    id: "effective_holdings",
    name: "Effective Number of Holdings Floor",
    defaultWarning: 4.0,
    defaultCritical: 2.0,
    minAllowed: 1.5,
    maxAllowed: 25.0,
    unit: "holdings (N_eff)",
    description: "Inverse HHI diversification floor. Triggers when N_eff drops below threshold.",
  },
  downside_volatility: {
    id: "downside_volatility",
    name: "Annualized Downside Volatility Ceiling",
    defaultWarning: 20.0,
    defaultCritical: 28.0,
    minAllowed: 5.0,
    maxAllowed: 50.0,
    unit: "% annualized",
    description: "Upper tolerance for negative semi-deviation.",
  },
  euler_risk_share: {
    id: "euler_risk_share",
    name: "Euler Risk Contribution Share Ceiling",
    defaultWarning: 30.0,
    defaultCritical: 45.0,
    minAllowed: 10.0,
    maxAllowed: 80.0,
    unit: "% risk share",
    description: "Maximum fraction of portfolio risk variance explained by a single asset.",
  },
};

export const ALERT_THRESHOLD_CONFIGS: AlertThresholdConfig[] = [
  {
    id: "risk_score",
    title: "Portfolio Risk Score Warning Ceiling",
    defaultValue: 60.0,
    min: 10.0,
    max: 95.0,
    step: 5.0,
    unit: "pts (0–100)",
    description: "Overall heuristic portfolio risk score ceiling triggering review.",
  },
  {
    id: "sector_ceiling",
    title: "Top Sector Allocation Ceiling",
    defaultValue: 25.0,
    min: 10.0,
    max: 80.0,
    step: 1.0,
    unit: "% capital",
    description: "Prudential maximum weight for any single industry sector.",
  },
  {
    id: "holding_concentration",
    title: "Single-Stock Capital Concentration",
    defaultValue: 20.0,
    min: 5.0,
    max: 60.0,
    step: 1.0,
    unit: "% capital",
    description: "Maximum capital allocation to any single holding.",
  },
  {
    id: "effective_holdings",
    title: "Effective Number of Holdings Floor",
    defaultValue: 4.0,
    min: 1.5,
    max: 25.0,
    step: 0.5,
    unit: "holdings (N_eff)",
    description: "Inverse HHI diversification floor. Triggers when N_eff drops below threshold.",
  },
  {
    id: "downside_volatility",
    title: "Annualized Downside Volatility Ceiling",
    defaultValue: 20.0,
    min: 5.0,
    max: 50.0,
    step: 1.0,
    unit: "% annualized",
    description: "Upper tolerance for negative semi-deviation.",
  },
  {
    id: "euler_risk_share",
    title: "Euler Risk Contribution Share Ceiling",
    defaultValue: 30.0,
    min: 10.0,
    max: 80.0,
    step: 1.0,
    unit: "% risk share",
    description: "Maximum fraction of portfolio risk variance explained by a single asset.",
  },
];

export const DEFAULT_ALERT_THRESHOLDS: Record<string, number> = Object.fromEntries(
  ALERT_THRESHOLD_CONFIGS.map((cfg) => [cfg.id, cfg.defaultValue])
);

const ALERT_STORAGE_PREFIX = "prism_alert_thresholds";

export function loadAlertThresholds(portfolioId?: string): Record<string, number> {
  const defaults: Record<string, number> = {};
  for (const [key, config] of Object.entries(ALERT_THRESHOLD_DEFAULTS)) {
    defaults[key] = config.defaultWarning;
  }
  try {
    const key = portfolioId ? `${ALERT_STORAGE_PREFIX}_${portfolioId}` : ALERT_STORAGE_PREFIX;
    const raw = localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null) {
        const validated: Record<string, number> = { ...defaults };
        for (const [k, v] of Object.entries(parsed)) {
          if (typeof v === "number" && !isNaN(v) && ALERT_THRESHOLD_DEFAULTS[k]) {
            const cfg = ALERT_THRESHOLD_DEFAULTS[k];
            validated[k] = Math.max(cfg.minAllowed, Math.min(cfg.maxAllowed, v));
          }
        }
        return validated;
      }
    }
  } catch {
    // Return defaults if parsing fails
  }
  return defaults;
}

export function saveAlertThresholds(
  thresholds: Record<string, number>,
  portfolioId?: string
): void {
  try {
    const key = portfolioId ? `${ALERT_STORAGE_PREFIX}_${portfolioId}` : ALERT_STORAGE_PREFIX;
    localStorage.setItem(key, JSON.stringify(thresholds));
  } catch {
    // Ignore storage errors in test or private environments
  }
}

export function resetAlertThresholds(portfolioId?: string): Record<string, number> {
  try {
    const key = portfolioId ? `${ALERT_STORAGE_PREFIX}_${portfolioId}` : ALERT_STORAGE_PREFIX;
    localStorage.removeItem(key);
  } catch {
    // Ignore
  }
  return loadAlertThresholds(portfolioId);
}
