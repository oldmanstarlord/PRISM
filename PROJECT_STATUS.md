# PRISM Project Status

This is the living implementation record for PRISM. It must be updated after every material code, architecture, dependency, data-source or phase-status change.

## Current snapshot

| Field | Value |
|---|---|
| Current phase | Phase 0 - Foundations |
| Overall status | Steps 11b, 14, and 15 implemented; manual exchange files, seven-day soak, and clean empirical validation remain pending |
| Last updated | 2026-10-06 |
| Requirements source | `PRISM_SRS.md` version 1.6 |
| Initial universe | NIFTY 200 |
| Active implementation focus | Review E1/E2/E3 user-facing wording and thresholds; supply real NSE disclosure exports; approve quarantined-row cleanup; then run validation, scheduler soak, and recovery sign-off |

## Phase status

| Phase | Name | Status | Exit evidence |
|---|---|---|---|
| 0 | Foundations | In progress (15/16 items complete) | Pending teammate sign-off (SRS item 16) |
| 1 | Portfolio insight | Not started | Pending |
| 2 | Text intelligence | Not started | Pending |
| 3 | Attribution and forecasting | Not started | Pending |
| 4 | Advanced research | Not started | Pending |

## Phase 0 checklist

- [x] Consolidated SRS created.
- [x] Core technology stack selected.
- [x] Initial NIFTY 200 universe selected.
- [x] Direct component-oriented repository structure created.
- [x] Python 3.12 environment provisioned.
- [x] Python dependencies installed and locked.
- [x] Frontend dependencies installed and locked.
- [x] Supabase PostgreSQL authentication and connection verified.
- [x] Initial Alembic migration created and applied.
- [x] Current NIFTY 200 membership source integrated.
- [x] Symbol/ISIN master implemented.
- [x] `yfinance` ingestion adapter implemented.
- [x] Data-quality checks implemented for duplicates, invalid/missing OHLCV, long gaps and extreme returns.
- [x] Layer 1 mathematical and input contract approved and documented.
- [x] Layer 1 point-in-time input preparation implemented and tested.
- [x] Layer 1 deterministic calculation engine implemented and tested.
- [x] Layer 1 persistence, calculation job, read API and results dashboard implemented locally.
- [x] Layer 1 and Layer 2 formulas and interfaces designed and approved.
- [x] Layer 1 and Layer 2 implementations tested and documented.
- [x] Reproducible Layer 1 and Layer 2 pipeline demonstrated.
- [x] Walk-forward validation utilities without shuffling implemented and tested (`splits.py`).
- [x] Last-known-good dataset preservation verified by automated failure-injection test.
- [x] CI workflow added with linting, typing, pytest and frontend verification.
- [x] Setup and recovery documentation written (`docs/SETUP_RECOVERY.md`) and sign-off checklist established.
- [ ] Setup and recovery instructions tested and signed off by another team member (SRS item 16).

## Known blockers

1. Teammate sign-off for SRS item 16.
2. Shares-outstanding data not yet loaded: the strict official NSE manual-import path is ready, but no real disclosure file has been supplied.
3. Benchmark is single-source Yahoo Finance.
4. Historical NIFTY 200 membership is not available.
5. `risk_engine_parameters:2.0.0` is intentionally `draft`; explicit owner approval is required before it becomes the default.
6. Previously imported fixture announcement/news/macro rows remain quarantined pending the exact cleanup approval phrase `APPROVE CLEANUP`; no production Step 12 score run has been executed against them.
7. Step 13 historical backfill/validation must not run on those contaminated inputs;
   empirical score, confidence, ablation, and Layer 1 conclusions remain unproven.
8. The Step 14 seven-day soak has not started: running the scheduler would score
   the quarantined fixture-derived inputs. The soak report records this plainly.
9. A real Supabase restore drill and teammate recovery sign-off remain external,
   destructive/coordination-sensitive checks and have not been claimed complete.

## Verification status

| Check | Result | Last run |
|---|---|---|
| Python environment | Python 3.12 provisioned by `uv` | 2026-10-05 |
| Python dependency lock | `uv lock --check` passed; `pyarrow>=25.0.1` locked; optional `ml` extra | 2026-10-05 |
| Ruff | Passed (0 errors across workspace) | 2026-10-06 |
| mypy strict mode | Passed (162 source files checked in backend and jobs, 0 errors); default paths are configured so `uv run mypy` is the exact gate | 2026-10-06 |
| pytest | Passed (267 tests, 0 failures, 1 dependency deprecation warning); DB-backed tests are transaction-isolated and rolled back | 2026-10-06 |
| ESLint | Passed (0 errors, 0 warnings across frontend) | 2026-10-06 |
| Vitest | Passed (55 tests across 18 suites, 0 failures) | 2026-10-06 |
| TypeScript/Vite production build | Passed; pre-existing Plotly chunk-size advisory remains | 2026-10-06 |
| Frontend frozen lockfile | `pnpm install --frozen-lockfile` passed with exact pinned versions | 2026-10-05 |
| Layer 1 and Layer 2 Immutability | Passed (0 git diff on `backend/app/correlation_mst` and `backend/app/sector_divergence`) | 2026-10-05 |
| Playwright smoke | Passed (1 end-to-end demo flow in Chromium) | 2026-10-06 |
| Alembic head | Exactly one head/current: `c1d2e3f4a520`; additive Step E3 config SQL inspected and applied successfully | 2026-10-06 |
| NIFTY 200 Benchmark Ingestion | Dry-run passed; all 7 PASS RULES passed; single source `^CNX200` verified (`docs/evidence/benchmark_check.md`) | 2026-10-05 |
| Step 5 Risk & Confidence Engine | Audited against RISK_SCORE_SPEC and CONFIDENCE_SPEC; no silent fallback on missing benchmark; all 145 tests green | 2026-10-05 |
| Step 6 Shock & Diversification | Shock scenarios, diversification run engine, MST-cluster HHI and portfolio diversification cards implemented; API and frontend verified | 2026-10-05 |
| Step 7 Fundamentals as Components | 4 fundamental components (leverage, coverage, profit trend, cash flow quality) registered; FundamentalsPanel rendered and tested | 2026-10-05 |
| Step 12 Full Score | Eight-dimension coverage contract, draft v2 config, real-input confidence, portfolio synthesis, change explanations, ablation, APIs and UI implemented; activation pending approval | 2026-10-06 |
| Step 13 Honest Validation | Persistence, PIT backfill job, forward labels, time-ordered metrics/baselines, ablation, calibration, Layer 1 bands, API and UI implemented; empirical run blocked by quarantined fixture inputs | 2026-10-06 |
| Step 14 Operations | Configured DAG, retries/failure isolation, freshness, explainable alerts, watchlists, incremental rescoring, APIs/UI and export/backup procedure implemented; seven-day soak not started | 2026-10-06 |
| Step 15 Demonstration | Three fixture portfolios, one-command loader, Playwright smoke, limitations page, demo/viva/architecture/recovery docs and final SRS audit implemented | 2026-10-06 |
| Step 11b Permitted Sources | 18-row source registry, verified RBI/SEBI RSS metadata ingestion, strict manual NSE importers, source-aware freshness API/UI, and refresh documentation implemented; real governance exports remain pending | 2026-10-06 |
| Step E1 Explanation Framework | Evidence-bound component explanations, deterministic guardrails, draft templates/glossary, APIs, generic drawer/tooltips, and Why actions implemented; wording approval pending | 2026-10-06 |
| Step E2 MST Explanations | Evidence-bound edge/pair/node explainers, deterministic MST math, APIs, interactive drawer/search/legends, and tests implemented; wording approval and production diagnostics remain pending | 2026-10-06 |
| Step E3 Sector Explanations | Evidence-bound stock/industry divergence explainers, read-only peer reconstruction, APIs, stock panels, and sectors overview implemented; draft thresholds await review | 2026-10-06 |
| Step E4 News Impact Engine | Multi-channel transmission (direct, rule, macro, spillover), MAX combination, recency decay, evidence on every row, API routes, honest empty state, drawer UI, tests verified; real-data run completed; config draft pending approval | 2026-10-06 |

## Update protocol

After every material update:

1. Update the current snapshot and relevant checklist.
2. Add a dated entry to the change log.
3. Record verification commands and results.
4. Record new blockers or decisions.
5. Change a phase to complete only when its SRS exit criteria are satisfied.

## Change log

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

### 2026-10-04 - Step 0b: Validation splits, last-known-good test, CI and recovery docs

