# PRISM Phase 2 Report: Market-Data Lineage and Portfolio Ledger Integrity

**Date:** 2026-10-20  
**Phase:** 2 of 7  
**Status:** Completed  
**Author:** PRISM Engineering Team  

---

## 1. Executive Summary

Phase 2 establishes strict market-data lineage and institutional ledger integrity across PRISM. All live provider network calls have been completely removed from user API request paths: all analytical endpoints serve exclusively from verified historical database tables or tenant-scoped caching. The portfolio ledger has been established as the single source of truth under the Weighted-Average Cost (WAC) basis convention, deriving holdings, cash, invested capital, realized P&L, and unrealized P&L deterministically.

Defect **DEF-04** (server-global `history.json` flat file vulnerability) has been eliminated. Portfolio risk history and transaction logs are now stored per-portfolio and per-owner in multi-tenant PostgreSQL tables with Row-Level Security (RLS) enforcement. In the frontend, the existing layout and 9 portfolio tabs were preserved with zero new routes or tabs, augmented with reconciliation badges, CSV import/export with formula injection rejection (`=`, `+`, `-`, `@`), and market-data lineage transparency.

---

## 2. Market Data Architecture & Lineage

### 2.1 Single Market Data Service & Zero Request-Path Provider Calls
- Live network queries to yfinance have been eliminated from `backend/app/market_data/live_service.py` and `backend/app/portfolio_analytics/stock_risk.py`.
- Historical price series, daily adjusted series, and benchmark index data (`^NSEI` / NIFTY 50) are queried directly from the local database (`PriceDailyRaw`, `PriceDailyAdjusted`, `SecurityMaster`).
- In case data is absent or insufficient, endpoints return an explicit HTTP 503 or qualified payload with `status="unavailable"` or `"stale"`. Plausible fake or fabricated data is strictly prohibited.
- Provider health is monitored and exposed via `GET /api/v1/market-data/health`, tracking database connection status, daily adjusted row count, raw bar row count, and pipeline last-success metadata.

### 2.2 Data Lineage Schema
Every market data observation ingested and served exposes the following lineage fields:

| Field | Type | Description | Production Example |
| :--- | :--- | :--- | :--- |
| `instrument` | `VARCHAR(32)` | Security trading symbol | `RELIANCE` |
| `exchange` | `VARCHAR(16)` | Primary exchange identifier | `NSE` |
| `trading_date` | `DATE` | Exchange session date | `2024-03-28` |
| `raw_close` | `NUMERIC(14,4)` | Unadjusted closing price | `2971.7000` |
| `adjusted_close`| `NUMERIC(14,4)` | Corporate-action adjusted close | `2971.7000` |
| `volume` | `BIGINT` | Trading session volume in shares | `8721400` |
| `currency` | `VARCHAR(8)` | Invariant trading currency | `INR` |
| `source` | `VARCHAR(32)` | Data vendor / ingestion pipeline | `yfinance_daily_pipeline` |
| `retrieved_at` | `TIMESTAMP` | ISO timestamp of ingest | `2026-09-30T18:30:00Z` |
| `adjustment_status` | `VARCHAR(32)` | Split and dividend adjustment status | `ADJUSTED_SPLIT_DIVIDEND` |
| `quality_status` | `VARCHAR(32)` | Data validation qualification | `VERIFIED` |

### 2.3 Quality Checks & Common-Date Alignment
- **Validation Checks:**
  1. Stale data detection (threshold > 5 business days without update).
  2. Duplicate date prevention via unique constraint `(security_id, date)`.
  3. Non-positive price filtering ($P \le 0$ rejected or flagged).
  4. Trading calendar gap analysis (holidays accounted for).
  5. Extreme single-session return flags ($|r_t| > 30\%$ flagged as `EXTREME_RETURN`, never silently deleted).
  6. Insufficient history rejection ($< 30$ aligned returns for covariance/beta estimation).
- **Date Alignment:** `align_price_series` aligns asset and benchmark price vectors on common valid trading dates before calculating covariance, correlation, or beta. Every calculation returns `observation_count` and `coverage_ratio`.

