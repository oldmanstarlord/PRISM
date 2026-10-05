# PRISM Multi-Dimensional Risk Score Specification

## 1. Scope and Authority
- **Authority**: Governed by `PRISM_SRS.md`.
- **Purpose**: Defines the multi-dimensional risk score synthesis engine across 8 core dimensions.
- **Principle**: Descriptive risk assessment and ranking, NOT price forecasting or trade recommendation.

## 2. Core Mathematical Formulation
The overall risk score $S \in [0, 100]$ for a security is computed as the renormalised weighted sum of available dimension scores:

$$S = \frac{\sum_{d \in \mathcal{D}_{\text{avail}}} W_d \cdot P_d}{\sum_{d \in \mathcal{D}_{\text{avail}}} W_d}$$

where:
- $W_d \ge 0$ is the configured weight for dimension $d$.
- $P_d \in [0, 100]$ is the point score of dimension $d$.
- $\mathcal{D}_{\text{avail}}$ is the subset of dimensions that have at least one valid component observation.

### Coverage Metric
Data coverage $C \in [0, 1]$ measures the proportion of total potential weight available:
$$C = \frac{\sum_{d \in \mathcal{D}_{\text{avail}}} W_d}{\sum_{d \in \mathcal{D}} W_d}$$
If $C < C_{\min}$ (from `model_config`, default $0.70$), the score is flagged as insufficient and subject to confidence caps. Missing components are **never silently imputed**.

## 3. Eight Dimensions and Default Weights
Weights are initial baseline values reflecting economic and operational risk significance, **NOT fitted to historical returns** (preventing in-sample over-fitting):

| Dimension $d$ | Code | Default Weight $W_d$ | Rationale |
|---|---|---|---|
| Market | `market` | 25 | Price volatility, beta, downside risk, historical drawdown. |
| Fundamentals | `fundamentals` | 20 | Leverage, solvency, earnings volatility, quality metrics. |
| Liquidity | `liquidity` | 10 | Bid-ask spread, Amihud illiquidity, turnover concentration. |
| Structure | `structure` | 10 | MST connectivity, graph centrality, cluster vulnerability. |
| Relative | `relative` | 10 | Sector divergence (Layer 1 residual), peer decoupling. |
| Governance | `governance` | 10 | Promoter pledging, board independence, auditor remarks. |
| Events | `events` | 10 | Regulatory queries, negative filing sentiment, management changes. |
| Macro | `macro` | 5 | Sensitivity to FX, rates, crude, and institutional flows. |
| **Total** | | **100** | |

## 4. Component Scoring and Percentile Rules
Within each dimension $d$, the dimension score is the weighted average of its active components:
$$P_d = \frac{\sum_{c \in \mathcal{C}_d} w_c \cdot p_c}{\sum_{c \in \mathcal{C}_d} w_c}$$
Where components are equal-weighted ($w_c = 1.0$) unless configured otherwise.

### Direction of Risk
Each component has an explicit direction:
- `higher_is_riskier`: Higher raw metric values indicate higher risk (e.g. Volatility, Amihud illiquidity, Debt/Equity).
  $$p_c = \text{percentile}(x_c)$$
- `lower_is_riskier`: Lower raw metric values indicate higher risk (e.g. Interest Coverage Ratio, Current Ratio, Turnover).
  $$p_c = 100 - \text{percentile}(x_c)$$

### Percentile Tie-Breaking Rule
Percentile rank across $N$ peer observations uses the weak empirical distribution with mid-point adjustment:
$$\text{percentile}(v) = 100 \times \frac{\sum_{i=1}^N \mathbf{1}(x_i < v) + 0.5 \sum_{i=1}^N \mathbf{1}(x_i = v)}{N}$$
This ensures:
1. Exact symmetry around the median.
2. Identical values receive identical percentile scores.
3. Scores span $[0, 100]$ deterministically.

