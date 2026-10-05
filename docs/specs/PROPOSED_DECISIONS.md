# PRISM Proposed Decisions

This file records decisions proposed by the implementation team for inclusion in
SRS Section 17.  A proposed decision becomes authoritative only after the
project owner reviews and approves it and it is added to PRISM_SRS.md.

**Do not edit PRISM_SRS.md directly.  Add entries here and ask for review.**

---

## Proposed decisions from Step 0b (2026-10-04)

### PD-1 — Walk-forward and purged split utilities reside in `backend/app/validation/`

**Proposed by:** Implementation  
**Date:** 2026-10-04  
**Status:** Proposed (pending review)

**Statement:**
The walk-forward and purged K-fold split utilities (`walk_forward_splits`,
`purged_kfold`) are implemented as pure Python functions in
`backend/app/validation/splits.py`.  They accept no `shuffle` argument and raise
`ValueError` for unsorted input, satisfying SRS Section 16 requirement *"Walk-
forward validation utilities prohibit shuffled evaluation."*

**Rationale:**
A dedicated validation package makes the time-ordering contract explicit and
discoverable.  Keeping it in the backend package (not in notebooks or scripts)
ensures CI covers the tests automatically.

**Impact:**
None on existing code.  Additive module only.

---

### PD-2 — Last-known-good is enforced at the per-symbol commit boundary

**Proposed by:** Implementation  
**Date:** 2026-10-04  
**Status:** Proposed (pending review)

**Statement:**
SRS Section 14.2 rule *"Do not replace a last-known-good dataset with an
incomplete run"* is enforced by `ingest_nifty200_prices` through per-symbol
transaction isolation: if a provider or database exception occurs for symbol B,
`session.rollback()` is called before recording the failure, so symbol B rows
are never committed.  Symbol A rows (already committed in their own transaction)
are unaffected.  This is now documented and tested in
`tests/market_data/test_service.py`.

**Rationale:**
The rollback pattern was already in the code; the test makes the guarantee
explicit and regression-proof.

**Impact:**
No change to `service.py`.  Additive test file only.

---

### PD-3 — CI uses `astral-sh/setup-uv` and no real database connection

**Proposed by:** Implementation  
**Date:** 2026-10-04  
**Status:** Proposed (pending review)

**Statement:**
The GitHub Actions CI workflow installs `uv` via the official
`astral-sh/setup-uv@v4` action.  All Python tests run with either in-memory
SQLite or pure unit mocks; no real PostgreSQL service container is required.
`mypy` is run on `backend/` and `jobs/` only (not tests) because the
pre-existing `import-untyped` pandas error in test files is a known issue
requiring `pandas-stubs` installation.

**Rationale:**
Avoiding a real database in CI keeps the workflow fast, free, and free of
secrets.  The mypy scope boundary is documented to avoid confusion.

**Impact:**
Adds `.github/workflows/ci.yml`.  No change to production code.

---

## Proposed decisions from Step 1 (2026-10-04)

### PD-4 — 8-Dimension Risk Score Formulation & Default Starting Weights

**Proposed by:** Step 1 Requirements  
**Date:** 2026-10-04  
**Status:** Approved by User (2026-10-04)

**Statement:**
The risk score $S \in [0, 100]$ aggregates 8 core dimensions with default starting weights:
- Market: 25
- Fundamentals: 20
- Liquidity: 10
- Structure (MST/Network): 10
- Relative (Sector Divergence): 10
- Governance: 10
- Events: 10
- Macro: 5
(Total: 100).
Within each dimension, active components are equal-weighted by default. Components use weak empirical percentile ranking across the universe (or industry for industry-scoped components with $\ge 5$ peers). Missing dimensions/components are dropped and remaining weights are re-normalised. Weights are initial baseline values, NOT fitted to past returns. Every score result envelope provides component-level point contributions and top-3 driver reasons.

**Decision Outcome:**
Approved by user on 2026-10-04.

---

### PD-5 — 6-Factor Confidence Engine & Hard Integrity Caps

**Proposed by:** Step 1 Requirements  
**Date:** 2026-10-04  
**Status:** Approved by User (2026-10-04)

