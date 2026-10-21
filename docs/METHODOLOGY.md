# PRISM Quantitative Risk Engine: Authoritative Methodology Reference

**Document Version:** 2026.1  
**Last Updated:** 2026-10-20  
**Phase:** 3 of 7  
**Scope:** Complete mathematical formulations, return conventions, numerical invariants, stress models, heuristic scoring, and reproducible risk envelopes across PRISM.

---

## 1. Mathematical Philosophy & Diagnostic Scope

PRISM is a diagnostic analytical system designed to measure, explain, decompose, and warn. It operates under strict quantitative governance:
- **No Buy/Sell Advice or Recommendations:** PRISM never issues investment recommendations, target prices, or trade signals.
- **No Causal Claims:** Correlation trees (Mantegna MST) and regression betas identify empirical co-movement and topology; they do not establish economic causality.
- **Explicit Labeling:** Heuristic indicators are explicitly labelled `HEURISTIC`. Machine-learning estimates (Phase 4+) are labelled `Model estimate` accompanied by validation metrics.
- **Zero Fabrication:** If market data is incomplete or falls below the minimum required observations ($N < N_{min}$), calculations are flagged as unreliable or rejected with HTTP 503 / qualified status rather than fabricated.

---

## 2. Return Construction Conventions

### 2.1 Daily-Rebalanced Constant-Weight Returns (Risk Metrics)
All portfolio-level statistical risk metrics (Annualized Volatility, Downside Volatility, Value at Risk, Expected Shortfall, Euler Decomposition, Diversification Ratio) are computed under the **daily-rebalanced constant-weight convention** using simple arithmetic returns:

$$R_{p,t} = \sum_{i=1}^N w_i R_{i,t} = \mathbf{w}^T \mathbf{R}_t$$

where:
- $w_i = \frac{V_{i,0}}{\sum_{j=1}^N V_{j,0}}$ is the target portfolio weight of holding $i$ with $\sum_{i=1}^N w_i = 1.0$.
- $R_{i,t} = \frac{P_{i,t} - P_{i,t-1}}{P_{i,t-1}}$ is the simple daily return of asset $i$ on trading day $t$, based on split- and dividend-adjusted closing prices.

#### Mathematical Justification & The Log-Return Linear Sum Approximation Error
In financial literature, log returns $r_t = \ln(1 + R_t)$ are frequently utilized for time-series additivity across consecutive trading sessions: $\sum_{t=1}^T r_t = \ln(W_T / W_0)$. However, across a cross-section of assets, the log return of a portfolio is strictly non-linear:

$$r_{p,t} = \ln\left(1 + \sum_{i=1}^N w_i R_{i,t}\right) = \ln\left(\sum_{i=1}^N w_i (1 + R_{i,t})\right)$$

A naive linear combination of log returns $\tilde{r}_{p,t} = \sum_{i=1}^N w_i r_{i,t} = \sum_{i=1}^N w_i \ln(1 + R_{i,t})$ systematically violates cross-sectional additivity. By **Jensen's inequality**, because the natural logarithm function $f(x) = \ln(x)$ is strictly concave on $\mathbb{R}^+$:

$$\sum_{i=1}^N w_i \ln(1 + R_{i,t}) \le \ln\left(\sum_{i=1}^N w_i (1 + R_{i,t})\right)$$

$$\tilde{r}_{p,t} - r_{p,t} \le 0$$

The difference is strictly negative whenever asset returns are non-identical:

$$\Delta_{Jensen} = \sum_{i=1}^N w_i \ln(1 + R_{i,t}) - \ln\left(1 + \sum_{i=1}^N w_i R_{i,t}\right) < 0$$

Under volatile market conditions, approximating portfolio returns via naive log sums introduces a systematic downward bias that compounds over time. PRISM enforces exact linear combinations of simple returns $R_{p,t} = \sum w_i R_{i,t}$ for all cross-sectional risk metrics.

---

### 2.2 Buy-and-Hold Wealth Series (Ledger P&L and Drawdown)
For actual historical equity curves, ledger profit-and-loss accounting, and portfolio drawdown calculations, PRISM employs the discrete **buy-and-hold wealth index** derived from actual share quantities and cash balances:

$$W_t = \text{Cash}_t + \sum_{i=1}^N Q_{i,t} \cdot P_{i,t}$$

where:
- $Q_{i,t}$ is the exact un-rebalanced integer quantity of shares of asset $i$ held on date $t$, derived from the immutable ledger replay.
- $P_{i,t}$ is the unadjusted or split-adjusted mark-to-market closing price on date $t$.
- $\text{Cash}_t$ is the residual cash balance after accounting for purchases, sales, transaction fees, and dividend receipts.

---

## 3. Covariance Matrix Construction & Spectral Regularization

### 3.1 Sample Covariance Matrix
Let $\mathbf{R} \in \mathbb{R}^{T \times N}$ denote the matrix of demeaned daily simple returns over $T$ common aligned trading days across $N$ holdings. The sample covariance matrix $\mathbf{\Sigma} \in \mathbb{R}^{N \times N}$ is:

$$\mathbf{\Sigma} = \frac{1}{T - 1} \mathbf{R}^T \mathbf{R}$$

The annualized covariance matrix is $\mathbf{\Sigma}_{ann} = 252 \cdot \mathbf{\Sigma}$.

---

### 3.2 Singular Matrices & Spectral Regularization
When the number of assets exceeds or approaches the number of observations ($N > T$), or when two or more assets are perfectly collinear (e.g., dual-listed shares, identical ETF wrappers), $\mathbf{\Sigma}$ becomes rank-deficient ($\det(\mathbf{\Sigma}) = 0$) or exhibits negative eigenvalues due to floating-point truncation.

PRISM applies **spectral eigenvalue floor regularization**:
1. Compute the eigendecomposition of the symmetric matrix $\mathbf{\Sigma}$:
   $$\mathbf{\Sigma} = \mathbf{V} \mathbf{\Lambda} \mathbf{V}^T$$
   where $\mathbf{V}$ is the orthogonal matrix of eigenvectors and $\mathbf{\Lambda} = \text{diag}(\lambda_1, \lambda_2, \dots, \lambda_N)$ are the real eigenvalues.
2. Determine the maximum eigenvalue $\lambda_{max} = \max_i(\lambda_i)$. If $\lambda_{max} \le 0$ (e.g., all flat prices with zero variance), $\mathbf{\Sigma}$ is preserved as an exact zero matrix $\mathbf{0}_{N \times N}$.
3. For non-zero matrices, regularize each eigenvalue against a relative spectral floor $\epsilon = 10^{-6}$:
   $$\lambda_i^{reg} = \max(\lambda_i, \epsilon \cdot \lambda_{max})$$
4. Reconstruct the regularized covariance matrix:
   $$\mathbf{\Sigma}_{reg} = \mathbf{V} \mathbf{\Lambda}_{reg} \mathbf{V}^T$$
5. Enforce strict numerical symmetry:
   $$\mathbf{\Sigma}_{final} = \frac{\mathbf{\Sigma}_{reg} + \mathbf{\Sigma}_{reg}^T}{2}$$

This guarantees that $\mathbf{\Sigma}_{final}$ is strictly positive definite ($\mathbf{x}^T \mathbf{\Sigma}_{final} \mathbf{x} > 0 \quad \forall \mathbf{x} \neq \mathbf{0}$), eliminating inversion failures and numerical instabilities in risk decomposition.

