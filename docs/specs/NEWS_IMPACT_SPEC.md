# PRISM Specification: News Impact & Transmission Engine (Step E4)

## 1. Overview and Authority
- **Authority:** `PRISM_SRS.md` (FR-D7, FR-P7, FR-P8, Section 10). Governed by `docs/agent/MASTER_CONTEXT.md` rules D1 (config-driven), D3 (result envelope), D8 (evidence-bound explanations), D9 (non-causal language, no advice), D10 (test isolation), and D11 (no fixture data in production).
- **Status:** **DRAFT** pending owner approval. Configuration stored under `news_impact:1.0.0` with status `draft`.
- **Core Principle:** News impact models *possible transmission effects* through formal regulatory rules, historical macro sensitivities, and network comovement. It is strictly descriptive and scenario-based. It does **not** forecast future prices, generate price targets, or provide investment recommendations.

---

## 2. Transmission Paths

Every affected entity is identified through one or more of four formal transmission channels:

### 2.1 Direct Path
- **Trigger:** An allowlisted news item explicitly references a company entity (verified by ISIN / Symbol / Company Name in `news_security_link`).
- **Direction:** `ambiguous` (unless signed by a verified sentiment/event model).
- **Default Severity:** Configurable, default `5.0 / 10.0`.
- **Signal Strength:** Match confidence of entity link $[0.0, 1.0]$.
- **Base Confidence:** `0.95`.

### 2.2 Rule Path
- **Trigger:** An allowlisted news item triggers an active policy rule in `policy_rule` via keyword/regex matching (`jobs/match_policy.py`).
- **Mapping:** Policy rule specifies affected industries, transmission direction (`tailwind`, `headwind`, `ambiguous`), severity $[1, 10]$, and economic rationale.
- **Signal Strength:** `1.0`.
- **Base Confidence:** `0.85`.
- **Unreviewed Rule Penalty:** `-0.25` applied to confidence if `reviewer` is empty or `"UNREVIEWED"`.

### 2.3 Macro Path
- **Trigger:** A policy rule contains `macro_series_links` mapping the event to an underlying macro factor (e.g. `IN_REPO_RATE`, `IN_INFLATION_CPI`, `USD_INR`) with an expected direction (`up` / `down`).
- **Mapping:** Industry sensitivities evaluated from Step 9 `sector_macro_sensitivity` where `is_significant = true`.
- **Direction:** Product of expected macro direction and historical industry beta.
- **Signal Strength:** $\min(1.0, |\beta|)$.
- **Base Confidence:** `0.70`.

### 2.4 Spillover Path
- **Trigger:** A stock that does not have a direct link comoves strongly with a directly impacted stock.
- **Model:** 120-day trailing regression beta ($\beta$) and Pearson correlation coefficient ($\rho$).
- **Eligibility Floor:** $R^2 = \rho^2 \ge \text{spillover\_min\_r\_squared}$ (default `0.25`). Pairs below the floor are strictly excluded.
- **Signal Strength:** $\min(1.0, R^2)$.
- **Base Confidence:** `0.65`.

---

## 3. Mathematical Formulation

### 3.1 Recency Decay
News impact decays exponentially with age:
$$\text{decay}(t) = 0.5^{\frac{\max(0, \text{age\_days})}{t_{\text{half-life}}}}$$
Where default half-life $t_{\text{half-life}} = 30.0$ days.

### 3.2 Path Exposure Score
For any individual candidate path $p$:
$$\text{Exposure}_p = \min\left(1.0, \frac{\text{severity}}{10} \times w_{\text{path}} \times \text{decay} \times \text{signal\_strength}\right)$$

Default path weights ($w_{\text{path}}$):
- Direct: `1.00`
- Rule: `0.85`
- Macro: `0.70`
- Spillover: `0.60`

### 3.3 MAX Combination Rule
When an entity is affected via multiple transmission paths, path exposures are combined using **MAX**, never a sum:
$$\text{Exposure}_{\text{stock}} = \max_{p \in \text{paths}}(\text{Exposure}_p)$$
*Rationale:* MAX prevents double-counting across correlated transmission channels.

