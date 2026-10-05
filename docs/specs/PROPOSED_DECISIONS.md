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