---

## 4. Euler Volatility Decomposition & Hedge Preservation

### 4.1 Euler's Homogeneous Function Theorem
Portfolio annualized volatility is given by:

$$\sigma_p(\mathbf{w}) = \sqrt{252} \cdot \sqrt{\mathbf{w}^T \mathbf{\Sigma} \mathbf{w}}$$

Because $\sigma_p(c \mathbf{w}) = c \cdot \sigma_p(\mathbf{w})$ for any scalar $c > 0$, $\sigma_p$ is a positively homogeneous function of degree 1. By **Euler's Homogeneous Function Theorem**:

$$\sigma_p(\mathbf{w}) = \sum_{i=1}^N w_i \frac{\partial \sigma_p}{\partial w_i}$$

---

### 4.2 Marginal Risk Contribution (Euler)
The partial derivative of portfolio volatility with respect to the weight of asset $i$ is:

$$\frac{\partial \sigma_p}{\partial w_i} = \frac{252 \cdot (\mathbf{\Sigma} \mathbf{w})_i}{\sigma_p} = \frac{\text{Cov}(R_i, R_p)}{\sigma_p}$$

This represents the marginal volatility added to the portfolio per unit increase in asset $i$'s allocation.

---

### 4.3 Component Risk Contribution & Reconciliation Invariant
The absolute component volatility contributed by holding $i$ is defined as:

$$C_i = w_i \cdot \frac{\partial \sigma_p}{\partial w_i} = \frac{252 \cdot w_i (\mathbf{\Sigma} \mathbf{w})_i}{\sigma_p}$$

#### Mathematical Invariants:
1. **Exact Volatility Reconciliation:**
   $$\sum_{i=1}^N C_i = \sigma_p \pm 10^{-6}$$
   The sum of all component volatilities matches total portfolio volatility within machine precision.
2. **Risk Contribution Share:**
   $$RC\%_i = \frac{C_i}{\sigma_p} \times 100\% \implies \sum_{i=1}^N RC\%_i = 100.0\%$$
3. **Legitimate Negative Contributions (Hedges):**
   If an asset is negatively correlated with the aggregate portfolio such that $(\mathbf{\Sigma} \mathbf{w})_i < 0$, its component contribution is strictly negative:
   $$C_i < 0 \quad \text{and} \quad RC\%_i < 0$$
   PRISM preserves legitimate negative contributions and labels the asset as an active `HEDGE` in the UI. Negative contributions are never artificially zeroed or clamped.

---

## 5. Volatility, Downside Risk & Maximum Drawdown

### 5.1 Annualized Volatility
Sample standard deviation of daily portfolio simple returns, scaled to an annualized figure using $A = 252$ trading sessions:

$$\sigma_{ann} = \sqrt{252} \cdot \sqrt{\frac{1}{T - 1} \sum_{t=1}^T (R_{p,t} - \bar{R}_p)^2}$$

---

### 5.2 Downside Semi-Volatility
Measures only unfavorable return fluctuations below a Minimum Acceptable Return (MAR) of zero:

$$\sigma_{down} = \sqrt{252} \cdot \sqrt{\frac{1}{T} \sum_{t=1}^T \left(\min(R_{p,t}, 0)\right)^2}$$

*Limitations:* Downside semi-deviation is estimated over a smaller effective sample (only sessions where $R_{p,t} < 0$).

---

### 5.3 Maximum Drawdown (MDD)
The peak-to-trough maximum observed decline across the cumulative wealth trajectory within the estimation lookback window:

$$\text{Peak}_t = \max_{s \le t} W_s$$

$$\text{Drawdown}_t = \frac{W_t - \text{Peak}_t}{\text{Peak}_t} \in [-1.0, 0.0]$$

$$\text{MDD} = \min_{t \in [0, T]} \text{Drawdown}_t$$

*Invariants:* $\text{MDD} \in [-1.0, 0.0]$ (reported as $0\%$ to $-100\%$). It is computed on the actual discrete wealth path $W_t$.

---

## 6. Systematic Risk: Beta & Jensen's Alpha

### 6.1 Market Beta ($\beta$)
Ordinary Least Squares (OLS) regression slope of asset or portfolio returns against the benchmark index (NIFTY 50 / `^NSEI`):

$$\beta = \frac{\text{Cov}(R_p, R_m)}{\text{Var}(R_m)}$$

- **Minimum Sample Rule:** Evaluated over $T \ge 30$ common aligned trading sessions. If $T < 30$, beta is marked unreliable (`status="unreliable"`).
- **Portfolio Beta Invariant:** $\beta_p = \sum_{i=1}^N w_i \beta_i$.

---

### 6.2 Jensen's Alpha ($\alpha$)
Annualized risk-adjusted excess return over the single-factor Capital Asset Pricing Model (CAPM):

$$\alpha = 252 \cdot \left[ (\bar{R}_p - R_f^{daily}) - \beta_p (\bar{R}_m - R_f^{daily}) \right]$$

- **Risk-Free Rate Assumption:** $R_f = 6.50\%$ annualized ($R_f^{daily} = \frac{0.065}{252} \approx 0.0002579$), representing the sovereign benchmark reference (Reserve Bank of India 91-day Treasury Bill rate).
- **Limitations:** Alpha is a backward-looking diagnostic estimate of historical excess return; it carries no predictive power for future performance.

---

## 7. Tail Risk: Value at Risk (VaR) & Expected Shortfall (CVaR)

### 7.1 Historical Value at Risk (VaR)
Historical 1-day VaR at confidence level $\alpha \in \{0.95, 0.99\}$ represents the empirical quantile of the portfolio daily return distribution:

$$\text{VaR}_\alpha = - Q_{1 - \alpha}(R_p)$$

where $Q_p$ denotes the $p$-th empirical quantile of the sample $\{R_{p,1}, R_{p,2}, \dots, R_{p,T}\}$.
- $\text{VaR}_{0.95} = - Q_{0.05}(R_p)$
- $\text{VaR}_{0.99} = - Q_{0.01}(R_p)$

---

### 7.2 Historical Expected Shortfall / Conditional VaR (CVaR)
Expected Shortfall measures the expected loss conditional on the portfolio return breaching the VaR threshold:

$$\text{ES}_\alpha = - \mathbb{E}\left[ R_p \;\middle|\; R_p \le -\text{VaR}_\alpha \right] = - \frac{1}{K_\alpha} \sum_{t: R_{p,t} \le -\text{VaR}_\alpha} R_{p,t}$$

where $K_\alpha = \sum_{t=1}^T \mathbb{I}_{R_{p,t} \le -\text{VaR}_\alpha}$.

#### Theoretical Properties & Invariants:
1. **Coherence:** Unlike VaR, Expected Shortfall is a coherent risk measure satisfying subadditivity: $\text{ES}(X + Y) \le \text{ES}(X) + \text{ES}(Y)$ (Artzner et al. 1999).
2. **Monotonicity with Confidence:**
   $$\text{VaR}_{0.99} \ge \text{VaR}_{0.95} \quad \text{and} \quad \text{ES}_{0.99} \ge \text{ES}_{0.95}$$
3. **Tail Exceedance:**
   $$\text{ES}_\alpha \ge \text{VaR}_\alpha \quad \forall \alpha \in (0, 1)$$
