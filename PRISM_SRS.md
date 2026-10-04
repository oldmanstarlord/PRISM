# PRISM - Software Requirements Specification

| Field | Value |
|---|---|
| Project | PRISM - Portfolio Risk & Intelligence System for Markets |
| Document version | 1.6 (consolidated working SRS) |
| Date | 2026-10-02 |
| Status | Approved project direction; open items are explicitly marked TBD |
| Initial universe | NIFTY 200 |
| Primary market | Indian listed equities, initially NSE |

---

## 0. Document authority and usage

This document is the consolidated source of truth for PRISM. It incorporates the original project requirements and the decisions made during requirements review. It is intended for the project team, evaluators, developers and AI assistants.

If another document conflicts with this one, this document takes precedence unless a later dated decision is recorded in Section 17.

### 0.1 Rules for contributors and AI assistants

1. Layer 1 and Layer 2 are new components to be designed, implemented and validated by this project. Their approved formulas and interfaces must be versioned once established.
2. Do not describe PRISM as a reliable stock-price prediction system. Its primary targets are portfolio risk, volatility, market regimes, diversification, attribution and explanation.
3. Price-direction modelling is experimental and must never appear as a headline capability.
4. No feature, model or backtest may use information that was unavailable at the calculation time.
5. Every alert, score and forecast must expose its reason, inputs, thresholds, model or method version, and limitations.
6. Every user-facing output must state that it is not investment advice.
7. Requirements must be referenced by ID when designing, implementing or testing work.
8. Unspecified behaviour must be identified as an assumption or TBD rather than invented.
9. The NIFTY 200 universe must be configurable and versioned; it must not be hard-coded into application logic.

### 0.2 Product summary

PRISM is an explainable portfolio-risk and market-intelligence platform for Indian equities. It combines deterministic sector-divergence and minimum-spanning-tree components to be built within PRISM with point-in-time market data, company filings and news analysis, return attribution, risk forecasting, diversification analysis, shock simulation, stock dossiers, alerts and a validation framework. Users interact with the system through a React dashboard backed by a FastAPI service and PostgreSQL.

---

## 1. Purpose, vision and scope

### 1.1 Purpose

PRISM must help an investor, analyst or evaluator answer:

- How risky and concentrated is a portfolio?
- How many genuinely independent exposures does it contain?
- Is a stock moving with the market, its sector or for company-specific reasons?
- What filings, results, ownership changes or news may explain recent behaviour?
- How might a hypothetical shock propagate through related holdings?
- Are warnings and forecasts historically useful outside the data used to build them?

### 1.2 Product principles

- **Risk before prediction:** forecast volatility and risk rather than promising price direction.
- **Point-in-time correctness:** use only information knowable at the time.
- **Explainability:** show why every result was produced.
- **Baselines first:** complex models remain only when they outperform simple baselines out of sample.
- **Modularity:** layers communicate through versioned contracts.
- **Reproducibility:** data, code, parameters and model versions identify every result.
- **Honest failure reporting:** weak or unstable signals remain visible in validation results.

### 1.3 In scope

- NIFTY 200 equities, with architecture capable of later NIFTY 500 expansion.
- Daily OHLCV and corporate-action data.
- Portfolio-level and stock-level risk measurements.
- Layer 1 sector-divergence and Layer 2 MST design, implementation and validation.
- Corporate filings, announcements and news intelligence.
- Return attribution, volatility forecasts, regimes and anomaly detection.
- Diversification analysis, graph-based shock simulation and stock dossiers.
- Explainable alerts, watchlists and digests.
- Web dashboard and API.
- Point-in-time validation and audit history.

### 1.4 Out of scope

- Order execution, brokerage integration and automated trading.
- Guaranteed or marketed stock-price predictions.
- Personalised investment advice.
- Derivatives and options valuation.
- Social-media scraping in the initial roadmap.
- Intraday trading features in the initial release.
- Non-Indian markets in the initial release.

---

## 2. Users and use cases

| User | Primary needs |
|---|---|
| Retail or student investor | Understand portfolio risk, concentration and why holdings move |
| Analyst | Review a stock timeline, filings, unusual behaviour and risk warnings |
| Project team | Build and test independent layers through stable contracts |
| Evaluator or researcher | Reproduce results and inspect out-of-sample evidence |

### 2.1 Principal use cases

1. Enter or upload a portfolio and receive a risk and diversification assessment.
2. Explore the portfolio MST, clusters, hubs and concentrated exposures.
3. Apply a hypothetical shock to one holding and inspect estimated propagation.
4. Open a stock dossier containing prices, filings, events, sentiment and signals.
5. Review an alert with its inputs, threshold, explanation and confidence.
6. Compare each model or signal with its required baseline.
7. Reproduce a historical result from the associated data and version metadata.

---

## 3. System architecture

```text
Yahoo Finance prototype data | NSE/BSE metadata and filings | RBI/macro | news
                                  |
                                  v
                    Python ingestion pipelines
                  (APScheduler and Tenacity)
                                  |
                                  v
                           PostgreSQL
                      point-in-time data store
                     /            |             \
                    v             v              v
           Layer 1 new      Layer 2 new      Layer 3 text
          divergence       correlation MST  intelligence
                    \             |              /
                     \            v             /
                      Layer 4 attribution and risk
                                  |
                                  v
                         Layer 5 insight features
                                  |
                                  v
                     FastAPI REST API and OpenAPI
                                  |
                                  v
                       React/TypeScript dashboard

Cross-cutting: validation, lineage, audit, security and data-quality controls
```

### 3.1 Layer map

| Layer | Name | Status |
|---|---|---|
| 0 | Data ingestion and storage | New |
| 1 | Sector divergence signal | New |
| 2 | Correlation minimum spanning tree | New |
| 3 | Text intelligence | New |
| 4 | Attribution and risk forecasting | New |
| 5 | Insight features | New |
| 6 | API, dashboard, tracking and trust | New |
| Cross-cutting | Validation and audit framework | New |

### 3.2 Temporal heterogeneous graph extension

Layer 4 may construct a separate temporal heterogeneous graph for advanced risk research. The approved Layer 2 MST is included as one versioned stock-to-stock relationship type alongside sector, macroeconomic, filing, event and news relationships.

