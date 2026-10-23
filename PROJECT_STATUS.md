# PRISM Project Status

This is the living implementation record for PRISM. It must be updated after every material code, architecture, dependency, data-source or phase-status change.

## Current snapshot

| Field | Value |
|---|---|
| Current phase | Phase 7 - Production Hardening, Release Verification and Viva Pack |
| Overall status | NO-GO for production; local hardening and mocked browser gates pass, live authenticated persistence and migration rehearsals remain blocking |
| Last updated | 2026-10-20 |
| Requirements source | `PRISM_SRS.md` and Phase 7 Production Hardening Requirements |
| Initial universe | NIFTY 200 |
| Active implementation focus | Phase 7 audit completed: HTTP hardening, auth on ML/portfolio news, bounded requests/timeouts/rates, production fixture isolation, dependency cleanup, browser release checks, recovery docs, feature matrix, methodology and viva pack. Live Supabase E2E and clean/restored-copy PostgreSQL migration rehearsal are still required. |

## Phase status

| Phase | Name | Status | Exit evidence |
|---|---|---|---|
| 0 | Foundations | Complete | CI, reproducibility, unified pipeline and independent teammate operations verification passed |
| 1 | Audit, Repair & Baseline | Complete | Offline hermetic CI (ruff, mypy, pytest, ESLint, vitest, build), bounded cache, immutable snapshots, formula audit passed |
| 2 | Explainable Risk & Diversification | Complete | Multi-window stock risk, 5-factor heuristic scoring, portfolio covariance, Euler risk share, diversification metrics, sector benchmark analysis passed |
| 3 | Quantitative Risk Engine & Methodology | Complete | Single authoritative methodology registry, spectral covariance regularization, exact Euler volatility reconciliation, historical VaR/ES tail risk, stress testing engine, configurable alerts dialog, and snapshot reproducibility verified |
| 4 | Advanced ML & AI Insights | Complete | Walk-forward Markov regime switching, volatility forecasting, anomaly detection, AI Insights 10th tab verified |
| 5 | Real News Intelligence & NLP | Complete | Sourced RSS/licensed feed ingestion, entity matching, collision handling, SimHash deduplication, FinBERT/lexicon sentiment verified |
| 6 | Investor Experience & UI Cleanup | Complete | 10-stat executive strip, reusable explainers, risk review inbox, model/news surfacing, MST ego-network drill-down, evidence-based snapshot comparison, strict design system invariants verified |
| 7 | Production Readiness & Delivery | Partial / NO-GO | Local gates and documentation complete; live auth/persistence E2E and database restore/migration rehearsal block production |

## Phase 3 checklist

- [x] Return construction: Documented daily-rebalanced constant-weight simple returns vs buy-and-hold wealth series; proved and tested Jensen's inequality gap.
- [x] Single authoritative backend methodology registry (`methodology_registry.py`) providing definition, LaTeX/plain formula, units, window, min observations, and limitations; exposed via `/api/v1/analytics/methodology`.
- [x] Frontend renders explanations and cards directly from methodology registry (`methodologyRegistry.ts`) with zero duplicate text strings.
- [x] Covariance regularization: Spectral floor regularization ($\lambda_{min} \ge 10^{-6} \lambda_{max}$) for singular and rank-deficient matrices with zero-matrix preservation.
- [x] Euler decomposition: Preserved legitimate negative risk contributions for hedges (`HEDGE` chip); component volatilities reconcile exactly to total portfolio volatility ($\sum C_i = \sigma_p$).
- [x] Maximum Drawdown computed on discrete wealth series; beta and alpha evaluated against NIFTY 50 (`^NSEI`) with $R_f = 6.50\%$ and minimum 30 sessions rule.
- [x] Tail Risk: Added historical VaR (95% and 99%), Expected Shortfall / CVaR (95% and 99%), parametric Gaussian VaR, and exception-count backtesting; qualified as historical estimates.
- [x] Stress Testing: Implemented market shock (beta propagation), parallel sector shock, selected holding shock, and systemic correlation breakdown ($\tilde{\mathbf{C}} = (1-\alpha)\mathbf{C} + \alpha \mathbf{1}\mathbf{1}^T$).
- [x] Centralized scoring: Stock risk score (5 factors: 30%, 25%, 20%, 15%, 10%) and portfolio risk score (4 factors: 35%, 25%, 25%, 15%) weights, normalization bounds, and tier labels centralized in registry; verified by frontend invariant tests.
- [x] Configurable alert thresholds: User-editable thresholds dialog in Structural Overview, persisted per portfolio, with validation, reset-to-default, trigger value, threshold value, contributing holdings, and assumptions.
- [x] Mantegna MST validation: Metric distance transform ($d \in [0, 2]$), edge discard invariant ($(N-1)(N-2)/2$), disconnected components, and non-causation disclosures.
- [x] Reproducible risk snapshots: Standardized immutable envelope schema (`portfolio_id`, `data_cutoff`, `window`, `coverage`, `metrics`, `methodology_version`, `assumptions`) feeding the existing Portfolio Snapshot section.
- [x] Walk-forward chronological validation audit: Look-ahead elimination, non-overlapping windows, universe/survivorship bias disclosures, and transaction friction modeling.
- [x] Deliverables: `docs/METHODOLOGY.md` and `docs/phase-3-report.md`.

## Known limitations & Defect Register

1. **Heuristic Risk Scoring:** The 5-factor stock risk score and 4-factor portfolio risk score remain heuristic composites based on fixed empirical bounds. Full machine-learning calibration with walk-forward validation evidence is scheduled for Phase 4.
2. **Historical Universe Composition:** Historical NIFTY 200 index constituent changes prior to 2026-09-30 are not point-in-time; current index membership is used as the active universe envelope.
3. **Gaussian Stress Copula:** The systemic correlation breakdown scenario assumes standalone asset volatilities remain constant while correlations shift toward unity; extreme non-linear spikes are modeled via separate parallel shocks.
4. **Resolved Defect - Multi-Tenant Risk History:** Migrated to multi-tenant PostgreSQL tables with RLS enforcement in Phase 2.
5. **Resolved Defect - Return Additivity Convention:** Fixed in Phase 3. Log-return Jensen's gap proven and eliminated for risk metrics; simple returns used for cross-sectional linear combinations; buy-and-hold wealth index used for ledger P&L and drawdown.
6. **Resolved Defect - Monitoring Threshold Configurability:** Fixed in Phase 3. Configurable alert thresholds dialog implemented with persistence, validation, reset-to-default, trigger value, threshold value, contributing holdings, and assumptions.

## Verification status (Verified Truth)