4. **Sample Size Requirements:** Historical 95% VaR requires $N \ge 30$ sessions; 99% VaR/ES requires $N \ge 100$ sessions (in 250 sessions, the 1% tail contains only 2–3 observations).
5. **Regulatory Labeling:** Historical VaR and ES are explicitly labelled **"Historical estimates, not guaranteed loss bounds"**.

---

### 7.3 Parametric Gaussian VaR
For direct diagnostic comparison against historical fat-tailed quantiles, PRISM provides parametric VaR assuming normally distributed returns:

$$\text{VaR}_\alpha^{param} = - \left( \mu_p - z_\alpha \cdot \sigma_p^{daily} \right)$$

where:
- $\mu_p = \frac{1}{T} \sum_{t=1}^T R_{p,t}$
- $\sigma_p^{daily} = \sqrt{\frac{1}{T - 1} \sum_{t=1}^T (R_{p,t} - \mu_p)^2}$
- $z_{0.95} = 1.644853$ and $z_{0.99} = 2.326348$.

*Diagnostic Utility:* Comparing $\text{VaR}_{0.95}^{hist}$ to $\text{VaR}_{0.95}^{param}$ reveals excess kurtosis and tail heaviness in the portfolio return distribution.

---

### 7.4 Exception-Count Backtesting
Whenever historical sample length supports it ($T \ge 250$ trading days), PRISM tracks the empirical breach count:

$$K = \sum_{t=1}^T \mathbb{I}_{R_{p,t} < -\text{VaR}_{0.95}}$$

Under the null hypothesis of accurate quantile estimation, $K \sim \text{Binomial}(T, 0.05)$, with expected breaches $\mathbb{E}[K] = 0.05 \cdot T$.

---

## 8. Stress Testing Framework

Stress tests evaluate portfolio vulnerability under hypothetical structural disruptions. **Stress tests are scenario estimates, never forecasts or predictive claims.**

### 8.1 Broad Market Shock
Propagates a hypothetical percentage shock $\Delta M$ in the NIFTY 50 benchmark through historical asset betas:

$$\Delta R_i = \beta_i \cdot \Delta M$$

$$\Delta R_p = \sum_{i=1}^N w_i \Delta R_i = \beta_p \cdot \Delta M$$

$$\Delta \text{Wealth} = W_0 \cdot \Delta R_p$$

*Pre-configured Scenarios:* $\Delta M \in \{-5\%, -10\%, -15\%, -20\%\}$.

---

### 8.2 Parallel Sector Shock
Applies a percentage shock $\Delta S$ uniformly to all holdings within a selected industry sector $\mathcal{S}$:

$$\Delta R_i = \begin{cases} \Delta S & \text{if } \text{Sector}(i) = \mathcal{S} \\ 0.0 & \text{otherwise} \end{cases}$$

$$\Delta R_p = \sum_{i \in \mathcal{S}} w_i \Delta S = w_{\mathcal{S}} \cdot \Delta S$$

---

### 8.3 Idiosyncratic Single-Holding Shock
Applies a direct shock $\Delta H_k$ to target holding $k$, with transmission to other holdings modeled via pairwise regression beta $\beta_{j,k} = \frac{\text{Cov}(R_j, R_k)}{\text{Var}(R_k)}$:

$$\Delta R_j = \begin{cases} \Delta H_k & \text{if } j = k \\ \beta_{j,k} \cdot \Delta H_k & \text{if } j \neq k \end{cases}$$

$$\Delta R_p = \sum_{j=1}^N w_j \Delta R_j$$

---

### 8.4 Systemic Correlation Breakdown Scenario
During severe liquidity crises, diversification often evaporates as cross-asset correlations shift uniformly toward unity. PRISM models systemic correlation breakdown via a convex combination of the empirical correlation matrix $\mathbf{C}$ and the unit rank-1 matrix $\mathbf{J} = \mathbf{1}_{N \times N}$:

$$\tilde{\mathbf{C}} = (1 - \alpha) \mathbf{C} + \alpha \mathbf{J}$$

where $\alpha \in [0, 1]$ represents the stress intensity ($\alpha = 0.50$ by default, representing a 50% shift toward uniform co-movement).

1. Diagonal elements are preserved identically at unity: $\tilde{C}_{ii} = (1 - \alpha) \cdot 1 + \alpha \cdot 1 = 1.0$.
2. Off-diagonal correlations contract toward 1: $\tilde{\rho}_{ij} = (1 - \alpha) \rho_{ij} + \alpha$.
3. Stressed annualized covariance is reconstructed using original standalone asset standard deviations $\mathbf{D} = \text{diag}(\sigma_1, \sigma_2, \dots, \sigma_N)$:
   $$\tilde{\mathbf{\Sigma}} = \mathbf{D} \tilde{\mathbf{C}} \mathbf{D}$$
4. Stressed portfolio volatility is computed as:
   $$\tilde{\sigma}_p = \sqrt{252} \cdot \sqrt{\mathbf{w}^T \tilde{\mathbf{\Sigma}} \mathbf{w}}$$
5. Stressed Volatility Expansion:
   $$\Delta \sigma_p = \tilde{\sigma}_p - \sigma_p$$

This quantifies the exact loss of diversification benefit when cross-asset correlations break down.

---

## 9. Centralized Risk Scoring (Heuristic)

All scoring constants, weights, bounds, and risk tiers are centralized in `backend/app/portfolio_analytics/methodology_registry.py` and mirrored in `frontend/src/methodologyRegistry.ts`.

### 9.1 Stock-Level Risk Score (5-Factor Composite)
A 0–100 heuristic composite evaluating 5 normalized risk dimensions:

$$S_{stock} = 0.30 S_{vol} + 0.25 S_{down} + 0.20 S_{mdd} + 0.15 S_{\beta} + 0.10 S_{instab}$$

#### Normalization Bounds & Factor Weights:

| Factor | Weight | Lower Bound (Score = 0) | Upper Bound (Score = 100) | Formula / Mapping |
| :--- | :---: | :---: | :---: | :--- |
| **Annualized Volatility** | $0.30$ | $15.0\%$ | $50.0\%$ | Clamped linear interpolation |
| **Downside Semi-Volatility** | $0.25$ | $10.0\%$ | $35.0\%$ | Clamped linear interpolation |
| **Maximum Drawdown** | $0.20$ | $10.0\%$ | $50.0\%$ | Clamped linear interpolation on $\|\text{MDD}\|$ |
| **Market Beta** | $0.15$ | $\beta \le 1.0 \implies 50$ | $\beta \ge 2.0 \implies 100$ | $50 + (\beta - 1.0) \times 50$, clamped in $[0, 100]$ |
| **Return Instability** | $0.10$ | $0.05$ | $0.25$ | Std of 20-day rolling vol, clamped in $[0, 100]$ |

*Missing Factor Rule:* If market beta or instability cannot be computed ($N < 30$ sessions), the factor defaults to neutral ($50.0$).

---

### 9.2 Portfolio-Level Diagnostic Risk Score
A 0–100 heuristic composite evaluating true portfolio covariance risk:

$$S_{portfolio} = 0.35 S_{\sigma_p} + 0.25 S_{down_p} + 0.25 S_{\text{MDD}_p} + 0.15 S_{\beta_p}$$