**Statement:**
Confidence $C \in [0, 100]$ is computed as $100 \times \text{weighted mean}$ of 6 factors in $[0, 1]$ (default equal weights $1/6$):
1. `data_coverage` (available dimension weight ratio)
2. `data_freshness` (calendar decay against maximum allowed age)
3. `source_agreement` (cross-check concordance)
4. `signal_agreement` (directional alignment across horizons)
5. `model_stability` (structural metric / observation completeness)
6. `evidence_volume` (sample size vs target requirements)

**Mandatory Integrity Caps:**
1. Stale price data (no active price for $\ge 5$ trading days) hard-caps final confidence at $50.0$.
2. Low data coverage ($F_{\text{coverage}} < 0.70$) hard-caps final confidence at $60.0$.

**Decision Outcome:**
Approved by user on 2026-10-04.

---

### PD-6 — Configuration-Driven Persistence and Component Registry Architecture

**Proposed by:** Step 1 Requirements  
**Date:** 2026-10-04  
**Status:** Proposed (implemented)

**Statement:**
All risk model configurations are persisted in `model_config` with canonical SHA-256 JSON checksums and versioning (`draft`, `approved`, `retired`). Risk components are registered in `score_component_definition` implementing the Python `Component` protocol. Adding or reweighting a component requires zero modifications to the core scoring engine, API schemas, or UI. Auditing is provided via `audit_log`.

---

## Proposed decisions from Step 2 (2026-10-05)

### PD-7 — Official Quarterly Filings for Shares Outstanding & Point-in-Time Market Cap (SRS OQ-8)

**Proposed by:** User clarification & Step 2 Requirements  
**Date:** 2026-10-05  
**Status:** Approved by User (2026-10-05)

**Statement:**
1. **Shares Outstanding Source (SRS OQ-8):** Official NSE/BSE quarterly shareholding filings archived point-in-time via manual or scheduled CSV import (`security_share_count`).
2. **Point-in-Time Constraint (D4):** Shares count records carry both `as_of` (quarter period end) and `published_at` (actual corporate filing timestamp). A filing is NEVER back-filled or utilized for dates earlier than its `published_at`.
3. **Market Cap & Liquidity Derivations:**
   - $\text{traded\_value} = \text{close} \times \text{volume}$
   - $\text{adv\_20} = \text{rolling 20-day mean of traded\_value}$
   - $\text{market\_cap} = \text{adjusted close} \times \text{shares\_outstanding (point-in-time effective)}$
   - Liquidity anomalies flagged: `zero_volume_days` and `thin_trading` ($\text{adv\_20} < \text{INR 10,000,000}$).
4. **Data Cross-Check & Quality Policy (FR-D9, NFR-9):**
   - Independent verification against official exchange daily series or secondary provider.
   - Record discrepancies in `data_crosscheck` with relative difference $\text{rel\_diff} = |A - B| / \text{mean}(A, B)$.
   - Report mismatch rate and worst offenders; STRICTLY DO NOT auto-correct price records.

---

## Proposed decisions from Step 3 (2026-10-05)

### PD-8 — Single Local User Mode Privacy Limitation (SRS NFR-7)

**Proposed by:** Implementation & Step 3 Specification  
**Date:** 2026-10-05  
**Status:** Proposed (pending review)

**Statement:**
Portfolio tables (`portfolio`, `portfolio_holding`, `portfolio_risk_run`) include an `owner_ref` column (defaulting to `'local-user'`) to logically partition user data without requiring full authentication infrastructure at Step 3. As documented in SRS NFR-7, until multi-tenant auth is implemented in a future phase, portfolio data resides without cryptographically enforced access control.

**Rationale:**
Allows smooth future migration to multi-tenant user authentication without breaking schema changes.

---

### PD-9 — Euler Risk Decomposition and Explicit Cash Drag Treatment

**Proposed by:** Implementation & PORTFOLIO_MATH_SPEC.md  
**Date:** 2026-10-05  
**Status:** Proposed (pending review)

**Statement:**
1. All portfolio assets (including `CASH` with zero volatility and zero correlation with risky assets) participate in Euler risk decomposition.
2. Residual weight when user weights $< 1.0$ is automatically attributed to `CASH` to preserve exact cash drag without leverage inflation.
3. Percentage Risk Contributions ($PRC_i = w_i (\Sigma w)_i / \sigma_p^2$) strictly sum to $1.0$, and Marginal Risk Contributions ($MRC_i = (\Sigma w)_i / \sigma_p$) satisfy $\sum w_i MRC_i = \sigma_p$.
4. Covariance matrices computed via Ledoit-Wolf shrinkage are stored as Parquet files with content SHA-256 in `analytics_artifact`.