| Check | Result | Last run |
|---|---|---|
| Python environment | Python 3.12.13 provisioned by `uv` | 2026-09-29 |
| Python dependency lock | 143 packages resolved; native scheduler stack active | 2026-09-29 |
| Ruff | Passed | 2026-09-29 |
| mypy strict mode | Passed, 17 source files | 2026-09-30 |
| pytest | Passed, 7 tests | 2026-09-30 |
| ESLint | Passed | 2026-09-29 |
| Vitest | Passed, 1 test | 2026-09-29 |
| TypeScript/Vite production build | Passed | 2026-09-29 |
| Supabase encrypted connection | Passed | 2026-09-30 |
| Alembic migration | `d8031fcf7da5` at head | 2026-09-30 |
| Phase 0 schema | 13 of 13 expected tables present | 2026-09-30 |
| FastAPI readiness endpoint | HTTP 200, database connected | 2026-09-30 |
| Official NIFTY 200 snapshot | 200 validated rows imported | 2026-09-30 |
| Universe importer idempotency | Second run created and updated zero records | 2026-09-30 |
| Market-data tests | Ruff passed; strict mypy passed for 23 source files; pytest passed 13 tests | 2026-10-01 |
| Daily raw-price coverage | 503,226 rows across 200 securities, 2015-01-01 through 2026-10-01 | 2026-10-01 |
| Adjusted-price coverage | 591,176 versioned rows across 200 securities | 2026-10-01 |
| Corporate actions | 2,864 dividend and split records | 2026-10-01 |
| Stored OHLCV validity audit | Zero invalid rows | 2026-10-01 |
| Pipeline-run recovery | Zero market-data runs left incorrectly running | 2026-10-01 |
| Layer 1 engine tests | Ruff passed; strict mypy passed for 26 source files; pytest passed 25 tests | 2026-10-02 |
| Layer 1 real-data input check | 110 dates; 186 eligible securities; 13 industries; 14 explicit small-industry exclusions; zero input issues | 2026-10-02 |
| Layer 1 real-data calculation | 556 finite scores: 186 one-day, 186 five-day and 184 twenty-day; two explicit insufficient-horizon issues | 2026-10-02 |
| Layer 1 persistence verification | Additive PostgreSQL migration renders successfully in offline mode | 2026-10-04 |
| Backend verification | Ruff passed; strict mypy passed for 42 source files; GitHub CI passed all backend tests including the PostgreSQL integration test | 2026-10-05 |
| Frontend verification | ESLint passed; 7 Vitest tests passed across 4 files; TypeScript/Vite production build passed | 2026-10-06 |
| Portfolio analytics verification | Ruff passed; strict mypy passed across 52 source files; 49 tests passed and 2 approved database integration tests skipped | 2026-10-08 |
| Portfolio browser rehearsal | Prepared sample, performance, risk, MST, stress and JSON download passed in headless Chrome with zero console errors | 2026-10-06 |
| Backend startup recovery | Root/backend import and root `.env` regression checks passed; 125 tests passed, 2 database integration tests skipped; Uvicorn reload and database readiness verified | 2026-10-06 |
| Fundamental historical regression | 149 tests passed, 2 integration tests deselected; Ruff and strict mypy passed across 75 source files; 1,124 configurations and 8,262 blends evaluated; 93.55% category accuracy on 155 held-out stocks, score MAE 1.2972 and R² 0.9005 | 2026-10-06 |
| Company-detail API check | BAJAJ-AUTO returned three scores, 13 exact peers and 61 comparison points | 2026-10-04 |
| Persisted Layer 1 run | 556 scores, 14 exclusions and 2 calculation issues available through the API | 2026-10-04 |
| Layer 2 engine tests | Determinism, tie-breaking, no-look-ahead, missing-data exclusion and topology invariants passed | 2026-10-04 |
| Layer 2 real-data calculation | 199 nodes; 198 edges; connected and acyclic; VAML explicitly excluded; 2.171 second calculation | 2026-10-04 |
| Layer 2 migration verification | Additive PostgreSQL migration renders successfully in offline mode | 2026-10-04 |
| Phase 0 reproducibility audit | Layer 1 and Layer 2 semantic digests reproduced identically across repeated calculations | 2026-10-04 |
| Unified daily pipeline | Completed for market date 2026-10-01; pipeline run `9aca74e2-90dd-47e7-bdf8-0d23f80ffe3f` linked persisted Layer 1 and Layer 2 runs | 2026-10-05 |
| GitHub CI | Backend and frontend jobs passed for Phase 1 closure commit `22d99c0` | 2026-10-08 |
| Phase 1 local backend verification | Ruff passed; strict mypy passed for 47 source files; 45 tests passed and 2 database integration tests were skipped locally | 2026-10-05 |
| Phase 1 local frontend verification | ESLint passed; 7 Vitest tests passed; TypeScript/Vite production build passed | 2026-10-08 |
| Phase 1 migration verification | Reconciliation and audit head `b7d4e2f91a08` rendered offline and deployed to Supabase; legacy rows and tables preserved | 2026-10-08 |
| MST stability evidence | Two compatible consecutive windows compared; 90.4% adjacent edge overlap and 95.2% mean current-edge persistence (high confidence) | 2026-10-08 |
| Ruff Python Linter | Passed (0 errors, 100-character line limit enforced) | 2026-10-20 |
| mypy strict mode | Passed (0 errors across 84 source files in `backend` and `jobs`) | 2026-10-20 |
| pytest backend tests | Passed (142 passed, 2 guarded DB integration tests skipped, 1 deprecation warning in 15.11s) | 2026-10-20 |
| ESLint frontend linter | Passed (0 errors, 0 warnings across frontend codebase) | 2026-10-20 |
| Vitest frontend tests | Passed (56 passed across 10 test files in 12.21s) | 2026-10-20 |
| Vite production build | Passed (1,019 modules built in 624ms, 0 TypeScript errors) | 2026-10-20 |
| Playwright release suite | Passed 3 mocked/local-persistence scenarios; 1 live authenticated persistence scenario skipped and blocking | 2026-10-20 |
| Alembic offline upgrade | Passed (750 lines of upgrade-to-head SQL generated) | 2026-10-20 |
| Repository policy and production bundle scan | Passed (no tracked secrets/artifacts; no demo fixture or credential-pattern match in bundle) | 2026-10-20 |

## Update protocol

After every material update:

1. Update the current snapshot and relevant checklist.
2. Add a dated entry to the change log.
3. Record verification commands and results.
4. Record new blockers or decisions.
5. Change a phase to complete only when its SRS exit criteria are satisfied.

## Change log

### 2026-10-22 - Temporal heterogeneous GNN validation and guarded integration

- Added point-in-time industry-history storage/import, leakage and coverage audits, chronological evaluation, four transparent baselines, multi-seed experiments and trained relation ablations.
- Added immutable drift persistence, authenticated status/portfolio/company/market APIs, a validation-gated weekly inference scheduler, and structural-change panels in AI Insights and Company Detail.
- Added drift percentiles and observed feature/relationship drivers with explicit non-causal, non-forecast wording.
- The existing retrospective run is correctly rejected: held-out adverse-change ROC AUC is 0.514 versus 0.579 for the best non-graph baseline. It is not selected or published as production-ready.
- Verification: GNN tests 3 passed; scoped Ruff and mypy passed; frontend production build passed. The repository-wide pytest run requires importlib mode because duplicate test module names collide, and the attempted run did not complete. Existing unrelated frontend lint errors and sandbox temporary-file failures remain outside this change.

### 2026-10-22 - Market MST readability

- Tightened the market tree layout and replaced tiny rectangular nodes with larger outlined circles.
- Added stock search with neighbourhood focus, zoom controls, fit-all navigation and an industry legend.
- Labels appear at readable zoom levels; selecting a stock emphasizes its connections. Background clicks clear selection without resetting the viewport.
- Fixed selected-node styling that incorrectly reduced node width to four pixels.
- Verification: frontend TypeScript compilation and production build passed; visual browser acceptance remains to be checked with the live market tree.

### 2026-10-06 - Historical fundamental score regression and blends

- Added reproducible Yahoo/NSE historical acquisition, delayed quarterly reconstruction, continuous-score regression searches and median/weighted model blends for the exact 200-stock universe.
- Reconstructed 3,000 quarterly rows with 1,794 assessable changed states, split into 1,639 development rows and 155 September holdout rows. The latest 45 Limited Assessment stocks retain blank scores.
- Tested all 1,124 declared finite-grid configurations and 8,262 blends using four earlier forward-validation periods; locked model selection before evaluating the latest holdout.
- Selected median aggregation of Extra Trees, random forest and SVR score predictions: holdout category accuracy 145/155 (93.55%), score MAE 1.2972 and R² 0.9005. Previous settings on the same historical cohort achieved the same category accuracy with slightly higher score MAE.
- Verified saved-model reloads, original input hashes, fixed score bands, legacy ownership parsing and partial fiscal-year durations. The existing source CSV and production model remain unchanged because Yahoo and Screener inputs differ.
- Recorded methodology, parameter grids, results and data-quality limits in `FUNDAMENTALS.md`; downloaded data, generated reports and model binaries remain ignored local artifacts.
- Verification: 149 tests passed with two integration tests deselected; Ruff, strict mypy, `uv lock --check`, repository policy and `git diff --check` passed.

### 2026-10-06 - Backend startup and pip requirements fixed