#### Normalization Bounds:
- **Portfolio Volatility ($35\%$):** Normalization range $[10.0\%, 35.0\%]$.
- **Downside Volatility ($25\%$):** Normalization range $[6.0\%, 25.0\%]$.
- **Maximum Drawdown ($25\%$):** Normalization range $[8.0\%, 38.0\%]$.
- **Portfolio Beta ($15\%$):** $S_{\beta} = 50 + (\beta_p - 1.0) \times 55$, clamped in $[0, 100]$.

#### Diagnostic Risk Tiers:
- **Low Risk:** $S < 30.0$
- **Moderate Risk:** $30.0 \le S \le 60.0$
- **High Risk:** $S > 60.0$

*Rule:* Labelled **HEURISTIC** until empirical calibration in Phase 4.

---

## 10. Network & Correlation Minimum Spanning Tree (MST)

### 10.1 Mantegna Metric Distance Transform
Pairwise Pearson correlation coefficients $\rho_{ij} \in [-1, 1]$ do not satisfy the mathematical axioms of a distance metric (specifically, $\rho_{ii} = 1 \neq 0$ and the triangle inequality fails).

PRISM applies the **Mantegna distance transform** (Mantegna 1999) to map correlations into a valid Euclidean metric space:

$$d_{ij} = \sqrt{2 (1 - \rho_{ij})}$$

#### Metric Axioms Satisfied:
1. Non-negativity: $d_{ij} \ge 0$.
2. Identity of indiscernibles: $d_{ij} = 0 \iff \rho_{ij} = 1$.
3. Symmetry: $d_{ij} = d_{ji}$ (since $\rho_{ij} = \rho_{ji}$).
4. Triangle inequality: $d_{ik} \le d_{ij} + d_{jk} \quad \forall i, j, k$.
5. Bounded Range: $d_{ij} \in [0, 2]$:
   - $\rho_{ij} = 1.0 \implies d_{ij} = 0.0$ (identical co-movement).
   - $\rho_{ij} = 0.0 \implies d_{ij} = \sqrt{2} \approx 1.4142$ (orthogonal/uncorrelated).
   - $\rho_{ij} = -1.0 \implies d_{ij} = 2.0$ (perfect inverse co-movement).

---

### 10.2 Kruskal Minimum Spanning Tree & Edge Discard Invariant
On a portfolio of $N$ holdings, the complete correlation graph contains $\frac{N(N - 1)}{2}$ edges. The MST extracted via Kruskal's algorithm retains exactly $N - 1$ edges connecting all vertices without cycles, minimizing total tree distance:

$$\text{Edges Retained} = N - 1$$

$$\text{Edges Discarded} = \frac{N(N - 1)}{2} - (N - 1) = \frac{(N - 1)(N - 2)}{2}$$

#### Critical Interpretive Limits:
- **Edge Discarding:** For a 20-stock portfolio, 171 out of 190 pairwise correlations ($90.0\%$) are discarded. The absence of an edge between two stocks does not imply zero correlation.
- **No Causality:** The tree represents hierarchical clustering of co-movement; it does not demonstrate causal influence or lead-lag transmission.
- **Disconnected Components:** If an asset lacks valid historical returns or zero overlap with peers, it is isolated from the spanning tree and flagged in the UI.

---

## 11. Configurable Alert Thresholds & Structural Monitoring

Hardcoded alert limits have been replaced with user-configurable thresholds persisted per portfolio with strict numerical validation:

| Threshold ID | Canonical Name | Default Warning | Default Critical | Min Allowed | Max Allowed | Units |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `risk_score` | Overall Risk Score Ceiling | $60.0$ | $80.0$ | $10.0$ | $95.0$ | pts ($0$–$100$) |
| `sector_ceiling` | Sector Weight Ceiling | $25.0\%$ | $35.0\%$ | $10.0\%$ | $80.0\%$ | $\%$ capital |
| `holding_concentration` | Single-Stock Allocation Ceiling | $20.0\%$ | $30.0\%$ | $5.0\%$ | $60.0\%$ | $\%$ capital |
| `effective_holdings` | Effective Holdings Floor ($N_{eff}$) | $4.0$ | $2.0$ | $1.5$ | $25.0$ | count |
| `downside_volatility` | Downside Volatility Ceiling | $20.0\%$ | $28.0\%$ | $5.0\%$ | $50.0\%$ | $\%$ annualized |
| `euler_risk_share` | Euler Risk Contribution Ceiling | $30.0\%$ | $45.0\%$ | $10.0\%$ | $80.0\%$ | $\%$ risk share |

Each alert in the UI explicitly displays:
1. **Trigger Value:** Observed portfolio value.
2. **Threshold Value:** Configured trigger boundary.
3. **Contributing Holdings:** Specific assets responsible for the alert condition.
4. **Assumptions & Model Notes:** Mathematical context and limitations.

---

## 12. Reproducible Risk Snapshots

Risk snapshots are immutable historical records capturing the exact analytical state of a portfolio. Every snapshot payload encapsulates the complete calculation envelope:

```json
{
  "portfolio_id": "018f3a5e-234b-7c89-a1b2-c3d4e5f6a7b8",
  "data_cutoff": "2026-09-30",
  "window": "250 trading days",
  "coverage": "100.0% (4/4 holdings qualified)",
  "metrics": {
    "annualized_volatility": 18.42,
    "downside_volatility": 12.15,
    "max_drawdown": -14.30,
    "historical_var_95": 1.78,
    "historical_es_95": 2.45,
    "portfolio_beta": 1.08,
    "portfolio_risk_score": 48.5
  },
  "methodology_version": "2026.1",
  "assumptions": [
    "Simple daily returns R_p,t = sum(w_i * R_i,t)",
    "Annualisation factor: 252 trading sessions",
    "Risk-free rate: 6.50% annualized (RBI 91-day T-bill)",
    "Benchmark: NIFTY 50 (^NSEI)",
    "Euler decomposition: linear degree-1 homogeneity",
    "Covariance regularization: eigenvalue spectral floor 1e-6"
  ]
}
```

Snapshots are stored immutably in PostgreSQL (`PortfolioSnapshot` table) with Row-Level Security, feeding the existing Portfolio Snapshot section without competing flat-file or history stores.

---

## 13. Walk-Forward Chronological Validation Audit

To ensure statistical integrity prior to Phase 4 machine learning models, all existing validation harnesses have been audited against the following methodological criteria:
1. **Look-Ahead Bias Prevention:** Training windows use strict date inequalities ($t_{train} < t_{test}$). Parameters (such as means, covariance, normalization bounds) are computed strictly on past data and applied out-of-sample.
2. **Window Overlap:** Rolling windows are evaluated with non-overlapping out-of-sample evaluation segments to prevent artificial autocorrelation in forecast errors.
3. **Survivorship Bias:** Acknowledged limitation. The current dataset covers constituents of the NIFTY 200 as of September 2026. Prior delistings are not in the database.
4. **Transaction Costs:** Walk-forward strategy evaluations account for execution friction (10 bps brokerage + STT).

---

## 14. Machine Learning Risk Models & Walk-Forward Validation (Phase 4)

Phase 4 integrates machine learning models strictly constrained to estimating and classifying **financial risk** (volatility, regime dynamics, and statistical anomalies). PRISM strictly prohibits price or return-direction prediction, alpha forecasting, or automated trading signals.

### 14.1 Institutional Risk Governance & Baseline Supremacy

