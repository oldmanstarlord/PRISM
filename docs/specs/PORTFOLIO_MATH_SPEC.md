# PRISM Portfolio Math Specification

## 1. Scope and Authority
- **Authority**: Subordinate to `PRISM_SRS.md`.
- **Purpose**: Defines the exact mathematical and operational rules for portfolio valuation, returns, risk aggregation, benchmark comparison, and missing data handling.
- **Principle**: PRISM provides descriptive risk and explanation, NOT price prediction and NOT investment advice.

## 2. Input Rules
1. **Input Mode**: A portfolio may be specified by **quantity** ($q_i \in \mathbb{R}^+$) or by **target weight** ($w_i \in [0, 1]$).
   - *Reason*: Accommodates both direct account holdings and synthetic portfolio allocations.
2. **Cash Line**: Cash is represented as a distinct holding with symbol `CASH` (or currency identifier `INR`), zero volatility, unit price $1.0$, and zero correlation with risky assets.
   - *Reason*: Preserves exact cash drag and prevents artificial over-leveraging of equity risks.
3. **Weight Normalization**: Total portfolio weights must strictly sum to $1.0$:
   $$w_i = \frac{q_i P_{i, t}}{\sum_j q_j P_{j, t} + C_t}$$
   For weight-based inputs, raw weights are scaled: $w_i = w_{i,\text{raw}} / \sum_j w_{j,\text{raw}}$.
   - *Reason*: Ensures all risk contributions and portfolio returns are mathematically bounded and coherent.

## 3. Valuation and Return Rules
4. **Valuation**: Asset valuation uses the latest adjusted closing price on or preceding the effective as-of date:
   $$V_t = \sum_{i=1}^M q_i P_{i, t}^{\text{adj}} + C_t$$
   - *Reason*: Adjusted close accounts for historical splits, bonuses, and capital structure changes without price discontinuities.
5. **Daily Returns**: Asset log returns are computed on consecutive trading days on adjusted prices:
   $$r_{i, t} = \ln\left(\frac{P_{i, t}^{\text{adj}}}{P_{i, t-1}^{\text{adj}}}\right)$$
   - *Reason*: Log returns provide time-additivity over multi-day calculation horizons.
6. **Portfolio Daily Return**:
   $$r_{p, t} = \ln\left( \sum_{i=1}^M w_{i, t-1} \exp(r_{i, t}) + w_{\text{cash}, t-1} \right)$$
   For linear aggregation approximation across short intervals ($|r_{i,t}| \ll 1$):
   $$r_{p, t} \approx \sum_{i=1}^M w_{i, t-1} r_{i, t}$$
   - *Reason*: Accurately reflects buy-and-hold portfolio value evolution.
7. **Dividends**: Ordinary and special cash dividends are incorporated via the price adjustment factor in $P_{i, t}^{\text{adj}}$.
   - *Reason*: Standardizes total-return calculations without requiring arbitrary reinvestment schedules.

## 4. Risk and Horizon Rules
8. **Annualisation Factor**: 252 trading days per calendar year:
   $$\sigma_{\text{ann}} = \sigma_{\text{daily}} \times \sqrt{252}$$
   - *Reason*: Standard Indian exchange (NSE/BSE) trading year convention.
9. **Default Lookback Window**: 250 active trading days (approx. 1 calendar year).
   - *Reason*: Captures recent market regimes while retaining sufficient sample size ($N = 250$) for covariance stability.
10. **Rebalancing Assumption**: Buy-and-hold; no intra-window rebalancing is assumed.
    - *Reason*: Avoids assuming unrealised trading activity, transaction costs, or market impact.
11. **Benchmark**: Official `NIFTY 200` index total return series.
    - *Reason*: Aligns with the core PRISM universe boundary defined in SRS Section 3.
12. **Risk-Free Rate**: Required ONLY if Sharpe ratio or excess returns are displayed; defaults to the 91-day Government of India Treasury Bill yield from `model_config`. Not required for raw volatility, beta, or drawdown.
    - *Reason*: Avoids introducing interest-rate assumptions into pure descriptive volatility models.

## 5. Missing and Stale Price Policy
13. **Stale Price Rule**: A security is flagged as stale if no active trading price is recorded for $N_{\text{stale}}$ consecutive trading days ($N_{\text{stale}}$ from `model_config`, default = 5).
    - *Reason*: Distinguishes normal market holidays from halted, suspended, or illiquid securities.
14. **Missing Day Treatment**: If a security is missing a price on day $t$, it is temporarily excluded from day $t$'s return vector, remaining weights are re-normalised for that day, and an explicit warning is logged in the result envelope.
    - *Reason*: Prevents zero-return distortion (which artificially suppresses volatility) while maintaining total portfolio weight equal to $1.0$.

---

## 6. Worked Numeric Example (Reproduced in Test)

Consider a simple portfolio on as-of date $T$ with 2 equity holdings and Cash:
- Holding A: 100 shares @ adjusted close 50.0 = Rs. 5,000
- Holding B: 200 shares @ adjusted close 20.0 = Rs. 4,000
- Cash: Rs. 1,000
- Total Portfolio Value $V_0 = 5000 + 4000 + 1000 = \text{Rs. } 10,000$.

### Normalized Weights
- $w_A = 5000 / 10000 = 0.50$
- $w_B = 4000 / 10000 = 0.40$
- $w_{\text{cash}} = 1000 / 10000 = 0.10$
Sum = $0.50 + 0.40 + 0.10 = 1.00$.

### 3-Day Daily Returns Table
| Day $t$ | $r_A$ | $r_B$ | $r_{\text{cash}}$ | Portfolio Return $r_{p, t} = 0.50 r_A + 0.40 r_B$ |
|---|---|---|---|---|
| 1 | +0.020 | -0.010 | 0.000 | $0.50(0.020) + 0.40(-0.010) = 0.010 - 0.004 = +0.006$ |
| 2 | -0.010 | +0.030 | 0.000 | $0.50(-0.010) + 0.40(0.030) = -0.005 + 0.012 = +0.007$ |
| 3 | +0.015 | +0.005 | 0.000 | $0.50(0.015) + 0.40(0.005) = 0.0075 + 0.0020 = +0.0095$ |

- Mean return $\bar{r}_p = \frac{0.006 + 0.007 + 0.0095}{3} = \frac{0.0225}{3} = 0.0075$
- Sample variance $s^2 = \frac{(0.006 - 0.0075)^2 + (0.007 - 0.0075)^2 + (0.0095 - 0.0075)^2}{3 - 1}$
  - $(0.006 - 0.0075)^2 = (-0.0015)^2 = 0.00000225$
  - $(0.007 - 0.0075)^2 = (-0.0005)^2 = 0.00000025$
  - $(0.0095 - 0.0075)^2 = (0.0020)^2 = 0.00000400$
  - Sum of squares = $0.00000650$
  - Variance $s^2 = 0.00000650 / 2 = 0.00000325$
  - Daily standard deviation $s = \sqrt{0.00000325} \approx 0.0018027756$
- Annualised volatility $\sigma_{\text{ann}} = s \times \sqrt{252} \approx 0.0018027756 \times 15.874507866 \approx 0.028618$ (or $2.8618\%$).

This exact sequence is tested in `tests/specs/test_portfolio_math_spec.py`.
