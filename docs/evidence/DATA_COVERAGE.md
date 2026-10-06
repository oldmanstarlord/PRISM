# Data Coverage

Generated at: `2026-10-06T18:40:05.878027+00:00`  
Active universe: **200 securities**

Only rows attributable to a permitted production source are counted. Quarantined fixture rows and supplied files that cannot satisfy a strict importer are excluded.

## Dataset coverage

| Dataset | Source | Real or missing | Coverage status | Rows | First date | Last date | Universe | Staleness | Limitations |
|---|---|---:|---:|---:|---|---|---:|---:|---|
| announcements | National Stock Exchange of India Limited | real | insufficient | 3 | 2026-10-06 | 2026-10-06 | 2/200 (1.0%) | fresh | Coverage is limited to the supplied official export window. |
| benchmark | Yahoo | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | Yahoo benchmark failed the strict calendar/correlation/freshness import gate. |
| corporate_actions | Yahoo | real | ok | 2,864 | 2015-01-14 | 2026-09-30 | 200/200 (100.0%) | missing | No row is expected for a security with no corporate action. |
| fundamentals | Yahoo | real | ok | 1,074 | 2025-03-31 | 2026-06-30 | 200/200 (100.0%) | fresh | Publication dates from Yahoo are explicitly estimated. |
| insider_trades | National Stock Exchange of India Limited | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | Requires normalized transaction fields, not XBRL links alone. |
| macro:crude_oil | Yahoo | real | ok | 1,701 | 2020-01-02 | 2026-10-05 | 200/200 (100.0%) | fresh | End-of-day series. |
| macro:fii_dii_net_flows | NSE/BSE/NSDL | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | A dated official daily/monthly export with actual publication timestamps is required. |
| macro:in_10y_yield | Yahoo | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | Yahoo ticker `^IN10YT=RR` returned HTTP 404; no alternative permitted source was substituted. |
| macro:india_vix | Yahoo | real | ok | 1,655 | 2020-01-02 | 2026-10-05 | 200/200 (100.0%) | fresh | Not an official NSE distribution feed. |
| macro:usd_inr | Yahoo | real | ok | 1,759 | 2020-01-01 | 2026-10-05 | 200/200 (100.0%) | fresh | End-of-day series. |
| news_policy | Press Information Bureau, Government of India | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | PIB is not enabled as a verified production feed. |
| news_policy | Reserve Bank of India | real | ok | 10 | 2026-10-05 | 2026-10-06 | 200/200 (100.0%) | fresh | Official press-release RSS metadata re-observed on the live feed. |
| news_policy | Securities and Exchange Board of India | real | ok | 30 | 2026-09-29 | 2026-10-04 | 200/200 (100.0%) | fresh | Official RSS metadata re-observed on the live feed. |
| news_policy | Ministry of Finance, Government of India | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | A separately verified official feed or documented manual export is required. |
| prices | Yahoo | real | ok | 503,227 | 2015-01-01 | 2026-10-01 | 200/200 (100.0%) | missing | Registry success predates source-registry tracking; row provenance is `yfinance`. |
| shareholding | National Stock Exchange of India Limited | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | Supplied export lacks symbol, FII/DII, pledge, shares outstanding, and actual normalized publication fields. |
| shares_outstanding | National Stock Exchange of India Limited | missing | missing | 0 | N/A | N/A | 0/200 (0.0%) | missing | Requires an official export containing total shares outstanding. |
| universe | NSE Indices Limited | real | ok | 200 | N/A | N/A | 200/200 (100.0%) | missing | Current membership only; historical survivorship remains unavailable. |

## Risk-dimension coverage

| Dimension | OK | Stale | Missing | Insufficient |
|---|---:|---:|---:|---:|
| market | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 200 (100.0%) |
| liquidity | 200 (100.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| structure | 0 (0.0%) | 0 (0.0%) | 200 (100.0%) | 0 (0.0%) |
| relative | 184 (92.0%) | 0 (0.0%) | 16 (8.0%) | 0 (0.0%) |
| fundamentals | 4 (2.0%) | 1 (0.5%) | 21 (10.5%) | 174 (87.0%) |
| governance | 0 (0.0%) | 0 (0.0%) | 200 (100.0%) | 0 (0.0%) |
| events | 2 (1.0%) | 0 (0.0%) | 198 (99.0%) | 0 (0.0%) |
| macro | 200 (100.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |

The market dimension is insufficient because the benchmark-dependent beta component is missing. Structure is missing because no current MST component values were available in this v1 run. Relative coverage comes from the existing point-in-time sector-divergence run.

## Fundamentals component status

| Component | OK | Stale | Missing | Insufficient |
|---|---:|---:|---:|---:|
| fund_leverage | 23 | 1 | 176 | 0 |
| fund_coverage | 135 | 0 | 65 | 0 |
| fund_profit_trend | 175 | 0 | 23 | 2 |
| fund_cashflow_quality | 4 | 0 | 196 | 0 |

Yahoo returned at least four quarters for 199 stocks and two quarters for VAML. Component availability is lower than quarter availability because Yahoo does not populate every required line item for every issuer, particularly cash from operations and interest expense.

## Score effect

| Snapshot | Run | Median risk | Median confidence |
|---|---|---:|---:|
| Before | Not available (no prior approved-v1 run) | N/A | N/A |
| After | `9c681f61-1490-4736-a604-68dea745e307` | 50.15 | 51.31 |

The first approved-v1 calculation scored 200/200 stocks. A second identical invocation reported `Reused existing` for the same run. Version 2 remains draft and was not executed.

## Still missing -- exact supply requirements

- **Benchmark**: supply official NIFTY 200 daily history covering at least 2015-01-01 through the latest stock-price date. The four supplied files cover only 2023-01-02 through 2026-10-06, while the Yahoo candidate failed the strict import gate. Preserve the official `Date, Open, High, Low, Close` values without filling dates.
- **Shareholding and shares outstanding**: create `data/raw/shareholding/nse_shareholding.csv` with `symbol,quarter_end,promoter_pct,promoter_pledged_pct_of_promoter,fii_pct,dii_pct,public_pct,published_at,shares_outstanding,source_doc_id`, copied from official disclosures without inference.
- **Insider trades**: create `data/raw/insider_trades/nse_insider_trades.csv` with `symbol,person_category,txn_type,quantity,value,txn_date,published_at,source_doc_id`.
- **FII/DII net flows**: confirm acceptance of a manual official daily or monthly export and supply `data/raw/macro/fii_dii_net_flows.csv` with `date,value,published_at,version`; `value` must be combined net flow in INR crores and `published_at` must include its actual timezone. The supplied one-day files are insufficient.
- **India 10-year yield**: supply a permitted RBI/CCIL export with observation date, yield, and actual publication timestamp, because Yahoo returned no series.
- **PIB and Ministry of Finance**: provide a verified official feed URL that is accessible to the application, or an official manual metadata export containing headline, URL, and actual publication time.

## Integrity statement

No fixture or invented data was written by this ingestion step. Supplied original files were preserved under `data/raw/`, and a dataset remains visibly missing when it cannot satisfy the strict schema, history, permission, or quality gate.