Every ML model deployed in PRISM operates under four non-negotiable principles:
1. **Diagnostic Risk Scope Only:** Models forecast volatility distributions, regime probabilities, and multivariate outliers. Zero outputs represent expected returns or trading recommendations.
2. **Mandatory Baseline Comparison:** Every model is benchmarked against established econometric baselines (e.g., RiskMetrics EWMA $\lambda = 0.94$, trailing rolling volatility, HAR-RV, Robust Z-Scores).
3. **Baseline Fallback Rule:** If an ML model fails to beat its simplest baseline by at least $2.0\%$ under out-of-sample walk-forward evaluation, the system automatically designates the baseline as primary and explicitly reports this in the user interface.
4. **Transparent Governance Labels:** Every output is badged `"Model estimate"` and exposes its training data cutoff, walk-forward evaluation window, out-of-sample loss metrics, and sample coverage.

---

### 14.2 Point-in-Time Feature Construction & Purged Walk-Forward Splits

To eliminate look-ahead bias and target leakage, all ML features are computed strictly from historical information available at observation time $t$:

$$\mathcal{F}_t = \sigma\left(\{P_\tau, V_\tau, M_\tau\}_{0 \le \tau \le t}\right)$$

#### Purged and Embargoed Expanding-Window Walk-Forward Splits
When training models on multi-day forward targets (e.g., $H = 21$ trading days), overlapping forward target windows between training and testing sets cause severe information leakage. PRISM enforces:
1. **Purged Training Horizon:** Observations within $t_{train, max} - H$ are purged from the training set so that no training target window extends into the out-of-sample test window.
2. **Embargo Gap:** An embargo period of $E = 21$ trading days separates the end of the training set from the beginning of the test set:
   $$t_{test, min} \ge t_{train, max} + H + E$$
3. **Leakage Verification Invariant:** Automated tests assert that for every observation $i$ and feature $k$:
   $$f_k(t) = f_k(t \mid \text{history up to } t)$$
   and that target shuffling completely collapses predictive skill ($R^2 \approx 0$).

---

### 14.3 Model A: 21-Day Forward Realized Volatility Forecasting

#### 14.3.1 Target Definition
The target variable is the annualized 21-trading-day forward realized volatility:

$$\sigma_{realized, t \to t+21} = \sqrt{\frac{252}{21} \sum_{k=1}^{21} \left(R_{t+k} - \bar{R}\right)^2}$$

#### 14.3.2 Point-in-Time Feature Vector $\mathbf{x}_t \in \mathbb{R}^{10}$
1. `vol_1d`: Absolute daily return scaled to annual volatility: $|R_t| \cdot \sqrt{252}$.
2. `vol_5d`: 5-day rolling annualized standard deviation.
3. `vol_21d`: 21-day rolling annualized standard deviation.
4. `vol_63d`: 63-day rolling annualized standard deviation.
5. `vol_ewma_94`: RiskMetrics exponential moving average volatility ($\lambda = 0.94$):
   $$\sigma_{ewma, t}^2 = 0.94 \cdot \sigma_{ewma, t-1}^2 + 0.06 \cdot R_t^2$$
6. `return_skew_21d`: 21-day sample return skewness.
7. `return_kurt_21d`: 21-day sample return excess kurtosis.
8. `downside_ratio`: Ratio of downside semi-deviation to total standard deviation.
9. `volume_spike_20d`: Ratio of 5-day average volume to 20-day average volume.
10. `benchmark_vol_21d`: 21-day rolling volatility of the NIFTY 50 index (`^NSEI`).

#### 14.3.3 Benchmark Baselines
- **Trailing 21-Day Volatility:** $\hat{\sigma}_{t+21} = \sigma_{21d, t}$.
- **RiskMetrics EWMA ($\lambda = 0.94$):** $\hat{\sigma}_{t+21} = \sigma_{ewma, t} \cdot \sqrt{252}$.
- **Heterogeneous Autoregressive (HAR-RV Linear Regression):**
  $$\hat{\sigma}_{t+21} = \beta_0 + \beta_d \sigma_{1d, t} + \beta_w \sigma_{5d, t} + \beta_m \sigma_{21d, t}$$

#### 14.3.4 Machine Learning Architecture
- **Model:** `HistGradientBoostingRegressor` (Histogram-based gradient boosted decision trees).
- **Point Forecast:** Trained with `squared_error` loss.
- **Quantile Prediction Intervals (90% Confidence):** Quantile gradient boosting fitted at $\alpha = 0.05$ (lower bound) and $\alpha = 0.95$ (upper bound).

#### 14.3.5 Evaluation Metrics
- **QLIKE Loss (Quasi-Likelihood):** The standard robust, scale-invariant loss function for volatility forecasts (Patton, 2011):
  $$\text{QLIKE} = \frac{1}{T} \sum_{t=1}^T \left( \frac{\sigma_{actual, t}^2}{\hat{\sigma}_t^2} - \ln\left(\frac{\sigma_{actual, t}^2}{\hat{\sigma}_t^2}\right) - 1 \right)$$
- **Mean Absolute Error of Log Volatility:**
  $$\text{MAE}_{\ln} = \frac{1}{T} \sum_{t=1}^T |\ln(\hat{\sigma}_t) - \ln(\sigma_{actual, t})|$$
- **Mincer-Zarnowitz Regression ($R^2$, $\alpha$, $\beta$):**
  $$\sigma_{actual, t}^2 = \alpha + \beta \hat{\sigma}_t^2 + \epsilon_t$$
  An unbiased, efficient forecast satisfies $\alpha = 0$, $\beta = 1$, and maximizes $R^2$.
- **90% Interval Coverage:** Empirical percentage of realized volatilities falling within $[\hat{\sigma}_{0.05}, \hat{\sigma}_{0.95}]$.

---

### 14.4 Model B: Market Regime Detection via Hamilton Markov Switching

#### 14.4.1 Formulation
To identify macroeconomic risk environments on the benchmark index (NIFTY 50), PRISM employs a 2-state first-order Markov-switching Gaussian regression model (Hamilton, 1989):

$$R_{m, t} = \mu_{S_t} + \epsilon_t, \quad \epsilon_t \sim \mathcal{N}\left(0, \sigma_{S_t}^2\right)$$

where $S_t \in \{0, 1\}$ represents the latent market state:
- **State 0 (Calm / Normal):** Higher mean return $\mu_0$, lower annualized volatility $\sigma_0$.
- **State 1 (Stressed / Elevated Risk):** Lower mean return $\mu_1$, higher annualized volatility $\sigma_1$.

The latent state transitions according to a stationary transition probability matrix $\mathbf{P} \in \mathbb{R}^{2 \times 2}$:

$$\mathbf{P} = \begin{bmatrix} p_{00} & p_{01} \\ p_{10} & p_{11} \end{bmatrix}, \quad p_{ij} = \mathbb{P}\left(S_t = j \mid S_{t-1} = i\right), \quad \sum_{j} p_{ij} = 1.0$$

#### 14.4.2 Strict Use of Filtered Probabilities (No Look-Ahead Leakage)
Financial state estimation frequently suffers from data leakage when practitioners utilize **smoothed probabilities** $\mathbb{P}(S_t \mid R_{1 \dots T})$, which condition past state estimates on future returns up to time $T$.

PRISM strictly mandates **filtered probabilities**:

$$\xi_{t \mid t} = \mathbb{P}\left(S_t = s \mid R_{1 \dots t}\right)$$

