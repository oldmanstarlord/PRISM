# Phase 1 Delivery Report: Audit, Repair and Honest Baseline

| Metadata | Value |
|---|---|
| Phase | Phase 1 of 7: Audit, Repair and Honest Baseline |
| Date | 2026-10-20 |
| Status | Complete & Verified |
| Environment | Windows 11, Python 3.12.5 (uv), Node.js v20+ (pnpm 10.16.1), FastAPI, React 19 / MUI v6 |
| Target Universe | NIFTY 200 |

---

## 1. Executive Summary

Phase 1 establishes an audited, honest, and hermetic baseline for the PRISM platform. Prior to this phase, while mathematical prototypes and UI sections for Phases 0 through 3 existed in the repository, the test suite and CI checks were broken across multiple fronts:
- **34 Ruff errors** (long lines, unused imports, import sort violations).
- **5 Mypy strict-mode errors** (missing stubs for pandas, undefined unbounded global `_inputs_cache`).
- **14 ESLint errors** (unused UI imports, unhandled variables, missing caught-error causes).
- **Non-hermetic tests:** 6+ backend tests called live Yahoo Finance (`^NSEI`, live quote queries) taking ~45 seconds and failing completely offline.
- **Data integrity defects:** Unbounded global in-memory caching, silent snapshot overwrite via `IDBObjectStore.put()`, silent fallback to session memory without user warning, and hardcoded monitoring thresholds documented as "configurable".
- **Documentation drift:** Stale reports claiming passing tests and omitting major implemented modules (Research Notes, Decision Journal, Snapshot Manager).

All verified defects have been repaired, all CI jobs pass 100% offline without live database or network access, quantitative metrics across all 9 portfolio tabs have been audited with independent tests, and the repository documentation now truthfully reflects verified reality.

---

## 2. Defect Register by Severity

| ID | Severity | Component | Description | Resolution Status |
|---|---|---|---|---|
| **DEF-01** | **Critical** | Backend Test Suite (`test_live_service.py`, `test_stock_risk.py`) | Tests made live HTTP requests to Yahoo Finance for `^NSEI` and stock quotes, failing in offline environments and causing non-deterministic runtimes (>45s). | **RESOLVED**: Replaced with deterministic `unittest.mock` fixtures. All 86 backend tests now run hermetically offline in 11.22s. |
| **DEF-02** | **High** | API Router (`router.py`) | `_inputs_cache` was an unbounded global dictionary causing memory leaks across repeated requests and triggering Mypy `name-defined` failures. | **RESOLVED**: Replaced with module-level `_inputs_lru_cache` (`OrderedDict`, `maxsize=16`) keyed by `(run_id, signal_date)`. |
| **DEF-03** | **High** | Browser Persistence (`journalStorage.ts`) | `savePortfolioSnapshot` used `store.put()`, which silently overwrote existing snapshots if an ID was supplied, violating snapshot immutability. Persistence failures also silently fell back to memory without alerting the user. | **RESOLVED**: Switched to `store.add()` (strictly rejects duplicate IDs), applied `Object.freeze(structuredClone(snapshot))`, and exposed fallback subscription displaying a prominent warning alert. |
| **DEF-04** | **High** | Historical Persistence (`structural_monitoring.py`) | Historical portfolio risk snapshots auto-persist to a single server-global flat file (`data/processed/portfolio_risk_history.json`), shared by all concurrent users without tenant isolation or file locks. | **DOCUMENTED**: Catalogued as a known architectural defect. Retained for single-session use; scheduled for migration to user-scoped PostgreSQL persistence in Phase 2. |
| **DEF-05** | **Medium** | News Intelligence (`news_signals.py`, `Phase3StructuralSections.tsx`) | The News tab rendered synthetic headline previews (`generate_modular_news_preview`) without explicit visual isolation, creating risk of users confusing simulated previews with real news. | **RESOLVED**: Added prominent `SIMULATED - NOT REAL NEWS` badges to the tab banner, signal table, and sample headline cards. Confirmed news risk multipliers do not alter quantitative market risk. |
| **DEF-06** | **Medium** | Stock Risk Scoring (`stock_risk.py`, `Phase2RiskSections.tsx`) | The 5-factor risk score was described in UI and documentation as "calibrated" despite utilizing fixed bounded parameter ranges without historical backtested calibration. | **RESOLVED**: Reworded "calibrated" to "heuristic" across UI copy, tooltips, and documentation until empirical calibration in Phase 4. |
| **DEF-07** | **Medium** | Structural Monitoring (`structural_monitoring.py`) | Monitoring alert thresholds (e.g. 60 risk score, 25% sector ceiling, 20% single-stock) were documented in docstrings as "configurable" despite being hardcoded constants. | **RESOLVED**: Updated docstrings and UI copy to truthfully state these are standard diagnostic prudential thresholds (full configurability scheduled for Phase 3). |
| **DEF-08** | **Low** | Code Style & Linters | 34 Ruff linting errors (line lengths in migrations and tests) and 14 ESLint unused-variable/import errors in React components. | **RESOLVED**: All Ruff and ESLint errors resolved. Strict 100-character line limit enforced. |
| **DEF-09** | **Low** | Mathematical Convention | Portfolio returns are calculated as a linear combination of log returns ($r_{p,t} = \sum w_i r_{i,t}$). In portfolio theory, linear combination applies strictly to simple returns. | **FLAGGED**: Documented in audit table and report. Not silently modified to maintain backward reproducibility with Layer 1/2 baselines. |

