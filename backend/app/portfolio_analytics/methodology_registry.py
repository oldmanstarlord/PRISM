"""Single authoritative methodology registry for PRISM quantitative risk metrics.

Provides formal mathematical definitions, formula text, units, lookback windows,
minimum observation requirements, limitations, scoring weights, normalization bounds,
and standard prudential alert thresholds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

METHODOLOGY_VERSION = "2026.1"
ANNUALISATION_FACTOR = 252
DEFAULT_RISK_FREE_RATE = 0.065  # 6.5% annualized (RBI 91-day T-Bill reference)


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    id: str
    name: str
    category: str
    definition: str
    formula_latex: str
    formula_plain: str
    units: str
    default_window: str
    min_observations: int
    return_type: str  # "simple" | "log" | "ratio"
    assumptions: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Authoritative Metric Definitions ───

METRIC_REGISTRY: dict[str, MetricDefinition] = {
    "ANNUALIZED_VOLATILITY": MetricDefinition(
        id="ANNUALIZED_VOLATILITY",
        name="Annualized Volatility",
        category="Risk",
        definition=(
            "Sample standard deviation of daily portfolio returns annualized by the "
            "square root of 252 trading sessions."
        ),
        formula_latex=(
            r"\sigma_{ann} = \sqrt{252} \cdot "
            r"\sqrt{\frac{1}{N-1}\sum_{t=1}^N (R_{p,t} - \bar{R}_p)^2}"
        ),
        formula_plain="sigma_ann = sqrt(252) * std(R_p, ddof=1)",
        units="% annualized",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "252 trading sessions per calendar year in Indian equity markets.",
            "Constant target portfolio asset weights rebalanced daily.",
            "Finite variance in underlying daily return series.",
        ],
        limitations=[
            "Assumes stationary return variance over the estimation lookback.",
            "Does not distinguish between upside and downside return variance.",
            "Underestimates tail risk under fat-tailed (leptokurtic) distributions.",
        ],
    ),
    "DOWNSIDE_VOLATILITY": MetricDefinition(
        id="DOWNSIDE_VOLATILITY",
        name="Downside Semi-Volatility",
        category="Risk",
        definition=(
            "Annualized root-mean-square of negative returns relative to a zero target, "
            "measuring only unfavorable downside volatility."
        ),
        formula_latex=(
            r"\sigma_{down} = \sqrt{252} \cdot "
            r"\sqrt{\frac{1}{N}\sum_{t=1}^N \min(R_{p,t}, 0)^2}"
        ),
        formula_plain="sigma_down = sqrt(252) * sqrt(mean(min(R_p, 0)^2))",
        units="% annualized",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Target minimum acceptable return (MAR) is fixed at 0.0.",
            "Constant target portfolio asset weights.",
        ],
        limitations=[
            "Sample size of down sessions is strictly smaller than total sessions.",
            "Path-independent within the lookback window.",
        ],
    ),
    "MAX_DRAWDOWN": MetricDefinition(
        id="MAX_DRAWDOWN",
        name="Maximum Drawdown (MDD)",
        category="Risk",
        definition=(
            "Peak-to-trough maximum observed capital decline across the cumulative "
            "wealth path within the estimation window."
        ),
        formula_latex=(
            r"\text{MDD} = \max_{\tau \in [0, T]} \left( "
            r"\frac{\max_{s \le \tau} W_s - W_\tau}{\max_{s \le \tau} W_s} \right)"
        ),
        formula_plain="MDD = max( (Peak(s<=t) - W_t) / Peak(s<=t) )",
        units="% decline",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="ratio",
        assumptions=[
            (
                "Constructed from discrete compounded portfolio wealth series "
                "W_t = W_0 * prod(1 + R_p)."
            ),
            "Values strictly bounded in [-1.0, 0.0] (or 0% to 100% loss).",
        ],
        limitations=[
            "Highly path-dependent and sensitive to estimation window start/end dates.",
            "Does not capture drawdown duration or recovery speed.",
        ],
    ),
    "HISTORICAL_VAR_95": MetricDefinition(
        id="HISTORICAL_VAR_95",
        name="Historical Value at Risk (95% 1-Day)",
        category="Tail Risk",
        definition=(
            "Negative 5th percentile of the empirical historical return distribution, "
            "estimating the loss exceeded on 5% of trading days."
        ),
        formula_latex=r"\text{VaR}_{0.95} = - Q_{0.05}(R_p)",
        formula_plain="VaR_95 = -quantile(R_p, 0.05)",
        units="% 1-day",
        default_window="250 trading days (~1Y)",
        min_observations=60,
        return_type="simple",
        assumptions=[
            "Historical sample distribution is representative of forward short-term risk.",
            "1-day holding horizon without active intraday liquidation.",
        ],
        limitations=[
            "Historical estimate, not a guaranteed loss ceiling.",
            "Provides no information on the magnitude of losses beyond the 95th percentile.",
        ],
    ),
    "HISTORICAL_VAR_99": MetricDefinition(
        id="HISTORICAL_VAR_99",
        name="Historical Value at Risk (99% 1-Day)",
        category="Tail Risk",
        definition=(
            "Negative 1st percentile of empirical historical returns, estimating the "
            "loss exceeded on 1% of trading sessions (~2.5 days per year)."
        ),
        formula_latex=r"\text{VaR}_{0.99} = - Q_{0.01}(R_p)",
        formula_plain="VaR_99 = -quantile(R_p, 0.01)",
        units="% 1-day",
        default_window="250 trading days (~1Y)",
        min_observations=100,
        return_type="simple",
        assumptions=[
            "Historical sample distribution is representative of tail extremes.",
            "Monotonically greater than or equal to 95% VaR: VaR_99 >= VaR_95.",
        ],
        limitations=[
            "High sample variance when N < 250 observations.",
            "Historical estimate, not a guaranteed maximum loss.",
        ],
    ),
    "HISTORICAL_ES_95": MetricDefinition(
        id="HISTORICAL_ES_95",
        name="Expected Shortfall / CVaR (95% 1-Day)",
        category="Tail Risk",
        definition=(
            "Expected loss conditional on the portfolio loss exceeding the 95% VaR threshold "
            "(average of tail losses)."
        ),
        formula_latex=r"\text{ES}_{0.95} = - \mathbb{E}[R_p \mid R_p \le -\text{VaR}_{0.95}]",
        formula_plain="ES_95 = -mean(R_p[R_p <= -VaR_95])",
        units="% 1-day",
        default_window="250 trading days (~1Y)",
        min_observations=60,
        return_type="simple",
        assumptions=[
            "Coherent risk measure satisfying subadditivity (Artzner et al. 1999).",
            "Monotonically greater than or equal to VaR: ES_95 >= VaR_95.",
        ],
        limitations=[
            "Requires sufficient observations in the tail (at least 3-5 tail observations).",
            "Sensitive to extreme historical outliers in small samples.",
        ],
    ),
    "HISTORICAL_ES_99": MetricDefinition(
        id="HISTORICAL_ES_99",
        name="Expected Shortfall / CVaR (99% 1-Day)",
        category="Tail Risk",
        definition=(
            "Expected loss conditional on the portfolio loss exceeding the 99% VaR threshold."
        ),
        formula_latex=r"\text{ES}_{0.99} = - \mathbb{E}[R_p \mid R_p \le -\text{VaR}_{0.99}]",
        formula_plain="ES_99 = -mean(R_p[R_p <= -VaR_99])",
        units="% 1-day",
        default_window="250 trading days (~1Y)",
        min_observations=100,
        return_type="simple",
        assumptions=[
            "Coherent risk measure; ES_99 >= VaR_99 and ES_99 >= ES_95.",
        ],
        limitations=[
            "In 250 days, the 1% tail contains only 2-3 observations; subject to sampling noise.",
        ],
    ),
    "PARAMETRIC_VAR_95": MetricDefinition(
        id="PARAMETRIC_VAR_95",
        name="Parametric Gaussian VaR (95% 1-Day)",
        category="Tail Risk",
        definition=(
            "Analytic VaR derived assuming portfolio returns follow a normal distribution "
            "with empirical mean and standard deviation."
        ),
        formula_latex=r"\text{VaR}_{0.95}^{param} = - (\mu_p - 1.64485 \cdot \sigma_p)",
        formula_plain="VaR_param_95 = -(mean(R_p) - 1.64485 * std(R_p))",
        units="% 1-day",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Normal (Gaussian) distribution of daily portfolio returns.",
            "z-score for 95% one-tailed confidence is 1.644853.",
        ],
        limitations=[
            (
                "Underestimates actual losses when returns exhibit negative skewness "
                "and excess kurtosis."
            ),
        ],
    ),
    "EULER_MARGINAL_RISK": MetricDefinition(
        id="EULER_MARGINAL_RISK",
        name="Marginal Risk Contribution (Euler)",
        category="Decomposition",
        definition=(
            "Partial derivative of portfolio volatility with respect to holding weight: "
            "d(sigma_p)/d(w_i)."
        ),
        formula_latex=r"\frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sigma_p}",
        formula_plain="marginal_risk_i = (Sigma @ w)_i / sigma_p",
        units="% volatility / weight",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            (
                "Portfolio volatility is a linearly homogeneous function of degree 1: "
                "f(lambda*w) = lambda*f(w)."
            ),
            "Sample covariance matrix Sigma is positive semi-definite.",
        ],
        limitations=[
            "Negative marginal risk is legitimate and indicates a hedging position.",
        ],
    ),
    "EULER_COMPONENT_RISK": MetricDefinition(
        id="EULER_COMPONENT_RISK",
        name="Component Risk Contribution (Euler)",
        category="Decomposition",
        definition=(
            "Absolute volatility contributed by holding i: C_i = w_i * d(sigma_p)/d(w_i). "
            "By Euler's theorem, sum(C_i) == sigma_p."
        ),
        formula_latex=(
            r"C_i = w_i \frac{\partial \sigma_p}{\partial w_i} "
            r"= \frac{w_i (\Sigma w)_i}{\sigma_p}"
        ),
        formula_plain="C_i = w_i * (Sigma @ w)_i / sigma_p",
        units="% volatility",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            (
                "Sum of all component contributions equals total portfolio volatility: "
                "sum(C_i) == sigma_p."
            ),
            "Negative contributions indicate hedging assets reducing overall portfolio volatility.",
        ],
        limitations=[
            (
                "Reflects marginal incremental changes; does not predict "
                "non-linear rebalancing impacts."
            ),
        ],
    ),
    "EULER_RISK_SHARE": MetricDefinition(
        id="EULER_RISK_SHARE",
        name="Percentage Risk Contribution Share",
        category="Decomposition",
        definition=(
            "Fraction of portfolio risk variance explained by holding i: RC%_i = C_i / sigma_p. "
            "Sum of all shares identically equals 100%."
        ),
        formula_latex=r"\text{RC}\%_i = \frac{w_i (\Sigma w)_i}{\sigma_p^2} \times 100\%",
        formula_plain="RC%_i = (w_i * (Sigma @ w)_i / sigma_p^2) * 100",
        units="%",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Identically sums to 100.0%: sum(RC%_i) == 100.0%.",
            "Negative percentages represent hedging benefits.",
        ],
        limitations=[
            "Shares can exceed 100% when other positions provide negative hedging offsets.",
        ],
    ),
    "MARKET_BETA": MetricDefinition(
        id="MARKET_BETA",
        name="Market Beta (NIFTY 50)",
        category="Systematic Risk",
        definition=(
            "Slope coefficient of ordinary least squares (OLS) regression of asset returns "
            "against the benchmark (NIFTY 50 ^NSEI)."
        ),
        formula_latex=r"\beta = \frac{\text{Cov}(R_i, R_m)}{\text{Var}(R_m)}",
        formula_plain="beta = cov(R_i, R_m) / var(R_m)",
        units="Sensitivity ratio",
        default_window="252 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Benchmark is NIFTY 50 (^NSEI), ingested into the local database.",
            "Asset and benchmark returns aligned strictly on common valid dates.",
        ],
        limitations=[
            "Assumes stable linear co-movement; unreliable below 30 common observations.",
            "Survivorship bias: benchmark constituents change over time.",
        ],
    ),
    "JENSENS_ALPHA": MetricDefinition(
        id="JENSENS_ALPHA",
        name="Jensen's Alpha",
        category="Systematic Risk",
        definition=(
            "Annualized excess return above the Capital Asset Pricing Model (CAPM) "
            "expected return, using a 6.5% risk-free rate assumption."
        ),
        formula_latex=(
            r"\alpha = 252 \cdot \left[ (\bar{R}_i - R_f) - \beta (\bar{R}_m - R_f) \right]"
        ),
        formula_plain=("alpha = 252 * ((mean(R_i) - R_f_daily) - beta * (mean(R_m) - R_f_daily))"),
        units="% annualized",
        default_window="252 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Risk-free rate assumed at 6.5% annualized (RBI 91-day T-bill reference).",
            "Single-factor CAPM linear relation.",
        ],
        limitations=[
            (
                "Diagnostic historical estimate; past alpha is not predictive of "
                "future outperformance."
            ),
        ],
    ),
    "DIVERSIFICATION_RATIO": MetricDefinition(
        id="DIVERSIFICATION_RATIO",
        name="Diversification Ratio (Choueifaty)",
        category="Diversification",
        definition=(
            "Ratio of weighted average individual asset volatilities to total "
            "portfolio volatility. Measures risk reduction achieved through "
            "non-perfect correlations."
        ),
        formula_latex=r"\text{DR} = \frac{\sum_{i=1}^N w_i \sigma_i}{\sigma_p}",
        formula_plain="DR = sum(w_i * sigma_i) / sigma_p",
        units="Ratio (>= 1.0)",
        default_window="250 trading days (~1Y)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Always greater than or equal to 1.0 (Cauchy-Schwarz inequality): DR >= 1.0.",
            "DR = 1.0 if and only if all assets are perfectly positively correlated (rho = 1.0).",
        ],
        limitations=[
            "Assumes asset volatilities are estimated without error.",
        ],
    ),
    "HOLDING_HHI": MetricDefinition(
        id="HOLDING_HHI",
        name="Holding Concentration (Herfindahl-Hirschman Index)",
        category="Concentration",
        definition="Sum of squared capital weights across all holdings: HHI = sum(w_i^2).",
        formula_latex=r"\text{HHI}_{holding} = \sum_{i=1}^N w_i^2",
        formula_plain="HHI = sum(w_i^2)",
        units="decimal (0 to 1)",
        default_window="Current Portfolio Allocation",
        min_observations=1,
        return_type="ratio",
        assumptions=[
            "Weights sum to 1.0: sum(w_i) == 1.0.",
            "Range: [1/N, 1.0]. Equal-weight gives 1/N; single monopoly position gives 1.0.",
        ],
        limitations=[
            "Does not account for correlations between holdings.",
        ],
    ),
    "EFFECTIVE_HOLDINGS": MetricDefinition(
        id="EFFECTIVE_HOLDINGS",
        name="Effective Number of Holdings (N_eff)",
        category="Concentration",
        definition="Inverse of Holding HHI: N_eff = 1 / HHI.",
        formula_latex=r"N_{eff} = \frac{1}{\sum_{i=1}^N w_i^2}",
        formula_plain="N_eff = 1 / sum(w_i^2)",
        units="Effective count",
        default_window="Current Portfolio Allocation",
        min_observations=1,
        return_type="ratio",
        assumptions=[
            "Range: [1.0, N]. Equals N for equal-weighted portfolio.",
        ],
        limitations=[
            "Measures capital concentration only, not risk concentration.",
        ],
    ),
    "SECTOR_HHI": MetricDefinition(
        id="SECTOR_HHI",
        name="Sector Concentration (Sector HHI & S_eff)",
        category="Concentration",
        definition=(
            "Sum of squared aggregate sector weights: HHI_sector = sum(s_j^2). "
            "S_eff = 1 / HHI_sector."
        ),
        formula_latex=(
            r"\text{HHI}_{sector} = \sum_{j=1}^M s_j^2, \quad "
            r"S_{eff} = \frac{1}{\sum_{j=1}^M s_j^2}"
        ),
        formula_plain="HHI_sec = sum(s_j^2), S_eff = 1 / sum(s_j^2)",
        units="Effective sector count",
        default_window="Current Portfolio Allocation",
        min_observations=1,
        return_type="ratio",
        assumptions=[
            "Each security mapped to exactly one primary industry sector from SecurityMaster.",
        ],
        limitations=[
            "Conglomerates and diversified businesses mapped to single sector.",
        ],
    ),
    "MANTEGNA_MST_DISTANCE": MetricDefinition(
        id="MANTEGNA_MST_DISTANCE",
        name="Mantegna MST Metric Distance",
        category="Network",
        definition=(
            "Non-linear distance transform mapping pairwise correlation rho into a valid "
            "Euclidean metric space: d_ij = sqrt(2 * (1 - rho_ij))."
        ),
        formula_latex=r"d_{ij} = \sqrt{2 (1 - \rho_{ij})}",
        formula_plain="d_ij = sqrt(2 * (1 - rho_ij))",
        units="Metric distance [0, 2]",
        default_window="120 trading days",
        min_observations=100,
        return_type="ratio",
        assumptions=[
            "Satisfies metric axioms: d_ii = 0, d_ij >= 0, d_ij = d_ji, and triangle inequality.",
            "Bounded in [0, 2]. rho=1 -> d=0 (identical co-movement); rho=-1 -> d=2 (inverse).",
        ],
        limitations=[
            (
                "Minimum Spanning Tree discards (N-1)(N-2)/2 edges; "
                "tree topology does not prove causation."
            ),
        ],
    ),
    "STRESS_MARKET_SHOCK": MetricDefinition(
        id="STRESS_MARKET_SHOCK",
        name="Stress Test: Broad Market Shock",
        category="Stress Testing",
        definition=(
            "Linear regression beta propagation of a hypothetical percentage shock "
            "in the benchmark index (NIFTY 50)."
        ),
        formula_latex=(
            r"\Delta R_i = \beta_i \cdot \text{Shock}_{market}, \quad "
            r"\Delta R_p = \sum_{i=1}^N w_i \Delta R_i"
        ),
        formula_plain="Delta_R_i = beta_i * Shock_market, Delta_R_p = beta_p * Shock_market",
        units="% return impact",
        default_window="252 trading days (~1Y beta)",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Linear historical market betas hold during the hypothetical shock.",
            "Scenario estimate, not a forecast or investment advice.",
        ],
        limitations=[
            "Non-linear tail correlation breakdown and liquidity evaporation are not captured.",
        ],
    ),
    "STRESS_SECTOR_SHOCK": MetricDefinition(
        id="STRESS_SECTOR_SHOCK",
        name="Stress Test: Parallel Sector Shock",
        category="Stress Testing",
        definition=(
            "Parallel percentage shock applied uniformly to all holdings "
            "within a selected industry."
        ),
        formula_latex=r"\Delta R_i = \text{Shock}_{sector} \cdot \mathbb{I}_{i \in \text{sector}}",
        formula_plain="Delta_R_i = Shock_sector if in_sector else 0.0",
        units="% return impact",
        default_window="Current Portfolio Allocation",
        min_observations=1,
        return_type="simple",
        assumptions=[
            "Holdings within the industry receive identical percentage shock.",
            "Cross-sector spillover effects excluded.",
        ],
        limitations=[
            "Assumes intra-sector beta equals 1.0 for all constituents.",
        ],
    ),
    "STRESS_HOLDING_SHOCK": MetricDefinition(
        id="STRESS_HOLDING_SHOCK",
        name="Stress Test: Selected Holding Idiosyncratic Shock",
        category="Stress Testing",
        definition=(
            "Direct idiosyncratic shock applied to target holding, with transmission to other "
            "holdings estimated via pair regression beta."
        ),
        formula_latex=r"\Delta R_j = \beta_{j, \text{target}} \cdot \text{Shock}_{\text{target}}",
        formula_plain="Delta_R_j = beta_j_target * Shock_target",
        units="% return impact",
        default_window="250 trading days",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Target holding receives exact shock; other holdings move by pairwise regression beta.",
        ],
        limitations=[
            "Liquidity, feedback loops, and simultaneous external shocks are excluded.",
        ],
    ),
    "STRESS_CORRELATION_EXPANSION": MetricDefinition(
        id="STRESS_CORRELATION_EXPANSION",
        name="Stress Test: Systemic Correlation Breakdown",
        category="Stress Testing",
        definition=(
            "Simulates systemic market crisis where pairwise asset correlations shift toward 1.0 "
            "by stress parameter alpha in (0, 1]: C_stressed = (1 - alpha)*C + alpha*J."
        ),
        formula_latex=(
            r"\tilde{\rho}_{ij} = (1 - \alpha) \rho_{ij} + \alpha, \quad "
            r"\tilde{\Sigma} = \text{diag}(\sigma) \tilde{C} \text{diag}(\sigma)"
        ),
        formula_plain=(
            "rho_stressed = (1 - alpha) * rho + alpha; Sigma_stressed = D * C_stressed * D"
        ),
        units="% volatility increase",
        default_window="250 trading days",
        min_observations=30,
        return_type="simple",
        assumptions=[
            "Linear correlation contraction toward unity (alpha = 0.5 default: 50% shift).",
            "Standalone asset volatilities held constant.",
            "Measures the destruction of diversification benefit in liquidity crises.",
        ],
        limitations=[
            "Does not alter marginal return distributions; Gaussian copula approximation.",
        ],
    ),
    "STOCK_RISK_SCORE_HEURISTIC": MetricDefinition(
        id="STOCK_RISK_SCORE_HEURISTIC",
        name="5-Factor Heuristic Stock Risk Score",
        category="Scoring (Heuristic)",
        definition=(
            "Heuristic 0–100 composite synthesizing 5 normalized risk dimensions: "
            "Volatility (30%), Downside (25%), Drawdown (20%), Beta (15%), and Instability (10%)."
        ),
        formula_latex=(
            r"S = 0.30 S_{vol} + 0.25 S_{down} + 0.20 S_{mdd} "
            r"+ 0.15 S_{\beta} + 0.10 S_{instab}"
        ),
        formula_plain=(
            "Score = 0.30*S_vol + 0.25*S_down + 0.20*S_mdd + 0.15*S_beta + 0.10*S_instab"
        ),
        units="Score (0–100)",
        default_window="252 trading days",
        min_observations=180,
        return_type="ratio",
        assumptions=[
            "Normalized to [0, 100] using that date's persisted NIFTY 200 P10/P90 cutoffs.",
            "Labelled HEURISTIC: diagnostic synthesis, not an ML prediction or buy/sell signal.",
        ],
        limitations=[
            "Unavailable when any factor or cross-sectional calibration is unavailable.",
        ],
    ),
    "PORTFOLIO_RISK_SCORE_HEURISTIC": MetricDefinition(
        id="PORTFOLIO_RISK_SCORE_HEURISTIC",
        name="Portfolio Diagnostic Risk Score",
        category="Scoring (Heuristic)",
        definition=(
            "Heuristic 0–100 composite evaluating overall portfolio covariance risk: "
            "Portfolio Volatility (35%), Downside Volatility (25%), Max Drawdown (25%), "
            "and Weighted Beta (15%)."
        ),
        formula_latex=(
            r"S_p = 0.35 S_{\sigma_p} + 0.25 S_{down_p} + 0.25 S_{\text{MDD}_p} "
            r"+ 0.15 S_{\beta_p}"
        ),
        formula_plain="Score = 0.35*S_vol + 0.25*S_down + 0.25*S_mdd + 0.15*S_beta",
        units="Score (0–100)",
        default_window="250 trading days",
        min_observations=30,
        return_type="ratio",
        assumptions=[
            (
                "Evaluates true portfolio covariance (w^T Sigma w), "
                "not simple average of stock scores."
            ),
            "Labelled HEURISTIC until Phase 4 empirical calibration.",
        ],
        limitations=[
            (
                "Fixed prudential bounds [vol: 0.10-0.35, down: 0.06-0.25, "
                "mdd: 0.08-0.38, beta: 50+(beta-1)*55]."
            ),
        ],
    ),
}


# ─── Centralized Scoring Constants ───

STOCK_RISK_FACTOR_WEIGHTS = {
    "annualized_volatility": 0.30,
    "downside_volatility": 0.25,
    "max_drawdown": 0.20,
    "market_beta": 0.15,
    "price_instability": 0.10,
}

STOCK_RISK_CALIBRATION_PERCENTILES = (0.10, 0.90)

PORTFOLIO_RISK_FACTOR_WEIGHTS = {
    "portfolio_volatility": 0.35,
    "downside_volatility": 0.25,
    "max_drawdown": 0.25,
    "portfolio_beta": 0.15,
}

PORTFOLIO_RISK_NORMALIZATION_BOUNDS = {
    "portfolio_volatility": (0.10, 0.35),
    "downside_volatility": (0.06, 0.25),
    "max_drawdown": (0.08, 0.38),
}

RISK_TIERS = [
    {"tier": "Low", "min_score": 0.0, "max_score": 35.0, "color": "#046A38"},
    {"tier": "Moderate", "min_score": 35.0, "max_score": 65.0, "color": "#8A5A00"},
    {"tier": "Elevated", "min_score": 65.0, "max_score": 80.0, "color": "#E34222"},
    {"tier": "High", "min_score": 80.0, "max_score": 100.0, "color": "#B8321A"},
]

# ─── Configurable Alert Threshold Registry ───


@dataclass(frozen=True, slots=True)
class AlertThresholdConfig:
    id: str
    name: str
    default_warning: float
    default_critical: float | None
    min_allowed: float
    max_allowed: float
    unit: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ALERT_THRESHOLD_REGISTRY: dict[str, AlertThresholdConfig] = {
    "risk_score": AlertThresholdConfig(
        id="risk_score",
        name="Portfolio Risk Score",
        default_warning=60.0,
        default_critical=80.0,
        min_allowed=10.0,
        max_allowed=95.0,
        unit="pts (0-100)",
        description="Overall heuristic portfolio risk score.",
    ),
    "sector_ceiling": AlertThresholdConfig(
        id="sector_ceiling",
        name="Top Sector Allocation Ceiling",
        default_warning=25.0,
        default_critical=35.0,
        min_allowed=10.0,
        max_allowed=80.0,
        unit="% capital",
        description="Prudential maximum weight for any single industry sector.",
    ),
    "holding_concentration": AlertThresholdConfig(
        id="holding_concentration",
        name="Single-Stock Capital Concentration",
        default_warning=20.0,
        default_critical=30.0,
        min_allowed=5.0,
        max_allowed=60.0,
        unit="% capital",
        description="Maximum capital allocation to any single holding.",
    ),
    "effective_holdings": AlertThresholdConfig(
        id="effective_holdings",
        name="Effective Number of Holdings Floor",
        default_warning=4.0,
        default_critical=2.0,
        min_allowed=1.5,
        max_allowed=25.0,
        unit="holdings (N_eff)",
        description="Inverse HHI diversification floor. Triggers when N_eff drops below threshold.",
    ),
    "downside_volatility": AlertThresholdConfig(
        id="downside_volatility",
        name="Annualized Downside Volatility Ceiling",
        default_warning=20.0,
        default_critical=28.0,
        min_allowed=5.0,
        max_allowed=50.0,
        unit="% annualized",
        description="Upper tolerance for negative semi-deviation.",
    ),
    "euler_risk_share": AlertThresholdConfig(
        id="euler_risk_share",
        name="Euler Risk Contribution Share Ceiling",
        default_warning=30.0,
        default_critical=45.0,
        min_allowed=10.0,
        max_allowed=80.0,
        unit="% risk share",
        description="Maximum fraction of portfolio risk variance explained by a single asset.",
    ),
    "max_portfolio_beta": AlertThresholdConfig(
        id="max_portfolio_beta",
        name="Portfolio Beta Ceiling",
        default_warning=1.30,
        default_critical=1.60,
        min_allowed=0.5,
        max_allowed=2.5,
        unit="beta (β)",
        description="Systematic sensitivity to the benchmark.",
    ),
    "max_drawdown": AlertThresholdConfig(
        id="max_drawdown",
        name="Historical Drawdown Tolerance",
        default_warning=20.0,
        default_critical=30.0,
        min_allowed=5.0,
        max_allowed=60.0,
        unit="% decline",
        description="Maximum tolerated peak-to-trough historical drawdown.",
    ),
}

THRESHOLD_ALIASES: dict[str, str] = {
    "max_single_stock_weight": "holding_concentration",
    "max_top_sector_weight": "sector_ceiling",
    "max_downside_volatility": "downside_volatility",
}


def get_default_alert_thresholds() -> dict[str, float]:
    """Return dictionary of default warning alert thresholds."""
    defaults = {key: config.default_warning for key, config in ALERT_THRESHOLD_REGISTRY.items()}
    for alias, canonical in THRESHOLD_ALIASES.items():
        if canonical in defaults:
            defaults[alias] = defaults[canonical]
    return defaults


DEFAULT_ALERT_THRESHOLDS: dict[str, float] = get_default_alert_thresholds()


def validate_alert_thresholds(thresholds: dict[str, float]) -> dict[str, float]:
    """Validate and clamp threshold overrides within permitted boundaries."""
    validated: dict[str, float] = {}
    for key, config in ALERT_THRESHOLD_REGISTRY.items():
        candidate_keys = [key] + [a for a, c in THRESHOLD_ALIASES.items() if c == key]
        found_val: float | None = None
        for ck in candidate_keys:
            if ck in thresholds:
                try:
                    found_val = float(thresholds[ck])
                    break
                except (ValueError, TypeError):
                    pass
        if found_val is not None:
            clamped = max(config.min_allowed, min(config.max_allowed, found_val))
            clamped_val = round(clamped, 2)
            validated[key] = clamped_val
            for a, c in THRESHOLD_ALIASES.items():
                if c == key:
                    validated[a] = clamped_val
        else:
            validated[key] = config.default_warning
            for a, c in THRESHOLD_ALIASES.items():
                if c == key:
                    validated[a] = config.default_warning
    return validated


def get_methodology_manifest() -> dict[str, Any]:
    """Serialize the complete methodology registry for API and client synchronization."""
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "annualisation_factor": ANNUALISATION_FACTOR,
        "default_risk_free_rate": DEFAULT_RISK_FREE_RATE,
        "metrics": {k: v.to_dict() for k, v in METRIC_REGISTRY.items()},
        "stock_risk_weights": STOCK_RISK_FACTOR_WEIGHTS,
        "stock_risk_calibration": {
            "method": "daily NIFTY 200 cross-sectional linear percentile normalization",
            "lower_percentile": STOCK_RISK_CALIBRATION_PERCENTILES[0],
            "upper_percentile": STOCK_RISK_CALIBRATION_PERCENTILES[1],
            "persistence_table": "score_calibration",
        },
        "portfolio_risk_weights": PORTFOLIO_RISK_FACTOR_WEIGHTS,
        "portfolio_risk_bounds": {
            k: list(v) for k, v in PORTFOLIO_RISK_NORMALIZATION_BOUNDS.items()
        },
        "risk_tiers": RISK_TIERS,
        "alert_thresholds": {k: v.to_dict() for k, v in ALERT_THRESHOLD_REGISTRY.items()},
        "return_conventions": {
            "risk_metrics": (
                "Daily-rebalanced constant-weight with simple returns R_p,t = sum(w_i * R_i,t)."
            ),
            "ledger_pnl": (
                "Discrete buy-and-hold wealth index based on actual executed "
                "transactions and share quantities."
            ),
            "log_return_approximation_note": (
                "Linear combination of log returns sum(w_i * r_i) understates "
                "simple return by the Jensen's inequality gap: "
                "sum(w_i * ln(1+R_i)) - ln(1 + sum(w_i * R_i)) <= 0."
            ),
        },
    }