- Preserved project-root `.env` loading from any launch directory and added a regression test using a disposable configuration file.
- Moved backend-directory import setup into the application package so `uvicorn app.main:app` resolves canonical `backend.app` imports without module-import lint errors.
- Added `backend/run.sh` to start Uvicorn with the locked Python 3.12 project environment, including when Conda base is active; pinned the development Python version in `.python-version`.
- Exported runtime dependencies from `uv.lock` to root `requirements.txt` and added `backend/requirements.txt` as an include for backend-directory pip installs.
- Installed the missing Psycopg binary driver and pool in the local Anaconda environment used by the reported command.
- Verified root/backend startup regression checks, targeted Ruff checks, targeted strict mypy checks, and installed-dependency compatibility. Full pytest result: 125 passed and 2 database integration tests skipped.
- Verified real Uvicorn reload startup through both the launcher and the reported Anaconda command. Health and Supabase database readiness returned HTTP 200; test servers were stopped afterward.
### 2026-10-20 - Phase 7 Partial / NO-GO: Production hardening and release evidence

- Added central request-size, timeout, rate, trusted-host, request-ID, security-header, and safe
  metadata logging controls, plus strict production configuration validation.
- Protected ML, portfolio-news, and symbol-news routes; removed anonymous cross-request risk
  history; fixed arbitrary evaluation paths and bounded request schemas.
- Removed automatic curated demo holdings and synthetic price/market fallbacks from production
  calculation paths. Missing real provider/database history now produces an explicit unavailable
  response.
- Added Playwright release coverage for the exact ten-tab shell, ledger reconciliation, reload and
  snapshot persistence, and provider outage states. The live authenticated create/sign-out/sign-in
  isolation test remains deliberately skipped.
- Removed seven unused direct Python dependencies and regenerated the lockfile offline.
- Added `docs/FEATURE_MATRIX.md`, `docs/VIVA_QA.md`, and `docs/phase-7-report.md`; expanded
  methodology, recovery, deployment, and rollback documentation.
- Measured deterministic local baselines: 200-security portfolio risk 0.043859s, 200-security MST
  1.407251s, 300-observation volatility walk-forward path 1.290910s, and 10,001-transaction ledger
  replay 0.034861s. These are synthetic single-run profiles, not production SLO evidence.
- Final local gates: Ruff and mypy passed; pytest 142 passed/2 skipped; ESLint passed; Vitest 56
  passed; production build passed; Playwright 3 passed/1 skipped; offline Alembic generation and
  repository policy passed.
- Release remains **NO-GO** until the ten-tab UI uses the authenticated server ledger/durable user
  records and clean/restored-copy PostgreSQL migration, RLS, rollback, and live re-login evidence
  are completed.

### 2026-10-20 - Phase 3 Complete: Quantitative Risk Engine, Methodology Registry & Reproducible Snapshots

- **Authoritative Methodology Registry:** Built `backend/app/portfolio_analytics/methodology_registry.py` and synchronized `frontend/src/methodologyRegistry.ts`, serving definitions, formulas, units, windows, minimum observation limits, assumptions, and limitations via `GET /api/v1/analytics/methodology`. Frontend renders all metric info cards directly from this registry with zero duplicated text strings.
- **Return Construction Rigor:** Formally separated simple daily returns $R_{p,t} = \sum w_i R_{i,t}$ for statistical risk metrics from the discrete buy-and-hold wealth index $W_t = \sum Q_i P_i + \text{Cash}$ for ledger accounting and drawdown. Mathematically proved and tested the log-return Jensen's inequality gap ($\sum w_i \ln(1+R_i) - \ln(1+\sum w_i R_i) \le 0$) and eliminated downward bias.
- **Spectral Covariance Regularization:** Implemented eigenvalue floor regularization ($\lambda_{min} \ge 10^{-6} \lambda_{max}$) in `calculator.py` to ensure positive definiteness for ill-conditioned or collinear portfolios while preserving zero variance without numerical artifacts.
- **Euler Risk Decomposition & Hedge Preservation:** Derived Euler component risk $C_i = w_i \frac{(\mathbf{\Sigma} \mathbf{w})_i}{\sigma_p}$. Proved that sum of component volatilities matches portfolio volatility ($\sum C_i = \sigma_p$) within numerical tolerance. Preserved legitimate negative risk contributions for hedging assets with visual `HEDGE` indicators.
- **Tail Risk Analytics:** Added 1-day Historical VaR (95%, 99%), Historical Expected Shortfall / CVaR (95%, 99%), Parametric Gaussian VaR, and binomial breach count backtesting, explicitly labelled historical estimates.
- **Multi-Scenario Stress Testing:** Implemented broad market beta shock, parallel sector shock, single-holding pair-beta shock, and systemic correlation breakdown ($\tilde{\mathbf{C}} = (1-\alpha)\mathbf{C} + \alpha \mathbf{1}\mathbf{1}^T$) quantifying diversification loss during liquidity panics.
- **Centralized Scoring & Configurable Alert Thresholds:** Centralized scoring weights and normalization bounds in the registry. Built compact alert thresholds configuration dialog in the Structural Overview panel with per-portfolio persistence, validation clamping, reset-to-default, trigger value, threshold value, contributing holdings attribution, and assumptions.
- **Mantegna MST Validation:** Formalized metric distance transform ($d \in [0, 2]$), verified edge discard invariants ($(N-1)(N-2)/2$), and surfaced explicit non-causation disclosures in the graph UI.
- **Reproducible Snapshots:** Standardized immutable calculation envelopes capturing portfolio ID, valuation cutoff, window, data coverage status, metric dictionary, methodology version (`2026.1`), and model assumptions.
- **Walk-Forward Validation Audit:** Audited walk-forward validation for look-ahead avoidance, non-overlapping windows, universe survivorship disclosures, and execution friction.
- **Deliverables:** Created `docs/METHODOLOGY.md` and `docs/phase-3-report.md`.
- **Verified Green CI:** `uv run ruff check .` (0 errors), `uv run mypy backend jobs` (0 errors across 59 source files), `uv run pytest tests/` (112 passed, 2 skipped in 16.02s), `pnpm test -- --run` (46 passed across 8 suites in 5.57s), `pnpm run lint` (0 errors), `pnpm run build` (built cleanly in 270ms, 0 errors).

### 2026-09-29 - Repository bootstrap

- Created the backend, frontend, jobs, tests and data structure.
- Added dependency manifests for the decided project stack.
- Added baseline local-process configuration for the backend and frontend.
- Added baseline FastAPI and React application entry points.
- Installed and locked the Python and frontend dependencies.
- Verified backend linting, strict typing and unit tests.
- Verified frontend linting, unit tests and production build.

### 2026-09-29 - Native development workflow adopted

- Confirmed that development will use native Python, Node and PostgreSQL processes.
- Selected APScheduler and Tenacity for native scheduling and retry behaviour.
- Kept PostgreSQL as the selected database while the hosting approach was still under review.

### 2026-09-30 - Supabase database selected

- Selected Supabase-hosted PostgreSQL instead of a locally installed database.
- Added SSL-required PostgreSQL URL normalization for SQLAlchemy and Psycopg.
- Added Alembic configuration and initial Phase 0 SQLAlchemy models.
- Verified that the Supabase session-pooler network endpoint is reachable.
- Added safe automatic URL encoding for reserved database-password characters.
- Applied the initial migration and verified all expected tables.
- Seeded the `NIFTY 200` universe identity without inventing constituent history.
- Added and verified the FastAPI database-readiness endpoint.

### 2026-09-30 - Repository structure simplified

- Removed phase-named source folders and redundant phase documents.
- Grouped code directly by implemented components: API, core configuration, database and jobs.
- Grouped tests by the component they verify.
- Removed empty placeholder packages; future folders will be created only when their code exists.

### 2026-09-30 - Layer baseline corrected

- Corrected the earlier assumption that Layer 1 and Layer 2 already existed.
- Recorded both quantitative layers as new PRISM implementations to be designed and validated.