### 3.4 Exposure Bands
Exposure scores are partitioned into three qualitative bands:
- **Low:** $[0.00, 0.35)$
- **Medium:** $[0.35, 0.65)$
- **High:** $[0.65, 1.00]$

### 3.5 Display Filter
A stock or news item is displayed in user-facing views only if:
$$\text{Confidence} \ge \text{minimum\_confidence\_to\_display} \quad (\text{default } 0.40)$$

---

## 4. Historical Reaction Requirement

Historical reaction is **never invented or assumed**.
- To display a historical market reaction, there must exist at least $N = 10$ prior analogues in `policy_event` strictly before the item's publication date:
  $$N_{\text{analogues}} \ge \text{historical\_min\_analogues}$$
- If $N_{\text{analogues}} \ge 10$, the engine reports the average abnormal industry return across horizons:
  $$\bar{R}_{\text{abnormal}}(h) \quad \text{for } h \in \{0, 1, 5\} \text{ days}$$
- If $N_{\text{analogues}} < 10$, the engine must display:
  $$\text{"insufficient history (n=} N_{\text{analogues}}\text{)"}$$

---

## 5. Worked Numeric Example

Suppose a regulatory announcement is published by RBI:
- **Headline:** *"RBI increases risk weights on unsecured retail loans by 25 basis points"*
- **Age:** 15 days ($t_{\text{half-life}} = 30$ days).
  $$\text{decay} = 0.5^{15 / 30} = 0.5^{0.5} \approx 0.7071$$

### Channel 1: Rule Path (Private Banks)
- Matched Rule: `RBI_UNSECURED_LENDING_OCT23` (Reviewer: `UNREVIEWED`).
- Severity: `8.0 / 10.0`.
- Path Weight: `0.85`.
- Signal Strength: `1.0`.
$$\text{Exposure}_{\text{rule}} = \frac{8.0}{10} \times 0.85 \times 0.7071 \times 1.0 = 0.68 \times 0.7071 = 0.4808$$
- Confidence: Base `0.85` - Penalty `0.25` (Unreviewed) = `0.60` $\ge 0.40$ (Visible).

### Channel 2: Spillover Path (NBFC peer)
- NBFC comoves with private bank with $\rho = 0.60 \implies R^2 = 0.36 \ge 0.25$ (Eligible).
- Path Weight: `0.60`.
- Signal Strength: $R^2 = 0.36$.
$$\text{Exposure}_{\text{spillover}} = \frac{8.0}{10} \times 0.60 \times 0.7071 \times 0.36 = 0.48 \times 0.7071 \times 0.36 = 0.1222$$
- Confidence: $\min(0.65, 0.36) = 0.36 < 0.40$ (Filtered out for direct display).

### Combination:
$$\text{Combined Exposure} = \max(0.4808, 0.1222) = 0.4808 \implies \mathbf{Medium \ Band}$$

---

## 6. Risk Considerations Templates (No Advice Rule D9)

Considerations sentences are strictly templated from evidence:
1. *"Check the portfolio weight held in the affected industries."*
2. *"Review whether exposed holdings share an MST cluster with a directly named stock."*
3. *"Monitor the linked macro indicators and their current stored regime."*

Banned phrases: `buy`, `sell`, `hold`, `target price`, `will rise`, `will fall`, `guaranteed`, `caused by`.

---

## 7. Methodological Limitations

Every explanation carries mandatory limitations:
1. *"Possible effects come from versioned rules and stored statistical relationships; they are not predictions or investment advice."*
2. *"Rules marked UNREVIEWED receive lower confidence."*
3. *"Co-movement and shared clusters do not prove a business relationship or causation."*
4. *"Prices are end-of-day, not real-time."*
5. *"Regulatory disclaimer: PRISM provides descriptive risk explanations, not investment advice or price predictions."*