---

## Proposed decisions from Step 4 (2026-10-05)

### PD-10 — MST Diagnostics, Stability Scoring, Deterministic Clustering, and Residual Variant

**Proposed by:** Step 4 Requirements  
**Date:** 2026-10-05  
**Status:** Implemented & Verified (pending owner review)

**Statement:**
1. **Layer 2 Code Immutability:** The approved `correlation-mst-v1` implementation in `backend/app/correlation_mst/` is completely untouched (zero git diff). All diagnostics, rolling stability tracking, clustering, and residual variant generation reside in `backend/app/mst_diagnostics/`.
2. **Residual Variant Formulation:** Point-in-time OLS market model regression against `NIFTY 200` benchmark ($r_{i,t} = \alpha_i + \beta_i r_{m,t} + \epsilon_{i,t}$) removes market factor co-movement ($\text{Cov}(\epsilon_i, r_m) = 0$). Synthetic prices $P_t = P_{t-1} \cdot \exp(\epsilon_t)$ feed the unchanged Layer 2 calculator, stored under variant label `"residual"`.
3. **Default Variant:** Maintained as `"raw"` in `model_config` and UI default, subject to user review.
4. **Deterministic Clustering ($k$-Cut):** Removes top $k$ longest edges sorted deterministically by `distance DESC, symbol_a ASC, symbol_b ASC`. Connected components define `cluster_id` (`CLUST-01`, `CLUST-02`), ordered by `size DESC, min_symbol ASC`.
5. **Node Metrics & Hub Ranking:** Node degree, weighted centrality ($\sum \rho_{uv}$ on incident tree edges), and hub rank ordered by `degree DESC, weighted_centrality DESC, symbol ASC`.
6. **Stability Grading:** Consecutive window edge persistence $|E_t \cap E_{t-1}| / |E_t|$ classified into HIGH ($\ge 0.65$), MEDIUM ($\ge 0.45$), or LOW ($< 0.45$).
7. **Descriptive Non-Causal Presentation:** MST relationships and clusters are explicitly framed as descriptive co-movement subgraphs, not causal connections or industrial classifications.

---

## Proposed decisions from Step 5 (2026-10-05)

### PD-11 — Step 5 Risk Engine Architecture & Component Protocol

**Proposed by:** Step 5 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending owner review)

**Statement:**
1. **Component Protocol & Generic Result Envelope (D1–D5):**
   - Every risk component implements `RiskComponent` protocol accepting `(as_of, universe, context)` and returning `list[ComponentValue]`.
   - The UI and API result envelope (`get_stock_risk_envelope`) generically dynamically render all registered components directly from `score_component_definition` without hardcoding specific component keys.
   - Any uncomputed, inactive, or missing component renders gracefully as `"Not yet available"`.
2. **Benchmark Stable ID Lookup:**
   - All benchmark queries across the entire backend (portfolio beta, risk scores, helper functions, and MST residual variant) strictly lookup the benchmark by its unique stable ID `NIFTY_200` from configuration, never by human-readable display names.
3. **No Silent Fallback Behavior:**
   - If benchmark data is unavailable or empty, `BetaToBenchmarkComponent` strictly assigns `status = "missing"` with `evidence_ref={"reason": "benchmark_unavailable"}` to all stocks.
   - No equal-weight market return or secondary index substitute is silently introduced.
4. **Idempotent MST Diagnostics CLI Job:**
   - `jobs/calculate_mst_diagnostics.py` runs diagnostics across the historical window series (`--history N`, default 26), computes stability, clustering, and centrality node metrics for both raw and residual MST variants, records a `PipelineRun` manifest, and ensures complete idempotency without duplicate DB rows.

---

### PD-12 — NIFTY 200 Benchmark Sourcing & Internal Consistency Verification

**Proposed by:** Step 5 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending owner review)