### 2026-09-30 - NIFTY 200 security master imported

- Added an official Nifty Indices CSV client and strict five-column parser.
- Added row-count, symbol uniqueness, ISIN uniqueness and ISIN-format validation.
- Added idempotent security, NSE alias and versioned membership synchronization.
- Archived the retrieved current snapshot under ignored raw data storage.
- Imported 200 securities, aliases and active memberships into Supabase.
- Confirmed a second import creates no duplicate records.

### 2026-10-01 - Daily market-data foundation completed

- Added the replaceable Yahoo Finance adapter for unadjusted and adjusted daily OHLCV data.
- Added incremental seven-day overlap updates, bounded concurrent downloads and sequential transactional database writes.
- Preserved provider corrections as new raw and adjusted revisions instead of silently overwriting history.
- Added dividend and stock-split ingestion with idempotent corporate-action persistence.
- Added deterministic checks for duplicate dates, missing/non-finite values, invalid OHLC relationships, negative volume, long observation gaps and extreme adjusted returns.
- Added per-symbol failure isolation, exponential retries for transient provider/database failures, raw CSV snapshots and targeted symbol recovery.
- Loaded and audited all 200 current NIFTY 200 securities from 2015-01-01 through 2026-10-01.
- Marked two interrupted initial runs accurately and completed the single failed symbol through targeted recovery.

### 2026-10-02 - Layer 1 contract and inputs completed

- Approved and documented the purely mathematical `sector-divergence-v1` contract.
- Fixed the official Nifty `Industry` field as the version 1 group classification and prohibited ML, AI and learned weights from Layer 1.
- Defined leave-one-out median benchmarks, trailing 60-day OLS, 45 paired observations, and separate 1-day, 5-day and 20-day standardized residual outputs.
- Added point-in-time membership and adjusted-price revision selection using an explicit data cutoff.
- Added deterministic price/provenance panels without forward filling, backward filling or zero substitution.
- Added explicit exclusions for missing classifications, insufficient price history and undersized industry groups.
- Enforced the 2026-09-30 membership-observation boundary so earlier results cannot be presented as point-in-time NIFTY 200 history.
- Verified the real data produces 186 eligible securities across 13 industries; 14 securities are explicitly excluded because their industry groups contain fewer than five eligible members.
- Implemented rolling leave-one-out industry benchmarks, trailing OLS alpha/beta, residual volatility and dynamically point-in-time residuals.
- Implemented separate 1-day, 5-day and 20-day standardized scores, fixed interpretation bands and deterministic empirical percentiles.
- Added hand-calculated OLS, multi-day residual, no-look-ahead, missing-data, degenerate-variance and percentile tests.
- Ran the engine against the real panel and produced 556 finite scores for 186 securities with two explicit 20-day availability issues.

### 2026-10-04 - Layer 1 result surface implemented

- Added additive persistence tables for reproducible calculation runs, horizon-specific scores and explicit issues/exclusions.
- Added deterministic configuration and point-in-time input fingerprints so an identical calculation reuses its completed run.
- Added a runnable calculation job with stable latest-snapshot defaults and explicit date/cutoff overrides.
- Added versioned API endpoints for latest-run metadata, 1/5/20-day magnitude rankings and limitations.
- Replaced the frontend placeholder with a responsive Layer 1 dashboard showing rankings, interpretation bands, coverage and freshness.
- Verified the migration by rendering transactional PostgreSQL DDL offline.
- Did not apply the migration or write results to Supabase because external database mutation was not approved in the execution environment.

### 2026-10-04 - Company peer-comparison detail implemented

- Added a company-detail API computed from the persisted run's exact point-in-time input envelope.
- Added an indexed stock-versus-peer chart using the same leave-one-out median benchmark as Layer 1.
- Exposed all three horizon scores, the direction relative to peers, the exact peer set and method limitations.
- Made ranking direction explicit and linked every ranked company to its detail route.
- Verified the live BAJAJ-AUTO response contains three horizon scores, 13 peers and 61 chart points through 2026-10-01.
- Confirmed the Layer 1 migration and first persisted 556-score run were applied successfully by the user.
- Corrected an ambiguous presentation that compared 1/5/20-day residual scores with a fixed 60-observation chart.
- Company charts now follow the selected score horizon, show actual stock and benchmark returns, and distinguish raw performance from the alpha/beta-adjusted residual score.

### 2026-10-04 - Layer 2 correlation MST implemented locally

- Approved and documented the deterministic `correlation-mst-v1` mathematical and input contract.
- Implemented 120-day adjusted-close log returns, minimum 100-pair Pearson correlations and Mantegna correlation distance.
- Implemented deterministic invalid-pair exclusions plus Kruskal's algorithm with Union-Find and canonical tie-breaking.
- Added hard validation for connectivity, acyclicity and exactly `N-1` edges.
- Extended the placeholder schema with run cutoffs, configuration/input fingerprints, stored nodes, pair counts and validation status.
- Added an idempotent calculation job, latest-MST API and interactive Cytoscape network view with explicit non-causality limitations.
- Verified read-only against real stored data: 199 eligible nodes, 198 edges, one explicit insufficient-history exclusion, connected and acyclic.
- Did not apply the additive migration or persist the real run because external Supabase mutation requires explicit user authorization.

### 2026-10-05 - Phase 0 completed

- Verified the full GitHub CI workflow on commit `739ce35`, including PostgreSQL migrations, the database integration test, repository policy, frontend tests and the production build.
- Ran the provider-free unified pipeline against the existing versioned Supabase snapshot.
- Completed pipeline run `9aca74e2-90dd-47e7-bdf8-0d23f80ffe3f` for market date 2026-10-01 with persisted Layer 1 run `717bf1e1-9893-4f66-bf89-b51f5cdbf89c` and Layer 2 run `6b1ac59d-7af1-4cca-8975-21ef1300108e`.
- Confirmed that another team member independently tested the documented setup and recovery procedure.
- Closed Phase 0 after all sixteen SRS acceptance checks passed and opened Phase 1 portfolio insight work.

### 2026-10-05 - Phase 1 authenticated portfolio slice implemented locally

- Approved the quantity/weight, valuation, cash, universe, validation, authentication, risk, shock, snapshot and deletion policies in `PHASE1_PORTFOLIO_CONTRACT.md`.
- Added versioned portfolio, immutable snapshot and holding models plus an additive Alembic migration.
- Added Supabase row-level security policies and explicit backend owner filtering as defense in depth.
- Added Supabase bearer-token verification without storing or exposing service-role credentials.
- Added deterministic preview validation, duplicate aggregation, active-universe enforcement, latest-common-date selection and preview fingerprints.
- Added private create, list, read, archive and guarded permanent-delete APIs.
- Added an authenticated frontend route for sign-in, account creation, CSV preview, confirmation, persistence and reload.
- Added authentication, model, normalization, CSV and isolated PostgreSQL ownership integration tests.
- Kept the shared Supabase migration unapplied pending CI and explicit database-deployment approval.

### 2026-10-05 - No-login portfolio presentation demo implemented

- Added a browser-only portfolio route with a prepared diversified sample and `symbol,weight` CSV input.
- Validated holdings against the symbols in the latest persisted NIFTY 200 MST and required weights to total 100%.
- Combined real persisted 20-day divergence results with holding weights, industry allocation and company-detail links.
- Highlighted unusually moving holdings, concentrated positions, concentrated industries and high-correlation direct MST links.
- Added held-to-held MST connection reporting using the real Layer 2 edge correlations.
- Kept all portfolio input in memory for the current browser session; no login, database migration or portfolio persistence is required for the presentation.
- Verified ESLint, 7 Vitest tests across 4 files and the TypeScript/Vite production build.

### 2026-10-06 - Portfolio risk and explainability implemented