### 2.4 Survivorship Limitation
The current database universe is strictly restricted to active NIFTY 200 constituents as of 2026-09-30. Inactive, delisted, or historical removals prior to this date are not reconstructed. This survivorship limitation is explicitly documented in API responses and in UI headers.

---

## 3. Portfolio Ledger Accounting & Formulas

Transactions (`PortfolioTransaction`) are the sole immutable source of truth. Holdings, cash, and P&L are derived state computed via the deterministic replay engine `backend/app/portfolio/ledger.py`.

### 3.1 Cost-Basis Method: Weighted-Average Cost (WAC)
PRISM uses the Weighted-Average Cost (WAC) accounting method.

#### 1. BUY Transaction
When buying quantity $Q_{in}$ at price $P_{in}$ with transaction fee $F$:
$$\Delta Q = Q_{in}$$
$$\text{Total Cost of Lot} = Q_{in} \cdot P_{in} + F$$
$$C_{invested, new} = C_{invested, prev} + (Q_{in} \cdot P_{in} + F)$$
$$Q_{new} = Q_{prev} + Q_{in}$$
$$\bar{P}_{unit, new} = \frac{C_{invested, new}}{Q_{new}}$$
$$\text{Cash}_{new} = \text{Cash}_{prev} - (Q_{in} \cdot P_{in} + F)$$

#### 2. SELL Transaction (Full or Partial)
When selling quantity $Q_{out}$ at price $P_{out}$ with transaction fee $F$:
- Validation: $Q_{out} \le Q_{prev}$ (selling more than current holdings raises `LedgerValidationError`).
$$\Delta Q = -Q_{out}$$
$$Q_{new} = Q_{prev} - Q_{out}$$
$$\text{Cost Basis Sold} = Q_{out} \cdot \bar{P}_{unit, prev}$$
$$C_{invested, new} = C_{invested, prev} - \text{Cost Basis Sold} \quad (\text{if } Q_{new} = 0, C_{invested} = 0)$$
$$\text{Net Proceeds} = Q_{out} \cdot P_{out} - F$$
$$\text{Realized P&L} = \text{Net Proceeds} - \text{Cost Basis Sold} = Q_{out} \cdot (P_{out} - \bar{P}_{unit, prev}) - F$$
$$\text{Cash}_{new} = \text{Cash}_{prev} + \text{Net Proceeds}$$

#### 3. DIVIDEND
When a cash dividend of total amount $D$ is received:
$$\text{Cash}_{new} = \text{Cash}_{prev} + D$$
$$\text{Total Dividends Received}_{new} = \text{Total Dividends Received}_{prev} + D$$
*Note:* Dividends are tracked as a separate income component; they are not deducted from asset cost basis nor conflated with capital gains.

#### 4. FEE_TAX
When an account-level management fee or tax $F_{acc}$ is assessed:
$$\text{Cash}_{new} = \text{Cash}_{prev} - F_{acc}$$
$$\text{Total Fees Paid}_{new} = \text{Total Fees Paid}_{prev} + F_{acc}$$

#### 5. DEPOSIT & WITHDRAWAL
- **DEPOSIT ($A$):** $\text{Cash}_{new} = \text{Cash}_{prev} + A$, $\text{Net Cash Inflow}_{new} = \text{Net Cash Inflow}_{prev} + A$.
- **WITHDRAWAL ($A$):** $\text{Cash}_{new} = \text{Cash}_{prev} - A$, $\text{Net Cash Inflow}_{new} = \text{Net Cash Inflow}_{prev} - A$.
*Rule:* Deposits and withdrawals adjust cash balance and external capital base; they are never counted as investment profit/loss.

