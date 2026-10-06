# PRISM Explanation Language Owner Review Pack

**Document ID:** `docs/specs/EXPLANATION_REVIEW.md`  
**Phase:** Step E6 — Explanation Faithfulness, Safety Guardrails & Language Governance  
**Status:** `PENDING_OWNER_REVIEW` (All items remain in `DRAFT` / `UNREVIEWED` status until explicitly approved by the system owner)  
**Governing Authority:** `PRISM_SRS.md` Section 10, 14, 16; `docs/agent/MASTER_CONTEXT.md` Rules D1, D8, D9, D10, D11.

---

## 1. Executive Summary

In accordance with Design Rule **D8** (Explanations are Evidence-Bound) and Design Rule **D9** (No Advice, No Causal Claims), PRISM explanations are strictly generated from deterministic templates populated exclusively by stored point-in-time database records. No generative language model produces user-facing explanatory text.

This review pack compiles the exhaustive checklist for the system owner to review:
1. **Glossary Term Definitions & Formulas** (14 versioned terms)
2. **Template Catalog** (Component, MST, Sector Divergence, News Impact, Shock Simulation, Portfolio Diversification, Score Change, and Alert explainers)
3. **Wording Bands & Quantitative Mapping**
4. **Seeded Regulatory Policy Rules & Rationales** (All marked `UNREVIEWED_SEED`)
5. **News Impact Parameters & Half-Life Decay Settings**