The heterogeneous graph is an advanced Phase 4 component. Simpler relational, tabular and homogeneous-graph baselines must be implemented first.

---

## 4. Decided technology stack

### 4.1 Core stack

| Area | Decision |
|---|---|
| Primary language | Python 3.12 |
| Database | Supabase-hosted PostgreSQL |
| Backend API | FastAPI |
| API validation | Pydantic |
| Frontend | React with TypeScript |
| Frontend build tool | Vite |
| Text model | `ProsusAI/finbert` through Hugging Face Transformers |

### 4.2 Backend, data and ML tools

| Purpose | Tool |
|---|---|
| ORM and SQL access | SQLAlchemy 2 |
| PostgreSQL driver | Psycopg 3 |
| Database migrations | Alembic |
| Python dependency management | `uv` |
| HTTP client | HTTPX |
| Settings and environment validation | `pydantic-settings` |
| Dataframes and numerical work | pandas and NumPy |
| Statistical modelling | statsmodels and `arch` |
| General machine learning | scikit-learn |
| Gradient-boosted models | XGBoost |
| Graph calculations | NetworkX |
| Deep learning | PyTorch |
| Heterogeneous graph learning | PyTorch Geometric |
| NLP models | Hugging Face Transformers |
| Native scheduling | APScheduler |
| Retry and backoff policy | Tenacity |
| Prototype price source client | `yfinance` |

Tools are introduced only in the phase that needs them. Phase 0 must not install advanced ML dependencies merely because they appear in the final stack.

### 4.3 Frontend tools

| Purpose | Tool |
|---|---|
| Component library | Material UI |
| Server-state and API requests | TanStack Query |
| Routing | React Router |
| Forms | React Hook Form |
| Client-side schema validation | Zod |
| Statistical and financial charts | Plotly.js |
| MST and network visualisation | Cytoscape.js |
| Unit and component tests | Vitest and React Testing Library |
| End-to-end browser tests | Playwright |
| Linting and formatting | ESLint and Prettier |

### 4.4 Development and deployment tools

| Purpose | Tool or policy |
|---|---|
| Local services | Native Python and Node processes |
| Database runtime | Managed PostgreSQL on Supabase |
| Public reverse proxy and HTTPS | Deferred until hosted deployment design |
| Source control and hosting | Git and GitHub |
| Continuous integration | GitHub Actions |
| Python tests | pytest |
| Python linting and formatting | Ruff |
| Python static typing | mypy |
| Commit-time checks | pre-commit |
| API description | FastAPI-generated OpenAPI |
| Dependency updates | Dependabot |
| Logging | Structured JSON logs |

### 4.5 Initial deployment and authentication

The first release is a single-user application with a locally run FastAPI backend and React frontend. It does not require application user accounts. Structured project and portfolio data is stored in the owner's Supabase project, accessed only through FastAPI, and database credentials are never exposed to the React application.

Before public or multi-user deployment, PRISM must add authenticated accounts, secure HTTP-only sessions, Argon2 password hashing or an approved identity provider, portfolio ownership checks, HTTPS and a documented deletion procedure.

---

## 5. Universe and market conventions

### 5.1 Initial universe

PRISM's first product universe is the **NIFTY 200**. Small subsets may be used during unit and integration testing, but production-facing results for the initial release target NIFTY 200.

### 5.2 Universe rules

- Membership must be stored with `valid_from` and `valid_to` dates.
- Historical evaluation must use membership effective on each historical date.
- Present-day membership must not be retroactively applied to old tests.
- Delisted, renamed, merged and removed securities must remain in historical snapshots.
- ISIN is the durable security identifier; exchange symbols are versioned aliases.
- Exclusions caused by missing data or insufficient history must be recorded with reasons.
- Expansion to NIFTY 500 must require configuration and data validation, not application rewrites.

### 5.3 Market conventions

| Item | Rule |
|---|---|
| Initial frequency | Daily |
| Primary exchange | NSE; BSE may be used for cross-checking and filings |
| Timezone | Asia/Kolkata |
| Calendar | Official exchange trading calendar |
| Currency | INR unless explicitly labelled otherwise |
| Daily information cutoff | After-close filings affect the next trading day |

---

## 6. Core quantitative layers to be built

### 6.1 Shared foundation

PRISM must calculate a versioned variance-covariance and correlation foundation from validated adjusted returns. Layer 1 and Layer 2 will be built on this foundation.

### 6.2 Layer 1: sector divergence

Layer 1 reports how differently a stock behaves from the other NIFTY 200 securities in
its official Nifty Indices `Industry` group. Version 1 is entirely deterministic. It must not
use machine learning, artificial intelligence, learned weights or model-generated scores.

#### 6.2.1 Classification and eligible universe

- The version 1 grouping field is the official `Industry` value supplied in the archived
  NIFTY 200 constituent CSV. Interfaces may display this as the sector benchmark but must
  retain the source field name and must not imply that a separate sector taxonomy was used.
- Membership and industry are selected as of the signal date.
- A group requires at least five otherwise eligible securities, including the target.
- The target is always removed from its own benchmark, leaving at least four peers.
- A date without enough contemporaneous peer returns produces no score; values are never
  forward-filled, backward-filled or replaced with zero.
- PRISM first observed versioned NIFTY 200 membership on 2026-09-30. Results for earlier
  dates cannot be described as point-in-time NIFTY 200 results. Any permitted research
  reconstruction must be labelled `reconstructed_current_universe` and excluded from
  headline backtest claims.

#### 6.2.2 Prices and returns

For security `i` on trading date `t`, version 1 uses the latest eligible adjusted-close
revision available by the calculation's data cutoff and calculates the daily log return:

```text
r(i,t) = ln(P(i,t) / P(i,t-1))
```

Prices must be finite and strictly positive. A return requires two consecutive observations
for that security; PRISM does not manufacture a return across an absent observation. At least
45 valid paired return observations are required in the 60-trading-day estimation window.

#### 6.2.3 Leave-one-out industry benchmark

The benchmark for target `i` is the median of the contemporaneous returns of the other
eligible securities in industry group `g(i)`:

```text
r(g,-i,t) = median({r(j,t) : j in g(i), j != i})
```