---

## 3. Quantitative Metric Audit Across All 9 Portfolio Tabs

| # | UI Label | Tab | Endpoint | Function | Mathematical Formula | Units | Input Window | Data Source | Status | Limitations / Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Annualized Volatility** | `portfolio-risk`, `dashboard`, `monitoring` | `POST /portfolio-analytics/risk` | `calculate_risk` | $\sigma_{ann} = \sqrt{252} \cdot \sqrt{\frac{1}{N-1}\sum_{t=1}^N (r_{p,t} - \bar{r}_p)^2}$ | % / decimal | 250 trading days | Adjusted close prices | Verified | Assumes 252 trading days/year; constant weights. |
| 2 | **Downside Volatility** | `portfolio-risk`, `dashboard`, `monitoring` | `POST /portfolio-analytics/risk` | `calculate_risk` | $\sigma_{down} = \sqrt{252} \cdot \sqrt{\frac{1}{N}\sum_{t=1}^N \min(r_{p,t}, 0)^2}$ | % / decimal | 250 trading days | Adjusted close prices | Verified | Target return fixed at 0.0 (semi-deviation). |
| 3 | **Maximum Drawdown** | `portfolio-risk`, `dashboard`, `stock-risk` | `POST /portfolio-analytics/risk` | `calculate_risk` | $\text{MDD} = \max_{\tau \in [0, t]} \left( \frac{\max_{s \le \tau} W_s - W_\tau}{\max_{s \le \tau} W_s} \right)$ | % / decimal | Trailing window (1M/3M/6M/1Y) | Reconstructed wealth index | Verified | Peak-to-trough path-dependent capital loss. |
| 4 | **Marginal Risk (Euler)** | `portfolio-risk`, `stock-risk` | `POST /portfolio-analytics/risk` | `calculate_risk` | $\frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma_{ann} w)_i}{\sigma_p}$ | % vol | 250 trading days | Asset covariance matrix | Verified | Linear homogeneous function of degree 1. |
| 5 | **Euler Risk Contribution Share** | `portfolio-risk`, `monitoring` | `POST /portfolio-analysis/comprehensive-risk` | `calculate_portfolio_comprehensive_risk` | $\text{RC}_i = \frac{w_i (\Sigma_{ann} w)_i}{\sigma_p^2} \times 100\%$ | % | 250 trading days | Asset covariance matrix | Verified | Proved: $\sum_{i=1}^N \text{RC}_i = 100.0\%$. |
| 6 | **Holding HHI** | `diversification`, `portfolio-risk` | `POST /portfolio-analytics/risk` | `calculate_risk` | $\text{HHI}_{holding} = \sum_{i=1}^N w_i^2$ | decimal (0 to 1) | Current portfolio | Invested weights | Verified | Min $1/N$ (equal weight), Max $1.0$ (monopoly). |
| 7 | **Effective Number of Holdings ($N_{eff}$)** | `diversification`, `monitoring` | `POST /portfolio-analytics/risk` | `calculate_risk` | $N_{eff} = \frac{1}{\sum_{i=1}^N w_i^2}$ | Count | Current portfolio | Invested weights | Verified | Inversely related to holding concentration. |
| 8 | **Sector HHI & $S_{eff}$** | `sector-exposure`, `diversification` | `POST /portfolio-analytics/risk` | `calculate_risk` | $S_{eff} = \frac{1}{\sum_{j=1}^M s_j^2}$ | Count | Current portfolio | Sector aggregate weights | Verified | Measures cross-industry concentration. |
| 9 | **Diversification Ratio (DR)** | `diversification` | `POST /portfolio-analysis/comprehensive-risk` | `calculate_portfolio_comprehensive_risk` | $\text{DR} = \frac{\sum_{i=1}^N w_i \sigma_i}{\sigma_p}$ | Ratio ($\ge 1.0$) | 250 trading days | Standalone vols & portfolio vol | Verified | $\text{DR} \ge 1.0$ by Cauchy-Schwarz inequality. |
| 10 | **Market Beta ($\beta$)** | `stock-risk`, `dashboard` | `POST /portfolio-analysis/comprehensive-risk` | `calculate_single_window_metrics` | $\beta = \frac{\text{Cov}(r_i, r_m)}{\text{Var}(r_m)}$ | Sensitivity | 21d, 63d, 126d, 252d | Stock & NIFTY 50 (`^NSEI`) | Verified | Linear regression slope; OLS reference. |
| 11 | **Jensen's Alpha ($\alpha$)** | `stock-risk` | `POST /portfolio-analysis/comprehensive-risk` | `calculate_single_window_metrics` | $\alpha = 252 \cdot (\bar{r}_i - \beta \bar{r}_m)$ | % ann | Trailing window | Stock & NIFTY 50 (`^NSEI`) | Verified | Risk-free rate $R_f$ set to 0.0 in baseline. |
| 12 | **Mantegna MST Distance** | `analysis` (MST) | `GET /correlation-mst/latest` | `calculate_mst` | $d_{ij} = \sqrt{2(1 - \rho_{ij})}$ | Metric distance | 120 trading days | Pairwise log returns | Verified | Ultrametric subdominant space; bounded $[0, 2]$. |
| 13 | **Single-Stock Stress Shock** | `analysis` (Stress) | `POST /portfolio-analytics/risk` | `calculate_stress` | $\Delta r_i = \beta_{i, \text{target}} \cdot \text{Shock}_{\text{target}}$ | % return | 250 trading days | Trailing regression beta | Verified | Assumes linear sensitivities hold during shock. |
| 14 | **Parallel Industry Stress Shock** | `analysis` (Stress) | `POST /portfolio-analytics/risk` | `calculate_stress` | $\Delta r_i = \text{Shock}_{\text{industry}} \cdot \mathbb{I}_{i \in \text{industry}}$ | % return | Current allocation | Sector classifications | Verified | Uniform shift across industry members. |
| 15 | **5-Factor Heuristic Stock Risk** | `stock-risk` | `POST /portfolio-analysis/comprehensive-risk` | `calculate_stock_risk` | $S = 0.30 S_{vol} + 0.25 S_{down} + 0.20 S_{mdd} + 0.15 S_{\beta} + 0.10 S_{instab}$ | Score (0–100) | 252d (or 126d baseline) | Multi-factor bounded normalization | Verified (Heuristic) | Fixed bounds; empirical calibration in Phase 4. |
| 16 | **Top Sector Allocation vs Ceiling** | `monitoring`, `sector-exposure` | `POST /portfolio-analysis/comprehensive-risk` | `evaluate_monitoring_indicators` | $s_{top} = \max_j s_j$; Alert if $s_{top} \ge 25.0\%$ | % weight | Current allocation | Invested weights | Verified | Standard prudential ceiling target is 25.0%. |
| 17 | **Unrealized Return & P&L** | `dashboard`, `transactions`, `stock-risk` | Local Calculation / Client State | `calculateHoldingsAnalytics` | $\text{Return} = \frac{P_{cur} - P_{buy}}{P_{buy}}$, $\text{PnL} = Q \cdot (P_{cur} - P_{buy})$ | % & INR (₹) | Position lifetime | Buy price & latest price | Verified | Cash outflows and brokerage excluded. |
| 18 | **Simulated News Polarity** | `news-preview` | `POST /portfolio-analysis/news-signals` | `generate_modular_news_preview` | Hash-based pseudo-sentiment score $\in [-1.0, 1.0]$ | Polarity index | 7-day simulated | Deterministic mock contract | Isolated | Labelled `SIMULATED - NOT REAL NEWS`. |