**Statement:**
1. **Single Source (Yahoo Finance `^CNX200`):**
   - The NIFTY 200 benchmark series is retrieved via `yfinance.Ticker("^CNX200").history(period="max", interval="1d", auto_adjust=False)`.
   - The series represents the NIFTY 200 PRICE index (not Total Return Index). The benchmark definition description is explicitly set to:
     `"NIFTY 200 PRICE index, single source Yahoo Finance ^CNX200 (unofficial), internally verified, not independently cross-checked."`
2. **Timezone & Calendar Integrity:**
   - Timestamps are converted to exchange-local calendar dates (`Asia/Kolkata`) without date shifting.
   - Partial bars for today's date are excluded; non-positive and NaN closes are dropped.
3. **Internal Consistency Verification & PASS RULES:**
   - Production benchmark ingestion (`jobs/ingest_benchmark.py`) defaults to DRY-RUN mode.
   - Data is only persisted when `--apply` is passed AND all 7 exact PASS RULES hold:
     - Rule 1 (Historical coverage): Start date $\le$ 2015-03-31.
     - Rule 2 (Data validity): 0 duplicate dates, 0 non-positive closes.
     - Rule 3 (Calendar alignment): $\le 1\%$ of $D_u$ missing from benchmark, $\le 1\%$ of benchmark dates outside $D_u$.
     - Rule 4 (Correlation): Overall Pearson correlation with equal-weighted NIFTY 200 proxy $\ge 0.95$; each full calendar year $\ge 0.90$.
     - Rule 5 (Stale data): No more than 3 consecutive identical closes.
     - Rule 6 (Extreme movement): Max 1-day move $\le 25\%$; moves $> 7\%$ flagged for review.
     - Rule 7 (Freshness): Benchmark latest date within 3 calendar days of latest stock price date.
   - If any PASS RULE fails, zero rows are written and the job exits with a full diagnostic report (`docs/evidence/benchmark_check.md`).
4. **Single-Source Risk & Future Mitigation:**
   - Relying on Yahoo Finance `^CNX200` poses single-source operational risk. Risk reduction through a secondary independent source (such as direct NSE Bhavcopy or official Nifty Indices daily CSV archives) should be scheduled for future procurement.

---

## Proposed decisions from Step 6 (2026-10-05)

### PD-13 — Portfolio Diversification & Effective Number of Bets (ENB) Formulation (SRS OQ-5)

**Proposed by:** Step 6 Implementation  
**Date:** 2026-10-05  
**Status:** Approved by User (2026-10-05)

**Statement:**
1. **Primary ENB Formulation:** Risk-contribution entropy $\text{ENB}_{\text{entropy}} = \exp\left(-\sum_{i=1}^N p_i \ln p_i\right)$, where $p_i$ is the normalized positive percentage risk contribution of asset $i$, is adopted as the primary diversification metric for all portfolios.
2. **Secondary ENB Formulation:** Eigenvalue decomposition $\text{ENB}_{\text{eigen}} = \left(\sum_{i=1}^N \lambda_i\right)^2 / \sum_{i=1}^N \lambda_i^2$ on the shrunk correlation matrix is computed and displayed alongside for spectral structural comparison.
3. **Cluster Concentration Analysis:** Portfolio holdings are mapped against Layer 2 MST clusters (`correlation-mst-v1`). Any cluster with $\ge 40\%$ aggregate weight is flagged as concentrated.
4. **Candidate Suggestions Language:** Universe assets with low average correlation ($\le 0.30$) and sufficient liquidity/confidence ($\text{confidence} \ge 60$, $\text{ADV}_{20} \ge 10\text{M INR}$) are surfaced under the strict rationale: *"Adding {SYMBOL} would reduce concentration in cluster {C} due to low correlation ({R}) with portfolio holdings."* In accordance with PRISM descriptive risk principles, investment advice terms such as `"buy"` or `"invest"` are strictly prohibited.

---

### PD-14 — Stress Shock Simulator & Propagation Methodology (SRS OQ-6)

**Proposed by:** Step 6 Implementation  
**Date:** 2026-10-05  
**Status:** Approved by User (2026-10-05)