### Industry vs Universe Scope
- If a component specifies `scope: industry`, percentiles are evaluated only within the security's official industry group.
- If the eligible industry peer count $< N_{\min}$ (from `model_config`, default 5), the engine falls back to `scope: universe` and attaches an explicit limitation flag `industry_group_undersized_fallback`.

## 5. Result Envelope, Contributions, and Top Reasons
Every score result envelope carries:
1. **Component Contributions**: $K_c = \frac{W_d \cdot w_c \cdot p_c}{\sum_{d'} W_{d'} \sum_{c'} w_{c'}}$ showing each component's point contribution to the final score.
2. **Top-3 Reasons**: The three components with the highest net risk contributions $K_c$, together with their raw values, percentiles, and direction explanations.
3. **Limitations**: Complete list of missing components, stale flags, and scope fallbacks.

---

## 6. Worked Numeric Example (Reproduced in Test)

Assume an evaluation with 3 active dimensions out of 8 (Market $W=25$, Liquidity $W=10$, Relative $W=10$). The remaining 5 dimensions are missing.

### Active Dimensions and Components
1. **Market** ($W = 25$):
   - Component $M_1$ (`volatility_60d`, `higher_is_riskier`): Raw value has percentile $80.0 \implies p_{M1} = 80.0$.
   - Component $M_2$ (`max_drawdown`, `higher_is_riskier`): Raw value has percentile $60.0 \implies p_{M2} = 60.0$.
   - Equal weights: $P_{\text{market}} = (80.0 + 60.0) / 2 = 70.0$.
2. **Liquidity** ($W = 10$):
   - Component $L_1$ (`turnover`, `lower_is_riskier`): Raw value has percentile $30.0$.
   - Direction `lower_is_riskier`: $p_{L1} = 100.0 - 30.0 = 70.0 \implies P_{\text{liquidity}} = 70.0$.
3. **Relative** ($W = 10$):
   - Component $R_1$ (`divergence_20d`, `higher_is_riskier`): Raw value has percentile $90.0 \implies P_{\text{relative}} = 90.0$.

### Renormalisation
- Total available weight = $25 + 10 + 10 = 45$.
- Data coverage $C = 45 / 100 = 0.45$ (or $45\%$).
- Weighted points sum = $(25 \times 70.0) + (10 \times 70.0) + (10 \times 90.0)$
  - $25 \times 70.0 = 1750.0$
  - $10 \times 70.0 = 700.0$
  - $10 \times 90.0 = 900.0$
  - Sum = $1750.0 + 700.0 + 900.0 = 3350.0$.
- Final Renormalised Score:
  $$S = \frac{3350.0}{45} = 74.4444\dots$$

### Component Contributions to Score $S$
- Total effective weight units = $45$.
- $M_1$: weight contribution $= (25 \times 0.5) / 45 \times 80.0 = (12.5 / 45) \times 80.0 = 22.2222$
- $M_2$: weight contribution $= (25 \times 0.5) / 45 \times 60.0 = (12.5 / 45) \times 60.0 = 16.6667$
- $L_1$: weight contribution $= (10 \times 1.0) / 45 \times 70.0 = (10 / 45) \times 70.0 = 15.5556$
- $R_1$: weight contribution $= (10 \times 1.0) / 45 \times 90.0 = (10 / 45) \times 90.0 = 20.0000$
- Sum of contributions $= 22.2222 + 16.6667 + 15.5556 + 20.0000 = 74.4444 = S$.

### Top-3 Reasons
1. $M_1$ (`volatility_60d`): Contributes $+22.22$ pts (Percentile 80.0, Market dimension).
2. $R_1$ (`divergence_20d`): Contributes $+20.00$ pts (Percentile 90.0, Relative dimension).
3. $M_2$ (`max_drawdown`): Contributes $+16.67$ pts (Percentile 60.0, Market dimension).

This exact calculation is verified in `tests/specs/test_risk_score_spec.py`.