- Implemented `backend/app/validation/splits.py` with `walk_forward_splits` and `purged_kfold`.
- Strictly enforced time ordering (raises `ValueError` for unsorted dates or test indices preceding train indices), disallowed any `shuffle` parameter, and added support for embargo and label purging.
- Added 23 unit tests in `tests/validation/test_splits.py` covering hand-calculated 20-date boundary tests, determinism tests, and look-ahead invariants.
- Confirmed failure isolation in `backend/app/market_data/service.py` where failed symbol ingestion triggers transactional rollback without deleting or overwriting pre-existing rows. Added `tests/market_data/test_service.py` verifying failure isolation and idempotency.
- Created `.github/workflows/ci.yml` covering backend linting (Ruff), strict type checking (mypy on 35 files), test execution (pytest 59 tests), and frontend linting/testing/building with pnpm/Node 20.
- Authored `docs/SETUP_RECOVERY.md` detailing fresh-machine bootstrap, migration, seeding, pipeline execution, Supabase backup/restore, and a teammate sign-off checklist.
- Recorded proposed decisions in `docs/specs/PROPOSED_DECISIONS.md`.
- Phase 0 acceptance status: 15 of 16 criteria verified; criteria 16 remains open pending teammate sign-off.

### 2026-10-04 - Step 1: Math specs, model_config, component registry and audit persistence

- Saved master context to `docs/agent/MASTER_CONTEXT.md`.
- Authored three core mathematical and operational specifications with worked numeric examples:
  - `docs/specs/PORTFOLIO_MATH_SPEC.md`: Input modes (quantity/weight), cash line, valuation at adjusted close, 252 annualisation factor, 250d window, buy-and-hold, NIFTY 200 benchmark, missing/stale rules, and worked portfolio return/variance/volatility example.
  - `docs/specs/RISK_SCORE_SPEC.md`: 8-dimension risk score aggregation (Market 25, Fundamentals 20, Liquidity 10, Structure 10, Relative 10, Governance 10, Events 10, Macro 5), weak empirical percentile tie-breaking, direction per component, missing-dimension re-normalisation, coverage metric, component point contributions, top-3 reasons, and worked numeric example.
  - `docs/specs/CONFIDENCE_SPEC.md`: 6-factor confidence engine (coverage, freshness, source agreement, signal agreement, model stability, evidence volume), linear freshness decay, hard caps (stale price <= 50, coverage < 0.70 <= 60), and worked numeric example.
- Recorded Step 1 proposed decisions PD-4, PD-5, and PD-6 in `docs/specs/PROPOSED_DECISIONS.md`.
- Implemented additive Alembic migration `e1a8b9c7f201` for 7 tables (`model_config`, `score_component_definition`, `score_run`, `stock_risk_result`, `score_component_value`, `confidence_factor_value`, `audit_log`) and draft seeds for configuration and component definitions. Offline PostgreSQL DDL verified via `alembic upgrade ... --sql`.
- Built typed backend module `backend/app/core/model_config.py` with Pydantic validation, canonical SHA-256 JSON hashing, config fingerprinting, and DB loaders.
- Built component registry `backend/app/risk_score/registry.py` implementing `Component` protocol (D2), seed definitions for Step 5 price-side components (`active=False`), and inactive placeholders.
- Built audit logging helper `backend/app/core/audit.py` (`write_audit`).
- Exposed read-only configuration and metadata endpoints in `backend/app/api/v1/router.py`: `GET /api/v1/config/models`, `GET /api/v1/config/components`, and `GET /api/v1/meta`.
- Added 14 unit tests across `tests/core/test_model_config.py`, `tests/risk_score/test_registry.py`, `tests/api/test_config_endpoints.py`, and spec verification tests `test_portfolio_math_spec.py`, `test_risk_score_spec.py`, and `test_confidence_spec.py`. Total test suite passes: 73 tests.

### 2026-10-05 - Step 2: Benchmark series, shares outstanding, liquidity & market stats, price cross-check

- Clarified and resolved SRS OQ-8 with user authorization: official NSE/BSE quarterly shareholding filings archived point-in-time via manual/scheduled CSV import. Recorded PD-7 in `docs/specs/PROPOSED_DECISIONS.md`.
- Implemented additive Alembic migration `f2b9c8d1e302` creating 5 tables: `benchmark_definition`, `benchmark_series`, `security_share_count`, `security_market_stat`, and `data_crosscheck`. Seeded `NIFTY_200` benchmark definition. DDL verified offline with `alembic upgrade e1a8b9c7f201:f2b9c8d1e302 --sql` (strictly additive, zero destructives).
- Benchmark Module (`backend/app/market_data/benchmark.py`):
  - Defined `BenchmarkAdapter` protocol (FR-D9) and `CsvBenchmarkAdapter` implementation.
  - Implemented quality validation checking date uniqueness, non-positive close values, high-low inversion, and extreme index return outliers (> 15% day-over-day).
  - Researched Nifty Indices access: official provider does not provide open unauthenticated REST API with SLA; documented CSV ingestion policy to respect terms and ensure reliability.
- Shares Outstanding Module (`backend/app/market_data/shares.py`):
  - Implemented `SharesAdapter` protocol and `CsvSharesAdapter` parser for quarterly filings.
  - Enforced strict point-in-time publication rule (D4): share count filings carry both `as_of` and `published_at`; `get_effective_shares` strictly prohibits back-filling prior to `published_at`.
- Derived Liquidity & Market Stats (`backend/app/market_data/market_stats.py`):
  - Derived $\text{traded\_value} = \text{close} \times \text{volume}$.
  - Computed rolling 20-day average daily traded value ($\text{adv\_20}$).
  - Computed $\text{market\_cap} = \text{adjusted close} \times \text{point-in-time shares\_outstanding}$.
  - Detected and flagged liquidity anomalies: `zero_volume` and `thin_trading` ($\text{adv\_20} < \text{INR 10,000,000}$).
- Price Cross-Check Engine (`backend/app/market_data/crosscheck.py`):
  - Compared primary feed prices (`yfinance`) against secondary exchange data (`exchange_daily_bhavcopy`).
  - Recorded relative price discrepancies in `data_crosscheck`.
  - Calculated aggregate mismatch rate and ranked worst offenders.
  - Strictly enforced non-destructive quality policy: NO automated overwriting or modification of price records.
- Ingestion & Derivation Jobs:
  - `jobs/ingest_benchmark.py`: Ingests benchmark series with pipeline run manifests.
  - `jobs/derive_market_stats.py`: Derives traded value, ADV-20, and market cap for all securities.
  - `jobs/crosscheck_prices.py`: Performs sampled or full price feed cross-checks.
- API Endpoints (`backend/app/api/v1/router.py`):
  - `GET /data/quality/summary`: Returns dataset health summary, flagged records, and quality policy statement.
  - `GET /data/freshness`: Returns latest observed trade date and ingested timestamp across datasets.
  - `GET /data/crosscheck/latest`: Returns latest cross-check run statistics, mismatch rate, and worst discrepancy records.
- Automated Tests (13 new tests, 86 total passing):
  - `tests/market_data/test_benchmark.py`: Csv parsing, duplicate rejection, extreme return flagging, high-low validation.
  - `tests/market_data/test_shares.py`: Point-in-time publication constraint (no back-filling before published_at), CSV parsing.
  - `tests/market_data/test_market_stats.py`: Hand-calculated traded value, market cap, rolling ADV-20, and thin-trading flag checks.
  - `tests/market_data/test_crosscheck.py`: Discrepancy comparison, mismatch rate computation, worst offenders sorting, no auto-correction.
  - `tests/api/test_data_endpoints.py`: Validation of `/data/quality/summary`, `/data/freshness`, and `/data/crosscheck/latest`.

### 2026-10-05 - Step 2b: Multi-page frontend foundation, shared data components, data health

- Pinned exact dependencies in `frontend/package.json` matching `pnpm-lock.yaml` (replaced all `"latest"` tags).
- Built shared layout (`AppLayout.tsx`):
  - Header branding and unified navigation for all 7 platform views: Sector Divergence (`/`), MST (`/mst`), Portfolio (`/portfolio`), Stocks (`/stocks`), Shock (`/shock`), Validation (`/validation`), and Data Health (`/data-health`).
  - Active route highlighting using React Router.
  - Created `PlaceholderPage.tsx` for unbuilt routes with informative "coming in a later step" states.
  - Shared regulatory disclaimer footer dynamically reading `/api/v1/meta` with fallback.
  - Removed duplicated headers from `Dashboard.tsx`, `CompanyDetail.tsx`, and `MstPage.tsx`.
- Built generic, data-driven shared components (`frontend/src/components/`):
  - `FreshnessBadge`: Computes and displays data age with green/amber/red stale coloring (stale >= 5 days).
  - `StatusChip`: Maps operational statuses (approved, draft, match, mismatch, normal, moderate, extreme).
  - `EmptyState`: Standardized empty view with call-to-action button.
  - `ErrorState`: Alert card with user-friendly error message and retry trigger.
  - `ExplainPanel`: Renders the SRS Section 10 result envelope (method + version, input fingerprint, lookback, thresholds, confidence score and caps, limitations).
  - `BreakdownBars`: Generic component breakdown table rendering percentiles, risk points, weights, age, and driver reasons without hardcoding dimension or component names (D5).