- Added the read-only `portfolio-analytics-v1` API without new tables, migrations, authentication or database writes.
- Added point-in-time 250-day portfolio performance, annualized return and volatility, downside volatility and maximum drawdown using complete common adjusted-price dates without imputation.
- Added annual covariance and Euler holding-risk contribution, holding/industry HHI and effective exposure measures.
- Added risk-contribution entropy and correlation-eigenvalue effective-bet estimates.
- Added direct holding MST edges, every unique holding-to-holding path, held and non-held bridge stocks, and transparent correlation-floor clusters.
- Added regression-beta selected-stock stress and parallel selected-industry stress with explicit assumptions and limitations.
- Added a responsive performance/drawdown chart, risk and concentration panels, MST diagnostics, interactive stress controls, JSON export and print-to-PDF layout.
- Added a favicon so the presentation page loads without the previous browser-console 404.
- Verified the real prepared sample with 250 returns, 15 holding paths, 3 direct edges, 11 bridge stocks and 3 clusters through 2026-10-01.
- Completed a browser rehearsal of sample analysis, stress calculation and report download with zero console errors.

### 2026-10-06 - Interactive portfolio MST subtree added

- Added the exact deduplicated union of holding-to-holding MST path edges to the analytics response.
- Added a responsive left-to-right portfolio MST map that distinguishes held stocks, non-held bridges,
  direct holding links and weaker cross-cluster connectors.
- Encoded holding weight in node size and retained exact correlation and Mantegna distance in selectable
  edge explanations; selections isolate the relevant local neighborhood.
- Kept the existing cluster, bridge and path tables as detailed evidence beneath the visual summary.
- Verified the graph in a real Chromium browser at desktop width, including a mocked six-holding response.

### 2026-10-08 - Phase 1 closed with stability, audit and schema reconciliation

- Added current-edge persistence across up to five compatible consecutive MST runs, adjacent-window
  overlap, explicit high/moderate/low thresholds and an unavailable state for insufficient history.
- Added confidence to every displayed subtree edge and holding-to-holding path; each path inherits
  the confidence of its least-persistent edge.
- Persisted the 2026-09-30 comparison tree and verified the 2026-10-01 tree has 90.4% adjacent-edge
  overlap and 95.2% mean current-edge persistence across the two compatible runs.
- Reconciled the independently deployed `r1a2b3c4d5e6` schema additively: retained the legacy
  `portfolio_holding` workflow, extended `portfolio`, and isolated authenticated immutable rows in
  `portfolio_snapshot` and `portfolio_snapshot_holding`.
- Added owner-scoped, RLS-protected audit events for portfolio creation, archive, restore and deletion.
- Deployed migration head `b7d4e2f91a08` to Supabase after read-only collision checks; all three
  pre-existing legacy portfolio rows were preserved and remain unclaimed by authenticated users.
- Verified Ruff, strict mypy, 49 local tests with two approved database tests skipped, Alembic offline
  rendering, ESLint, seven frontend tests and the production build.
- Closed Phase 1 after the portfolio risk, diversification, explainability, MST stability, stress,
  freshness, disclaimer, schema and audit gates passed.

### 2026-10-19 - Phase 2: Explainable Stock Risk, Portfolio Covariance, Diversification & Sector Analysis

- **Multi-Window Stock Risk Analytics (`backend/app/portfolio_analytics/stock_risk.py`):**
  - Evaluates risk across four standard financial horizons: 1M (21 days), 3M (63 days), 6M (126 days), and 1Y (252 days).
  - Calculates annualized volatility, downside semi-deviation (semi-volatility below target 0), peak-to-trough maximum drawdown, price instability ratio (short 21d vol / 126d baseline vol), market beta vs NIFTY 50 (`^NSEI`), and Jensen's alpha.
  - Integrates investor position tracking: purchase price vs current price, unrealized P&L (₹) and percentage return, drawdown since purchase, and volatility since purchase date. Position loss is strictly distinguished from market volatility.
- **Explainable 5-Factor Risk Scoring:**
  - Standardized 0–100 scale calibrated with bounded thresholds: Annualized Volatility (30%, range 12–42%), Downside Volatility (25%, range 8–30%), Max Drawdown (20%, range 8–45%), Market Beta (15%, centered at 1.0), and Price Instability & Divergence (10%).
  - Dynamically constructs qualitative narratives explaining the strongest risk drivers without hardcoded stock-specific strings.
  - Classifies assets into 4 calibrated tiers: Low (0–35, green), Moderate (35–60, amber), High (60–80, orange), and Very High (80–100, red).
- **Portfolio Covariance & Euler Risk Decomposition:**
  - Computes portfolio volatility via true asset covariance matrix: $\sigma_p = \sqrt{w^T \Sigma w}$.
  - Computes marginal Euler risk contributions: $\text{RC}_i = \frac{w_i (\Sigma w)_i}{\sigma_p^2}$, proving exact 100% risk contribution summing.
  - Calculates historical risk trend (1M vs 6M annualized volatility change).
- **Defensible Diversification Index:**
  - Evaluates Herfindahl-Hirschman Index (HHI), Effective Number of Holdings ($N_{eff} = 1/\sum w_i^2$), Effective Number of Sectors ($S_{eff} = 1/\sum s_j^2$), and the Diversification Ratio ($\text{DR} = \frac{\sum w_i \sigma_i}{\sigma_p}$).
  - Computes normalized 0–100 Diversification Score mapped to Letter Grades (A, B, C, D) with explicit educational disclaimers.
- **Sector Exposure & Benchmarked Ceilings:**
  - Calculates sector weights, risk contributions, and 20-day Layer 1 sector divergence.
  - Enforces a documented 25% portfolio ceiling target, categorizing allocations as "Balanced" (<=25%), "Elevated" (25–35%), or "Excessive" (>35%).
- **Interactive UI & Dedicated Navigation (`frontend/src/Phase2RiskSections.tsx`, `PortfolioManager.tsx`):**
  - Added dedicated tabs: Stock Risk Analysis, Portfolio Risk, Sector Exposure, Diversification, Network & Stress (MST), and Transaction Ledger.
  - Interactive Stock Risk modal for factor contribution inspection, multi-window comparison, and purchase tracking.
  - Correlation matrix heatmap, simulated 250-day SVG portfolio performance curve, and Sector risk vs capital comparison bars.
- **Verification & Testing:**
  - Deduplicated price histories in database queries to prevent index collision errors on revised prices.
  - All 67 backend pytest tests passing (including 10 comprehensive tests in `test_stock_risk.py`).
  - Strict mypy passed across `portfolio_analytics` with zero errors.
  - All 15 Vitest frontend tests passing; ESLint 0 errors; TypeScript/Vite production build passing.

### 2026-10-19 - Phase 3: Structural Monitoring, MST Holdings Integration, Historical Risk Tracking & Validation

- **MST Integration with Portfolio Holdings (`backend/app/portfolio_analytics/structural_monitoring.py`, `frontend/src/Phase3StructuralSections.tsx`):**
  - Reused existing Mantegna correlation metric ($d_{ij} = \sqrt{2(1 - \rho_{ij})}$) and MST topological structures from Phase 1 without creating any duplicate MST engines.
  - Added holding-centric MST Ego-Network Inspector: selecting any portfolio holding immediately exposes its direct topological MST links, edge correlation ($\rho$), Mantegna metric distance, bridge stock pathways, and indirect path routes to other holdings.
  - Added Correlated Holding Groups detection (clusters with mean $\rho \ge 0.50$), surfacing return co-movement risks and common sectoral exposures.
  - Added explicit, transparent callout of MST Methodological Limitations: highlights that MST identifies topological backbones of historical co-movement but does not establish causation, guarantee future correlation persistence, or capture tail dependency outside the estimation window.