---

## 4. Mathematical Audit Findings & Convention Flags

### 4.1 Euler Risk Decomposition Invariance
Euler's theorem for homogeneous functions states that if $f(\lambda w) = \lambda f(w)$ (degree 1), then $f(w) = \sum_{i=1}^N w_i \frac{\partial f}{\partial w_i}$.
For portfolio volatility $\sigma_p = \sqrt{w^T \Sigma w}$:
$$\frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sigma_p}$$
$$w_i \frac{\partial \sigma_p}{\partial w_i} = \frac{w_i (\Sigma w)_i}{\sigma_p}$$
Summing across all assets:
$$\sum_{i=1}^N w_i \frac{\partial \sigma_p}{\partial w_i} = \frac{w^T \Sigma w}{\sigma_p} = \frac{\sigma_p^2}{\sigma_p} = \sigma_p$$
Dividing by $\sigma_p$ confirms that the relative shares $\frac{w_i (\Sigma w)_i}{\sigma_p^2}$ sum identically to $1.0$ (100%). This has been tested and verified to $10^{-12}$ precision.

### 4.2 Portfolio Return Additivity Convention (FLAGGED)
In `backend/app/portfolio_analytics/calculator.py` line 159:
$$r_{p,t} = \sum_{i=1}^N w_i r_{i,t} \quad \text{where} \quad r_{i,t} = \ln\left(\frac{P_{i,t}}{P_{i,t-1}}\right)$$
*Quantitative Observation:* Log returns are not additive across assets:
$$\ln\left(\sum w_i \frac{P_{i,t}}{P_{i,t-1}}\right) \ne \sum w_i \ln\left(\frac{P_{i,t}}{P_{i,t-1}}\right)$$
The linear combination represents the return of a continuous rebalancing strategy rather than a discrete buy-and-hold portfolio. Because this is an established convention in the Layer 1/2 contracts, it is **flagged as a convention note** and preserved without silent breaking changes.