- Upgraded data layer (`frontend/src/api.ts`):
  - Implemented `@tanstack/react-query` `useApi` hook with query keys, stale time (60s), retry logic, and abort signals.
  - Refactored `Dashboard.tsx`, `CompanyDetail.tsx`, `MstPage.tsx`, and `AppLayout.tsx` from raw `useEffect`/`fetch` to `useApi`.
- Implemented Data Health page (`/data-health` in `frontend/src/DataHealthPage.tsx`):
  - Ingests and renders `/data/quality/summary`, `/data/freshness`, and `/data/crosscheck/latest`.
  - Displays dataset timestamps, anomaly counters (zero-volume and thin-trading), quality policy statement, and worst cross-check discrepancies table.
- Automated Frontend Testing (17 Vitest tests passing across 4 suites):
  - `routes.test.tsx`: Validates rendering of every registered route (`/`, `/mst`, `/portfolio`, `/stocks`, `/shock`, `/validation`, `/data-health`, `/companies/TEST`) inside `AppLayout` and verifies the regulatory disclaimer is rendered on every page.
  - `components.test.tsx`: Validates `ExplainPanel`, `BreakdownBars`, `FreshnessBadge`, `StatusChip`, `EmptyState`, and `ErrorState` using fixture payloads.
  - Existing `App.test.tsx` and `CompanyDetail.test.tsx` continue to pass.
  - ESLint (0 errors, 0 warnings), Vitest (17 passed), and Vite production build (`dist/` generated) all verified.

### 2026-10-05 - Step 3: Portfolio input and core risk metrics (SRS FR-P1, FR-R1 to FR-R7)

- **Database Migration (`c3d4e5f6a703_step_3_portfolio_engine_schema.py`)**:
  - Additive migration adding 5 tables: `portfolio`, `portfolio_holding`, `portfolio_risk_run`, `portfolio_risk_contribution`, and `analytics_artifact`.
  - Added `owner_ref` column (default `'local-user'`) with indexed ownership for single local user mode; noted SRS NFR-7 privacy limitation in documentation.
  - Verified static SQL generation offline via `alembic upgrade f2b9c8d1e302:c3d4e5f6a703 --sql` confirming 100% additive DDL (5 new tables, indexes, constraints, 0 drops or column alterations).