The median is fixed for version 1 because it is transparent and less sensitive than the mean
to a single extreme constituent. No capitalization weights or learned weights are used.

#### 6.2.4 Rolling alpha, beta and residual

For signal date `t`, alpha, beta and residual volatility are estimated from the preceding 60
trading dates, excluding `t`, using only dates on which both the target and its leave-one-out
benchmark have valid returns:

```text
beta(i,t)  = Cov(r(i), r(g,-i)) / Var(r(g,-i))
alpha(i,t) = mean(r(i)) - beta(i,t) * mean(r(g,-i))
expected(i,t) = alpha(i,t) + beta(i,t) * r(g,-i,t)
epsilon(i,t)  = r(i,t) - expected(i,t)
```

The covariance and variance use the sample convention (`ddof = 1`). If benchmark variance is
zero or fewer than 45 paired observations exist, the result is unavailable with an explicit
reason. To prevent floating-point noise from turning a mathematically degenerate regression
into an extreme score, benchmark variance or residual volatility less than or equal to
`1e-15` is treated as zero. The calculation must not use observations after `t` or fit on the
signal-date return.

#### 6.2.5 Standardized divergence horizons

The primary outputs remain separate rather than being hidden in a composite score:

```text
Z(i,t,h) = sum(epsilon(i,t-k), k=0..h-1) / (sigma_epsilon(i,t) * sqrt(h))
h in {1, 5, 20}
```

Each daily residual in a multi-day horizon must be produced using parameters available for
that residual's date. `sigma_epsilon(i,t)` is the sample standard deviation of the residuals
from the same trailing estimation window. Zero residual volatility produces no standardized
score. Version 1 publishes `z_1d`, `z_5d` and `z_20d`; it does not publish a weighted composite.

The fixed descriptive bands are:

| Absolute score | Label |
|---:|---|
| `< 1` | Normal |
| `>= 1 and < 2` | Moderate |
| `>= 2 and < 3` | Strong |
| `>= 3` | Extreme |

The sign indicates unusual outperformance or underperformance. These labels are descriptive,
not probability claims, because equity residuals need not be normally distributed.

#### 6.2.6 Ranking, determinism and version

- Percentiles are calculated separately for each signal date, industry and horizon using the
  weak empirical cumulative distribution: `100 * count(score <= target) / N`. Equal values
  therefore receive the same upper-rank percentile deterministically.
- Stable ordering is by trading date, industry, symbol and ISIN where a tie remains.
- Identical source revisions, cutoff, membership snapshot and configuration must produce
  identical results.
- The approved formula identifier is `sector-divergence-v1`.
- Every output must retain the signal date, industry, horizon, raw residual, standardized
  value, alpha, beta, residual volatility, observations used, lookback bounds, data cutoff,
  membership source, adjustment method/revision and computation time.

### 6.3 Layer 2: correlation MST

Layer 2 uses the approved deterministic `correlation-mst-v1` contract.

#### 6.3.1 Point-in-time universe and prices

- The universe and NSE symbols are those valid on the window end and observed by the data cutoff.
- Prices are the latest positive finite adjusted closes whose computation time is no later than
  the explicit data cutoff.
- Each selected price retains its adjustment method/revision and computation timestamp.
- Historical membership before PRISM's first official observation must not be inferred.

#### 6.3.2 Returns and window

For adjusted close `P(i,t)`, the daily return is:

```text
r(i,t) = ln(P(i,t) / P(i,t-1))
```

The calculation uses at most the latest 121 aligned price dates through the window end, producing
120 daily returns. A return is unavailable unless both adjacent prices exist. Prices and returns
are never forward-filled, backward-filled or replaced with zero. Layer 2 is refreshed after a
validated daily close, not from incomplete intraday data.

#### 6.3.3 Eligibility and missing data

- A security initially requires at least 100 finite returns in the 120-return window.
- Every included pair requires at least 100 paired finite returns and non-degenerate return
  variance greater than `1e-15` for both members on those paired dates.
- If the initially eligible set is not a complete valid correlation graph, PRISM iteratively
  excludes the security participating in the greatest number of invalid pairs. Ties are resolved
  by ascending symbol. Each exclusion and reason is retained.
- The run fails rather than publishing a partial tree if fewer than two securities remain or the
  eligible graph cannot produce a connected tree.

#### 6.3.4 Correlation and distance

Each eligible pair uses Pearson sample correlation on its paired finite daily log returns. Values
are clamped to `[-1, 1]` only to remove floating-point overflow at the mathematical boundary. The
Mantegna distance is:

```text
d(i,j) = sqrt(2 * (1 - rho(i,j)))
```

This maps perfect positive correlation to `0`, zero correlation to `sqrt(2)` and perfect negative
correlation to `2`. Correlation and MST edges describe co-movement, not causality.

#### 6.3.5 MST algorithm and determinism

- Candidate pairs use canonical ascending symbol order `(symbol_a, symbol_b)`.
- Candidate edges are sorted by `(distance, symbol_a, symbol_b)`.
- Kruskal's algorithm with Union-Find selects an edge only when it joins two components.
- Edge rank is the one-based selection order.
- A valid run must be connected, acyclic and contain exactly `N-1` edges for `N` included nodes.
- Re-running an identical versioned input fingerprint and configuration reuses the completed run.

The reference implementation target is `O(N^2*T + N^2 log N)` time and `O(N^2)` candidate-edge
memory for `N <= 200` and `T = 120`; actual daily runtime must be measured on the development
machine.

### 6.4 Mandatory design decisions

The following decisions must be approved and documented before the quantitative layers are complete:

- Public entry points and interfaces.
- Required input fields, types, shapes and ordering.
- Return calculation and adjustment policy.
- Lookback window and update frequency.
- Minimum observations and missing-data treatment.
- Sector aggregation and divergence definition.
- Correlation method and correlation-to-distance transformation.
- MST tie-breaking and determinism.
- Output fields, shapes and error behaviour.
- Runtime and memory targets.

The Layer 1 and Layer 2 version 1 choices above are approved for implementation. Layer 2 edge
stability across consecutive windows remains a Phase 1 requirement rather than a Phase 0 input to
the first valid tree.