---

## 5. Verification Commands and Real Output

### 5.1 Backend Ruff Linter
```bash
uv run ruff check .
```
**Actual Result:**
```text
All checks passed!
Exit Code: 0
```

### 5.2 Backend Mypy Strict Type Checking
```bash
uv run mypy backend jobs
```
**Actual Result:**
```text
Success: no issues found in 57 source files
Exit Code: 0
```

### 5.3 Backend Pytest Suite
```bash
uv run pytest
```
**Actual Result:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.5, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, platformdirs-4.12.1, asyncio-1.4.0, cov-7.1.0
collected 88 items

tests\api\test_health.py ..                                              [  2%]
tests\core\test_auth.py ..                                               [  4%]
tests\core\test_config.py ..                                             [  6%]
tests\correlation_mst\test_mst.py ...                                    [ 10%]
tests\correlation_mst\test_mst_inputs.py ..                              [ 12%]
tests\correlation_mst\test_mst_service.py .                              [ 13%]
tests\db\test_models.py .                                                [ 14%]
tests\integration\test_database_pipeline.py ss                           [ 17%]
tests\market_data\test_live_service.py ........                          [ 26%]
tests\market_data\test_quality.py ....                                   [ 30%]
tests\market_data\test_yahoo.py ..                                       [ 32%]
tests\pipeline\test_pipeline.py ...                                      [ 36%]
tests\portfolio\test_service.py ..                                       [ 38%]
tests\portfolio_analytics\test_calculator.py ....                        [ 43%]
tests\portfolio_analytics\test_phase1_formula_audit.py ............      [ 56%]
tests\portfolio_analytics\test_stock_risk.py ..........                  [ 68%]
tests\portfolio_analytics\test_structural_monitoring.py .......          [ 76%]
tests\sector_divergence\test_calculator.py ......                        [ 82%]
tests\sector_divergence\test_inputs.py ......                            [ 89%]
tests\sector_divergence\test_service.py ...                              [ 93%]
tests\universe\test_nifty200.py ...                                      [ 96%]
tests\validation\test_reproducibility.py .                               [ 97%]
tests\validation\test_walk_forward.py ..                                 [100%]