- **Backend Architecture (`backend/app/portfolio/`)**:
  - `parser.py`: Multi-format input parser (CSV and JSON) supporting target weight ($w_i$) and quantity ($q_i$) modes. Symbol resolution against `security_alias` (date-valid) and `security.isin`, with special handling for `CASH`/`INR`. Row-level validation reporting duplicate symbols, non-numeric values, negative quantities/weights, and unresolvable assets. Automatic residual allocation to explicit `CASH` holding per PORTFOLIO_MATH_SPEC.md when weights sum $< 1.0$, scaling when $> 1.0$.
  - `covariance.py`: Strict point-in-time ($trade\_date \le as\_of$) log returns panel from `price_daily_adjusted`. Ledoit-Wolf shrinkage covariance estimation via `sklearn.covariance.LedoitWolf`, reporting shrinkage intensity $\lambda$. Supported exact sample covariance (`shrinkage=0`) for testing. Serialized covariance matrix to Parquet with SHA-256 hash stored in `analytics_artifact`.
  - `metrics.py`: Annualized volatility $\sigma_p = \sqrt{w' \Sigma w} \times \sqrt{252}$, Marginal Risk Contributions $MRC_i = (\Sigma w)_i / \sigma_p$, Percentage Risk Contributions $PRC_i = w_i (\Sigma w)_i / \sigma_p^2$ strictly satisfying Euler decomposition $\sum w_i MRC_i = \sigma_p$ and $\sum PRC_i = 1.0$. Benchmark beta estimation ($\beta_i = \mathrm{Cov}(r_i, r_m)/\mathrm{Var}(r_m)$, $\beta_p = \sum w_i \beta_i$) vs official `NIFTY 200` series. Drawdown time series and max drawdown ($MDD$). 1-day 95% Parametric VaR/ES (Normal distribution) and Historical VaR/ES. Concentration metrics: Holding HHI, Effective N ($1/HHI$), Industry HHI, and Layer 2 MST Cluster HHI.
  - `service.py`: Orchestrator implementing D3 ResultEnvelope (`SRS Section 10`), input fingerprinting (`canonical_json_hash` over sorted holdings and weights), and D6 idempotent re-runs reusing existing runs without duplicate records.
- **API Endpoints (`backend/app/api/v1/router.py`)**:
  - `POST /api/v1/portfolios`: Creates portfolio and snapshots normalized holdings.
  - `POST /api/v1/portfolios/import-csv`: Parses and imports CSV file or text with row-level error reporting.
  - `GET /api/v1/portfolios`: Lists user portfolios.
  - `GET /api/v1/portfolios/{id}`: Retrieves portfolio details and current holdings.
  - `POST /api/v1/portfolios/{id}/risk-runs`: Computes or retrieves cached risk decomposition.
  - `GET /api/v1/portfolios/{id}/risk/latest`: Retrieves latest risk run and result envelope.
- **Frontend (`/portfolio` in `frontend/src/PortfolioPage.tsx`)**:
  - Dynamic tabs for manual entry (with react-hook-form + zod) and CSV upload with row-level error display.
  - 4 Key metric summary cards (Annualized Volatility, Benchmark Beta, Max Drawdown, 1-Day VaR & ES).
  - Plotly interactive charts (`PortfolioCharts.tsx`): Risk contribution bar chart (PRC vs Capital Weight) and historical drawdown curve.
  - Concentration tables for Holdings (HHI, Effective N, Top Weight), Industry allocation, and Layer 2 MST clusters.
  - Integrated `ExplainPanel` rendering full D3 ResultEnvelope and `FreshnessBadge`.
  - Updated `App.tsx` routing `/portfolio` to `PortfolioPage`.
- **Verification & Testing (96 Python tests + 20 Frontend tests)**:
  - `tests/portfolio/test_portfolio_math.py`: Hand-calculated worked example: weights `[0.5, 0.3, 0.2]`, vols `[0.2, 0.3, 0.25]`, correlations `0.6/0.4/0.5` $\implies$ portfolio volatility $19.97\%$, risk contributions $43.6\% / 39.5\% / 16.9\%$. Weight normalization with cash, beta on constructed proportional series, max drawdown on toy path, CSV row-level error validation.
  - `tests/portfolio/test_portfolio_service.py`: Point-in-time no-look-ahead validation, D6 idempotent re-run (zero new rows on re-run), Parquet artifact persistence.
  - `tests/api/test_portfolio_endpoints.py`: Portfolio creation, CSV upload, and risk run endpoints.
  - `frontend/src/PortfolioPage.test.tsx`: Vitest tests for CSV validation error display, empty input validation, and route rendering.
  - Gates passed: `ruff check` (0 errors), `mypy` (52 files clean), `pytest` (96 passed), `eslint` (0 errors), `vitest` (20 passed), `vite build` (clean production build).

### 2026-10-05 - Step 4: MST Trust & Diagnostics (SRS Section 6, FR-M1 to FR-M5)

- **Database Migration (`d4e5f6a7b804_step_4_mst_diagnostics.py`)**:
  - Additive migration adding 3 tables: `mst_stability`, `mst_cluster`, and `mst_node_metric`.
  - Seeded approved model configuration `mst_diagnostics` (version `1.0.0`) in `model_config` with canonical SHA-256 JSON checksum.
  - Verified static SQL generation offline via `alembic upgrade c3d4e5f6a703:d4e5f6a7b804 --sql` confirming 100% additive DDL (3 tables, indexes, constraints, 1 seed row, 0 drops or column alterations).
- **Backend Architecture (`backend/app/mst_diagnostics/`, strictly outside Layer 2)**:
  - `config.py`: Configuration loader for `mst_diagnostics` with versioned fallback defaults.
  - `stability.py`: Edge persistence $|E_t \cap E_{t-1}| / |E_t|$, node overlap $|V_t \cap V_{t-1}| / |V_t|$, window gap days, and stability grade classification (HIGH $\ge 0.65$, MEDIUM $\ge 0.45$, LOW $< 0.45$).
  - `clustering.py`: Deterministic segmentation via $k$-longest edge cuts ($k=10$ by default) with canonical tie-breaking (`distance DESC, symbol_a ASC, symbol_b ASC`). Connected components assigned to `cluster_id` (`CLUST-01`, `CLUST-02`, etc.) sorted by `size DESC, min_symbol ASC`. Node metrics: degree in MST, weighted centrality ($\sum \rho_{uv}$ on incident edges), and hub rank ordered by `degree DESC, weighted_centrality DESC, symbol ASC`.
  - `residual.py`: Point-in-time market model OLS regression ($r_{i,t} = \alpha_i + \beta_i r_{m,t} + \epsilon_{i,t}$) removing market factor co-movement ($\text{Cov}(\epsilon_i, r_m) = 0$). Cumulative synthetic price series fed directly to unchanged Layer 2 `calculate_mst`.
  - `service.py`: Orchestrator computing and persisting diagnostics for MST runs, providing API data with cluster membership and node metrics.
  - `history.py`: Rolling weekly MST window runner over $N=26$ historical windows computing sequential stability and comparative persistence (raw vs residual).
- **API Endpoints (`backend/app/api/v1/router.py`)**:
  - `GET /api/v1/mst/latest?variant=raw|residual`: Enriched with variant, stability grade, edge persistence, clusters count, and node metrics (degree, hub rank, cluster ID).
  - `GET /api/v1/mst/stability/latest?variant=raw|residual`: Latest stability transition and history summary across rolling windows.
  - `GET /api/v1/mst/clusters/latest?variant=raw|residual`: Deterministic cluster mappings and member counts.
  - `GET /api/v1/mst/nodes/{symbol}/metrics?variant=raw|residual`: Node degree, centrality, hub rank, cluster peers, and incident tree edges.
- **Frontend (`/mst` in `frontend/src/MstPage.tsx`)**:
  - Added Tree Variant Selector: `Raw Returns MST` vs `Residual Variant (Market Neutral)`.
  - Added Color Encoding Toggle: `Industry` palette vs `Cluster (k-cut forest)` palette.
  - Added dynamic Stability Badge rendering the current stability grade (HIGH/MEDIUM/LOW) and edge persistence percentage.
  - Interactive Node Side Panel displaying Symbol, Industry, Degree, Hub Rank, Weighted Centrality, Cluster Peers (clickable chips to navigate and select peers in the graph), and Incident Tree Connections table.
  - Integrated `ExplainPanel` (`frontend/src/ExplainPanel.tsx`) detailing descriptive non-causal limitations, sparse subset disclaimer, and scenario boundaries.
- **Verification & Testing (108 Python tests + 25 Frontend tests)**:
  - `tests/mst_diagnostics/test_stability.py`: Hand-calculated worked example: 2 of 4 edges preserved $\implies 50\%$ persistence, grade MEDIUM; complete preservation (100%) and complete turnover (0%).
  - `tests/mst_diagnostics/test_residual.py`: Verification that OLS residuals have zero correlation with benchmark ($< 1e-12$), parameter recovery, and execution of synthetic residual panel through unchanged Layer 2 calculator.
  - `tests/mst_diagnostics/test_clustering.py`: Verification of deterministic tie-breaking on equal edge distances, component ordering, and star-topology hub ranking.
  - `tests/mst_diagnostics/test_layer2_untouched.py`: Verified `backend/app/correlation_mst/` has 0 git diff.
  - `tests/api/test_mst_endpoints.py`: Unit tests for `/mst/latest`, `/mst/stability/latest`, `/mst/clusters/latest`, and `/mst/nodes/{symbol}/metrics`.
  - `frontend/src/MstPage.test.tsx`: 5 Vitest tests for header, stability badge, variant selector, color toggle, and ExplainPanel.
  - All gates clean: `ruff check` (0 errors), `mypy` (60 files clean), `pytest` (108 passed), `eslint` (0 errors), `vitest` (25 passed), `vite build` (clean production build).


### 2026-10-05 - Step 5: Risk & Confidence Engine (SRS FR-R8 to FR-R14, CONFIDENCE_SPEC)

- **Database Migration (`e5f6a7b8c905_step_5_score_components_activation.py`)**:
  - Seeded all approved score component definitions to `active=True` and set canonical SHA-256 configuration fingerprints for the risk engine.
  - Verified offline via `alembic upgrade d4e5f6a7b804:e5f6a7b8c905 --sql`.
- **Risk Score Engine (`backend/app/risk_score/`)**:
  - Implemented the 8-dimension score aggregation per `RISK_SCORE_SPEC.md`: Market 25, Fundamentals 20, Liquidity 10, Structure 10, Relative 10, Governance 10, Events 10, Macro 5.
  - Implemented weak empirical percentile tie-breaking, missing-dimension re-normalisation, top-3 reasons, and coverage metric.
  - Added price-side components: EWMA volatility, downside semi-deviation, max drawdown, beta-to-benchmark, liquidity ratio.
  - Implemented the 6-factor confidence engine per `CONFIDENCE_SPEC.md` with linear freshness decay and hard caps.
  - Added strict no-silent-fallback: missing NIFTY 200 benchmark raises `DataUnavailableError` instead of defaulting to zero.
- **API**: `GET /api/v1/stocks/{symbol}/risk/latest` and `GET /api/v1/stocks/{symbol}/risk/history`.
- **Frontend (`/stocks/:symbol` in `StockDetailPage.tsx`)**: Dynamic component breakdown, risk score gauges, trajectory cards, ExplainPanel.
- **Tests**: 37 new tests; all 136 passed.

### 2026-10-05 - Step 6: Shock Simulation & Diversification (SRS FR-S1 to FR-S5, FR-P8)

- **Database Migration (`f6a7b8c9d006_step_6_diversification_shock.py`)**:
  - Additive migration adding `diversification_run` and `shock_scenario` tables.
  - Seeded `shock_simulation` model config with canonical SHA-256 fingerprint.
  - Verified offline via `alembic upgrade e5f6a7b8c905:f6a7b8c9d006 --sql`.
- **Backend Architecture (`backend/app/portfolio/shock.py`, `diversification.py`)**:
  - `shock.py`: Historical-correlation and user-defined shock scenarios applied to portfolio weights with parametric VaR/ES re-computation. Descriptive scenario framing (not a forecast).
  - `diversification.py`: Computed diversification score from MST cluster HHI, industry HHI, and holding HHI; scored 0-100 with text interpretation.
- **API**: `POST /api/v1/portfolios/{id}/shock-run`, `GET /api/v1/portfolios/{id}/shock/latest`, `GET /api/v1/portfolios/{id}/diversification/latest`.
- **Frontend**: `ShockPage.tsx` with scenario input, result rendering and SRS Section 10 envelope; diversification cards on `/portfolio`.
- **Tests**: New tests for shock math, diversification scoring, API endpoints; all gates passed.

### 2026-10-05 - Step 7: Fundamentals as Score Components (SRS FR-F1 to FR-F7)

- **Database Migration (`a7b8c9d0e107_step_7_fundamentals.py`)**:
  - Additive migration adding `source_document`, `fundamental_period`, and `fundamental_metric` tables.
  - Seeded 4 fundamental component definitions in `score_component_definition`.
  - Verified offline via `alembic upgrade f6a7b8c9d006:a7b8c9d0e107 --sql`.
- **Backend Architecture (`backend/app/fundamentals/`)**:
  - `adapters/base.py`: `ResultAdapter` protocol.
  - `adapters/file_import.py`: CSV and JSON ingestion (point-in-time, versioned restatements).
  - `adapters/yfinance_adapter.py`: Yahoo Finance adapter with 15% freshness discount for estimated publication dates.
  - `metrics.py`: TTM and point-in-time ratio computation (debt/equity, interest coverage, profit growth trend, CFO/PAT quality).
  - `service.py`: `get_stock_fundamentals` profile builder with peer percentile computation.
  - `ingest_results.py` job: Idempotent incremental ingestion.
- **Risk Integration**: 4 fundamental components (`fund_leverage`, `fund_coverage`, `fund_profit_trend`, `fund_cashflow_quality`) registered in `backend/app/risk_score/components/fundamentals.py` and `registry.py`. Confidence discounted 15% for estimated publication dates.
- **API**: `GET /api/v1/stocks/{symbol}/fundamentals`.
- **Frontend**: `FundamentalsPanel.tsx` renders quarterly periods table, TTM ratio cards with peer percentile bars, source chip, and limitations list. Integrated into `StockDetailPage.tsx`.
- **mypy overrides**: Per-module `warn_unused_ignores = false` added to `pyproject.toml` for frozen Layer 1/2 files only, restoring strict mypy across 85 files.
- **Tests**: 145 Python tests (0 failures); 29 Vitest tests (0 failures); ruff 0 errors; mypy 0 errors.

### 2026-10-05 - Step 9: Macro Series, Rule-Based Market Regime, & Sector Sensitivity (SRS FR-F4, OQ-10)

- **Database Migration (`c9d0e1f2a309_step_9_macro_regime_sensitivity.py`)**:
  - Additive migration adding 4 tables: `macro_series_definition`, `macro_observation`, `market_regime`, and `sector_macro_sensitivity`.
  - Added unique constraints, foreign keys, and indexes for deterministic lookup and point-in-time point queries.
  - Applied and verified against live Supabase PostgreSQL database.
- **Series Selection & Adapters (`backend/app/macro/adapters/`)**:
  - Resolving SRS OQ-10, five macro series implemented: Brent Crude Oil (`crude_oil`, Yahoo `BZ=F`), USD/INR (`usd_inr`, Yahoo `INR=X`), India 10Y Sovereign Yield (`in_10y_yield`, CSV/Yahoo), India VIX (`india_vix`, Yahoo `^INDIAVIX`), FII/DII Net Flows (`fii_dii_net_flows`, NSE CSV).
  - Clean `MacroSeriesAdapter` protocol with Yahoo Finance and CSV fallback implementations.
  - Ingestion job `jobs/ingest_macro.py` populated all 5 series into live database with point-in-time publication tracking.
- **Rule-Based Market Regime Classification with Hysteresis (`backend/app/macro/regime.py`, `jobs/calculate_regime.py`)**:
  - Classification driven by 21-day rolling realised volatility percentile vs 252-day history, average pairwise correlation percentile, and India VIX level.
  - Regime multipliers: `calm` = 1.00x, `trending` = 1.25x, `stressed` = 1.50x.
  - Pure 5-day exit hysteresis state machine prevents rapid whipsawing when exiting `stressed` market conditions.
- **Rolling OLS Sector Macro Sensitivity (`backend/app/macro/sensitivity.py`, `jobs/calculate_macro_sensitivity.py`)**:
  - Rolling 63-day regression of 18 Layer 1 equal-weighted industry returns on daily deltas of each macro series.
  - Insignificance filter ($|t| \ge 1.96$, $p \le 0.05$): Insignificant exposures are set to zero (no forced exposure).
- **Dynamic Risk Score Component (`macro_exposure`)**:
  - Registered in `backend/app/risk_score/components/macro.py` under dimension `macro` (5% starting weight).
  - Formulated as $\sum_s |\beta_{\text{ind}, s} \cdot \mathbf{1}_{\text{sig}}| \times |z_s| \times M_{\text{regime}}$.
  - Specified with hand-calculated worked example in `docs/specs/MACRO_SPEC.md`.
- **API Endpoints**:
  - `GET /api/v1/macro/regime/latest`: Latest market regime, features, multiplier, and hysteresis status.
  - `GET /api/v1/macro/series`: List all registered macro series.
  - `GET /api/v1/macro/series/{key}`: Detailed observations for series with point-in-time filtering.
  - `GET /api/v1/macro/sensitivities`: All sector sensitivities across industries.
  - `GET /api/v1/industries/{industry}/macro-sensitivity`: Sensitivities for a specific industry.
  - `GET /api/v1/stocks/{symbol}/macro`: Full stock macro exposure profile.
- **Frontend**:
  - `AppLayout.tsx`: Top market regime status banner showing active regime, RV percentile, correlation percentile, VIX, multiplier, and link to `/macro`.
  - `MacroPage.tsx`: Interactive regime card, Plotly line chart with series switcher, and filterable sector sensitivity table with significance chips.
  - `MacroPanel.tsx`: Stock-level macro breakdown integrated into `StockDetailPage.tsx`.
- **Tests & Quality Gates**:
  - Python tests: `tests/macro/test_macro_math.py` (5 tests), `test_regime.py` (7 tests), `test_macro_point_in_time.py` (2 tests), `test_macro_api.py` (6 tests). Total Python tests: 182 passed.
  - Frontend tests: `MacroPage.test.tsx` (5 tests), `routes.test.tsx` (10 tests). Total Vitest tests: 36 passed across 9 suites.
  - All 6 gates clean: `ruff` (0 errors), `mypy` (106 files clean), `pytest` (182 passed), `pnpm lint` (0 errors), `pnpm test` (36 passed), `pnpm build` (clean bundle).

### 2026-10-05 - Step 10: Corporate Announcements & Explainable Events (Dimension: Events, SRS OQ-9)

- **Database Migration (`d0e1f2a3b410_step_10_events_intelligence.py`)**:
  - Additive migration adding 3 tables: `event_rule` (dynamic classification rules), `event_item` (point-in-time announcements), and `text_score` (NLP sentiment & evidence extraction).
  - Seeded 13 canonical `event_rule` rows covering standard exchange categories.
  - Seeded `model_config` row for `event_risk_pressure` (v1.0.0, checksummed, approved) and registered `event_risk_pressure` in `score_component_definition` (10% weight, dimension: `events`).
  - Verified offline via `alembic upgrade c9d0e1f2a309:d0e1f2a3b410 --sql` and applied to live Supabase Postgres database.
- **Backend Architecture (`backend/app/events/`)**:
  - `adapters/base.py`: Clean `AnnouncementAdapter` protocol and `RawAnnouncement` model.
  - `adapters/exchange_adapter.py` & `adapters/json_adapter.py`: Official exchange corporate announcement feed adapter with resilient local fallback (`data/announcements/announcements.json`).
  - `rules.py`: Dynamic rule mapping from exchange categories to canonical event types, security linking hierarchy (ISIN exact > symbol exact via `security_alias` > flagged company name fallback), and after-close (15:30 IST) next-day trading calendar rollover (D4).
  - `importance.py`: Resolves SRS OQ-9 via explainable formula: $\min(10.0, \max(1.0, \text{base\_weight} \times \text{magnitude\_multiplier}))$.
  - `finbert.py`: Switchable FinBERT engine pinned to exact HuggingFace revision `90eb618b0f7ca7067d2feae4d588523ee734c5db`. Default disabled via `model_config` (`finbert_enabled: false`), with deterministic zero-dependency financial dictionary fallback. Token chunking and multi-chunk aggregation implemented.
  - `eval_finbert.py`: Evaluation script reporting accuracy and per-class precision/recall/F1 on `data/labelled/labelled_examples.csv` (100% precision/recall across classes).
  - `service.py`: Query service for stock timeline and global announcement feed.
- **Idempotent Background Jobs**:
  - `jobs/ingest_announcements.py`: Incremental, idempotent ingestion into `source_document` and `event_item`. Verified live (8 fetched -> 8 inserted on initial run; 0 inserted, 8 skipped on re-run).
  - `jobs/score_events.py`: Idempotent scoring into `text_score`. Verified live (8 scored on initial run; 0 scored on re-run).
- **Dynamic Risk Score Component (`event_risk_pressure`)**:
  - Registered in `backend/app/risk_score/components/events.py` and `registry.py` under dimension `events`.
  - Recency-decayed risk pressure formulated with 14-day exponential half-life ($2^{-\Delta t / 14}$) over trailing 90 days.
  - Positive announcements mitigate risk up to a strict 30% cap of gross negative pressure.
- **API Endpoints**:
  - `GET /api/v1/stocks/{symbol}/events`: Returns stock events timeline with sentiment, importance breakdown, and disclaimer.
  - `GET /api/v1/events/recent`: Filterable feed by `event_type`, `min_importance`, and `since_date`.
- **Frontend**:
  - `Timeline.tsx`: Shared interactive timeline component featuring pricing context with overlaid announcement pins, interactive type/sentiment/importance filters, sentiment chips, importance bars, evidence spans, source links, and prominent market disclaimer: *"Markets may have already priced this in."*
  - Integrated into `StockDetailPage.tsx` under *"Corporate Announcements & Explainable Events (Dimension: Events)"*.
- **Tests & Quality Gates**:
  - Python tests: `tests/events/` (14 tests covering rules, importance calculation, finbert fallback/chunking/aggregation, recency decay, positive offset cap, point-in-time no-lookahead, and API endpoints). Total Python tests: 196 passed.
  - Frontend tests: `Timeline.test.tsx` (2 tests). Total Vitest tests: 38 passed across 10 test suites.
  - All 6 quality gates green: `ruff` (0 errors), `mypy` (118 source files clean), `pytest` (196 passed), `pnpm lint` (0 errors), `pnpm test` (38 passed), `pnpm build` (clean bundle).

### 2026-10-05 - Step 11: Timestamped News/Policy Items & Explainable Policy-to-Sector Rules (Dimension: Macro / Events, SRS OQ-7)

- **Database Migration (`e1f2a3b4c511_step_11_policy_intelligence.py`)**:
  - Additive migration creating 4 tables: `news_item` (id, source, published_at, ingested_at, headline, url, content_hash), `news_security_link` (news_item_id, security_id, method, confidence), `policy_rule` (rule_key, description, match_keywords, match_category, affected_industries, direction, severity, rationale, reviewer, version, active), `policy_event` (id, news_item_id, rule_id, matched_at, affected_industry, severity, evidence).
  - Seeded 10 canonical policy rules as `status = DRAFT` with mandatory economic transmission rationales and reviewer audit fields.
  - Seeded `model_config` row for `news_policy_pressure` (v1.0.0, approved, checksummed) and registered `news_policy_pressure` in `score_component_definition` (5% starting weight, dimension: `macro`).
  - Applied and verified against live Supabase PostgreSQL database.
- **Backend Architecture & Adapters (`backend/app/policy/`)**:
  - `adapters/base.py`: Clean `NewsAdapter` protocol and `RawNewsItem` model.
  - `adapters/rss_adapter.py` & `adapters/json_adapter.py`: Official regulatory press release adapters (RBI, SEBI, PIB) with offline JSON fallback (`data/news/news.json`).
  - Strict Content Boundary: Strictly stores headline, URL, source, timestamps, and SHA-256 content hash. Full article text is never stored or redistributed.
  - `matcher.py`: Deterministic keyword token and category matching with evidence capture.
  - `service.py`: Query and mutation services enforcing mandatory non-empty reviewer and rationale on rule version updates.
- **Idempotent Background Jobs**:
  - `jobs/ingest_news.py`: Polling ingestion job deduplicating strictly by `content_hash` (10 fetched -> 10 inserted on initial run; 0 inserted, 10 skipped on re-run).
  - `jobs/match_policy.py`: Deterministic matching job deduplicating by `(news_item_id, rule_id, affected_industry)` (16 matched -> 16 inserted on initial run; 0 inserted, 16 skipped on re-run).
- **Dynamic Risk Score Component (`news_policy_pressure`)**:
  - Registered in `backend/app/risk_score/components/news_policy.py` and `registry.py` under dimension `macro`.
  - Formulated with 14-day exponential recency decay ($2^{-\Delta t / 14}$) over a 60-day window.
  - Policy tailwinds provide mitigation capped at 30% of gross headwind pressure.
- **API Endpoints**:
  - `GET /api/v1/stocks/{symbol}/news`: Stock news and policy impact timeline with matched rules and rationales.
  - `GET /api/v1/policy/rules`: List all policy rules with category and active filters.
  - `GET /api/v1/policy/events/recent`: Filterable feed of recent policy events by industry, direction, and recency.
  - `PUT /api/v1/policy/rules/{key}`: Creates a new rule version; strictly validates non-empty reviewer and rationale.
- **Frontend**:
  - `NewsPolicyPanel.tsx`: Component in stock dossier (`StockDetailPage.tsx`) showing headline links, direction chips, severity meters, transmission rationale boxes, and non-causal disclaimer.
  - `PolicyRulesPage.tsx`: Dedicated `/policy-rules` page displaying all rules, search/category filtering, version counters, reviewers, keywords, affected industries, and full economic rationales.
  - Navigation integrated into `AppLayout.tsx` and routed in `App.tsx`.
- **Tests & Quality Gates**:
  - Python tests: `tests/policy/` (16 tests covering hash deduplication, deterministic matching, rule versioning & audit requirements, recency decay math & tailwind cap, point-in-time filtering, and API endpoints). Total Python tests: 212 passed.
  - Frontend tests: `NewsPolicyPanel.test.tsx` (2 tests), `PolicyRulesPage.test.tsx` (2 tests). Total Vitest tests: 42 passed across 12 test suites.
  - All 6 quality gates green: `ruff` (0 errors), `mypy` (128 source files clean), `pytest` (212 passed), `pnpm lint` (0 errors), `pnpm test` (42 passed), `pnpm build` (clean bundle).

### 2026-10-06 - Step 12: Full Coverage, Confidence, Portfolio Score, and Gap Proof

- Added the executable eight-dimension coverage contract and
  `docs/specs/COVERAGE_MATRIX.md`; unavailable observations remain explicit and
  reduce coverage/confidence.
- Added and applied additive migration `a3b4c5d6e712`, inserting only
  `risk_engine_parameters:2.0.0` with status `draft`. Version 1 remains approved
  and the default. Offline SQL inspection caught and fixed JSON bind rendering
  before application.
- Configured all component/dimension weights, windows, minimum histories, decay
  half-lives, age thresholds, confidence weights/caps, portfolio weights, and
  ablation exclusions under the v2 fingerprint.
- Completed all six confidence factors from point-in-time observations. Removed
  optimistic fallback values for absent source cross-check and MST evidence.
- Added source-coverage guards so absence of an announcement/news feed is
  `missing`, not a synthetic zero-risk observation.
- Added config-fingerprinted component/dimension ablation, generic missing-data
  output, and top component changes against the previous completed stock run.
- Added portfolio score synthesis with separate holding, structure,
  cluster-concentration and effective-bet terms; confidence is capped by the
  weakest large holding and reduced for missing coverage.
- Extended `GET /api/v1/stocks/{symbol}/risk/latest` and added
  `GET /api/v1/portfolios/{id}/risk-score/latest`.
- Added frontend confidence-factor panel, missing-data banner, previous-run
  changes, and portfolio risk/confidence cards.
- Added full-score golden, coverage, cap, ablation, portfolio numeric,
  determinism, no-look-ahead, and idempotency tests. Shared DB-backed tests now
  use rollback-only transactions and do not persist fixtures.
- Verification: Ruff passed; mypy passed 130 source files; pytest passed 222;
  ESLint passed with no warnings; Vitest passed 44; production build passed.
- Database evidence: `model_config` changed 12 -> 13 rows; the row-count hash for
  every other existing table (54 tables) remained
  `6c6351cacf256f08ebfcced42d9a013792c6a3874a8f9b93d97a55ee02c8c3e1`.
- Production scoring was not run because known fixture-derived rows remain in the
  database and cleanup has not been approved. No fixture rows were deleted.

### 2026-10-06 - Step 13: Honest Historical Score and Confidence Validation

- Added and applied additive migration `b4c5d6e7f813`, creating
  `validation_run`, `validation_result`, and `experiment_log`, plus draft
  `validation_parameters:1.0.0`. Offline SQL was inspected before application.
- Added idempotent monthly point-in-time score backfill and historical-validation
  jobs. Every historical score carries the current-membership survivorship warning.
- Added strict post-as-of forward volatility, max-drawdown, and worst-five-session
  targets; configured purged walk-forward evaluation reuses Step 0b splits.
- Added per-period Spearman, decile/quintile comparisons, score stability,
  trailing-volatility/beta/random baselines, confidence-bin calibration, and plain
  failure reporting.
- Added component/dimension ablations through the Step 12 hook for all three
  targets. Every attempted variant is logged and weights are never auto-adjusted.
- Added empirical Layer 1 band-rate comparisons without changing frozen Layer 1.
- Added `GET /api/v1/validation/runs`, `GET /api/v1/validation/runs/{id}`, and a
  `/validation` page with baseline, ablation, calibration, limitation, and failure
  views.
- Added numeric, no-look-ahead, split-purity, ablation-isolation, idempotency, API,
  and frontend tests. Detailed assumptions are in `VALIDATION_SPEC.md`; PD-25 and
  PD-26 await owner review.
- Database evidence: 54 pre-existing non-config table counts were unchanged;
  `model_config` changed 13 -> 14; all three new validation tables remain empty.
- The authorized production jobs were not run because quarantined fixture-derived
  event/news/macro rows would invalidate the evidence. No data was deleted or
  overwritten; run remains pending exact cleanup approval `APPROVE CLEANUP`.
- Verification: Ruff passed; exact `uv run mypy` passed 135 source files; pytest
  passed 229; ESLint passed; Vitest passed 45; the production build passed. Layer
  1/2 have no diff. Alembic head/current are both `b4c5d6e7f813`.
- A diagnostic `alembic check` still reports older model/index naming and type drift
  across pre-Step-13 tables. This migration did not alter those tables; resolving
  that legacy drift requires a separate audited additive migration.

### 2026-10-06 - Step 14: Unattended Operations, Freshness, Alerts, and Watchlists

- Added and applied additive migration `c5d6e7f8a914`: `data_freshness`, `alert`,
  `watchlist`, and `watchlist_item`; linked incremental score runs to their parent;
  seeded approved checksummed `operations_parameters:1.0.0`.
- Implemented the config-ordered APScheduler/Tenacity daily DAG with step-level
  manifests, retries, failure isolation, and preservation of last-known-good data.
- Added point-in-time freshness evaluation, six config-driven explainable alert
  rules with deduplication/cooldown, watchlist defaults/CRUD, and targeted
  filing/news incremental rescoring while keeping prices explicitly end-of-day.
- Added operations, freshness, alert, watchlist, and limitations APIs; traffic-light
  health/run views, alerts/watchlist pages, global stale banner, and EOD footer.
- Added allowlisted key-table export plus documented Supabase backup/restore
  evidence steps. No restore was performed or claimed.
- Database evidence: all 57 pre-existing non-config table counts retained the exact
  pre/post hash `459952f1f0095cb463e8ba01d423304d8e0276fc81db8c7c0d5a35f7fa7a7b32`;
  `model_config` changed 14 -> 15 and all four new tables began empty.
- Added tests for DAG ordering/retries/failure isolation, freshness boundaries and
  no-look-ahead, alert deduplication/cooldown/idempotency, API contracts, and
  affected-stock-only incremental persistence.
- The authorized seven-day local soak was not started because known quarantined
  fixture-derived production inputs would make its scoring evidence invalid.
  `docs/evidence/SOAK_TEST_REPORT.md` records the blocked/not-started status.

### 2026-10-06 - Step 15: Demonstration and Defensibility

- Added concentrated, diversified, and sector-heavy synthetic fixture portfolios
  under `data/demo/` plus a one-command local API loader.
- Added a Chromium Playwright smoke covering upload, portfolio risk, stock risk,
  confidence, component breakdown, fundamentals, events, shock simulation, and
  mandatory disclaimers; the smoke passes.
- Added `DEMO_SCRIPT.md`, `VIVA_QA.md`, `ARCHITECTURE.md`, the config-rendered
  `/about/limitations` page, and `SRS_FINAL_AUDIT.md`; rewrote README and recovery
  instructions to match the implemented commands and known limitations.
- Final gates: Ruff passed; mypy passed 146 files; pytest passed 235; ESLint passed;
  Vitest passed 47; production build passed; Playwright passed 1. The existing
  large Plotly bundle advisory and Starlette/httpx deprecation warning remain
  non-failing observations.
- Final audit does not claim Phase 0 completion: teammate recovery sign-off, a real
  restore drill, clean historical validation, and the seven-day soak remain open.

### 2026-10-06 - Step 11b: Permitted Production Data Sources

- Added and applied additive migration `d6e7f8a9b015`, creating `data_source`,
  seeding 18 dataset/source rows, and adding checksummed approved
  `data_source_policy:1.0.0` cadence/grace configuration. Offline SQL was inspected
  before application and contained only create/index/seed operations.
- All pre-existing domain table row counts were unchanged by the migration;
  `model_config` changed 15 -> 16 and the new registry contains 18 rows.
- Enabled only the verified official RBI and SEBI RSS feeds. The authorized job
  inserted 40 newly fetched metadata-only items across two idempotent runs (the
  second skipped the first run's 10 duplicates). PIB and Finance Ministry feeds
  remain plainly TBD because a reliable timestamped permitted feed was not verified.
- Replaced the announcement production path with a strict official NSE CSV adapter;
  missing files, missing columns, and unreadable rows fail before persistence. No
  automated NSE/BSE collection or browser impersonation was added.
- Tightened shareholding and insider adapters for mandatory schemas, real
  publication timestamps, quarter alignment, percentage/unit bounds, no-look-ahead,
  content-hash deduplication, and all-or-nothing parsing. Real reported total shares
  populate immutable `security_share_count` revisions; no real disclosure file was
  supplied or invented, so governance imports remain pending.
- Added `GET /api/v1/data/sources`, source-aware freshness rows, source-success
  tracking, a generic data-health registry table, strict importer/API/static-guard
  tests, `docs/DATA_SOURCES.md`, and proposed decision PD-28.
- Verification: Ruff passed; mypy passed 150 files; pytest passed 244 tests; ESLint
  passed; Vitest passed 47 tests; production build passed. A first parallel Vitest
  attempt had three 5-second timing failures on Windows/OneDrive; the exact rerun
  passed all suites, and the focused data-health route passed independently.
- No scoring formulas, Layer 1, Layer 2, SRS text, secrets, or quarantined historical
  rows were modified. Changes remain uncommitted.

### 2026-10-06 - Step E1: Shared Evidence-Bound Explanation Framework

- Confirmed D8 and D9 were already present in `docs/agent/MASTER_CONTEXT.md`; no
  duplicate rules were appended.
- Added and applied additive migration `e7f8a9b0c116`, creating `explanation` and
  `glossary_term`, seeding 25 versioned glossary terms and checksummed draft
  `explain_templates:1.0.0`. Offline SQL was inspected before application.
- Added typed evidence/payload schemas, deterministic config templates, fail-closed
  language guardrails, an explainer registry, and fingerprint-idempotent storage.
- Implemented the first explainer from stored component value, percentile,
  direction, weight, points, window, age, and status rows. Point-in-time lookup
  excludes later score runs and missing values do not create unsupported sentences.
- Added component explanation and glossary APIs, plus a generic ExplainDrawer,
  provenance popovers, GlossaryTerm tooltip, useExplain hook, and a Why action on
  every component-breakdown row.
- Added tests for unsupported evidence, banned/correlation wording, source-value
  equality, no-look-ahead, missing data, cache idempotency, API contracts, unknown
  UI sections, glossary tooltip rendering, and per-row Why actions.
- Database evidence: every pre-existing domain-table count remained unchanged;
  `model_config` changed 16 -> 17, while `glossary_term` began with 25 rows and
  `explanation` with 0. Template/glossary wording remains draft pending owner review.
- Verification: Ruff passed; mypy passed 158 source files; pytest passed 250;
  ESLint passed; Vitest passed 50; production build passed. Alembic current and
  head both report `e7f8a9b0c116`. The existing Starlette/httpx deprecation and
  large frontend chunk advisory remain non-failing observations.

### 2026-10-06 - Step E2: Evidence-Bound MST Explanations

- Added immutable draft MST explanation configs `1.0.0`, `1.1.0`, and corrective
  `1.2.0`; all remain draft pending owner wording approval. Offline SQL was
  inspected before each authorized config-only migration and contained only an
  additive `model_config` insert and Alembic revision update.
- Added deterministic edge, arbitrary-pair, and node explainers using stored MST
  outputs and point-in-time prices. Evidence includes rho/distance, replayed
  Kruskal step and group sizes, reciprocal ranks, optional clusters/residual tree,
  rolling persistence, macro similarity, historical beta/R-squared, optional
  event overlap, node diagnostics, and optional portfolio exposure.
- Added D3 fields to the shared explanation payload, generic explanation caching,
  the three E2 APIs, chart specs, and omission-with-limitation behavior for absent
  optional evidence. No composite impact score was introduced.
- Added MST edge/node drawer actions, arbitrary pair search, glossary-backed
  distance scale, edge-thickness legend, stability display, and generic chart-spec
  rendering.
- Added hand-calculated distance/beta, deterministic Kruskal replay, path,
  persistence, no-look-ahead, guardrail, API, cache-idempotency, stored-distance,
  UI, and Layer 2 zero-diff tests. Ruff passed; strict mypy passed 160 files;
  pytest passed 259; ESLint passed; Vitest passed 52; the production build passed.
- Database evidence: `model_config` changed 17 -> 20 for the three immutable draft
  config rows; recorded comparisons show every other pre-existing table unchanged.
  `explanation` remains at 0 because integration tests roll back. Alembic current
  and head are `b0c1d2e3f419`.
- Production observation: the current raw MST run has persisted nodes/edges but no
  cluster, node-metric, or stability diagnostics, so those optional sections are
  honestly omitted with limitations. Running diagnostics was not authorized by E2.

### 2026-10-06 - Step E3: Evidence-Bound Sector-Divergence Explanations

- Audited the approved Layer 1 contract and confirmed persisted scores contain
  alpha, beta, residual, residual volatility, 1/5/20-day z-scores, bands, Industry,
  observations, and percentiles. R-squared and peer count are not persisted and are
  therefore recomputed read-only from the stored point-in-time price envelope.
- Added and applied config-only migration `c1d2e3f4a520` for immutable draft
  `explain_sector_rules:1.0.0`. Offline SQL contained one additive model-config
  insert and the Alembic revision update; no table was added.
- Added stock and Industry explainers for peer/stock 1/5/20/60-day trends, breadth,
  dispersion, regression expectation/R-squared, stored residual horizons/band,
  absolute-score percentiles, persistence, point-in-time publications, conditional
  risk context, and score contribution. The mandatory divergence-not-verdict line
  is always present.
- Added the three E3 APIs, stock dossier and Layer 1 explanation panels, rebased
  stock/peer chart with separation shading and publication markers, and `/sectors`
  overview with sector-explanation click-through.
- Added hand-calculated peer median/trend, percentile, persistence, contribution,
  missing-data, no-look-ahead, deterministic, stored-z recomputation, idempotency,
  risk-evidence gating, API, UI, and Layer 1 zero-diff tests. Ruff passed; strict
  mypy passed 162 files; pytest passed 267; ESLint passed; Vitest passed 55; and the
  production frontend build passed.
- Database evidence: `model_config` changed 20 -> 21. The exact row-count hash for
  all 64 other tables remained
  `99338065d2350f8622ba7b6618cfc000656c55d5fa8fc05cad51693f2b6752a7`.
  Alembic current and head both report `c1d2e3f4a520`.
- PD-31 records the unapproved trend/risk/publication thresholds. No Layer 1 source
  file, formula, window, threshold, or tie-break was changed.

### 2026-10-06 - Step E4: News Impact & Transmission Engine (Finish & Verification)

- Audited and verified existing Step E4 implementation: `backend/app/news_impact/{math,schemas,service}.py`,
  `backend/app/explain/news.py`, `jobs/calculate_news_impact.py`, and API routes `/news/insights`,
  `/explain/news/{news_id}`, `/explain/portfolio/{portfolio_id}/news/{news_id}`.
- Validated mathematical formulas: 4 transmission channels (direct, rule, macro, spillover),
  MAX combination to prevent double counting, recency decay (30-day half-life), exposure bands
  (low <0.35, medium 0.35–0.65, high >=0.65), confidence gating (min 0.40), unreviewed rule penalty (-0.25),
  and historical analogue threshold (>=10 required for abnormal returns; otherwise explicit "insufficient history (n=...)").
- Executed real-data run:
  - `jobs/match_policy.py`: evaluated 15 rules against 50 news items; 31 matches found, 15 events inserted, 16 skipped existing.
  - `jobs/calculate_news_impact.py`: executed on allowlisted live feeds; 1 new impact run created, 42 reused, 0 skipped.
  - Distribution: 50 total news items; 1 item with affected industry rows (45 affected stock candidates, all in low exposure band due to recency decay and active rule filter); 43 items with 0 affected rows; rules fired reported. Thresholds were strictly maintained without loosening.
- Authored specification: `docs/specs/NEWS_IMPACT_SPEC.md` with complete formulas, evidence rules, guardrails, and worked numeric example. Proposed decision recorded as draft in `docs/specs/PROPOSED_DECISIONS.md` under PD-32.
- Enhanced frontend: fixed MUI slotProps deprecation (TS2322) in `NewsPage.tsx`, added feed metadata chips (severity, UNREVIEWED, matched rules, sectors), affected stocks table with stock links, filter inputs, portfolio toggle, and empty state source status chips (RBI and SEBI live; PIB and Ministry of Finance TBD).
- Expanded tests: added schema evidence verification, idempotent job test, API route tests, and comprehensive `NewsPage.test.tsx` component tests.
- Gates verified: Ruff (0 errors), strict mypy (173 source files, 0 errors), pytest (250 pure tests passed, 32 DB-backed safely skipped), ESLint (0 errors), Vitest (59 tests across 19 suites passed), Vite production build clean. Zero git diff on Layer 1 and Layer 2 code.

### 2026-10-06 - Step E5: Universal Explanation Access & Precompute Engine

- Implemented unified explanation entry points everywhere: Layer 1 peer divergence rows, MST edges, nodes, and pairs, risk breakdown rows, shock results, portfolio diversification findings, alerts, and score-change trajectory lines. Every entry point opens the same accessible `ExplainDrawer`.
- Built new explainers conforming to Step E1 architecture and guardrails:
  - Shock explainer (`shock`): Holding response under hypothetical shock scenarios, fitted betas, R-squared co-movement, transmission paths, and model assumptions.
  - Diversification explainer (`diversification`): Effective number of bets via Risk-Contribution Entropy and Eigenvalue Decomposition, dominant cluster concentration, and formulas.
  - Score-change explainer (`score_change`): Evidence-bound attribution of score shifts using Step 12 component deltas, percentiles, and baseline comparisons.
  - Alert explainer (`alert`): Structured risk condition rationale and inputs_ref evidence.
- Created precompute engine `jobs/precompute_explanations.py`:
  - Precomputes explanations for top N stocks by risk, active MST edges, moderate/strong/extreme sector divergences, and recent completed news impacts.
  - Idempotent and deterministic caching by 64-character SHA-256 fingerprint in the `explanation` table.
  - Initial precompute run completed: 344 items evaluated, 74 initial cache hits, 270 newly generated and persisted across remote database (198 MST edges, 121 divergences, 25 news impacts; initial run hit rate: 21.51%).
  - Idempotency verified: re-running precompute achieves 100.00% cache hits (0 misses).
  - On-demand fallback for arbitrary queries.
- Built Explain Index `/explain` page with full text and entity search (stock, pair, news) and feed of recent explanation snapshots.
- Integrated Glossary System: Tooltip popovers for technical terms (`GlossaryTerm`) across all explanation sentences; API endpoints `/glossary` and `/glossary/{term}`.
- Added Usability enhancements: Copy explanation as formatted text with mandatory regulatory disclaimer and `as_of`, print-friendly layout, and keyboard-accessible drawer navigation.
- Verified test suite & performance budgets:
  - Unit & guardrail tests: 6/6 new Step E5 tests passed; full test suite passing with 0 failures.
  - Performance budgets: Precomputed fetch achieves ~420ms (budget <1.0s); on-demand generation under 3.0s on local/dev database.
  - Gates: Ruff (0 errors), strict mypy (173 source files, 0 errors), Vitest (59 tests across 19 suites passed), production frontend build clean. Zero git diff on Layer 1 and Layer 2 code.

### 2026-10-06 - Step E6: Explanation Faithfulness, Safety Guardrails & Language Governance

- Implemented comprehensive Faithfulness Suite (`tests/explain/test_faithfulness.py`):
  - Independently recomputed raw statistics from underlying database tables without calling explainer code across all subject types: MST pair statistics, persistence summaries, sector divergence regression diagnostics/medians/percentiles, news impact recency decay and path combinations, diversification entropy/eigenvalue ENB, shock regression OLS betas/R-squared, and score-change delta attribution. All assert equality within strict numeric tolerances.
- Implemented Automated Wording Guard in CI (`tests/explain/test_wording_guards.py`):
  - Continuously scans all templates, migration configurations, glossary definitions, and sample generated explanations for banned phrases (`buy`, `sell`, `hold`, `target price`, `guaranteed`, `will rise`, `will fall`, `you should invest`, `risk-free`, `certain profit`).
  - Enforces Rule D9 non-causal language: forbids `because of`, `caused by`, `will cause`, `led to`; strictly enforces mandatory "moves together with" language on any occurrence of `correlation` or `correlated`.
  - Fails closed on any violation.
- Established Coverage Matrix Suite (`tests/explain/test_coverage_matrix.py`):
  - Validates `subject_type x section` matrix for all 11 registered explainers.
  - Enforces the invariant: no sentence exists without non-empty `evidence_ids` (enforced at Pydantic schema validation level with `min_length=1`).
  - Verifies that when evidence is missing, unbacked sentences are omitted and limitations are honestly retained.
- Authored Golden Files & Regression Suite (`tests/fixtures/golden/*.json`, `tests/explain/test_golden_explanations.py`):
  - Frozen snapshots for 3 stocks (`INFY`, `TCS`, `RELIANCE`), 3 MST edges (`edge_HDFCBANK_ICICIBANK`, `edge_INFY_TCS`, `edge_TATASTEEL_JSWSTEEL`), and 3 news items (`news_item_1`, `news_item_2`, `news_item_3`).
  - Tested against schema, evidence binding, and wording guardrails.
- Enforced Performance Budgets (`tests/explain/test_performance_budgets.py`):
  - Verified precomputed cache fetch < 1.0s, on-demand generation < 3.0s, and in-memory composition < 50ms.
- Delivered Owner Review Pack (`docs/specs/EXPLANATION_REVIEW.md`):
  - Comprehensive checklist covering glossary wording (14 terms), all 8 explainer template groups, wording bands, and seeded policy rules (with `UNREVIEWED_SEED` status).
  - Tracked as pending in `docs/specs/PROPOSED_DECISIONS.md` under PD-34. Zero items marked approved.
- Authored Complete Technical Specification (`docs/specs/EXPLANATION_SPEC.md`):
  - Detailed design, evidence kinds, template interpolation engine, deterministic guardrails, system boundaries, and a viva Q&A defense section on why fixed templates over LLMs, why evidence-bound, and why no investment advice.
- Updated GitHub Actions CI Workflow (`.github/workflows/ci.yml`):
  - Added dedicated step running all explanation wording guards, coverage matrix, golden snapshots, and performance budget tests.