### 6.5 Target Layer 1 interface envelope

The Layer 1 implementation must expose at least:

```text
symbol, date, industry, horizon, residual_value, divergence_value,
alpha, beta, residual_volatility, industry_percentile,
lookback_start, lookback_end, observations_used, data_cutoff,
membership_source, adjustment_version, status,
implementation_version, computed_at
```

### 6.6 Target Layer 2 interface envelope

The Layer 2 implementation must expose edge records:

```text
run_id, window_start, window_end, universe_version,
symbol_a, symbol_b, correlation, paired_observations,
distance, edge_rank, implementation_version, computed_at, data_cutoff
```

It should also expose run metadata including requested symbols, included symbols, exclusions with reasons, edge count and connectivity status. For an eligible connected universe of `N` nodes, validation must confirm `N-1` edges and no cycles.

---

## 7. Data requirements and source policy

### 7.1 Source registry

| Dataset | Initial source | Verification or fallback | Status |
|---|---|---|---|
| Daily OHLCV | `yfinance` | NSE/BSE or later licensed provider | Decided for prototype |
| Dividends and splits | `yfinance` | NSE/BSE corporate actions | Decided for prototype |
| NIFTY 200 membership | Official Nifty Indices constituent CSV | Archived PRISM snapshots | Current snapshot integrated; historical source TBD |
| Symbol and ISIN master | NSE/BSE metadata | Controlled manual correction | Source integration TBD |
| Sector and industry | Official index/exchange classification | Versioned mapping | Source integration TBD |
| Filings and announcements | NSE/BSE official pages | None initially | Phase 2 |
| Market capitalisation | Price multiplied by verified shares outstanding | Provider TBD | Source TBD |
| Index and macro series | RBI, exchange and index-provider publications | Approved alternative | Phase 3 |
| News | Timestamped licensed/free feed | Provider TBD | Phase 2 source TBD |

### 7.2 `yfinance` policy

`yfinance` is approved only as the initial research and educational source for prototype daily prices, volume, dividends and splits. It is unofficial and must not be treated as authoritative or automatically suitable for commercial redistribution.

The ingestion implementation must:

- Request unadjusted OHLC plus adjusted close and corporate actions.
- Preserve the raw response before normalization.
- Retain missing rows for quality inspection where possible.
- Record request parameters, retrieval time and library version.
- Cache results and avoid unnecessary complete-history downloads.
- Validate currency, splits, duplicates, gaps and extreme returns.
- Cross-check suspicious observations against NSE/BSE.
- Keep the source adapter replaceable by an official or licensed feed.

Historical data downloaded today must not automatically be described as a historically captured point-in-time snapshot. PRISM's own append-only snapshots begin when its ingestion system records them.

### 7.3 Point-in-time rule

A record is eligible for a calculation at time `t` only if it was genuinely available to the system by `t`. Each source record must preserve, when applicable:

```text
event_time
published_at
ingested_at
effective_from
source_revision
source_url
content_hash
```

Corrections create new versions. They must not silently overwrite the historical record used by a prior calculation.

### 7.4 Raw-file policy

Structured records and metadata reside in PostgreSQL. Large raw filings, PDFs and source snapshots are stored outside normal relational columns. The local release uses a versioned `data/raw` directory with checksums and database references. A hosted deployment may replace this with S3-compatible object storage without changing domain interfaces.

### 7.5 Core logical entities

- `security` and `security_alias`
- `universe` and `universe_membership`
- `trading_calendar`
- `price_daily_raw` and `price_daily_adjusted`
- `corporate_action`
- `filing` and `news_item`
- `text_score`
- `signal_l1`
- `mst_run` and `mst_edge`
- `graph_snapshot`, `graph_node` and `graph_edge`
- `graph_node_type` and `graph_relation_type`
- `macro_series` and `macro_observation`
- `event` and `event_security_link`
- `portfolio` and `holding`
- `risk_measure`
- `attribution`
- `forecast`
- `alert`
- `pipeline_run`
- `model_version`
- `validation_result`
- `audit_event`

The physical PostgreSQL schema is managed through reviewed Alembic migrations.

### 7.6 Data-quality policy

At minimum, ingestion must detect:

- Duplicate security-date observations.
- Unknown or ambiguous symbols.
- Missing required fields.
- Negative prices or volume.
- `high < low` or a close outside the reported range.
- Missing exchange trading days.
- Currency mismatches.
- Extreme returns without a matching corporate action.
- Implausible adjustment factors.
- Insufficient observations for a downstream calculation.

Invalid data must be rejected or quarantined; suspicious data must be flagged. Source observations must not be silently deleted. Exact warning and rejection thresholds are Phase 0 configuration items.

---

## 8. Functional requirements

Priority: **M** = Must, **S** = Should, **C** = Could.

### 8.1 Layer 0 - ingestion and storage

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-D1 | Ingest daily raw and adjusted OHLCV for the effective NIFTY 200 universe. | M | 0 |
| FR-D2 | Ingest and version dividends, splits, bonus issues and other supported corporate actions. | M | 0 |
| FR-D3 | Maintain versioned security, symbol, ISIN, sector, industry and universe-membership records. | M | 0 |
| FR-D4 | Preserve event, publication and ingestion times and never silently overwrite source history. | M | 0 |
| FR-D5 | Schedule ingestion with retries, run manifests and data-quality reports. | M | 0 |
| FR-D6 | Ingest NSE/BSE announcements, results, board meetings, insider disclosures, shareholding patterns and event calendars. | M | 2 |
| FR-D7 | Ingest timestamped news headlines from an approved source. | S | 2 |
| FR-D8 | Ingest index levels, USD/INR, crude oil, rates and institutional-flow series. | S | 3 |
| FR-D9 | Make source adapters replaceable without changing downstream layer contracts. | M | 0 |

### 8.2 Core quantitative layers

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-L1 | Design, implement and validate a sector-divergence measure with documented returns, sector benchmark, lookback, missing-data rules and thresholds. | M | 0 |
| FR-L2 | Design, implement and validate a correlation-distance MST using Kruskal's algorithm and Union-Find with deterministic tie-breaking. | M | 0 |
| FR-L2D | Calculate consecutive-window edge persistence and expose an MST stability measure. | S | 1 |