**Statement:**
1. **Default Propagation Mechanism:** Pairwise regression beta $\beta_{j,s} = \text{Cov}(r_j, r_s) / \text{Var}(r_s)$, computed from 252-day daily log returns, serves as the default stress propagation method.
2. **Optional Tree Decay Mode:** Users may optionally simulate stress along the unique Minimum Spanning Tree path with edge correlation product attenuation: $D_{s,j} = \prod_{(u,v) \in P(s,j)} \max(0, \rho_{u,v})$.
3. **Mandatory Disclaimer Banner:** All stress shock simulation outputs, whether API responses or UI screens, prominently display:
   > *"Scenario estimate, not a prediction. Hypothetical stress scenarios model historical co-movement and statistical sensitivities. They do not constitute forward price forecasts, guarantees, or investment advice."*
4. **Permitted Shock Bounds:** Exogenous shocks are strictly bounded in $[-50\%, +50\%]$ to prevent unrealistic mathematical extrapolations of linear models.

---

## Proposed decisions from Step 9 (2026-10-05)

### PD-15 — Macroeconomic Series Selection & Source Ingestion Strategy (SRS OQ-10)

**Proposed by:** Step 9 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
Resolving SRS Open Question OQ-10, five macroeconomic and market-wide series are approved for production ingestion and dynamic sector risk mapping:
1. **Brent Crude Oil (`crude_oil`):** Primary adapter via Yahoo Finance `BZ=F`, daily USD/barrel. Fallback via `data/macro/crude_oil.csv`. Licensing: Public market quote / non-redistributed research data. Publication lag: $T+0$ post-London close.
2. **USD/INR Exchange Rate (`usd_inr`):** Primary adapter via Yahoo Finance `INR=X` / RBI reference rate, daily INR per USD. Fallback via `data/macro/usd_inr.csv`. Licensing: Public open exchange rate. Publication lag: $T+0$ at 13:30 IST.
3. **India 10-Year Benchmark Yield (`in_10y_yield`):** Primary adapter via CCIL/FIMMDA / Yahoo Finance `^IN10YT=RR`, daily annualized yield percent. Fallback via `data/macro/in_10y_yield.csv`. Licensing: Public benchmark sovereign yield curve. Publication lag: $T+0$ post-17:00 IST.
4. **India VIX (`india_vix`):** Primary adapter via Yahoo Finance `^INDIAVIX` / NSE India daily indices, implied volatility index level. Fallback via `data/macro/india_vix.csv`. Licensing: NSE public market index. Publication lag: $T+0$ post-market.
5. **FII / DII Net Institutional Flows (`fii_dii_net_flows`):** Ingested via exchange daily summary reports and fallback `data/macro/fii_dii_net_flows.csv`, daily net institutional flow in INR crores. Licensing: NSE/BSE daily trade bulletin. Publication lag: $T+0$ post-market.

All series are ingested through the `MacroSeriesAdapter` protocol into immutable, append-only `macro_observation` tables with strict point-in-time auditing (`obs_date`, `value`, `published_at`, `ingested_at`, `version`).

---

### PD-16 — Rule-Based Market Regime Classification & Hysteresis State Machine (FR-F4)

**Proposed by:** Step 9 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Classification Inputs:**
   - Market Realised Volatility Percentile ($P_{\text{vol}}$): 21-day rolling annualized volatility of equal-weighted market returns ranked against trailing 252-day history.
   - Average Pairwise Correlation Percentile ($P_{\text{corr}}$): Median pairwise return correlation of top universe assets ranked against trailing 252-day history.
   - India VIX Level: Daily index close (where available).
2. **Deterministic Classification Rules:**
   - `stressed`: $P_{\text{vol}} \ge 80.0$ OR $P_{\text{corr}} \ge 80.0$ OR $\text{VIX} \ge 24.0$. Regime Risk Multiplier: $1.50\times$.
   - `trending`: (Not stressed) AND ($P_{\text{vol}} \ge 50.0$ OR $P_{\text{corr}} \ge 50.0$ OR $\text{VIX} \ge 18.0$). Regime Risk Multiplier: $1.25\times$.
   - `calm`: $P_{\text{vol}} < 50.0$ AND $P_{\text{corr}} < 50.0$ AND $\text{VIX} < 18.0$. Regime Risk Multiplier: $1.00\times$.
3. **Exit Hysteresis State Machine:**
   To prevent rapid regime oscillation (whipsawing), a market classified as `stressed` cannot transition to `trending` or `calm` unless all regime indicators remain below the exit thresholds ($P_{\text{vol}} < 75.0$, $P_{\text{corr}} < 75.0$, $\text{VIX} < 22.0$) for at least **5 consecutive trading days**.
