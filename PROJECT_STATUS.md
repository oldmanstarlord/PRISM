# PRISM Project Status

This is the living implementation record for PRISM. It must be updated after every material code, architecture, dependency, data-source or phase-status change.

## Current snapshot

| Field | Value |
|---|---|
| Current phase | Phase 3 - Structural Monitoring, MST Integration, Historical Risk Tracking & Validation |
| Overall status | Implemented and Verified |
| Last updated | 2026-10-19 |
| Requirements source | `PRISM_SRS.md` and Phase 3 Requirements |
| Initial universe | NIFTY 200 |
| Active implementation focus | Phase 3 Complete: Structural Monitoring, MST Ego-Network, Historical Tracking, Modular News Contracts & Final Validation |

## Phase status

| Phase | Name | Status | Exit evidence |
|---|---|---|---|
| 0 | Foundations | Complete | CI, reproducibility, unified pipeline and independent teammate operations verification passed |
| 1 | Portfolio insight | Complete | Risk, diversification, MST stability, stress, audit and presentation gates passed |
| 2 | Explainable Risk & Diversification | Complete | Multi-window stock risk, 5-factor scoring, portfolio covariance, Euler risk share, diversification metrics, sector benchmark analysis passed |
| 3 | Structural Monitoring & Validation | Complete | Holdings-integrated MST ego-network, structural dashboard, historical risk tracking & audit persistence, configurable monitoring alerts, modular news contracts, all 74 backend tests & 15 frontend tests passing |
| 4 | Advanced research & forecasting | Not started | Pending |

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

## Phase 1 checklist

- [x] Weighted sample and CSV portfolio input without login.
- [x] Point-in-time historical performance, volatility, downside volatility and drawdown.
- [x] Holding-level covariance/Euler risk contribution.
- [x] Holding and industry HHI plus effective exposures.
- [x] Risk-entropy and correlation-eigenvalue effective bets.
- [x] Direct and indirect MST paths, bridge stocks and correlation-defined clusters.
- [x] Selected-holding and selected-industry stress scenarios with visible assumptions.
- [x] Current 20-day divergence annotations and company-detail links.
- [x] Downloadable JSON report and print-to-PDF presentation view.
- [x] Reconcile the independently developed shared-database portfolio schema before persistence.
- [x] Add owner-scoped audit persistence and MST stability confidence.

## Known limitations

1. Historical NIFTY 200 membership data is not yet available; the official source provides the current composition.
2. The presentation portfolio is session-only: it performs no authentication, persistence or shared Supabase writes.
3. Three legacy portfolio rows from the independently developed schema intentionally remain
   unclaimed (`owner_id IS NULL`) and are not exposed by the authenticated portfolio API.

## Verification status

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