### 8.3 Core portfolio risk

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-R1 | Calculate portfolio return and annualised volatility using documented weight and missing-price rules. | M | 1 |
| FR-R2 | Calculate each holding's marginal and percentage contribution to portfolio risk. | M | 1 |
| FR-R3 | Report concentration by holding, sector and MST cluster. | M | 1 |
| FR-R4 | Report portfolio and holding beta against the configured benchmark. | S | 1 |
| FR-R5 | Report historical drawdown and maximum drawdown. | M | 1 |
| FR-R6 | Report historical or parametric VaR and expected shortfall with method, horizon and assumptions visible. | S | 3 |
| FR-R7 | Compare portfolio risk and drawdown with the configured benchmark. | S | 1 |

### 8.4 Layer 3 - text intelligence

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-T1 | Classify filings and headlines as positive, negative or neutral with class probabilities using FinBERT. | M | 2 |
| FR-T2 | Chunk texts beyond the model limit and aggregate chunk scores through a documented method. | M | 2 |
| FR-T3 | Classify events into results, dividends, management, debt/ratings, insider/promoter, M&A, regulatory and other categories. | M | 2 |
| FR-T4 | Calculate a documented importance score using event type, magnitude and company relevance. | S | 2 |
| FR-T5 | Link items by exchange metadata and ISIN, using name matching only as a controlled fallback. | M | 2 |
| FR-T6 | Store the evidence sentence or passage supporting a text score. | S | 2 |
| FR-T7 | Evaluate and optionally fine-tune sentiment on labelled Indian financial text. | C | 4 |
| FR-T8 | Generate short summaries of important filings only after cost, privacy and factuality controls are approved. | C | 4 |

### 8.5 Layer 4 - attribution and forecasting

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-F1 | Attribute stock returns to market, sector and idiosyncratic components. | M | 3 |
| FR-F2 | Link large idiosyncratic moves to eligible company events and rank possible explanations. | S | 3 |
| FR-F3 | Forecast stock and portfolio volatility, comparing ML challengers with EWMA and GARCH-family baselines. | M | 3 |
| FR-F4 | Identify documented market regimes from volatility and average correlation. | S | 3 |
| FR-F5 | Detect unusual volume, price gaps and decoupling from Layer 2 neighbours. | S | 3 |
| FR-F6 | Construct a temporal heterogeneous graph of stocks, sectors, macro variables, filings, events and news, with the approved Layer 2 MST represented as one stock-to-stock relation. Evaluate it for risk, volatility and spillover forecasting. | C | 4 |
| FR-F6A | Record every graph node and edge with its type, source, event or validity time, ingestion time, construction method and graph-snapshot version. | M | 4 |
| FR-F6B | Compare heterogeneous models against tabular, relational non-neural, non-graph and homogeneous stock-graph baselines. | M | 4 |
| FR-F6C | Report relation ablations that remove MST, sector, macro, filing and news relations individually. | M | 4 |
| FR-F6D | Construct each graph snapshot using only nodes, edges and features available by the snapshot timestamp. | M | 4 |
| FR-F6E | Retain a heterogeneous model only when it provides stable, material out-of-sample improvement appropriate to its added complexity. | M | 4 |
| FR-F7 | Keep price-direction models experimental, clearly labelled and outside headline product features. | C | 4 |

#### 8.5.1 Heterogeneous graph schema

Initial node types and representative features are:

| Node type | Examples | Representative point-in-time features |
|---|---|---|
| Stock | NIFTY 200 securities | Returns, volume, volatility, Layer 1 divergence and company attributes |
| Sector | Banking, IT, Energy | Sector return, volatility, breadth and average correlation |
| Macro variable | USD/INR, crude, rates, FII/DII | Level, change, trend, surprise where available and volatility |
| Filing or event | Results, rating action, insider trade | Event type, importance, FinBERT output and text embedding |
| News item | Timestamped headline or article | Sentiment, relevance, source and text embedding |
| Market regime | Calm, trending, stressed | Regime probabilities and defining market features |

Initial directed relation types are:

| Source type | Relation | Target type | Construction |
|---|---|---|---|
| Stock | `mst_connected_to` | Stock | Versioned Layer 2 output for the applicable window |
| Stock | `correlated_with` | Stock | Training-window relationship using documented thresholds |
| Stock | `belongs_to` | Sector | Versioned classification effective at snapshot time |
| Filing or event | `issued_by` | Stock | Exchange metadata or controlled entity linking |
| News item | `mentions` | Stock | Metadata or validated entity linking |
| Macro variable | `affects_sector` | Sector | Documented economic rule or training-only estimated exposure |
| Sector | `contains` | Stock | Reverse of effective membership relation |
| Stock | `exposed_to` | Macro variable | Documented or training-only estimated sensitivity |
| Filing, event or news | `related_to` | Filing, event or news | Time-valid similarity or explicit source relationship |

Relation definitions must remain sparse, economically defensible and versioned. PRISM must not connect every macro variable to every stock merely to create model capacity. Estimated exposures must be fitted inside each training window and must never use future observations.

#### 8.5.2 Heterogeneous modelling progression

Development must proceed in the following order:

1. Relational non-neural aggregation with a linear or gradient-boosted model.
2. Homogeneous stock graph using Layer 2 MST edges.
3. Simple heterogeneous model such as relation-aware GraphSAGE or R-GCN.
4. Heterogeneous Graph Transformer only if simpler models show stable value.
5. Continuous-time temporal graph model only if snapshot models justify the added complexity.

Initial targets are future realised volatility, idiosyncratic-risk change, cluster stress, risk spillover, anomalies and regime transitions. Price direction remains governed by `FR-F7`.

### 8.6 Layer 5 - insight features

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-I1 | Report effective independent exposures, cluster weights and diversification findings using a documented algorithm. | M | 1 |
| FR-I2 | Simulate a user-selected stock shock through graph/correlation relationships and display assumptions and uncertainty. | M | 1 |
| FR-I3 | Present a stock timeline combining prices, filings, sentiment, ownership changes, divergence and peer behaviour. | S | 2 |
| FR-I4 | Produce an explainable early-warning score whose component contributions and weights are visible. | S | 4 |
| FR-I5 | Mark graph-derived conclusions as low confidence when MST stability or data sufficiency is poor. | M | 1 |