Filtered probabilities condition solely on information known on or before day $t$. Smoothed probabilities are strictly rejected.

#### 14.4.3 Regime-Conditional Statistics
For each identified regime, PRISM computes:
- Regime-conditional annualized index volatility $\sigma_{m \mid S}$.
- Average pairwise correlation across active NIFTY holdings during sessions assigned to that regime:
  $$\bar{\rho}_{\mid S} = \frac{2}{N(N-1)} \sum_{i < j} \text{Corr}\left(R_{i, \tau}, R_{j, \tau} \mid S_\tau = s\right)$$
- State stability and expected regime duration:
  $$E[D_s] = \frac{1}{1 - p_{ss}}$$

---

### 14.5 Model C: Unsupervised Statistical Anomaly Detection

#### 14.5.1 Diagnostic Purpose
Anomaly detection surfaces holdings exhibiting statistically unusual market behaviour (sudden volatility explosion, extreme return moves relative to volatility, abnormal volume spikes, or breakdown in sectoral co-movement). It is unsupervised: PRISM explicitly claims **no predictive accuracy** and does not issue trading signals.

#### 14.5.2 Feature Vector $\mathbf{z}_i \in \mathbb{R}^4$
For each portfolio holding $i$:
1. `return_zscore_60d`: Normalized daily return relative to trailing 60-day mean and volatility:
   $$z_{R, i} = \frac{R_{i, t} - \mu_{60d, i}}{\sigma_{60d, i}}$$
2. `volume_spike_20d`: Ratio of latest volume to 20-day moving average volume.
3. `vol_ratio_5_20`: Ratio of short-term 5-day volatility to medium-term 20-day volatility ($\frac{\sigma_{5d}}{\sigma_{20d}}$).
4. `benchmark_divergence`: Absolute difference between holding return and sector median return:
   $$|R_{i, t} - R_{\text{sector}, t}|$$

#### 14.5.3 Algorithms
- **Baseline:** Robust Z-Score computed via Median Absolute Deviation (MAD):
  $$\text{Score}_{robust} = \max_k \left( \frac{|z_{i, k} - \text{median}(z_k)|}{1.4826 \cdot \text{MAD}(z_k)} \right)$$
- **Machine Learning:** `IsolationForest` (ensemble of randomized isolation trees, 100 estimators, contamination $= 0.10$). Anomalies are isolated near tree roots, yielding an anomaly score $s \in [0, 1]$.

#### 14.5.4 Diagnostics & Governance
- **Feature Attribution:** Each flagged asset reports the percentage contribution of each feature to its anomaly score.
- **Flag Rate:** Percentage of holdings flagged as unusual (target: $5.0\% - 15.0\%$).
- **Window Stability (Jaccard Index):** Stability of flagged holdings across consecutive rolling windows:
  $$J(W_t, W_{t-1}) = \frac{|A_t \cap A_{t-1}|}{|A_t \cup A_{t-1}|}$$

---

### 14.6 Model D: Risk-Score Walk-Forward Validation & Empirical Frequency Calibration

#### 14.6.1 Empirical Validation of the 5-Factor Heuristic Risk Score
In Phase 2, PRISM introduced an explainable 5-factor heuristic stock risk score ($S_i \in [0, 100]$) based on volatility, downside volatility, maximum drawdown, market beta, and price instability.

Phase 4 submits this score to rigorous out-of-sample walk-forward validation against subsequent realised risk over $H \in \{21, 63\}$ trading days:
1. **Spearman Rank Information Coefficient (IC):**
   $$\text{IC} = \text{Corr}_{rank}\left(S_{i, t}, \sigma_{i, t \to t+H}\right)$$
   Tests whether higher scores monotonically rank future asset volatility.
2. **Quintile Volatility Spread:**
   $$\Delta Q = \bar{\sigma}_{Q5} - \bar{\sigma}_{Q1}$$
   Measures the spread in forward volatility between the highest-risk quintile ($Q_5$) and lowest-risk quintile ($Q_1$).
3. **Worst-Quintile Drawdown Discrimination (ROC-AUC):**
   $$\text{AUC} = \mathbb{P}\left(S_{\text{severe drawdown}} > S_{\text{normal}}\right)$$
   Evaluates the score's ability to discriminate stocks experiencing forward maximum drawdowns in the worst $20\%$ of the historical distribution.

#### 14.6.2 Non-Parametric Isotonic Calibration
To provide intuitive, calibrated risk context without making false parametric assumptions, PRISM fits an **isotonic regression**:

$$\hat{f}_{iso} = \arg\min_f \sum_{i} \left( y_i - f(S_i) \right)^2 \quad \text{subject to } f(S_a) \le f(S_b) \text{ for } S_a \le S_b$$

where $y_i = \mathbb{I}(\text{Drawdown}_{i, t \to t+21} > 10\%)$.

#### 14.6.3 Governance & Wording Mandate
The calibrated output is explicitly labelled:
> **"Historical frequency of drawdown > 10% under similar score conditions. This reflects empirical historical outcomes and is NOT a probability of future loss."**

PRISM explicitly reports whether the score demonstrates measured predictive skill ($\text{IC} > 0.05$ and $\Delta Q > 0$) or lacks statistical significance.

---

### 14.7 Model Registry & Artifact Management

Model artifacts and validation scorecards are serialized to `data/models/{name}_card.json` under git-ignore governance:
- **Model Card Schema:**
  - `name`: Model identifier string.
  - `version`: Version identifier (e.g., `2026.1`).
  - `data_cutoff`: Exact market date cutoff used for feature construction.
  - `window`: Walk-forward expanding evaluation window.
  - `features`: Full list of point-in-time input features.
  - `hyperparameters`: Dictionary of estimator parameters.
  - `metrics_vs_baseline`: Comparative dictionary of ML vs baseline metrics.
  - `config_fingerprint`: SHA-256 hash of configuration parameters.
  - `trained_at`: ISO UTC timestamp.
  - `status`: Lifecycle state (`trained`, `stale`, `insufficient_data`).
  - `model_selected`: `ml` or `baseline_*` based on the 2% supremacy rule.
  - `governance_notes`: Standard disclaimer.

---

## 15. Phase 5: Real News Intelligence and NLP

### 15.1 Ingestion Architecture & Provenance Governance
PRISM replaces synthetic headline generators with a sourced, traceable ingestion pipeline strictly adhering to publisher terms of use:
1. **Feed Sourcing:** Ingests syndicated public RSS feeds and licensed commercial equity news streams covering NSE-listed companies with zero scraping and zero paywall bypass.
2. **Provenance Preservation:** Every stored article records its canonical URL, headline, verified publisher, UTC publication timestamp, retrieved-at timestamp, unique source hash, language, and processing status. Text storage is restricted to short fair-use syndicated excerpts.
3. **Provider Status Disclosure:** When environment credentials (`PRISM_NEWS_API_KEY` or `PRISM_NEWS_FEED_URL`) are omitted or unconfigured, the system explicitly reports `"Provider not configured"` status rather than fabricating articles.

