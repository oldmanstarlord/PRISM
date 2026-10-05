# PRISM Macro Risk Specification (MACRO_SPEC)

**Dimension:** `macro` (Weight: 5.0% in PRISM Risk Score)  
**Method Version:** `macro-regime-sensitivity-v1`  
**Status:** Approved / Specification  

---

## 1. Macro Series Definitions (Resolves SRS OQ-10)

Per SRS Section 14 and requirement FR-D9 (replaceable adapters, point-in-time timestamps, no look-ahead), the 5 approved macro series for PRISM are specified below:

| Series Key | Name | Production source | Explicit import only | Update Frequency | Publication Lag | Unit | Licensing Note |
|---|---|---|---|---|---|---|---|
| `crude_oil` | Brent Crude Oil Continuous | Yahoo Finance (`BZ=F`) | `--source csv --file PATH` | Daily (Trading days) | T+0 at market close (EOD) | USD/bbl | Yahoo market quote; single-source limitation. |
| `usd_inr` | USD / INR Exchange Rate | Yahoo Finance (`INR=X`) | `--source csv --file PATH` | Daily (Working days) | Provider timestamp | INR per USD | Yahoo market quote; single-source limitation. |
| `in_10y_yield` | India 10-Year Benchmark G-Sec Yield | Yahoo (`^IN10YT=RR`) if verified; otherwise TBD | `--source csv --file PATH` | Daily (Trading days) | Provider timestamp | % (Annualised) | Live availability must be verified before use. |
| `india_vix` | India VIX | Yahoo (`^INDIAVIX`) if verified; otherwise TBD | `--source csv --file PATH` | Daily (Trading days) | Provider timestamp | Index points (%) | Live availability must be verified before use. |
| `fii_dii_net_flows` | FII & DII Cash Market Net Investment | TBD | `--source csv --file PATH` | Daily (Trading days) | TBD | INR Crores | No verified live adapter is configured. |

CSV is never a fallback. A failed Yahoo series is logged and left stale; no substitute rows are written.

### Data Model & Point-in-Time Schema
All macro data is persisted in `macro_observation` with:
- `obs_date`: Observation date.
- `published_at`: Exact UTC timestamp when the data was made publicly available.
- `ingested_at`: UTC timestamp when ingested into PRISM.
- `version`: Integer version (supports point-in-time restatements without overwriting).

Strict Point-in-Time Contract: For calculation as of date $t$ with cutoff $\tau$, only rows with `published_at <= tau` are visible.

---

## 2. Rule-Based Market Regime Classification (FR-F4)

The market regime classifies the macro state into one of three discrete states:
1. `calm` (Low volatility, low correlation, stable macro environment)
2. `trending` (Moderate directional momentum, normal dispersion)
3. `stressed` (High volatility, systemic correlation spike, elevated risk transmission)

### Feature Derivations
1. **Realised Volatility Percentile ($RV_{pctl}$)**:
   - 21-day rolling annualised realised volatility of the benchmark index (NIFTY 200):
     $$\sigma_{21, t} = \sqrt{252 \times \frac{1}{20} \sum_{k=0}^{20} (r_{m, t-k} - \bar{r}_m)^2}$$
   - $RV_{pctl}$ is the percentile rank of $\sigma_{21, t}$ over a trailing 252-day lookback window.
2. **Average Pairwise Correlation Percentile ($Corr_{pctl}$)**:
   - Average pairwise correlation $\bar{\rho}_t = \frac{2}{N(N-1)} \sum_{i < j} \rho_{i,j,t}$ from Layer 2 correlation matrix (63-day lookback).
   - $Corr_{pctl}$ is the percentile rank of $\bar{\rho}_t$ over trailing 252 days.
3. **India VIX Level ($VIX_t$)**:
   - Spot level of India VIX on date $t$ (if available).

### Thresholds & Hysteresis Rules
To prevent oscillating regime transitions near boundary thresholds, state transitions follow an explicit hysteresis state machine:

| Current State | Condition to Transition to `stressed` | Condition to Transition to `calm` | Condition to Transition to `trending` |
|---|---|---|---|
| `calm` | $RV_{pctl} \ge 75$ OR $Corr_{pctl} \ge 75$ OR $VIX \ge 22.0$ | Remains `calm` | $RV_{pctl} \ge 45$ OR $Corr_{pctl} \ge 45$ OR $VIX \ge 16.5$ |
| `trending` | $RV_{pctl} \ge 75$ OR $Corr_{pctl} \ge 75$ OR $VIX \ge 22.0$ | $RV_{pctl} < 35$ AND $Corr_{pctl} < 35$ AND ($VIX < 14.5$ or null) | Remains `trending` |
| `stressed` | Remains `stressed` (Hysteresis lock) | $RV_{pctl} < 35$ AND $Corr_{pctl} < 35$ AND ($VIX < 14.5$ or null) | $RV_{pctl} < 65$ AND $Corr_{pctl} < 65$ AND ($VIX < 19.0$ or null) |

---

## 3. Sector Macro Sensitivity Estimation

For each industry $J \in \{\text{Automobile}, \text{Banking}, \text{IT}, \dots\}$:
1. Equal-weighted daily return of all active securities in industry $J$:
   $$R_{J, t} = \frac{1}{|S_J|} \sum_{i \in S_J} r_{i, t}$$