#### 6. Valuation & Unrealized P&L
For each holding $i$ with derived quantity $Q_i$, unit cost $\bar{P}_{unit, i}$, and current market price $P_{market, i}$:
$$\text{Market Value}_i = Q_i \cdot P_{market, i}$$
$$\text{Unrealized P&L}_i = Q_i \cdot (P_{market, i} - \bar{P}_{unit, i})$$
$$\text{Portfolio Equity} = \text{Cash} + \sum_{i} \text{Market Value}_i$$
$$\text{Total Portfolio Return} = \frac{\text{Portfolio Equity} - \text{Net Cash Inflows}}{\text{Net Cash Inflows}} \quad (\text{if Net Inflows} > 0)$$

---

## 4. Multi-Tenant Database Migrations (RLS)

### 4.1 Migration Script
- **Revision ID:** `d9e1f2a3b4c5`
- **File:** `migrations/versions/d9e1f2a3b4c5_phase_2_ledger_and_risk_history.py`
- **Reversibility:** Fully reversible `upgrade()` and `downgrade()` functions.
- **SQL Verification:** Verified offline using `alembic upgrade head --sql`.

### 4.2 New Tables Created
1. `portfolio_transaction`:
   - Primary key: `id` (UUID).
   - Foreign keys: `portfolio_id` -> `portfolios.id` (CASCADE), `security_id` -> `securities.id` (SET NULL).
   - Columns: `owner_id`, `transaction_type`, `symbol`, `quantity`, `price`, `fees`, `transaction_date`, `notes`, `source`, `created_at`.
   - Constraints & Indexes: Check constraints on `transaction_type`, positive `quantity`, non-negative `price`, non-negative `fees`. Indexes on `(portfolio_id, transaction_date)` and `(owner_id)`.
   - RLS Policies: `ENABLE ROW LEVEL SECURITY`, `owner_tenant_isolation` policy checking `(auth.uid() = owner_id)`.
2. `portfolio_risk_history`:
   - Primary key: `id` (UUID).
   - Foreign keys: `portfolio_id` -> `portfolios.id` (CASCADE).
   - Columns: `owner_id`, `as_of_date`, `hhi`, `effective_n`, `max_drawdown`, `top_position_weight`, `sector_max_weight`, `var_historical_95`, `cvar_historical_95`, `metrics_payload` (JSONB), `created_at`.
   - Indexes: Index on `(portfolio_id, as_of_date)` and `(owner_id)`.
   - RLS Policies: `ENABLE ROW LEVEL SECURITY`, `owner_risk_history_tenant_isolation` policy checking `(auth.uid() = owner_id)`.

---

## 5. API Endpoints Added / Updated

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/market-data/health` | Provider Health Status | Returns database connectivity, price table bar counts, and last ingested session. |
| `GET` | `/api/v1/market-data/benchmark` | Historical Benchmark | Serves `^NSEI` adjusted close series from local DB with observation count. |
| `GET` | `/api/v1/market-data/history/{symbol}` | Instrument Price History | Serves daily raw & adjusted prices from local DB with quality qualification. |
| `GET` | `/api/v1/portfolios/{id}/transactions` | List Transactions | Returns all transactions for the authenticated portfolio owner. |
| `POST` | `/api/v1/portfolios/{id}/transactions` | Append Transaction | Records and validates a transaction, immediately updating derived ledger state. |
| `GET` | `/api/v1/portfolios/{id}/reconciliation` | Ledger Reconciliation | Computes ledger-derived holdings vs snapshot holdings and flags discrepancies. |
| `POST` | `/api/v1/portfolios/{id}/transactions/import-csv` | CSV Ledger Import | Imports CSV rows with formula protection and atomic rollback on errors. |
| `GET` | `/api/v1/portfolios/{id}/transactions/export-csv` | CSV Ledger Export | Exports transaction ledger with formula injection escaping. |
| `GET` | `/api/v1/portfolios/{id}/risk-history` | Tenant Risk History | Queries risk snapshots scoped strictly to the authenticated portfolio owner. |

---

## 6. Frontend Ledger Integrity & UI Implementation

- **Strict UI Constraints Preserved:**
  - Preserved the existing 9 portfolio tabs (no new tabs, routes, or navigation items created).
  - Maintained Warm Ivory palette (`#F9EBD7`, `#E3D7C4`, `#292D2A`, `#046A38`, `#E34222`), Inter & JetBrains Mono typography, no white backgrounds, no rounded borders.