### 8.7 Layer 6 - API, dashboard and trust

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-P1 | Accept manual and CSV portfolio input using quantity or weight. | M | 1 |
| FR-P2 | Display portfolio overview, risk metrics, MST, clusters and alerts. | M | 1 |
| FR-P3 | Provide watchlists and alerts with a reason and effective timestamp. | S | 3 |
| FR-P4 | Provide portfolio health summaries and daily or weekly digests. | S | 3 |
| FR-P5 | Keep an audit record of every alert and the data and version used to produce it. | M | 1 |
| FR-P6 | Display out-of-sample validation against baselines, including weak and failed signals. | S | 4 |
| FR-P7 | Show reasons, inputs, thresholds, confidence and limitations for every score and alert. | M | 1 |
| FR-P8 | Display a not-investment-advice disclaimer on all relevant outputs. | M | 1 |
| FR-P9 | Display data freshness and the latest successful pipeline time. | M | 1 |
| FR-P10 | Expose versioned REST endpoints documented through OpenAPI. | M | 1 |

---

## 9. Portfolio calculation policy

The following must be defined before Phase 1 acceptance testing:

- Whether a portfolio is entered using quantities, weights or both.
- Valuation date and price-selection rule.
- Treatment of cash and uninvested weight.
- Weight normalization.
- Missing and stale-price handling.
- Dividend treatment in return calculations.
- Benchmark selection.
- Rebalancing assumptions for historical analysis.
- Annualisation factor and risk-free rate where relevant.

All displayed risk values must state their observation window, frequency, annualisation and benchmark. These policies remain **TBD until the portfolio mathematics specification is approved**.

---

## 10. Explainability and uncertainty contract

Every derived result must provide, as applicable:

```text
subject and effective time
method or model name and version
input data snapshot or references
lookback and forecast horizon
result and units
component contributions
thresholds or decision rule
data-sufficiency status
confidence or uncertainty indicator
known limitations
calculation timestamp
```

Correlation and MST relationships must not be presented as causal relationships. Shock simulation is a scenario estimate, not a prediction of an actual future event.

---

## 11. Validation and evaluation

### 11.1 Time ordering

- Never randomly shuffle financial time series for evaluation.
- Use walk-forward evaluation.
- Use purged cross-validation and an embargo when labels or windows overlap.
- Apply publication and ingestion cutoffs before feature generation.
- Use historical universe membership to prevent survivorship bias.

### 11.2 Required baselines

| Component | Baseline |
|---|---|
| Volatility | Historical volatility, EWMA and GARCH-family model |
| Sentiment | Lexicon or exchange category rules |
| Event classification | Exchange labels and deterministic rules |
| Homogeneous graph model | Same features with a non-graph model |
| Heterogeneous graph model | Tabular model, relational aggregates and homogeneous MST graph |
| Early warning | Individual component signals and simple weighted rule |

Complex challengers are retained only when they demonstrate material out-of-sample value appropriate to their complexity.

### 11.3 Metrics

- Volatility: forecast error against realised volatility and calibration by regime.
- Sentiment/events: per-class precision, recall, F1 and confusion matrix on Indian data.
- Alerts: hit rate, false-alarm rate, lead time and alert frequency.
- Regimes: stability and separation of realised portfolio behaviour.
- Shock simulation: historical scenario calibration and sensitivity to unstable edges.
- Heterogeneous graph: target error, calibration, regime stability, relation ablation and improvement over every required baseline.
- Data pipeline: completeness, timeliness, error rate and unresolved quality flags.

### 11.4 Experiment discipline

- Record all attempted model and material parameter variants.
- Record datasets, features, training windows, parameters and code revision.
- Correct trading-style claims for multiple testing where applicable.
- Do not hide negative results.
- Do not promote a research model to a user-visible feature without an approval record.
- Do not describe learned graph attention weights as causal explanations; support explanations with feature and relation ablation and source evidence.

---

## 12. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Every derived output is traceable to data, method and version. |
| NFR-2 | Identical snapshots, configuration and code versions produce identical outputs. |
| NFR-3 | Layers communicate through documented, versioned interfaces. |
| NFR-4 | The daily NIFTY 200 batch should complete within one hour on the agreed development machine; the target must be measured in Phase 0. |
| NFR-5 | Precomputed dashboard views should respond within a few seconds under expected local use. |
| NFR-6 | Baseline operation uses free or open-source software and legally permitted data. |
| NFR-7 | Data sources are used within their terms and restricted data is not redistributed. |
| NFR-8 | Portfolio data is stored in the configured Supabase project; credentials remain only in backend environment configuration and are never exposed to the frontend. |
| NFR-9 | Unit, integration, data-quality and contract tests run in CI. |
| NFR-10 | Database changes use reviewed Alembic migrations. |
| NFR-11 | Credentials are never committed and sensitive values are redacted from logs. |
| NFR-12 | The codebase uses type checks, linting, formatting and documented setup procedures. |
| NFR-13 | APIs use explicit versioning and backwards-incompatible changes require migration notes. |
| NFR-14 | A stale or failed pipeline is visibly reported; stale data must not appear current. |

---

## 13. Security, privacy and compliance

- Secrets are provided through environment configuration; local `.env` files are ignored by Git.
- Logs must exclude credentials, session tokens and unnecessary portfolio details.
- SQL access must use parameterized ORM or Core queries.
- Uploaded CSV files must be size-limited and validated.
- Source URLs and downloaded documents must be treated as untrusted input.
- Dependencies must be scanned and updated through a controlled process.
- Local portfolio data must have a documented deletion method.
- Public deployment requires authentication, authorization, HTTPS, CSRF protection where applicable, rate limiting and backup procedures.
- This SRS is not a legal determination of data rights; source terms must be reviewed before public or commercial deployment.

---

## 14. Operational behaviour

### 14.1 Pipeline runs

Every scheduled run records:

```text
run_id, workflow, code_version, configuration_hash,
source_versions, started_at, completed_at, status,
row_counts, quality_summary, error_summary
```

### 14.2 Failure rules