2. Daily macro delta for series $s$:
   - For price/index series (`crude_oil`, `usd_inr`, `india_vix`): Log or relative change $\Delta M_{s, t} = \frac{M_{s, t} - M_{s, t-1}}{M_{s, t-1}}$.
   - For yield/flows (`in_10y_yield`, `fii_dii_net_flows`): Absolute change $\Delta M_{s, t} = M_{s, t} - M_{s, t-1}$ (or standardized net flow).
3. Rolling 63-day OLS regression (minimum 30 valid paired observations):
   $$R_{J, t} = \alpha_{J, s} + \beta_{J, s} \Delta M_{s, t} + \epsilon_{J, s, t}$$
4. Statistical Significance:
   $$t_{J, s} = \frac{\hat{\beta}_{J, s}}{\text{SE}(\hat{\beta}_{J, s})}$$
   A sensitivity is marked **significant** ($\mathbf{1}_{\text{sig}} = 1$) if $|t_{J, s}| \ge 1.96$ ($p \le 0.05$). Insignificant sensitivities are assigned $\mathbf{1}_{\text{sig}} = 0$ to prevent penalizing stocks for spurious noise.

---

## 4. Component Formula: `macro_exposure`

The dynamic risk component `macro_exposure` evaluates a stock's vulnerability to current macro shocks transmitted through its industry sector:

$$\text{macro\_exposure}_i = \left( \sum_{s \in \mathcal{S}} \left( |\hat{\beta}_{\text{industry}(i), s}| \cdot \mathbf{1}_{\text{sig}}(s) \cdot |z_s| \right) \right) \times M_{\text{regime}}$$

Where:
- $\mathcal{S}$ is the set of approved macro series.
- $z_s = \frac{\Delta M_{s, \text{recent}} - \mu_{s, 63}}{\sigma_{s, 63}}$ is the standardized $z$-score of the recent macro move (over trailing 5 trading days relative to rolling 63-day mean and volatility).
- $M_{\text{regime}}$ is the config-driven regime amplifier:
  - `calm`: $M = 1.0$
  - `trending`: $M = 1.25$
  - `stressed`: $M = 1.50$
- Direction: `higher_is_riskier`.
- Component Score: Mapped via empirical percentile ranking across the universe (0 to 100), contributing to the 5.0% `macro` dimension weight.

---

## 5. Worked Example (Hand-Calculated Numeric Verification)

Consider Stock **XYZ** belonging to the **Oil & Gas** industry during a **stressed** market regime:
- Current Regime: `stressed` $\implies M_{\text{regime}} = 1.50$.
- Recent macro shocks ($|z_s|$ over 5-day window):
  1. `crude_oil`: 5-day jump of $+8.5\%$, 63-day $\mu = 0.1\%, \sigma = 2.0\% \implies z = \frac{8.5 - 0.1}{2.0} = 4.20 \implies |z| = 4.20$.
  2. `usd_inr`: 5-day depreciation $+1.2\%$, 63-day $\mu = 0.05\%, \sigma = 0.40\% \implies z = \frac{1.2 - 0.05}{0.40} = 2.875 \implies |z| = 2.88$.
  3. `in_10y_yield`: 5-day change $+0.04\%$, 63-day $\mu = 0.01\%, \sigma = 0.06\% \implies z = \frac{0.04 - 0.01}{0.06} = 0.50 \implies |z| = 0.50$.
  4. `india_vix`: 5-day jump $+4.2$ pts, 63-day $\mu = 0.0, \sigma = 1.5 \implies z = \frac{4.2}{1.5} = 2.80 \implies |z| = 2.80$.
  5. `fii_dii_net_flows`: 5-day net outflow $-4,500$ Cr, $\mu = 0, \sigma = 2,000 \implies z = \frac{-4500}{2000} = -2.25 \implies |z| = 2.25$.

- Oil & Gas Industry Sensitivities ($\beta, t\text{-stat}$):
  1. `crude_oil`: $\beta = -0.45, t = -3.21 \implies |t| \ge 1.96 \implies \mathbf{1}_{\text{sig}} = 1$.  
     Contribution: $0.45 \times 4.20 = 1.890$.
  2. `usd_inr`: $\beta = -0.30, t = -2.15 \implies |t| \ge 1.96 \implies \mathbf{1}_{\text{sig}} = 1$.  
     Contribution: $0.30 \times 2.875 = 0.8625$.
  3. `in_10y_yield`: $\beta = -0.15, t = -0.80 \implies |t| < 1.96 \implies \mathbf{1}_{\text{sig}} = 0$ (Insignificant; zeroed out!).  
     Contribution: $0.0$.
  4. `india_vix`: $\beta = -0.22, t = -2.50 \implies |t| \ge 1.96 \implies \mathbf{1}_{\text{sig}} = 1$.  
     Contribution: $0.22 \times 2.80 = 0.616$.
  5. `fii_dii_net_flows`: $\beta = +0.10, t = +1.10 \implies |t| < 1.96 \implies \mathbf{1}_{\text{sig}} = 0$ (Insignificant; zeroed out!).  
     Contribution: $0.0$.

- Raw Sum:
  $$\sum = 1.890 + 0.8625 + 0.0 + 0.616 + 0.0 = 3.3685$$
- Regime-Scaled `macro_exposure`:
  $$\text{macro\_exposure} = 3.3685 \times 1.50 = 5.05275$$

This exact numeric case is verified in `tests/macro/test_macro_components.py`.