================== 86 passed, 2 skipped, 1 warning in 11.22s ==================
Exit Code: 0
```
*(The two skipped tests are approved integration tests gated by `PRISM_RUN_DB_INTEGRATION` to keep CI hermetic without live external PostgreSQL).*

### 5.4 Frontend ESLint
```bash
pnpm run lint
```
**Actual Result:**
```text
> prism-frontend@0.1.0 lint C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM\frontend
> eslint .

C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM\frontend\src\PortfolioManager.tsx
  111:14  warning  Fast refresh only works when a file only exports components
  299:14  warning  Fast refresh only works when a file only exports components

✖ 2 problems (0 errors, 2 warnings)
Exit Code: 0
```

### 5.5 Frontend Vitest Suite
```bash
pnpm test
```
**Actual Result:**
```text
> prism-frontend@0.1.0 test C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM\frontend
> vitest run

 ✓ src/journalStorage.test.ts (8 tests) 14ms
 ✓ src/portfolioCsv.test.ts (2 tests) 6ms
 ✓ src/demoPortfolio.test.ts (3 tests) 14ms
 ✓ src/portfolioCalculations.test.ts (8 tests) 4ms
 ✓ src/journalAndDecision.test.ts (11 tests) 12ms
 ✓ src/App.test.tsx (1 test) 317ms
 ✓ src/CompanyDetail.test.tsx (1 test) 371ms

 Test Files  7 passed (7)
      Tests  34 passed (34)
   Duration  5.44s
Exit Code: 0
```

### 5.6 Frontend TypeScript Production Bundle Build
```bash
pnpm run build
```
**Actual Result:**
```text
> prism-frontend@0.1.0 build C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM\frontend
> tsc -b && vite build

vite v8.3.1 building client environment for production...
transforming...
✓ 969 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                             1.09 kB │ gzip:   0.56 kB
dist/assets/rolldown-runtime-CbXtAM7H.js    0.58 kB │ gzip:   0.36 kB
dist/assets/MstPage-CEZKmwW0.js             8.33 kB │ gzip:   3.05 kB
dist/assets/PortfolioManager-dls_zqAv.js  199.77 kB │ gzip:  46.46 kB
dist/assets/journalStorage-BukNXDRe.js    234.29 kB │ gzip:  74.24 kB
dist/assets/index-Dy3VBtC7.js             433.29 kB │ gzip: 129.20 kB
dist/assets/cytoscape.esm-Yq6u8L66.js     434.85 kB │ gzip: 137.78 kB

✓ built in 256ms
Exit Code: 0
```

---

## 6. Files Changed and Summary of Modifications

1. `backend/app/api/v1/router.py`:
   - Replaced unbounded global `_inputs_cache` with a bounded module-level LRU cache (`_inputs_lru_cache`, `maxsize=16`, `OrderedDict`) keyed by `(run_id, signal_date)`.
   - Formatted database query expressions to comply with 100-character line length limit.
2. `backend/app/sector_divergence/service.py`:
   - Added `# type: ignore[import-untyped]` for `pandas` to resolve Mypy strict mode error.
   - Wrapped long lines in `build_company_comparison` to resolve Ruff E501 errors.
3. `backend/app/sector_divergence/calculator.py`:
   - Wrapped long lines in intraday return calculations to resolve Ruff E501 errors.
4. `backend/app/market_data/live_service.py`:
   - Formatted `fetch_quote`, `fetch_historical_ohlcv`, and error quote builders within 100-character line limits.
5. `backend/app/portfolio_analytics/structural_monitoring.py`:
   - Corrected docstring in `evaluate_monitoring_indicators` to truthfully describe thresholds as fixed diagnostic prudential benchmarks.
6. `migrations/versions/9c41ad7b218e_complete_layer_2_persistence.py`:
   - Wrapped long column addition lines to comply with Ruff line-length constraints.