- **Reconciliation Badge & Card:**
  - Added a compact ledger reconciliation status card in the Transaction Ledger tab.
  - Displays ledger-derived cash, invested capital, realized P&L, and verified status (`RECONCILED` in Emerald `#046A38` or `DISCREPANCY DETECTED` in Vermilion `#E34222`).
- **CSV Import / Export:**
  - Integrated modal dialog for CSV file upload with live preview and row-level error reporting.
  - **Formula Injection Defense:** Blocks cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r`. On export, formula characters are safely escaped with a prepended apostrophe (`'`).
- **Data Lineage Header:**
  - Header and tab headers display: `Source: yfinance DB pipeline | As-of: 2026-09-30 | Universe: NIFTY 200 (Active) | Coverage: 100% active universe`.
  - Survivorship disclaimer clearly stated.

---

## 7. Verification & Test Results

All quality and test gates were executed locally and passed cleanly:

### 7.1 Backend Test Results
```bash
uv run pytest
```
- **Result:** **101 passed, 2 skipped in 12.37s**
- **Coverage of Phase 2 Test Suites:**
  - `tests/portfolio/test_ledger_integrity.py` (8 passed):
    - WAC buy lot accumulation and average cost calculation.
    - Partial sell and realized P&L computation.
    - Overselling rejection (`LedgerValidationError`).
    - Negative quantity / price rejection.
    - Future date rejection.
    - Atomic rollback on failed batch import.
    - CSV formula injection rejection (`=SUM()`, `+100`, `@COMMAND`).
    - Multi-transaction buy, partial sell, dividend, and deposit reconciliation.
  - `tests/portfolio/test_authorization.py` (2 passed):
    - Tenant isolation: User A cannot read or modify User B's portfolios or transactions.
    - RLS policy validation for risk history and transactions.
  - `tests/market_data/test_lineage_and_quality.py` (5 passed):
    - Zero live network requests on API request paths.
    - Common-date alignment with observation count.
    - Extreme single-day return flagging ($> 30\%$).
    - Stale / non-positive data rejection and qualification.
    - Provider health reporting.

### 7.2 Code Style & Type Safety
```bash
uv run ruff check .
```
- **Result:** **All checks passed! (0 errors, 0 warnings)**

```bash
uv run mypy backend jobs
```
- **Result:** **Success: no issues found in 58 source files**

### 7.3 Frontend Test & Build Results
```bash
pnpm test -- --run
```
- **Result:** **7 test files passed, 39 tests passed in 5.51s**
  - `src/portfolioCsv.test.ts` (7 tests passed): Formula injection rejection, CSV roundtrip parsing, and escaping.
  - `src/journalStorage.test.ts` (8 tests passed).
  - `src/demoPortfolio.test.ts` (3 tests passed).
  - `src/portfolioCalculations.test.ts` (8 tests passed).
  - `src/journalAndDecision.test.ts` (11 tests passed).
  - `src/App.test.tsx` (1 test passed).
  - `src/CompanyDetail.test.tsx` (1 test passed).

```bash
pnpm run lint
```
- **Result:** **0 errors, 0 warnings**

```bash
pnpm run build
```
- **Result:** **Production bundle built in 260ms (`dist/index.html` + asset chunks)**

---

## 8. Unsupported Items & Limitations

1. **Stock Splits & Bonus Issues in Ledger:**
   - Reliable historical corporate-action split/bonus ratios are not yet integrated into the interactive user ledger. Corporate actions must currently be recorded as compensating BUY/SELL transactions at zero cost. Automatic adjustment will be evaluated in Phase 3.
2. **Survivorship Bias:**
   - Security master and historical price series cover the active constituents of the NIFTY 200 as of 2026-09-30. Portfolios containing historical constituents delisted or removed prior to this date cannot be analyzed.
