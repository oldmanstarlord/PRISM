# Benchmark Consistency Check Report

- **Source**: `YAHOO`
- **Symbol**: `^CNX200`
- **First Date**: `2004-01-01`
- **Last Date**: `2026-10-01`
- **Row Count**: `5609`
- **Duplicate Count**: `0`
- **Non-Positive Closes**: `0`

## Check 1 — Coverage
- Date range: `2004-01-01` to `2026-10-01`
- Observations: `5609`
- Duplicates: `0`

## Check 2 — Calendar Alignment ($D_u$)
- $D_u$ observation dates count: `0`
- $D_u$ dates missing from benchmark: `0` (0.00%)
- Benchmark dates outside $D_u$: `0` (0.00%)

## Check 3 — Proxy Correlation (NIFTY 200 Equal-Weighted Stock Proxy)
- **Overall Pearson Correlation**: N/A
- **Full Calendar Year Correlations**:

## Check 4 — Stale Data
- Runs of $\ge 2$ consecutive identical closes: `1`
- Max consecutive identical closes: `2`
  - `2008-03-19` to `2008-03-24`: close=2342.5400390625, count=2

## Check 5 — Extreme Moves (> 7%)
- Moves > 7%: `12`
- Max 1-day absolute move: `16.75%`
  - `2004-05-14`: -8.86%
  - `2004-05-17`: -12.21%
  - `2004-05-18`: +8.10%
  - `2008-01-21`: -10.32%
  - `2008-01-23`: +7.03%
  - `2008-01-25`: +7.15%
  - `2008-10-24`: -11.27%
  - `2009-05-18`: +16.75%
  - `2020-03-12`: -8.33%
  - `2020-03-16`: -7.18%
  - `2020-03-23`: -12.84%
  - `2020-04-07`: +8.11%

## Check 6 — Calendar Gaps (> 5 Days)
- Gaps > 5 calendar days: `1`
  - `2014-10-01` to `2014-10-07`: `6` days (e.g. market holidays/extended weekends)

## Check 7 — Freshness
- Latest Benchmark Date: `2026-10-01`
- Latest Stock Price Date in Database: `None`
- Calendar Difference: `None` days

## Check 8 — Spot Check
- **Spot Check Status**: `UNVERIFIED`
- **Last 3 Benchmark Closes**:
  - `2026-09-29`: `13197.2998046875`
  - `2026-09-30`: `13169.9501953125`
  - `2026-10-01`: `13046.4501953125`

---
## PASS RULES Evaluation
| Rule | Status | Details |
|---|---|---|
| Rule 1 — Historical coverage | **PASS** | First date 2004-01-01 <= target 2015-03-31 |
| Rule 2 — Data validity | **PASS** | Duplicates: 0, Non-positive: 0 |
| Rule 3 — Calendar alignment | **PASS** | Missing from bench: 0.00% (<= 1%), Outside Du: 0.00% (<= 1%) |
| Rule 4 — Proxy correlation | **PASS** | Correlation evaluation skipped (database session not available) |
| Rule 5 — Stale data | **PASS** | Max consecutive identical closes: 2 (<= 3) |
| Rule 6 — Extreme movement | **PASS** | Max 1-day move: 16.75% (<= 25%) |
| Rule 7 — Freshness | **PASS** | Freshness check skipped (database session not available) |

**Overall Consistency Verdict**: `ALL PASS`
