# PRISM Confidence Score Specification

## 1. Scope and Authority
- **Authority**: Subordinate to `PRISM_SRS.md`.
- **Purpose**: Defines the formula, factors, and caps that determine the confidence score $C_{\text{final}} \in [0, 100]$ accompanying every derived risk result.
- **Principle**: Transparency of uncertainty. Low data quality or stale sources explicitly down-rate confidence rather than halting or inventing observations.

## 2. Core Mathematical Formulation
The unconstrained confidence score $C_{\text{raw}} \in [0, 100]$ is the weighted average of 6 distinct factors $F_k \in [0, 1]$:

$$C_{\text{raw}} = 100 \times \frac{\sum_{k=1}^6 w_k \cdot F_k}{\sum_{k=1}^6 w_k}$$

Default configuration assigns equal weights: $w_k = 1.0$ for all $k \in \{1, \dots, 6\}$.

### The Six Confidence Factors
1. **Data Coverage ($F_{\text{coverage}}$)**:
   $$F_{\text{coverage}} = \frac{\sum_{d \in \mathcal{D}_{\text{avail}}} W_d}{\sum_{d \in \mathcal{D}} W_d}$$
   Ratio of available dimension weights to total possible dimension weights in the risk scoring framework.
2. **Data Freshness ($F_{\text{freshness}}$)**:
   Component-level freshness decaying linearly with calendar age:
   $$f_c = \max\left(0.0, 1.0 - \frac{\text{age\_days}_c}{\text{max\_age\_days}_c}\right)$$
   Aggregated across all available components:
   $$F_{\text{freshness}} = \frac{\sum_{c \in \mathcal{C}_{\text{avail}}} w_c \cdot f_c}{\sum_{c \in \mathcal{C}_{\text{avail}}} w_c}$$
   Where $\text{max\_age\_days}$ defaults to: Market/Liquidity = 5 days, Fundamentals = 120 days, Governance = 365 days.
3. **Source Agreement ($F_{\text{source}}$)**:
   Measures consistency between redundant sources or cross-checks (e.g. NSE official close vs Yahoo Finance adjusted close):
   $$F_{\text{source}} = 1.0 - \min(1.0, \text{max\_price\_discrepancy} \times 100)$$
   When a single primary source is configured and passes validation, $F_{\text{source}} = 1.0$.
4. **Signal Agreement ($F_{\text{signal}}$)**:
   Internal concordance between multi-horizon or directional signals (e.g. Layer 1 1-day, 5-day, and 20-day divergence sign alignment):
   $$F_{\text{signal}} = \frac{1 + \text{mean\_pairwise\_sign\_concordance}}{2} \in [0, 1]$$
   If signals diverge sharply across horizons, $F_{\text{signal}}$ drops towards $0.5$.
5. **Model Stability ($F_{\text{stability}}$)**:
   Measures structural robustness of underlying models (e.g. MST edge persistence across adjacent windows or OLS standard error ratio):
   $$F_{\text{stability}} = \max\left(0.0, 1.0 - \frac{\text{SE}(\beta)}{\text{SE}_{\max}}\right)$$
   For baseline price calculations, defaults to observation completeness ratio $\frac{N_{\text{obs}}}{N_{\text{expected}}}$.
6. **Evidence Volume ($F_{\text{volume}}$)**:
   Degree to which the required statistical sample size is satisfied:
   $$F_{\text{volume}} = \min\left(1.0, \frac{N_{\text{actual}}}{N_{\text{target}}}\right)$$
   E.g., $N_{\text{target}} = 60$ for Layer 1 OLS; if 60 observations exist, $F_{\text{volume}} = 1.0$.

## 3. Confidence Caps and Overrides
Hard constraints override $C_{\text{raw}}$ when data integrity is compromised:

1. **Stale Price Data Cap**:
   - If any core market price is older than $N_{\text{stale}}$ trading days (default 5):
     $$C_{\text{final}} \le 50.0$$
   - *Reason*: Stale pricing fundamentally invalidates risk assessments regardless of how stable models appear.
2. **Low Coverage Cap**:
   - If $F_{\text{coverage}} < C_{\min}$ (default 0.70):
     $$C_{\text{final}} \le 60.0$$
   - *Reason*: Results missing >30% of risk dimensions cannot claim high confidence.
3. **Composite Application**:
   $$C_{\text{final}} = \min(C_{\text{raw}}, \text{active\_caps})$$
   Every applied cap is recorded in the result envelope alongside its reason.

---

## 4. Worked Numeric Example (Reproduced in Test)

Consider an evaluation for Security XYZ with equal weights ($w_k = 1.0$ for all 6 factors):

### Factor Values
1. $F_{\text{coverage}} = 0.45$ (only 45% of potential dimension weight is available: $0.45 < 0.70$).
2. $F_{\text{freshness}} = 0.90$ (market data is 1 day old out of 10 max days: $1 - 1/10 = 0.90$).
3. $F_{\text{source}} = 1.00$ (official NSE verified).
4. $F_{\text{signal}} = 0.80$ (1d, 5d, 20d signals mostly aligned in sign).
5. $F_{\text{stability}} = 0.95$ (MST edge is stable, OLS residuals stationary).
6. $F_{\text{volume}} = 1.00$ (full 60 observations available).

### Unconstrained Mean
- Sum of factors $= 0.45 + 0.90 + 1.00 + 0.80 + 0.95 + 1.00 = 5.10$.
- Average factor value $= 5.10 / 6 = 0.85$.
- Unconstrained confidence:
  $$C_{\text{raw}} = 100 \times 0.85 = 85.0$$

### Application of Caps
- **Check 1: Stale price cap (50)**: Market data is 1 day old $\le 5$ days $\implies$ Not triggered.
- **Check 2: Low coverage cap (60)**: $F_{\text{coverage}} = 0.45 < 0.70 \implies$ **TRIGGERED** (cap = $60.0$).
- **Final Confidence**:
  $$C_{\text{final}} = \min(85.0, 60.0) = 60.0$$
- Result envelope logs:
  - `raw_confidence`: 85.0
  - `final_confidence`: 60.0
  - `caps_applied`: `["low_coverage_cap_60"]`

This exact calculation is verified in `tests/specs/test_confidence_spec.py`.