### 15.2 Entity Matching & Collision Handling
1. **Security Master Linkage:** Text is evaluated against the PRISM Security Master catalog incorporating symbols, official corporate names, aliases, and ISIN identifiers.
2. **Ambiguous Ticker Collision Resolution:** Common dictionary words and general terms matching tickers (e.g., `OIL` vs crude oil, `CAN` vs modal verb, `BEL`, `IDEA`, `SAIL`) are flagged for review. A bare ticker token matching an ambiguous symbol without company-specific corroboration is classified as `is_ambiguous=True` with confidence $< 0.50$ and status `"needs_review"`. Only when explicit corporate context (e.g. "Oil India Limited") or full company aliases are present is the entity automatically matched.
3. **Market-Wide vs Company-Specific News:** Multi-entity macroeconomic releases (e.g. RBI monetary policy, repo rate revisions, Union Budget, general inflation) are flagged as `is_market_wide=True` to prevent false attribution to individual corporate operational performance.

### 15.3 Near-Duplicate Detection (SimHash & Token Jaccard)
Syndicated wire reprints from multiple publishers frequently flood news streams with identical or slightly modified phrasing:
1. **64-Bit SimHash:** Text is tokenized into word n-grams and mapped to a 64-bit vector using Charikar's locality-sensitive hashing (LSH). Articles with a Hamming distance $d_H \le 4$ are flagged as near-duplicates.
2. **Token Jaccard Overlap:** Short headlines ($< 12$ words) are cross-checked via token Jaccard similarity:
   $$J(A, B) = \frac{|T_A \cap T_B|}{|T_A \cup T_B|} \ge 0.65$$
3. **Double-Counting Prevention:** Near-duplicates are linked to a single primary canonical article (`primary_article_id`). Secondary reprints are flagged `is_duplicate=True` and filtered out of portfolio-level sentiment aggregation.

### 15.4 Financial Sentiment & Corporate Event Taxonomy
1. **Model Hierarchy:**
   - **Transformer:** `ProsusAI/finbert` (financial domain pre-trained BERT) produces softmax probabilities for `[positive, negative, neutral]`.
   - **Lexicon Baseline Fallback:** Loughran & McDonald financial sentiment lexicon adapted for Indian equities, computing normalized polarity score on $[-1.0, +1.0]$.
2. **Uncertainty Governance:** Low-confidence inferences ($\max_k p_k < 0.55$) or headlines where uncertainty vocabulary dominates are explicitly classified as `"uncertain"`. Low-confidence results are never forced into polarized sentiment categories.
3. **Corporate Event Taxonomy:** News is classified into structured corporate catalysts:
   - `earnings`: Results, quarterly profit, PAT, EBITDA, revenue beats/misses.
   - `guidance`: Forecast revisions, forward margins, annual targets.
   - `dividend`: Payouts, special dividends, bonus issues, stock splits.
   - `m&a`: Mergers, acquisitions, stake purchases, joint ventures.
   - `regulation`: SEBI mandates, RBI circulars, antitrust actions.
   - `litigation`: Court disputes, tribunal hearings, patent challenges.
   - `product`: New launches, service agreements, technological deployment.
   - `macro`: Central bank rates, inflation, sovereign policy.
   - `routine_coverage`: General commentary without catalytic event triggers.

### 15.5 Portfolio Exposure Aggregation & Decoupling Mandate
1. **Holding Exposure Weighting:** Unique articles are mapped to portfolio holdings. Portfolio-level news sentiment is aggregated across weighted holdings:
   $$S_{\text{portfolio}} = \sum_{i \in \text{Holdings}} w_i \cdot \bar{S}_i$$
   where $\bar{S}_i$ is the unweighted mean sentiment of distinct non-duplicate articles associated with holding $i$.
2. **Decoupling from Quantitative Market Risk:** Sentiment signals are strictly qualitative diagnostic overlays. **Sentiment never silently alters historical asset covariance, idiosyncratic risk, portfolio beta, or parametric/historical VaR.**
3. **Heuristic Multiplier:** An experimental news risk multiplier is formulated strictly as an illustrative diagnostic:
   $$\text{Multiplier}_{\text{heuristic}} = 1.0 + \max\left(0.0, -\bar{S}_i \times 0.30\right)$$
   and is visibly labeled `"Heuristic"` with its exact formula exposed in tooltips.

### 15.6 Truthful Evaluation Governance
Ground-truth sentiment and entity recognition accuracy is evaluated strictly on human-verified labels provided in `data/evaluation/news_sentiment_label_template.csv`. Metrics (Accuracy, Precision, Recall, Macro-F1) are never computed against synthetic, auto-generated, or fabricated ground-truth. When user labels are missing or sparse, the pipeline reports sample counts and explicit limitations.

---

## 16. Portfolio Ledger and Performance Accounting

Transactions are the accounting source of truth. PRISM uses weighted-average cost (WAC), not FIFO
or tax-lot accounting. For a buy of quantity $q$ at price $p$ with fees $f$:

$$Q' = Q + q, \qquad C' = C + qp + f, \qquad \bar p' = C'/Q'$$

For a sale of $q_s \le Q$ at price $p_s$ with fees $f_s$:

$$C_{sold}=q_s\bar p, \qquad \text{RealizedPnL}=q_sp_s-f_s-C_{sold}$$

$$Q'=Q-q_s, \qquad C'=C-C_{sold}$$

Cash decreases by buy cost plus fees and increases by net sale proceeds. Deposits and withdrawals
change external capital and cash but are not profit. Dividends increase cash and are tracked
separately. For current price $P_i$:

$$MV_i=Q_iP_i, \qquad \text{UnrealizedPnL}_i=Q_i(P_i-\bar p_i)$$

$$\text{Equity}=\text{Cash}+\sum_i MV_i$$

Limitations: corporate-action ledger adjustments are not automatically reconstructed; WAC may not
match a broker's FIFO or jurisdiction-specific tax statement; missing prices produce unavailable
valuation rather than zero.

## 17. Diversification, Concentration, and Sector Divergence

For normalized capital weights $w_i$ and sector weights $s_j$:

$$HHI_{holding}=\sum_i w_i^2, \qquad N_{eff}=1/HHI_{holding}$$

$$HHI_{sector}=\sum_j s_j^2, \qquad S_{eff}=1/HHI_{sector}$$

The diversification ratio uses standalone annualized volatilities and portfolio volatility:

$$DR=\frac{\sum_i w_i\sigma_i}{\sigma_p}$$

Risk-contribution entropy and correlation-eigenvalue effective bets are descriptive concentration
measures. They do not prescribe an optimal allocation and PRISM is not an optimizer or a Modern
Portfolio Theory efficient-frontier implementation.

Layer 1 sector divergence uses a leave-one-out median peer benchmark. For stock $i$ in industry
$g$, the peer return is:

$$B_{i,t}=\operatorname{median}_{j\in g,\,j\ne i}(r_{j,t})$$

A trailing OLS fit over 60 sessions estimates $r_{i,t}=\alpha_i+\beta_iB_{i,t}+\epsilon_{i,t}$.
The 1-, 5-, and 20-session residual moves are standardized by the trailing residual volatility.
At least 45 paired observations and a sufficiently sized peer group are required. The statistic
describes unusual movement relative to peers; it neither predicts reversal/continuation nor proves
an economic cause.

## 18. Data Quality, Availability, and Reproducibility Rules

Price-based calculations use adjusted daily closes selected point-in-time by an explicit data
cutoff. Asset and benchmark observations are intersected on common trading dates. No forward fill,
backfill, or zero substitution is used for missing returns. Non-positive prices are rejected;
duplicate revisions are resolved by the versioned retrieval cutoff; extreme returns are flagged
and retained for review.