7. `tests/market_data/test_live_service.py`:
   - Eliminated live Yahoo Finance network queries. Mocked `yf.Ticker`, `fetch_quote`, and `fetch_benchmark` with hermetic test doubles.
8. `tests/portfolio_analytics/test_stock_risk.py`:
   - Patched `get_benchmark_returns` and `_load_stock_prices_yfinance` in `test_sector_exposure_benchmarks_and_allocation` to make tests 100% hermetic offline.
   - Wrapped long assertion lines.
9. `tests/portfolio_analytics/test_structural_monitoring.py`:
   - Organized imports (I001), removed unused imports, and formatted fixtures.
10. `tests/portfolio_analytics/test_phase1_formula_audit.py` *(NEW)*:
    - Added 12 independent mathematical integrity tests verifying daily/annualized volatility, downside semi-deviation, max drawdown, beta, alpha, Euler risk decomposition, HHI, Effective N, Diversification Ratio, Mantegna MST distance, stress testing, and edge cases (single asset, zero variance, negative correlation).
11. `frontend/src/journalStorage.ts`:
    - Replaced `store.put()` with `store.add()` in `savePortfolioSnapshot` to strictly reject duplicate IDs (create-only snapshot immutability).
    - Applied `Object.freeze(structuredClone(snapshot))` to prevent reference mutation.
    - Added `isPersistenceFallbackActive()`, `subscribePersistenceFallback()`, and `notifyPersistenceFallback()` to track session memory fallback.
    - Attached `{ cause: err }` to re-thrown storage errors.
12. `frontend/src/PortfolioSnapshotSection.tsx`:
    - Subscribed to persistence fallback state and rendered a visible warning alert banner whenever IndexedDB is unavailable.
    - Integrated `loading` state indicator.
    - Removed unused MUI imports (`Divider`, `IconButton`, `Tooltip`).
13. `frontend/src/Phase3StructuralSections.tsx`:
    - Added `SIMULATED - NOT REAL NEWS` chips to the news tab banner, overview card, and sample headlines.
    - Rendered sample headline cards with simulated labels.
    - Removed unused `Alert` import and fixed MUI v6 `Stack` props.
14. `frontend/src/Phase2RiskSections.tsx`:
    - Reworded "calibrated synthesis" to "heuristic synthesis" in methodology descriptions.
    - Removed unused `Divider` import.
15. `frontend/src/Dashboard.tsx`, `frontend/src/PortfolioManager.tsx`, `frontend/src/StockDecisionJournal.tsx`, `frontend/src/StockResearchNotes.tsx`:
    - Cleaned up unused `Divider` imports and unused helper functions (`getDecisionTypeColor`).
16. `frontend/src/journalAndDecision.test.ts`:
    - Removed unused variables (`subsequentMarketRiskScore`, `subsequentPortfolioWeight`).
17. `frontend/src/journalStorage.test.ts`:
    - Added unit test suite verifying snapshot create-only behavior, duplicate ID rejection, data cloning/freezing, and fallback status reporting.
18. `README.md` & `PROJECT_STATUS.md`:
    - Rewritten to accurately document verified system capabilities, defect register, truthful test counts, and dated changelog.

---

## 7. Limitations & Blockers

1. **Server-Global Flat File Risk History:**
   - As catalogued in **DEF-04**, `data/processed/portfolio_risk_history.json` is a single file on the local disk. In a multi-user environment, concurrent calculations will overwrite historical snapshots. This is prioritized for replacement with user-scoped Supabase PostgreSQL tables in Phase 2.
2. **Empirical Risk Score Calibration:**
   - The 0–100 5-factor risk score uses heuristic weighting (30% vol, 25% downside vol, 20% max drawdown, 15% beta, 10% price instability). Empirical backtesting across historical regimes (volatility regime clustering and weights validation) is scheduled for Phase 4.
3. **News Layer Coupling:**
   - Real news scraping and qualitative sentiment aggregation are decoupled mock interfaces until Phase 5. All news components remain strictly labelled `SIMULATED - NOT REAL NEWS`.
4. **No New Dependencies:**
   - All repairs were completed using existing libraries in `pyproject.toml` and `package.json`. No new dependencies were added.