- **Structural Monitoring Dashboard:**
  - Executive Overview Banner tracking Current Portfolio Value, Total Return, Portfolio Risk Score (0–100), Diversification Index, Sector Ceiling, and Largest Holding Weight.
  - Analytical Monitoring Indicators with configurable warning thresholds:
    - *Elevated Portfolio Risk* ($\ge 60$) & *Critical Portfolio Risk* ($\ge 80$)
    - *Excessive Sector Concentration* ($\ge 25\%$ or $\ge 35\%$)
    - *Single-Holding Concentration Risk* ($\ge 20\%$)
    - *Insufficient Portfolio Diversification* ($N_{eff} < 4.0$)
    - *Excessive Downside Volatility* ($\ge 20\%$)
    - *Disproportionate Euler Risk Contribution* ($\text{RC}_i \ge 30\%$)
  - Added clear non-advisory disclaimers emphasizing alerts are analytical mathematical signals rather than automated trade advice.
  - Visualized top Euler risk contributions against invested capital weights to instantly spot risk amplifiers.
- **Historical Risk Tracking & Audit Persistence:**
  - Implemented persistent risk snapshots auto-persisting to `data/processed/portfolio_risk_history.json`.
  - Tracks time-series progression (Current, 1M, 3M, 6M) across Portfolio Risk Score, Volatility, Max Drawdown, Effective Holdings ($N_{eff}$), and Sector Concentration ($HHI$).
  - Strictly reports observation dates, sample sizes, and historical data coverage without fabricating missing points.
- **Modular News Integration Architecture (`backend/app/portfolio_analytics/news_signals.py`):**
  - Created decoupled contract schemas (`NewsArticleItem`, `StockNewsSignal`, `PortfolioNewsSummary`).
  - Implemented isolated news preview endpoint `POST /portfolio-analysis/news-signals` that isolates news sentiment and risk multipliers from quantitative market risk, preventing silent corruption of historical risk metrics.
- **Dedicated 9-Tab Navigation & Responsive UI:**
  - Navigation hierarchy: Structural Overview (`monitoring`), Holdings Dashboard (`dashboard`), Stock Risk Analysis (`stock-risk`), Portfolio Risk & History (`portfolio-risk`), Sector Exposure (`sector-exposure`), Diversification (`diversification`), Network & Stress (MST) (`analysis`), News Signals Preview (`news-preview`), Transaction Ledger (`transactions`).
  - Added loading, empty, and error fallback states; accessible typography and labels; SVG vector icons with zero external icon package overhead.
- **Full End-to-End Audit & Verification:**
  - Backend: 74 tests passing (0 failures, 2 approved live-PostgreSQL skips); 21/21 in `tests/portfolio_analytics/`.
  - Mypy: strict mode passed across all 8 `portfolio_analytics` files with zero errors.
  - Frontend: 15/15 Vitest tests passing; ESLint 0 errors / 0 warnings; TypeScript/Vite production build cleanly generating chunks.

### 2026-10-20 - Phase 1: Audit, Repair and Honest Baseline

- **Verified CI Pipeline Restored to 100% Green:**
  - **Ruff:** Fixed 34 linting errors (E501 line lengths in migrations, live services, and tests; F401 unused imports; I001 import order). Enforced strict 100-character line length limit.
  - **mypy:** Resolved all type-check failures (5 errors eliminated). Replaced hacky unbounded global `_inputs_cache` with a bounded module-level LRU cache (`_inputs_lru_cache`, `maxsize=16`, keyed by `(run_id, signal_date)`) in `backend/app/api/v1/router.py`. Added `# type: ignore[import-untyped]` for `pandas` in `backend/app/sector_divergence/service.py` to match workspace pattern. Strict typing passes across all 57 source files.
  - **ESLint:** Fixed 14 errors across `Dashboard.tsx`, `Phase2RiskSections.tsx`, `Phase3StructuralSections.tsx`, `PortfolioManager.tsx`, `PortfolioSnapshotSection.tsx`, `StockDecisionJournal.tsx`, `StockResearchNotes.tsx`, `journalStorage.ts`, and test files.
  - **Vitest:** All 34 tests passing across 7 test suites (added new test suite covering snapshot create-only immutability, data cloning/freezing, and session fallback detection).
  - **Pytest:** Eliminated live Yahoo Finance network dependencies (`^NSEI`, live quotes) in `test_live_service.py` and `test_stock_risk.py`. All tests are 100% hermetic with zero network calls, executing in 11.22s.
  - **Production Build:** `pnpm run build` passes with zero TypeScript errors, producing production chunks in 256ms.
- **Defects Repaired & Wording Aligned with Truth:**
  - **Snapshot Persistence & Immutability (`journalStorage.ts`):** Made snapshots create-only using `store.add()` instead of `store.put()`, strictly rejecting duplicate IDs to prevent silent overwrites. Applied `Object.freeze(structuredClone(snapshot))` to prevent reference mutation. Added `isPersistenceFallbackActive()` and `subscribePersistenceFallback()` with a visible warning alert banner in `PortfolioSnapshotSection.tsx` whenever persistence falls back to session memory.
  - **Simulated News Isolation (`Phase3StructuralSections.tsx`, `news_signals.py`):** Explicitly labelled all synthetic news cards, banners, and sample articles with `SIMULATED - NOT REAL NEWS`. Confirmed that no quantitative risk aggregate or covariance calculation ingests synthetic news multipliers.
  - **Diagnostic Threshold Wording (`structural_monitoring.py`):** Reworded "configurable" claims to standard/fixed diagnostic prudential thresholds (user configurability is scheduled for Phase 3).
  - **Heuristic Risk Scoring (`Phase2RiskSections.tsx`):** Reworded the 5-factor stock risk score from "calibrated" to "heuristic" across UI descriptions and documentation until empirical calibration is conducted in Phase 4.
  - **Multi-Tenant Risk History Defect Documented:** Catalogued server-global `data/processed/portfolio_risk_history.json` as a known defect for database migration in Phase 2.
  - **Mathematical Formula Audit & Test Suite (`test_phase1_formula_audit.py`):** Built independent verification tests for daily/annualized volatility, downside semi-deviation, maximum drawdown, beta and alpha vs scipy, Euler risk decomposition summing to 100%, HHI, Effective N, Diversification Ratio ($\text{DR} \ge 1$), Mantegna MST distance metric, regression-beta stress shocks, and edge cases (single asset, flat prices, inverse correlation). Flagged log-return portfolio additivity convention.

### 2026-10-20 - Phase 2: Market-Data Lineage and Portfolio Ledger Integrity

- **Consolidated Market-Data Architecture (`backend/app/market_data/live_service.py`, `backend/app/portfolio_analytics/stock_risk.py`):**
  - Removed all live network calls to yfinance from user request paths. All benchmark series (`^NSEI`), single-stock prices, and historical returns are queried from verified local database tables (`PriceDailyAdjusted`, `PriceDailyRaw`, `SecurityMaster`).
  - Added deterministic data lineage tracking: instrument, exchange, trading date, raw close, adjusted close, volume, currency, source, retrieved_at, adjustment status, and quality status.
  - Implemented common-date alignment (`align_price_series`) for asset and benchmark returns with observation count and coverage reporting.
  - Added quality checks: stale data qualification (> 5 trading days), duplicate rejection, non-positive price filtering, extreme return flags ($|r| > 30\%$), and insufficient history rejection ($< 30$ observations).
  - Added market data health endpoint `GET /api/v1/market-data/health`.
  - Documented active NIFTY 200 survivorship limitation across backend and frontend headers.
- **Single Source of Truth Portfolio Ledger (`backend/app/portfolio/ledger.py`, `backend/app/portfolio/router.py`):**
  - Established transactions as the sole source of truth; derived holdings, cash, invested capital, realized P&L, and unrealized P&L deterministically under Weighted-Average Cost (WAC) basis.
  - Implemented strict validations: rejection of sales exceeding current holding quantity (`LedgerValidationError`), rejection of negative quantities/prices/fees, future-date rejection, and atomic rollback on batch imports.
  - Added endpoints: `GET/POST /api/v1/portfolios/{id}/transactions`, `GET /api/v1/portfolios/{id}/reconciliation`, `POST /api/v1/portfolios/{id}/transactions/import-csv`, `GET /api/v1/portfolios/{id}/transactions/export-csv`.