Each item below is tracked as a pending decision in [`docs/specs/PROPOSED_DECISIONS.md`](file:///c:/Users/Pratham/OneDrive/Desktop/Mini/PRISM/docs/specs/PROPOSED_DECISIONS.md).

---

## 2. Glossary Term Review Checklist

| Status | Term Key | Label | Plain Language Definition | Mathematical Formula | See Also |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [ ] PENDING | `correlation` | Correlation | A statistic describing how two series move together. | $\rho_{ij} = \frac{\text{Cov}(R_i, R_j)}{\sigma_i \sigma_j}$ | `correlation_distance` |
| [ ] PENDING | `correlation_distance` | Correlation distance | A non-negative transformation of correlation used to construct the approved network. | $d_{ij} = \sqrt{2(1 - \rho_{ij})}$ | `correlation`, `minimum_spanning_tree` |
| [ ] PENDING | `minimum_spanning_tree` | Minimum spanning tree | A sparse network connecting every stock while minimizing total configured edge distance. | Kruskal's algorithm on $d_{ij}$ | `correlation_distance`, `hub` |
| [ ] PENDING | `hub` | Hub | A node with relatively many or important links in the stored network. | Degree $k_i \ge \text{threshold}$ | `minimum_spanning_tree`, `cluster` |
| [ ] PENDING | `cluster` | Cluster | A group identified from stored statistical relationships; it is not a causal group. | Louvain modularity optimization | `correlation`, `hub` |
| [ ] PENDING | `residual` | Residual | The part of an observed value left after subtracting the fitted model component. | $\epsilon_i = R_i - (\alpha + \beta R_m)$ | `r_squared`, `beta` |
| [ ] PENDING | `z_score` | Z-score | The number of standard deviations a value lies above or below its reference mean. | $Z = \frac{x - \mu}{\sigma}$ | `volatility` |
| [ ] PENDING | `beta` | Beta | A fitted measure of how strongly an asset's returns move with a benchmark's returns. | $\beta = \frac{\text{Cov}(R_i, R_m)}{\text{Var}(R_m)}$ | `r_squared`, `correlation` |
| [ ] PENDING | `r_squared` | R-squared | The share of observed variation described by a fitted model in the stored sample. | $R^2 = 1 - \frac{\text{SS}_{\text{res}}}{\text{SS}_{\text{tot}}}$ | `beta`, `residual` |
| [ ] PENDING | `percentile` | Percentile | The percentage of comparable observations at or below a value under the configured tie rule. | $\text{rank}(x) / N \times 100$ | `z_score` |
| [ ] PENDING | `mst_path_decay` | MST path decay | The attenuated transmission factor along the unique path connecting two assets in the tree. | $D(s, j) = \prod \max(0, \rho_{uv})$ | `minimum_spanning_tree`, `correlation` |
| [ ] PENDING | `entropy` | Entropy | A mathematical measure of dispersion across portfolio percentage risk contributions. | $H = -\sum p_i \ln(p_i)$ | `effective_number_of_bets`, `diversification` |
| [ ] PENDING | `eigenvalue` | Eigenvalue | A scalar reflecting variance explained along an uncorrelated principal axis of the correlation matrix. | $\det(\Sigma - \lambda I) = 0$ | `effective_number_of_bets`, `correlation` |
| [ ] PENDING | `score_change` | Score change | The net shift in total risk score between successive evaluation dates decomposed into components. | $\Delta S = S_t - S_{t-1}$ | `risk_score`, `component_weight` |

---

## 3. Explanation Template Catalog Review

### 3.1 Risk Component Explainer (`explain_component_templates:1.0.0`)
- **Headline:** `{component_label} for {symbol}`
- **Value Sentence:** `The stored component value was {raw_value}{unit_suffix}.`
- **Percentile Sentence:** `The value ranked at the {percentile}th percentile in its scoring peer set.`
- **Points Sentence:** `The component received {points} risk points before dimension aggregation.`
- **Direction & Weight:** `Its configured direction was {direction_label} and its component weight was {weight}.`
- **Status & Age:** `Its stored status was {status}, with data age of {data_age_days} days.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.2 Minimum Spanning Tree Explainer (`mst_explain_templates:1.2.0`)
- **Edge Headline:** `Why {a} and {b} are linked in the stored MST`
- **Kruskal Sentence:** `The edge was accepted at Kruskal step {step} of {edge_count}; it joined stored groups of {left_size} and {right_size} stocks at distance {distance}.`
- **Strength Sentence:** `{a} moves together with {b} at stored correlation {correlation}; the configured distance formula gives {distance}.`
- **Beta Sensitivity:** `Across {observations} stored observations, when {a} moved 10%, {b} moved about {ten_percent_effect}% on average; R-squared was {r_squared_pct}%.`
- **Tree Path:** `The stored tree path has {hop_count} links: {path}; its weakest link has correlation {weakest_correlation}.`
- **Hub Definition:** `A hub is connected to several tree neighbours and may be inspected as a possible statistical transmission channel; this is not a causal claim.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.3 Sector Divergence Explainer (`explain_sector_rules:1.0.0`)
- **Headline:** `{symbol} vs {industry} Sector Divergence Analysis ({horizon}-day horizon)`
- **Peer Dispersion:** `Peer 20-day return dispersion is {dispersion} percentage points across {peer_count} eligible peers.`
- **Regression Residual:** `The 1-day standardized residual is {z_1} (residual log return {residual_1}) against an expected return of {expected_return}.`
- **Divergence Assessment:** `{symbol} is categorized as {band_text} ({direction_text}) with 20-day divergence score {z_20}.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.4 Shock Simulation Explainer (`explain_shock_templates:1.0.0`)
- **Headline:** `Scenario Shock Transmission for {holding} under {shock_pct}% Shock to {shocked_symbol}`
- **Scenario Impact:** `Holding {holding} has an estimated scenario impact of {impact_pct}% under a {shock_pct}% shock to {shocked_symbol}.`
- **Sensitivity:** `The sensitivity of {holding} to {shocked_symbol} is {sensitivity} ({sensitivity_type}), where higher positive values indicate it moves together with {shocked_symbol}.`
- **R-squared:** `The historical co-movement explains an R-squared of {r_squared_pct}% of {holding}'s return variance over the trailing window.`
- **Loss Contribution:** `Holding {holding} has a portfolio weight of {weight_pct}%, contributing {contribution_pct}% to total portfolio loss.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.5 Portfolio Diversification Explainer (`explain_diversification_templates:1.0.0`)
- **Headline:** `Portfolio Diversification & Effective Number of Bets Analysis`
- **Entropy ENB:** `The portfolio has an Effective Number of Bets (ENB) of {enb_entropy:.2f} based on risk-contribution entropy across {holding_count} holdings.`
- **Eigenvalue ENB:** `Principal component eigenvalue decomposition indicates an effective diversification dimensionality of {enb_eigen:.2f} uncorrelated risk factors.`
- **Dominant Clusters:** `Risk concentration is dominated by {dominant_cluster}, representing {dominant_weight:.1f}% of total cluster risk.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.6 Score Change Explainer (`explain_score_change_templates:1.0.0`)
- **Headline:** `Risk Score Shift Decomposition for {symbol} ({start_date} to {end_date})`
- **Net Delta:** `The total risk score shifted by {delta:+.1f} points from {previous_score:.1f} to {current_score:.1f}.`
- **Primary Driver:** `Primary risk driver shift: {top_driver_name} ({top_driver_delta:+.2f} points, {top_driver_percent:+.1f}% percentile change).`
- **Secondary Driver:** `Secondary component shift: {second_driver_name} ({second_driver_delta:+.2f} points).`
- **Review Status:** [ ] PENDING OWNER APPROVAL

### 3.7 Alert Explainer (`explain_alert_templates:1.0.0`)
- **Headline:** `Alert Explanation: {rule_label}`
- **Condition Sentence:** `Alert triggered by condition: {reason}.`
- **Threshold Comparison:** `The observed metric was {observed_value} against a configured threshold of {threshold_value}.`
- **Review Status:** [ ] PENDING OWNER APPROVAL

---

## 4. Wording Bands & Numeric Calibration

| Parameter Domain | Quantitative Range | Display Label / Wording | Review Status |
| :--- | :--- | :--- | :--- |
| Correlation Strength | $[0.0, 0.2)$ | `very weak` | [ ] PENDING |
| Correlation Strength | $[0.2, 0.4)$ | `weak` | [ ] PENDING |
| Correlation Strength | $[0.4, 0.6)$ | `moderate` | [ ] PENDING |
| Correlation Strength | $[0.6, 0.8)$ | `strong` | [ ] PENDING |
| Correlation Strength | $[0.8, 1.0]$ | `very strong` | [ ] PENDING |
| Rolling Stability | $\ge 0.65$ | `high stability` | [ ] PENDING |
| Rolling Stability | $[0.45, 0.65)$ | `medium stability` | [ ] PENDING |
| Rolling Stability | $< 0.45$ | `low stability` | [ ] PENDING |
| Sector Trend | $> +1.5\%$ | `up` | [ ] PENDING |
| Sector Trend | $< -1.5\%$ | `down` | [ ] PENDING |
| Sector Trend | $[-1.5\%, +1.5\%]$ | `flat` | [ ] PENDING |
| News Impact Severity | $\ge 7.0$ | `high exposure` | [ ] PENDING |
| News Impact Severity | $[4.0, 7.0)$ | `medium exposure` | [ ] PENDING |
| News Impact Severity | $< 4.0$ | `low exposure` | [ ] PENDING |

---

## 5. Seeded Regulatory Policy Rules & Rationales

All policy rules seeded in migration `9a0b1c2d3e09_step_09_policy_engine.py` are designated with reviewer status `UNREVIEWED_SEED`. None are marked approved.

| Rule Key | Agency | Event Type | Default Severity | Reviewer Status | Owner Approval |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RBI_REPO_RATE_HIKE` | RBI | `policy_rate_change` | 8.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `RBI_REPO_RATE_CUT` | RBI | `policy_rate_change` | 7.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `RBI_REPO_RATE_PAUSE` | RBI | `policy_rate_change` | 4.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `RBI_CRR_HIKE` | RBI | `reserve_ratio_change` | 8.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `RBI_CRR_CUT` | RBI | `reserve_ratio_change` | 6.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `SEBI_MARGIN_DERIVATIVES` | SEBI | `margin_framework` | 7.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `SEBI_ASM_SURVEILLANCE` | SEBI | `surveillance_action` | 6.0 | `UNREVIEWED_SEED` | [ ] PENDING |
| `SEBI_INSIDER_TRADING` | SEBI | `enforcement_order` | 5.0 | `UNREVIEWED_SEED` | [ ] PENDING |

**Owner Action Required:** The owner must inspect each transmission rationale and assign formal reviewer sign-off prior to production promotion.

---

## 6. News Impact Configuration Review

- **Recency Decay Half-Life:** `7.0 days` (exponential decay: $e^{-\lambda \cdot t}$, $\lambda = \frac{\ln(2)}{7.0}$)
- **Path Transmission Weights:**
  - `direct_entity`: 1.00
  - `first_order_supplier_customer`: 0.70
  - `sector_industry`: 0.60
  - `mst_network_spillover`: 0.40
- **Spillover R-Squared Floor:** `0.20`
- **Minimum Confidence to Display:** `0.40`
- **Review Status:** [ ] PENDING OWNER APPROVAL (Tracked in `PROPOSED_DECISIONS.md` as PD-34)