- Retry transient source and network failures using bounded backoff.
- Do not replace a last-known-good dataset with an incomplete run.
- Mark affected views as stale when a required run fails.
- Quarantine ambiguous symbols and malformed observations.
- Allow unaffected symbols or layers to complete where consistency permits.
- Record corrections and identify alerts affected by corrected data.
- Provide health endpoints for the API and database dependencies.

### 14.3 Backups

Backup and restore procedures must be tested before any hosted deployment. The local prototype must at minimum support database export and preservation of raw source snapshots and migration history.

---

## 15. Phased implementation plan

| Phase | Goal | Included work | Exit criteria |
|---|---|---|---|
| 0 - Foundations | Reliable NIFTY 200 data and reproducible calculations | Core repository; PostgreSQL; migrations; `yfinance` adapter; security master; versioned membership; data quality; Layer 1/2 design and implementation; validation skeleton | Clean versioned daily store; reproducible runs; approved Layer 1/2 formulas and interfaces; tested divergence and MST outputs; quality report and baseline test utilities work |
| 1 - Portfolio insight | Useful product without advanced ML | Portfolio input; core risk metrics; MST views; diversification; shock simulator; audit; explanations; freshness and disclaimer | User can load a portfolio and receive risk, clustering, diversification and shock results with assumptions and reasons |
| 2 - Text intelligence | Explain company background | NSE/BSE filings; news source; FinBERT; event classification; evidence; dossier | Text is linked, scored and evaluated on labelled Indian examples; dossier merges time-aligned events and prices |
| 3 - Attribution and forecasting | Explain moves and forecast risk | Macro data; attribution; volatility baselines/challengers; regimes; anomalies; alerts; watchlists and digest | Attribution covers eligible stocks; forecasts are compared out of sample; alerts and digests expose reasons |
| 4 - Advanced research | Add ambitious components only if justified | Temporal heterogeneous graph; relational, homogeneous and heterogeneous baselines; relation ablations; early warning; optional fine-tuning and summaries; experimental direction model; validation dashboard | Graph snapshots pass point-in-time audits; advanced components beat all required baselines or are documented as negative results; final demo and documentation are complete |

Phase 1 and Phase 2 may proceed in parallel after Phase 0. Every phase must leave a usable and demonstrable system.

---

## 16. Phase 0 acceptance checklist

Phase 0 is complete only when all applicable statements are true:

- [ ] The NIFTY 200 universe is loaded from a versioned source rather than hard-coded.
- [ ] Security identity uses ISIN with versioned symbol aliases.
- [ ] Daily raw and adjusted price records are stored with ingestion metadata.
- [ ] Corporate actions and adjustment provenance are retained.
- [ ] Quality checks detect duplicates, gaps, invalid OHLC relationships and suspicious moves.
- [ ] Failed or partial ingestion cannot replace the last-known-good dataset.
- [ ] Layer 1 and Layer 2 formulas, windows and missing-data rules are approved.
- [ ] Layer 1 and Layer 2 implementations and interfaces are documented and tested.
- [ ] The covariance and correlation foundation is reproducible from a versioned price snapshot.
- [ ] Valid Layer 2 runs are connected, acyclic and contain `N-1` edges.
- [ ] Re-running the same snapshot and configuration reproduces the same outputs.
- [ ] Walk-forward validation utilities prohibit shuffled evaluation.
- [ ] Database schema changes are reproducible through Alembic.
- [ ] Unit, contract, integration and data-quality tests pass in CI.
- [ ] No credentials or restricted datasets are committed.
- [ ] Setup and recovery instructions have been tested by another team member.

---

## 17. Decision log

| ID | Decision | Status |
|---|---|---|
| D1 | Layer 1 and Layer 2 will be designed and implemented within PRISM; their interfaces become stable only after approval and validation. | Decided |
| D2 | Layer 1 and Layer 2 are deterministic mathematical components; later layers may use statistical learning, ML and AI subject to validation. | Decided |
| D3 | FinBERT is the baseline financial sentiment model. | Decided |
| D4 | PRISM focuses on risk and explanation; price direction is experimental. | Decided |
| D5 | PostgreSQL is the primary structured database. | Decided |
| D6 | Python 3.12 is used for ingestion, analytics, ML and backend services. | Decided |
| D7 | FastAPI and Pydantic provide the application API and validation. | Decided |
| D8 | React, TypeScript and Vite provide the frontend. | Decided |
| D9 | SQLAlchemy, Psycopg and Alembic provide persistence and migrations. | Decided |
| D10 | APScheduler and Tenacity provide native scheduling, retries and backoff for data and model workflows. | Decided |
| D11 | NIFTY 200 is the initial product universe and is versioned by effective date. | Decided |
| D12 | Daily data is the initial frequency. | Decided |
| D13 | `yfinance` supplies prototype OHLCV and actions under the controls in Section 7.2. | Decided |
| D14 | NSE/BSE are verification and official filing/metadata sources, subject to access terms. | Decided |
| D15 | The initial application is local and single-user. | Decided |
| D16 | Advanced dependencies are introduced only in the phase that requires them. | Decided |
| D17 | Phase 4 will evaluate a temporal heterogeneous graph using the approved MST as one versioned relation type. | Decided |
| D18 | Supabase provides the managed PostgreSQL database; FastAPI connects through an SSL-required PostgreSQL connection and React never receives database credentials. | Decided |
| D19 | The official Nifty Indices constituent CSV supplies current NIFTY 200 membership; PRISM archives each imported snapshot and does not claim pre-observation history from it. | Decided |
| D20 | Layer 1 uses the deterministic `sector-divergence-v1` contract in Section 6.2: official Industry groups, leave-one-out median benchmarks, 60-day trailing OLS, at least 45 paired observations, and separate 1/5/20-day standardized residual outputs. | Decided |
| D21 | Layer 2 uses the deterministic `correlation-mst-v1` contract in Section 6.3: 120 adjusted-close log returns, at least 100 paired observations, Pearson correlation, Mantegna distance and deterministic Kruskal/Union-Find tie-breaking. | Decided |

---

## 18. Open questions and required discoveries