4. **Point-in-Time Transparency:**
   Each state is logged to `market_regime` with exact feature payloads, timestamps, and config versions.

---

### PD-17 — Sector Rolling Macro Sensitivity & Statistical Insignificance Filter

**Proposed by:** Step 9 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Rolling OLS Sensitivity:** For each of the 18 Layer 1 industry groups, equal-weighted daily returns are regressed over a 63-day rolling window on daily deltas of each macro series:
   $$r_{\text{ind}, t} = \alpha + \beta_s \cdot \Delta m_{s, t} + \epsilon_t$$
2. **Insignificance Policy (No Forced Exposure):**
   Only sensitivities achieving two-tailed statistical significance at the 5% level ($|t| \ge 1.96$, $p \le 0.05$) with sufficient sample size ($N \ge 30$) are marked significant (`is_significant = true`).
3. **Macro Component Formula:**
   For any stock $i$ in industry $k$, its raw macro risk contribution is formulated as:
   $$\text{macro\_exposure}_i = \left(\sum_{s=1}^5 |\beta_{k, s} \cdot \mathbf{1}_{\text{significant}}| \times |z_s|\right) \times M_{\text{regime}}$$
   where $z_s = \frac{\Delta_{21, s}}{\sigma_{252, s} \cdot \sqrt{21}}$ is the standardized 21-day move of factor $s$, and $M_{\text{regime}}$ is the active regime multiplier. Insignificant sensitivities are assigned zero weight, strictly preventing spurious factor risk allocations.
4. **Descriptive Non-Causal Mandate:**
   Macro sensitivities reflect statistical historical co-movement and are never framed or presented as causal drivers or forward price predictions.

---

## Proposed decisions from Step 10 (2026-10-05)

### PD-18 — Canonical Announcement Classification & Security Linking Priority (D1, D4)

**Proposed by:** Step 10 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Dynamic Event Rules Engine:**
   Corporate announcements are classified into canonical event types (`regulatory_action`, `debt_rating`, `results`, `management_change`, `promoter_insider`, `ma_order`, `dividend`, `other`) and flagged for risk relevance and direction (`positive`, `negative`, `neutral`) using versioned database rows in `event_rule` (seeded from config, editable without code redeployment).
2. **Security Linking Hierarchy:**
   - Priority 1: Exact ISIN match (`isin_exact`). Highest confidence.
   - Priority 2: Exact exchange ticker symbol match (`symbol_exact`) via `security_alias`.
   - Priority 3: Legal entity name matching (`name_fallback`), stripped of standard corporate suffixes ("Limited", "Ltd", "Inc", "Corp"), flagged explicitly as a fallback.
   - Unmatched announcements are logged and excluded from scoring without failing the pipeline.
3. **Point-in-Time Trading Calendar Rollover:**
   Announcements published strictly after exchange market close (15:30 IST) or on non-trading days/weekends are assigned an `effective_trading_date` equal to the next valid session in `trading_calendar` (D4).

---

### PD-19 — Resolution of OQ-9: Explainable Event Importance Scoring Formula (D1, D3)

**Proposed by:** Step 10 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Importance Formula:**
   $$\text{importance} = \min\left(10.0, \max\left(1.0, \text{base\_weight} \times \text{magnitude\_multiplier}\right)\right)$$
2. **Base Categorical Weights:**
   - `regulatory_action`: 10.0
   - `debt_rating`: 8.5
   - `results`: 8.0
   - `management_change`: 7.0
   - `promoter_insider`: 6.5
   - `ma_order`: 5.0
   - `dividend`: 3.0
   - `other`: 2.0
3. **Magnitude & Severity Multipliers:**
   - Debt Default: $2.0\times$
   - Auditor Resignation: $1.5\times$
   - Regulatory Monetary Penalty / Warning: $1.5\times$
   - Credit Downgrade: $1.4\times$
   - CEO / CFO Resignation: $1.3\times$
   - Standard Filing: $1.0\times$
4. **Envelope Transparency (D3):**
   Every scored item stores `importance_components` detailing base weight, magnitude multiplier, parsed rationale, linking method, and rule key.

---

### PD-20 — Recency-Decayed Event Risk Pressure Component & Switchable FinBERT (D1, D2)