The active historical universe is based on the available NIFTY 200 membership snapshot and is not
a complete point-in-time reconstruction of former constituents. This creates survivorship bias in
long historical evaluations. Public feed outages, missing credentials, insufficient observations,
untrained model artifacts, empty portfolios, and database interruptions must yield explicit
unavailable/stale/error states. A production response must never replace those states with a DEMO
fixture.

Every durable analytical artifact records, where applicable, the portfolio or universe identity,
data cutoff, window, observation coverage, implementation/methodology version, configuration or
input fingerprint, and assumptions. Browser-only notes, journal entries, review-inbox items, and
snapshots are not equivalent to server-side multi-user audit records and remain a production
limitation until owner-scoped database persistence is implemented and verified.
## NIFTY 200 Data Foundation (`nifty200-risk-percentile-v1`)

The daily stock-metric publication uses only persisted, provider-observed values. Missing
observations remain `NULL`; they are never replaced by zero, a cross-sectional average, or a
synthetic return.

- Prices and returns: adjusted close is used for risk metrics. Daily return is the natural-log
  return, `r[t] = ln(P[t] / P[t-1])`. Raw close and raw volume are retained for traded value.
- Annualization: volatility and downside volatility use `sqrt(252)`. Volatility uses sample
  standard deviation (`ddof=1`). Downside volatility is
  `sqrt(252) * sqrt(mean(min(r[t], 0)^2))`.
- Windows and minimums: 1M is 21 returns (minimum 15), 3M is 63 (minimum 45), 6M is 126
  (minimum 90), and 1Y is 252 (minimum 180). Downside volatility and maximum drawdown require
  180 returns. A history shorter than 252 sessions is independently flagged
  `insufficient_history`.
- Maximum drawdown: the largest observed peak-to-trough loss over at most the trailing 253
  adjusted closes, `abs(min(P[t] / running_max(P)[t] - 1))`.
- Beta: `cov(r_stock, r_NIFTY50) / var(r_NIFTY50)` over at most 252 same-date returns. At least
  60 common returns and positive benchmark variance are required. The benchmark is `^NSEI`.
- Liquidity: 20-session average traded value is `mean(raw_close[t] * raw_volume[t])`; at least
  15 observed sessions are required.
- Five factor values: annualized 1Y volatility, downside volatility, maximum drawdown,
  `abs(beta)`, and instability (`1M volatility / 1Y volatility`). Higher values always mean
  higher measured risk.
- Calibration and score: for each metric date and factor, the observed NIFTY 200 cross-section
  supplies P10 and P90 (linear quantiles). The factor score is
  `clip(100 * (x - P10) / (P90 - P10), 0, 100)`. A zero percentile range is unavailable, not
  assigned a neutral value. The weighted score is 30% volatility, 25% downside volatility,
  20% drawdown, 15% beta, and 10% instability, and is `NULL` unless all five factors exist.
  Cut-offs and eligible counts are persisted in `score_calibration`.
- Quality: expected sessions come only from the persisted NSE trading calendar. Checks cover
  missing sessions, non-positive prices, five-session zero-volume streaks, adjusted moves over
  40% without a recorded corporate action, stale last dates, and insufficient history.
  Unavailable calendars are reported explicitly. A failed quality result prevents a score.
- Revisions: incremental fetches re-request the last 10 stored sessions. Any adjusted-close
  change triggers a full five-year symbol refetch. Raw and adjusted revisions remain versioned;
  idempotent upserts prevent duplicate published metric/calibration rows.
- Fundamentals: only provider-returned fields are stored. The provider reporting date is used
  when available; a snapshot older than 120 days is stale.
- Reproducible spot checks: ten symbols are selected using the SHA-256-derived seed from the
  metric date and methodology version. If no independent source is configured, the check is
  published as unavailable rather than simulated.

## ML Risk Validation (`ml-risk-v2`)

All ML inputs come from the Step 1 adjusted-price, raw-volume, quality, universe, and benchmark
tables at an explicit data cutoff. Quality failures are excluded. Training jobs create immutable
versioned artifacts and cards; daily inference only loads a checksum-verified artifact. API
requests query `model_run` and `model_prediction` and never fit a model or contact a provider.

### 21-session volatility

The target at date `t` is
`sqrt(252 * mean(simple_return[t+1:t+21]^2))`. An incomplete 21-session label is missing. Features
use information through `t`: trailing 1/5/21/63-session realized volatility, EWMA variance with
decay 0.94, trailing return skew/kurtosis, downside-volatility ratio, observed 20-session volume
ratio, and NIFTY 50 trailing volatility. A required missing feature makes that schema unavailable;
there is no imputation.

Training, validation, and test observations are chronological. A 21-session purge separates
training from validation and validation from test. Individual and pooled (stock-identity)
HistGradientBoosting candidates are selected by minimum validation QLIKE against trailing-21,
EWMA, and HAR(1,5,21) baselines. Ties select the baseline. MAE, RMSE, QLIKE, sample count, and test
dates are reported on the untouched test set. Fitted weights are not updated with test labels.
A 90% interval uses the 90th percentile absolute validation residual; unseen test coverage and
mean width are reported and are not forced to 90%.

### NIFTY 50 market regime

The two-state Gaussian Markov regression uses simple NIFTY 50 returns and switching variance.
Only filtered probabilities conditional on observations through the stated date are published.
States are named after fitting by estimated conditional volatility, so the lower-volatility state
is calm and the higher-volatility state stressed. Weighted mean return, annualized volatility,
transition probabilities, and expected duration `1 / (1 - p_ii)` are stored for each state.
Shifted-window stability compares the volatility-aligned calm/stressed labels, not raw state IDs.

### Cross-sectional anomalies

The fixed schema is daily simple return, one-day change in trailing 20-session realized
volatility, one-day change in 60-session beta to NIFTY 50, observed volume divided by its exact
20-session mean, and return minus the same-day sector peer mean. A sector requires at least two
eligible members. RobustScaler and Isolation Forest are fitted only on historical complete rows
with seed 42 and contamination 10%. The stored score is the empirical percentile of the raw
Isolation Forest score in the training distribution. Feature contributions are normalized
absolute robust deviations from training medians; they are explanations of unusual observations,
not causal attributions or forecasts. Independent event review is explicitly unavailable unless
a point-in-time event source is configured.

### Five-factor score validation

The score remains an analytical score. At each historical month end, the already persisted
point-in-time percentile factors and fixed weights (30/25/20/15/10 percent) are evaluated against
forward 21- and 63-session realized volatility and peak-to-trough drawdown. Incomplete forward
windows and incomplete factor rows are excluded, not imputed. Cross-sectional average-rank
Spearman IC and top-minus-bottom quintile spread are calculated separately by month. The IC
t-statistic is the mean monthly IC divided by its ordinary standard error and is descriptive
because monthly samples may be dependent. Drawdown AUC defines the positive class as that month's
highest 20% forward 21-session drawdowns. Results are compared without refitting against a
volatility-only score and an equal-weight five-factor score on the later chronological test period.

Dashboard statuses use this precedence: an actual failed/insufficient/unavailable operation is
shown as such; otherwise an output older than seven calendar days is stale; otherwise a selected
baseline is `baseline_selected`; otherwise it is `ready`. Missing fields remain absent or `NULL`.