| ID | Question or discovery | Blocking phase |
|---|---|---|
| OQ-2 | Which official source and archival method will provide historical NIFTY 200 membership? | 0 |
| OQ-3 | What warning and rejection thresholds govern data-quality checks? | 0 |
| OQ-4 | What are the portfolio weighting, cash, dividend and rebalancing rules? | 1 |
| OQ-5 | What precise algorithm defines independent bets in `FR-I1`? | 1 |
| OQ-6 | What propagation model and calibration define the shock simulator? | 1 |
| OQ-7 | Which approved news source will be used and what are its terms and budget? | 2 |
| OQ-8 | What source supplies point-in-time shares outstanding and market capitalisation? | 2/3 |
| OQ-9 | What formula and calibration define filing importance? | 2 |
| OQ-10 | Which macro and institutional-flow sources meet timeliness and licensing needs? | 3 |
| OQ-11 | What formula and weights define the early-warning score? | 4 |
| OQ-12 | Will LLM summaries be local or hosted, and what privacy/cost controls apply? | 4 |
| OQ-13 | Which macro-to-sector and stock-to-macro relations have sufficient economic justification and point-in-time data? | 4 |
| OQ-14 | Which graph snapshot frequency and prediction horizons provide enough samples without excessive temporal overlap? | 4 |
| OQ-15 | What minimum improvement and stability thresholds must the heterogeneous model meet for retention? | 4 |

---

## 19. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Lookahead or survivorship bias | Misleading validation | Point-in-time cutoffs, versioned membership, walk-forward tests |
| Unofficial or corrected Yahoo data | Incorrect price history | Raw snapshots, quality flags, cross-checks and replaceable source adapter |
| MST instability | Unreliable diversification or propagation | Edge-stability diagnostic, confidence labels and sensitivity analysis |
| Filing/news access failures | Broken dossiers and delayed explanations | Caching, retries, monitoring and source abstraction |
| FinBERT domain mismatch | Weak Indian filing sentiment | Local labelled evaluation, chunking and optional later fine-tuning |
| Dense or unjustified heterogeneous relations | Spurious graph effects and overfitting | Sparse documented relations, training-only exposure estimation and relation ablation |
| Heterogeneous model complexity | Poor generalisation on NIFTY 200 | Relational and homogeneous baselines, staged progression and stopping rule |
| Overfitting and repeated experiments | Inflated claims | Baselines, experiment logging, purging, embargo and multiple-test controls |
| Scope expansion | Incomplete product | Phase gates and dependency introduction by phase |
| Licensing violations | Legal and operational risk | Source registry, terms review and no unauthorized redistribution |
| Public exposure of portfolio data | Privacy loss | Local-first release and mandatory hosted security controls |
| Overclaiming predictions | Loss of credibility | Risk-first language, visible limitations and experimental labels |

---

## 20. Traceability and definition of done

Every implementation task must reference at least one requirement ID. A requirement is complete only when:

1. Its implementation is reviewed.
2. Its automated tests pass.
3. Its inputs, outputs and error states are documented.
4. Its relevant security and data-quality checks pass.
5. Its acceptance evidence is linked from the project tracker.
6. User-facing behaviour includes required explanations and disclaimers.
7. Any model component has an out-of-sample comparison with its baseline.

---

## 21. Glossary

- **Adjusted price:** price transformed for specified corporate actions so returns are comparable.
- **Attribution:** separation of a return into market, sector and company-specific components.
- **Baseline:** simple reference method that a more complex model must outperform.
- **Corporate action:** split, bonus issue, dividend or other issuer event affecting a security.
- **Effective membership:** inclusion of a security in an index during a specific date interval.
- **Embargo:** time buffer removed around evaluation boundaries to reduce leakage.
- **EWMA/GARCH:** established statistical approaches for volatility estimation and forecasting.
- **FinBERT:** BERT-family model trained for financial-language sentiment classification.
- **Heterogeneous graph:** graph containing multiple node types, edge types or both, with relation-specific semantics.
- **HGT:** Heterogeneous Graph Transformer, a model using node-type and relation-specific attention and transformations.
- **Idiosyncratic return:** return component not explained by the selected market and sector factors.
- **ISIN:** durable international identifier for a security.
- **MST:** minimum spanning tree connecting all eligible nodes with minimum total edge distance.
- **Point-in-time:** retaining what was available and when, so historical computations use only knowable information.
- **Purged validation:** evaluation that removes training samples overlapping test-label periods.
- **Regime:** a market state such as calm, trending or stressed.
- **Sector divergence:** a versioned Layer 1 measure of separation from sector behaviour, to be defined and validated in Phase 0.
- **Survivorship bias:** distortion caused by testing only securities that remain present today.
- **Temporal graph:** graph whose nodes, edges or features change over time and are evaluated at explicit timestamps.
- **VaR:** value at risk, an estimate of a loss threshold at a specified confidence and horizon.
- **Expected shortfall:** average loss beyond a specified VaR threshold.

---

## 22. References

1. Mantegna, R. N. (1999). *Hierarchical Structure in Financial Markets.* European Physical Journal B, 11, 193-197.
2. Araci, D. (2019). *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models.* arXiv:1908.10063.
3. Lopez de Prado, M. (2018). *Advances in Financial Machine Learning.* Wiley.
4. Ledoit, O. and Wolf, M. (2003). *Improved estimation of the covariance matrix of stock returns.* Journal of Empirical Finance, 10(5).
5. Sinha, S. and Pan, R. K. (2007). *Uncovering the internal structure of the Indian financial market: cross-correlation behavior in the NSE.*
6. Official NSE and BSE corporate filing and market-information pages.
7. Hu, Z., Dong, Y., Wang, K. and Sun, Y. (2020). *Heterogeneous Graph Transformer.* arXiv:2003.01332.
8. Schlichtkrull, M. et al. (2017). *Modeling Relational Data with Graph Convolutional Networks.* arXiv:1703.06103.
9. Rossi, E. et al. (2020). *Temporal Graph Networks for Deep Learning on Dynamic Graphs.* arXiv:2006.10637.
10. Official `yfinance`, FastAPI, React, Vite, PostgreSQL, APScheduler, PyTorch Geometric and Hugging Face documentation.

---

_End of document. Update the version, date and decision log whenever an approved requirement or decision changes._