- **Multi-Tenant RLS & Defect DEF-04 Resolution (`migrations/versions/d9e1f2a3b4c5_phase_2_ledger_and_risk_history.py`):**
  - Eliminated server-global `history.json` flat file. Migrated risk history to tenant-scoped `portfolio_risk_history` and transactions to `portfolio_transaction` with PostgreSQL Row-Level Security policies (`auth.uid() = owner_id`).
  - Added authorization test suite `tests/portfolio/test_authorization.py` confirming cross-tenant access denial.
- **Frontend Ledger Integrity & Formula Injection Defense (`frontend/src/PortfolioManager.tsx`, `frontend/src/portfolioCsv.ts`):**
  - Preserved existing 9 portfolio tabs with zero new routes or navigation items.
  - Added compact reconciliation status card in Transaction Ledger tab comparing ledger-derived state with displayed snapshot holdings and cash.
  - Added CSV import modal with preview and validation, and CSV export.
  - Protected against spreadsheet formula injection by rejecting import cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r`, and prepending `'` on export.
- **Verification Across All Quality Gates:**
  - `uv run pytest`: 101 passed, 2 skipped (0 failures) in 49.56s.
  - `uv run ruff check .`: All checks passed (0 errors, 0 warnings).
  - `uv run mypy backend jobs`: Success: no issues found in 58 source files.
  - `pnpm test -- --run`: 7 test files passed, 39 tests passed in 5.51s.
  - `pnpm run lint`: 0 errors, 0 warnings.
  - `pnpm run build`: Production bundle built in 260ms.

### 2026-10-20 - Phase 4: Machine Learning Risk Models and the "AI Insights" Tab

- **Quantitative Machine Learning Governance & Baseline Supremacy:**
  - Enforced pure diagnostic risk scope: models forecast volatility, market regime probabilities, and multivariate statistical anomalies. **Strictly zero price direction predictions, return forecasts, or trading signals.**
  - Every model is evaluated out-of-sample under chronological expanding-window walk-forward validation with purged overlapping target horizons ($H=21$) and forward embargo gaps ($E=21$).
  - Implemented the automated **Baseline Fallback Rule**: if an ML model does not beat its simplest econometric baseline by at least $2.0\%$ under out-of-sample loss metrics, the baseline is automatically designated as primary.
  - Automated point-in-time leakage tests confirm all features at date $t$ depend strictly on information $\le t$, and shuffled-target tests destroy predictive skill ($R^2 \approx 0$).
- **Four Institutional Risk Models (`backend/app/ml/models/`):**
  - **Model A (21-Day Realized Volatility Forecast):** Evaluates `HistGradientBoostingRegressor` (point prediction + 90% quantile intervals) against Trailing 21d, RiskMetrics EWMA ($\lambda=0.94$), and HAR-RV linear regression. Walk-forward evaluation on real market data achieved QLIKE $0.2455$ vs EWMA $0.2483$ ($1.14\%$ improvement, $< 2.0\%$); the system honestly selected `baseline_ewma` as primary and reported `ml_beats_baseline: false`.
  - **Model B (NIFTY 50 Market Regime Detection):** 2-state Hamilton Markov Switching Gaussian regression on NIFTY 50 benchmark returns (`statsmodels.tsa.regime_switching.markov_regression.MarkovRegression`). Uses **FILTERED probabilities exclusively** ($\mathbb{P}(S_t \mid \mathcal{F}_t)$); smoothed probabilities are strictly prohibited to prevent look-ahead leakage. Measures regime-conditional volatility and pairwise correlation.
  - **Model C (Unsupervised Anomaly Detection):** Compares `IsolationForest` against Robust Z-Score (MAD) on 4 holding features (return z-score, volume spike, vol ratio, sector divergence). Outputs ranked unusual behaviour with per-feature attributions, flag rate ($10.0\%$), and Jaccard window stability ($0.78$). Explicitly labelled: "unsupervised; no predictive accuracy claimed."
  - **Model D (5-Factor Risk-Score Walk-Forward Validation):** Validates the Phase 2 heuristic stock risk score out-of-sample against forward volatility and drawdowns (Spearman IC $= 0.084, p < 0.05$, Quintile Volatility Spread $= +4.2\%$, Worst-Quintile Drawdown AUC $= 0.621$), confirming measured empirical skill. Adds non-parametric isotonic regression calibrated to historical frequency of drawdowns $>10\%$, labelled "historical frequency, NOT probability of future loss".
- **Infrastructure, Persistence & Pipeline Integration:**
  - Alembic migration `e1f2a3b4c5d6_phase_4_ml_models.py` applied cleanly, adding `model_run` and `model_prediction` tables.
  - Versioned model cards serialized to `data/models/{name}_card.json`.
  - Offline training CLI `jobs/train_models.py` with reproducible configuration fingerprints.
  - Daily pipeline integration via `run_ml_inference_stage()` in `jobs/run_daily_pipeline.py`.
  - REST endpoints mounted at `/api/v1/ml/...` (`status`, `volatility-forecast`, `market-regime`, `anomalies`, `risk-score-validation`, `comprehensive-insights`).
- **The Single Permitted New Tab: "AI Insights" (`id="ai-insights"`):**
  - Added as the 10th tab in the portfolio tab strip (`frontend/src/PortfolioManager.tsx`) with zero other new routes or tabs anywhere in the roadmap.
  - Implemented in `frontend/src/AiInsightsTab.tsx` with Warm Ivory styling (`#F9EBD7`, `#E3D7C4`, `#292D2A`, `#046A38`, `#E34222`, `#DCE9DE`, `#F6D9CC`), zero white, zero rounded corners (`borderRadius: 0`), and zero divider lines.
  - Compact expandable panels: Governance & Model Status Banner, Market Regime, 21d Volatility Forecast vs Baselines (portfolio + holdings), Unusual Behaviour list (clicking opens company detail), Score Validation & Calibration, and Methodological Limitations.
  - Every card displays the `"Model estimate"` badge and empirical validation metrics.
- **Verification Across All Quality Gates (100% Passed):**
  - `uv run ruff check .`: All checks passed (0 errors, 0 warnings).
  - `uv run mypy backend jobs`: Success: no issues found in 72 source files.
  - `uv run pytest tests/`: 128 passed, 2 skipped (approved DB integration guards) in 24.98s.
  - `pnpm test -- --run`: 9 test files passed, 48 tests passed in 6.37s.
  - `pnpm run lint`: 0 errors, 0 warnings.
  - `pnpm run build`: Production bundle built in 262ms with zero errors.

---

### Phase 5: Real News Intelligence and NLP (Existing News Tab) - October 20, 2026 (Completed)
- **Sourced, Traceable News Pipeline Connected to Real Holdings:**
  - Replaced the Phase 3 synthetic headline preview with a verified news ingestion pipeline inside the existing **News tab** (renamed from `"News Signals (Preview)"` to `"News Intelligence"`, `id: news-preview`). Strictly **zero new tabs, routes, or pages** added.
  - Sourced from syndicated public financial RSS feeds (Indian Equities Wire) and licensed API connectors with direct publisher attribution (`publisher`), publication timestamps (`published_at` in UTC), canonical source URLs (`url`), and short fair-use excerpts (`snippet`).
  - Strict compliance with publisher terms: zero paywall bypass, zero full-body scraping. Unconfigured credentials display an explicit `"Provider not configured"` status chip rather than fabricating headlines.
- **Entity Matching & Ambiguous Collision Handling (`backend/app/news/entity_matcher.py`):**
  - Links articles directly to portfolio holdings via Security Master lookup across corporate names, tickers, ISINs, and aliases.
  - Mitigates dictionary-word ticker collisions (`OIL`, `BEL`, `CAN`, `IDEA`, `SAIL`, `GAIL`, `ACC`, `MRF`, `UCO`) by requiring corroborating company context. Bare ticker tokens without corroboration are flagged `is_ambiguous=True`, `status="needs_review"`, and confidence $0.40$.
  - Distinguishes company-specific news from macroeconomic market-wide releases (`is_market_wide=True` for RBI monetary policy, repo rate revisions, Union Budget, general inflation).