**Proposed by:** Step 10 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Event Risk Pressure Component (`event_risk_pressure`):**
   - Belongs to dimension `events` with a 10% weight in `prism-risk-score-v1`.
   - Computes recency-decayed pressure over trailing 90 days with a 14-day exponential half-life:
     $$w_i = 2^{-\Delta t_i / 14}$$
   - Gross negative pressure sums decayed importance of negative risk-relevant announcements:
     $$\text{GrossNeg} = \sum_{\text{neg}} \text{importance}_i \cdot 2^{-\Delta t_i / 14}$$
   - Positive announcements provide mitigation capped at 30% of gross negative pressure:
     $$\text{NetPressure} = \max\left(0, \text{GrossNeg} - \min\left(\text{PosMitigation}, 0.30 \times \text{GrossNeg}\right)\right)$$
2. **Switchable FinBERT Sequence Inference:**
   - Pinned revision: `ProsusAI/finbert` at `90eb618b0f7ca7067d2feae4d588523ee734c5db`.
   - Disabled by default via `model_config` (`finbert_enabled: false`) until explicitly approved by the user.
   - When disabled, uses a fast, deterministic, zero-dependency financial dictionary scorer with evidence sentence extraction.
   - Evaluation tooling and template created in `data/labelled/` and `backend/app/events/eval_finbert.py` for evaluating Indian market announcements.
3. **Descriptive Non-Causal Mandate & Disclaimer:**
   Event signals reflect descriptive corporate risk pressure. All frontend views and API envelopes prominently display: *"Markets may have already priced this in. PRISM event signals are descriptive risk indicators and not investment advice or price forecasts."*

---

## Proposed decisions from Step 11 (2026-10-05)

### PD-21 — Regulatory Press Releases Feed Strategy & Headline-Only Guardrail (FR-D9, OQ-7)

**Proposed by:** Step 11 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Primary Regulatory Feed Adapters:**
   - Reserve Bank of India (RBI): `https://www.rbi.org.in/pressreleases_rss.xml` (Monetary, Banking)
   - Securities and Exchange Board of India (SEBI): `https://www.sebi.gov.in/sebirss.xml` (Capital Markets)
   - Press Information Bureau (PIB): `https://pib.gov.in/rss/RssFinance.xml` (Macro, Trade, Infrastructure)
   - Resilient Fallback: `data/news/news.json` for deterministic offline verification and CI.
2. **Storage and Redistribution Boundary:**
   - Stored attributes are strictly restricted to `headline`, `url`, `source`, `published_at`, `ingested_at`, and `content_hash` (SHA-256).
   - Full article body text, editorial comments, or vendor wire text are strictly excluded from database models and API payloads.
3. **Idempotent Ingestion:**
   - Ingestion jobs enforce deduplication by `content_hash` across polling executions.

---

### PD-22 — Deterministic Policy-to-Sector Rules & Recency-Decayed Policy Risk Pressure (D1, D2, D3)

**Proposed by:** Step 11 Implementation  
**Date:** 2026-10-05  
**Status:** Proposed (pending user review)

**Statement:**
1. **Explainable Deterministic Matching:**
   - Policy-to-sector rules (`policy_rule`) map regulatory headlines to the 18 Layer 1 industries via keyword tokens and policy categories.
   - Every rule requires an explicit, audited economic transmission rationale and reviewer name (`NOT NULL`).
   - Every match records point-in-time evidence (`matched_keywords`, `headline`, `published_at`) in `policy_event`.
2. **Dynamic Risk Score Component (`news_policy_pressure`):**
   - Belongs to dimension `macro` with a default weight of 5% in `prism-risk-score-v1` (configurable via `model_config`).
   - Computes recency-decayed headwind pressure with a 14-day exponential half-life ($2^{-\Delta t / 14}$) over a 60-day window.
   - Policy tailwinds provide mitigation capped at 30% of gross headwind pressure:
     $$\text{NetPressure} = \max\left(0, \text{GrossHeadwind} - \min\left(\text{GrossTailwind}, 0.30 \times \text{GrossHeadwind}\right)\right)$$
3. **Immutable Rule Versioning:**
   - Modifying a policy rule via `PUT /policy/rules/{key}` creates a new active version row, supersedes the previous version, and preserves the complete audit trail.