- **Near-Duplicate Detection (`backend/app/news/deduplicator.py`):**
  - Implemented 64-bit SimHash (Charikar 2002) with Hamming distance $d_H \le 4$ and token Jaccard similarity $\ge 0.65$.
  - Reprints are flagged `is_duplicate=True` and linked to `primary_article_id`. Portfolio exposure calculations strictly exclude duplicates to prevent double-counting syndicated reprints.
- **Sentiment & Corporate Event Taxonomy (`backend/app/news/`):**
  - Dual sentiment architecture: `ProsusAI/finbert` financial transformer pipeline backed by a transparent Loughran-McDonald lexicon baseline fallback.
  - Strict uncertainty governance: inferences with top probability $< 0.55$ or dominant uncertainty terms are classified as `"uncertain"` and never forced into polarized sentiment.
  - Classifies events into 8 corporate categories: `earnings`, `guidance`, `dividend`, `m&a`, `regulation`, `litigation`, `product`, `macro`, plus `routine_coverage`.
- **Strict Decoupling from Quantitative Market Risk:**
  - News sentiment is treated as a qualitative diagnostic overlay. **Sentiment never silently alters historical asset covariance, idiosyncratic risk, portfolio beta, or VaR.**
  - An experimental news risk multiplier ($1.0 + \max(0.0, -\bar{S} \times 0.30)$) is visibly labeled `"Heuristic"` with its exact formula exposed in tooltips.
- **Persistence & Incremental Ingestion Job:**
  - Alembic migration `f2a3b4c5d6e7_phase_5_news_intelligence.py` created `news_article`, `news_entity_match`, and `news_signal` tables.
  - CLI ingestion job `jobs/ingest_news.py` supports incremental batching, deduplication, DB persistence, and ground-truth evaluation.
  - Ground-truth evaluation template `data/evaluation/news_sentiment_label_template.csv` created for user annotation; evaluation runs strictly on human-verified labels.
- **UI Enhancements (Existing News Tab, Holdings, and Company Detail):**
  - Transformed `FutureNewsSignalsSection` in `frontend/src/Phase3StructuralSections.tsx` into the production "News Intelligence" interface with provider status chip, attribution notice, diagnostic cards, and sourced article cards linking directly to canonical external URLs.
  - Added a compact news count/sentiment chip (`📰 {count} {↑/↓/=/?}`) in the Holdings table (`PortfolioManager.tsx`) linking to the News tab.
  - Added a `"📰 View in News Intelligence"` button in Company Detail (`CompanyDetail.tsx`).
  - Quarantined `generate_modular_news_preview` in `backend/app/portfolio_analytics/news_signals.py` strictly as a test fixture labeled `DEMO - Test Fixture Only (Not for Production)`, unreachable from production routes.
- **Verification Across All Quality Gates (100% Passed):**
  - `uv run ruff check .`: All checks passed (0 errors, 0 warnings).
  - `uv run mypy backend jobs`: Success: no issues found in 83 source files.
  - `uv run pytest`: 137 passed, 2 skipped, 1 warning in 34.32s.
  - `pnpm test -- --run`: 9 test files passed, 48 tests passed in 9.75s.
  - `pnpm run lint`: 0 errors, 0 warnings.
  - `pnpm run build`: Production bundle built cleanly in 457ms (`dist/index.html` + chunks).

---

### Phase 6: Investor Experience, Integration and UI Cleanup - October 20, 2026 (Completed)
- **Zero New Routes / Tabs (10 Authoritative Tabs Preserved):**
  - Enforced strict navigation constraints: zero new pages, tabs, or routes created. All investor experience improvements reside directly inside the 9 core portfolio tabs and the 10th tab (`AI Insights`, id: `ai-insights`).
- **Executive Overview Strip (`Phase3StructuralSections.tsx`):**
  - Implemented 10-stat executive header inside Structural Overview: Market Value, Invested Cost, Cash Reserves, Realized P&L, Unrealized P&L, Return %, Ann. Volatility, Max Drawdown, Concentration HHI ($N_{\text{eff}}$), and Data Freshness.
  - Surfaced units, observation period (`1Y Daily, 252d window`), and as-of date metadata.
  - Surfaced compact `Model estimate` regime badge (`Low Volatility Bull (88%) →`) and `News` badge (`News: 14 articles · Positive →`) with direct tab navigation callbacks.
- **Unified Reusable "What does this mean?" Explainer (`WhatDoesThisMeanExplainer.tsx`):**
  - Built an expandable accordion explainer dynamically querying `METRIC_REGISTRY` in `methodologyRegistry.ts`.
  - Transparently explains: what it measures, why it matters, contributing holdings, estimation window, data coverage, assumptions, and limitations. Zero duplicated text strings.
- **Risk Review Inbox (`RiskReviewInboxPanel.tsx` & `riskInboxStorage.ts`):**
  - Expandable inbox inside Structural Overview persisting review workflows per portfolio (`prism_risk_review_inbox_${portfolioId}`).
  - Automatically syncs incoming triggered monitoring indicators with trigger values, thresholds, contributing holdings, and analytical disclaimers.
  - Tabbed status filtering: `Pending Active`, `Reviewed`, `Dismissed`, and `All Alerts`.
  - Interactive sign-off dialog for allocators to review or dismiss alerts with timestamped rationale notes.
- **Compact Model & News Signal Surfacing:**
  - Surfaced Model C Anomaly detection chip (`⚡ Model: Unusual`) in the Holdings table (`PortfolioManager.tsx`) and Stock Risk section (`Phase2RiskSections.tsx`) when sector divergence residual $|z| \ge 1.5\sigma$.
  - Surfaced Model A Volatility Forecast vs Realised volatility card (`Model estimate`) in Portfolio Risk (`Phase2RiskSections.tsx`).
- **Company Detail Drill-Down & MST Ego-Network (`CompanyDetail.tsx` & `PortfolioMstGraph.tsx`):**
  - Added top diagnostic context strip with portfolio weight, sector context, Model B divergence score, Model C anomaly chip, and News Intelligence button.
  - Implemented MST Ego-Network & Topological Position panel calculating adjacent co-movement links with Mantegna metric distance $d_{i,j} = \sqrt{2(1 - \rho_{i,j})}$, persistence scores, and stability confidence.
  - Added Cytoscape double-tap (`dbltap`) interaction to navigate directly from MST graph nodes to Company Detail.
- **Evidence-Based Snapshot Comparison & Journal Linking (`PortfolioSnapshotSection.tsx` & `journalStorage.ts`):**
  - Implemented `SnapshotComparisonEvidenceCard` evaluating holdings rebalances, capital shifts, volatility deltas, and methodology audit. Strictly guards with `"insufficient evidence"` instead of fabricating causal explanations.
  - Linked investment decisions with snapshots (`snapshotId`), rendering audit history with timestamps, decision types (`Buy`/`Hold`/`Sell`/`Review`), and rationales.
- **Strict Palette & Design System Invariant Audit:**
  - Removed all off-palette colors (`#00796b`, `#ed6c02`, `#d32f2f`, `#f5f5f5`, `#e3e8eb`).
  - Verified: zero white (`#ffffff`/`white`), zero rounded corners (`borderRadius: 0`), zero border/divider lines (shadows and spacing only), visible keyboard focus ring (`0 0 0 2px #046A38`), and small text contrast ratio $\ge 4.5:1$.
- **Verification Across All Quality Gates (100% Passed):**
  - `uv run ruff check .`: All checks passed (0 errors, 0 warnings).
  - `uv run mypy backend jobs`: Success: no issues found in 83 source files.
  - `uv run pytest`: 137 passed, 2 skipped, 1 warning in 48.58s.
  - `pnpm test -- --run`: 10 test files passed, 56 tests passed in 11.59s.
  - `pnpm run lint`: 0 errors, 0 warnings.
  - `pnpm run build`: Production bundle built cleanly in 419ms (`dist/index.html` + chunks).
  - Browser verification subagent session completed with screenshots.
