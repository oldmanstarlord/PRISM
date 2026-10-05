ARCHIVED: superseded by PRISM_SRS.md v1.6. Do not use as a requirements source.

# PRISM — Software Requirements Specification (SRS)

| Field | Value |
|---|---|
| Project | PRISM — Portfolio Risk & Intelligence System for Markets |
| Document version | 0.1 (draft for team review) |
| Date | 2026-09-28 |
| Status | Planning. Requirements are proposals until marked **Decided** in Section 12 |
| Project lead | Sanjit |
| Team | _TBD — add names and roles in Section 3.4_ |

---

## 0. How to use this document (humans and AI assistants)

This file is the single source of context for the project. If you are an AI assistant reading this on behalf of a team member, treat this section as your briefing.

**One-paragraph summary.** PRISM is a platform that monitors the risk and diversification of a stock portfolio (Indian equities, NSE/BSE) and explains what is happening to each stock in the background. It starts from two existing, working base layers (a sector divergence signal and a minimum-spanning-tree map of how stocks move together) and adds a data pipeline, text understanding of company filings and news (FinBERT), risk forecasting, and a set of insight features (diversification check, shock simulator, stock dossier, early-warning score), all shown in a dashboard with a strict validation framework.

**Rules for AI assistants working on this project:**

1. **Layer 1 and Layer 2 are frozen.** Do not propose modifying their logic or outputs. New code consumes their outputs as fixed inputs. Any diagnostics about them (for example stability checks) must live outside them.
2. **Do not frame PRISM as a system that reliably predicts stock prices.** The primary predictive targets are risk, volatility, regimes and explanations. Price-direction prediction is experimental and must be labelled as such (see FR-F7).
3. **No lookahead.** Any feature, label or backtest must use only information available at the time (see Section 6.3 and Section 8).
4. **Every alert must be explainable.** Outputs need a reason and the inputs behind them (FR-P7).
5. **Use requirement IDs** (for example `FR-T1`, `NFR-3`) when discussing or generating work, so the team stays aligned.
6. **Mark assumptions.** If something is not stated here, say it is an assumption rather than inventing details of the existing base layers.
7. **This is not investment advice.** Any user-facing output must carry that disclaimer.

**Layer map at a glance:**

| Layer | Name | Status |
|---|---|---|
| Layer 0 | Data ingestion and storage | New |
| Layer 1 | Sector divergence signal | **Existing, frozen** |
| Layer 2 | Correlation graph (minimum spanning tree) | **Existing, frozen** |
| Layer 3 | Text intelligence (FinBERT) | New |
| Layer 4 | Attribution and forecasting | New |
| Layer 5 | Insight features | New |
| Layer 6 | Presentation, tracking and trust | New |
| Cross-cutting | Validation framework | New |

---

## 1. Introduction

### 1.1 Purpose
This document specifies what the extended PRISM system must do, how the work is divided into layers, and in what order it will be built. It is written so that teammates and their AI tools share the same understanding of scope and constraints.

### 1.2 Product vision
Give an investor or analyst one place that answers, for any stock or portfolio:

- How risky is this portfolio, and is it really diversified?
- What is moving this stock today: the market, its sector, or something specific to the company?
- What is happening in the background (filings, results, insider activity, news) and does it matter?
- What could go wrong next, and how would a shock to one stock spread to the others?

The system does this by combining statistics, graph structure, text understanding and machine learning, and by tracking everything over time so that claims can be checked.

### 1.3 Scope
**In scope:** Indian listed equities (NSE/BSE), portfolio-level and stock-level risk monitoring, filing and news understanding, risk and volatility forecasting, explanation and alerting, a web dashboard, and a validation framework.

**Out of scope (see Section 11):** order execution or trading, guaranteed price predictions, personalised investment advice, social media scraping (deferred), derivatives pricing.

### 1.4 Definitions
See the glossary in Section 13.

---

## 2. Existing system baseline (frozen)

PRISM began as a portfolio risk and diversification monitoring platform. It is built from two layers that stay exactly as they are.

### 2.1 Foundation: variance-covariance matrix
The system computes a variance-covariance matrix of asset returns for a portfolio. Both base layers build on this.

### 2.2 Layer 1: Sector divergence signal
A signal that flags when a stock's behaviour diverges from the behaviour of its sector.

### 2.3 Layer 2: Minimum spanning tree (MST)
A graph in which stocks are nodes and edges are derived from how strongly stocks move together. The minimum spanning tree is built with Kruskal's algorithm using a Union-Find structure. It reveals clusters and hub stocks. The idea comes from the econophysics literature (Mantegna, 1999).

### 2.4 Interface contract for the frozen layers
> **TODO (layer owner):** document the exact inputs and outputs of Layer 1 and Layer 2 from the existing code (function names, data shapes, time window used). New layers depend on these contracts.

Assumed minimum contract, to be confirmed:

- Layer 1 outputs, per stock and per date, a divergence value relative to its sector.
- Layer 2 outputs, per date or window, a list of edges (stock A, stock B, distance) forming the tree, from which clusters and node connectivity can be derived.

---

## 3. Overall description

### 3.1 Users
| User | Need |
|---|---|
| Retail investor / student investor | Understand real portfolio risk and why holdings move |
| Analyst | Fast background dossier on a stock; early warnings |
| Project team and evaluators | Transparent, reproducible, validated system |

### 3.2 Operating environment (proposed, not decided)
- Language: Python for data and ML work.
- Text model: FinBERT (`ProsusAI/finbert` on Hugging Face) via the `transformers` library.
- Storage: files (Parquet) and SQLite to start; a server database later if needed.
- Dashboard: a web app (Streamlit for speed, or a JavaScript front end if the team prefers).
- Compute: laptops and free-tier notebooks; no paid GPU required for the baseline plan.

### 3.3 Constraints
1. Layer 1 and Layer 2 logic is unchanged.
2. Prefer free and open-source tools and data.
3. Respect the terms of use of every data source (see Section 6.1).
4. Student-team bandwidth: scope must be deliverable in stages, each stage usable on its own.

### 3.4 Team and ownership
| Area | Owner | Notes |
|---|---|---|
| Overall design, Layers 1-2 integration | Sanjit | |
| Layer 0 data pipeline | _TBD_ | |
| Layer 3 text intelligence | _TBD_ | |
| Layer 4 attribution and forecasting | _TBD_ | |
| Layers 5-6 features and dashboard | _TBD_ | |
| Validation framework | _TBD_ | Should start in Phase 0 |

### 3.5 Assumptions
- Daily data is enough for the first release; intraday is optional.
- The initial universe is a manageable index-sized set (see open question OQ-1).
- Filings and announcements can be obtained from official exchange pages within their terms.

---

## 4. System architecture

```
 Sources: prices | NSE/BSE filings | macro series | news
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Layer 0: Data ingestion      │  point-in-time store
        └──────────────────────────────┘
              │                    │
              ▼                    ▼
   ┌────────────────────┐  ┌────────────────────┐
   │ Layer 1 (frozen)   │  │ Layer 2 (frozen)   │
   │ Sector divergence  │  │ Correlation MST    │
   └────────────────────┘  └────────────────────┘
              │                    │            ┌──────────────────────┐
              │                    │            │ Layer 3: Text        │
              │                    │            │ intelligence         │
              │                    │            │ (FinBERT, events)    │
              │                    │            └──────────────────────┘
              ▼                    ▼                       │
        ┌───────────────────────────────────────────────────┐
        │ Layer 4: Attribution and forecasting              │
        │ return attribution, volatility, regime, anomaly,  │
        │ graph model                                       │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │ Layer 5: Insight features                         │
        │ diversification check, shock simulator, dossier,  │
        │ early-warning score                               │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │ Layer 6: Dashboard, watchlists, alerts, digests,  │
        │ audit log, validation dashboard                   │
        └───────────────────────────────────────────────────┘

 Cross-cutting: validation framework (time-ordered splits, baselines, logging)
```

**Design principles**

- **Modular:** each layer has a defined input and output, and can be built and tested on its own.
- **Explainable:** every derived output stores the reason and inputs.
- **Point-in-time:** stored data records when something happened and when the system learned it.
- **Baselines first:** every ML component must beat a simple baseline in validation to be kept.

---

## 5. Functional requirements

Priority: **M** = Must, **S** = Should, **C** = Could. Phase refers to Section 9.

### 5.1 Layer 0 — Data ingestion and storage
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-D1 | Ingest daily prices (open, high, low, close, volume), adjusted for splits and bonus issues, for the chosen universe. | M | 0 |
| FR-D2 | Maintain market capitalisation and volume series per stock. | M | 0 |
| FR-D3 | Ingest corporate filings and announcements from NSE/BSE: announcements, financial results, board meetings, insider trading disclosures, shareholding patterns, corporate actions, event calendar. | M | 2 |
| FR-D4 | Ingest market-wide series: index levels, USD/INR, crude oil, interest rates, institutional flows (FII/DII). | S | 3 |
| FR-D5 | Ingest news headlines with timestamps and source. | S | 2 |
| FR-D6 | Store every record with event time and ingestion time; never overwrite history (point-in-time storage). | M | 0 |
| FR-D7 | Maintain a symbol master: symbol, ISIN, sector, industry, listing exchange. | M | 0 |
| FR-D8 | Scheduled runs with retries and data-quality checks (missing days, outliers, corporate-action adjustments). | M | 0 |

**Acceptance (example, FR-D1):** for any symbol in the universe, the system returns a continuous adjusted price history with no unexplained gaps, and a data-quality report lists any exceptions.

### 5.2 Layer 1 — Sector divergence signal (existing, frozen)
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-L1 | Provide the divergence of each stock from its sector, per date, exactly as the existing implementation does. | M | 0 (integrate) |

### 5.3 Layer 2 — Correlation MST (existing, frozen)
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-L2 | Provide the MST over the universe or a portfolio, per date or window, exactly as the existing implementation does. | M | 0 (integrate) |
| FR-L2d | **Diagnostic outside the layer:** compute a stability measure of the tree across consecutive windows (for example, fraction of edges that persist) and expose it to Layers 5-6. Does not change Layer 2. | S | 1 |

### 5.4 Layer 3 — Text intelligence
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-T1 | Score the sentiment of each filing and headline as positive, negative or neutral with class probabilities, using FinBERT. | M | 2 |
| FR-T2 | Split texts longer than the model limit (about 512 tokens) into chunks and aggregate chunk scores into one document score. | M | 2 |
| FR-T3 | Classify each item into an event type: results, dividend, board or management change, debt or credit rating, promoter or insider transaction, merger or acquisition, regulatory action, other. Start with rules based on the exchange's own category labels, then add a learned classifier. | M | 2 |
| FR-T4 | Compute an importance score per item (event type, size of change, company relevance). | S | 2 |
| FR-T5 | Link each item to its company using exchange metadata (symbol, ISIN); fall back to name matching only when metadata is missing. | M | 2 |
| FR-T6 | Store the sentence or passage that drove the score, for explanation. | S | 2 |
| FR-T7 | Fine-tune the sentiment model on labelled Indian filings to handle local phrasing. | C | 4 |
| FR-T8 | Generate short plain-English summaries of high-importance filings with a language model. | C | 4 |

### 5.5 Layer 4 — Attribution and forecasting
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-F1 | **Return attribution:** split each stock's daily return into a market component, a sector component and a company-specific (idiosyncratic) component. | M | 3 |
| FR-F2 | Link large company-specific moves to Layer 3 events in a defined time window, and rank likely causes. | S | 3 |
| FR-F3 | **Volatility forecast** per stock and for the portfolio. Baselines: EWMA and GARCH-type models. ML challenger: gradient-boosted trees or a sequence model using price, Layer 1, Layer 3 and macro features. Keep the ML model only if it beats the baseline out of sample. | M | 3 |
| FR-F4 | **Regime detector:** label market state (for example calm, trending, stressed) from market volatility and average correlation; report portfolio behaviour by regime. | S | 3 |
| FR-F5 | **Anomaly detection:** unusual volume, price gaps, and decoupling of a stock from its Layer 2 cluster. | S | 3 |
| FR-F6 | **Graph model:** a graph neural network using the Layer 2 tree (and optionally sector links) as its structure to forecast risk spillover between connected stocks. Kept only if it beats non-graph baselines. | C | 4 |
| FR-F7 | Price-direction models are **experimental only**, clearly labelled, and excluded from headline features. | C | 4 |

### 5.6 Layer 5 — Insight features
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-I1 | **Diversification check:** using Layer 2 clusters, report how many independent bets the portfolio really contains, weight concentrated in each cluster, and plain-language findings (for example, "7 of 10 holdings sit in one cluster"). Suggest low-connection candidates from the universe that would add diversification. | M | 1 |
| FR-I2 | **Shock simulator:** the user selects a stock and a price shock; the system propagates the shock through the graph and correlations, estimates the impact on each holding and the portfolio, and lists the most affected holdings. Assumptions of the propagation method must be shown. | M | 1 |
| FR-I3 | **Stock dossier:** for any stock, a timeline that merges price moves, filings, sentiment shifts, insider and shareholding changes, divergence signals and peer behaviour, with a plain-English summary. | S | 2 |
| FR-I4 | **Early-warning score:** one explainable per-holding flag combining Layer 1 divergence, sentiment turn, insider or promoter activity and rising volatility, with each component's contribution visible. | S | 4 |

### 5.7 Layer 6 — Presentation, tracking and trust
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-P1 | Portfolio input by manual entry and CSV upload (symbol, quantity or weight). | M | 1 |
| FR-P2 | Dashboard with portfolio overview, MST visualisation, cluster view and alerts. | M | 1 |
| FR-P3 | Watchlists and alerts, each with the reason it fired. | S | 3 |
| FR-P4 | Portfolio health score and daily or weekly digest. | S | 3 |
| FR-P5 | Audit log of every alert and the data used to produce it. | M | 1 |
| FR-P6 | Validation dashboard showing historical performance of each signal and model against baselines, out of sample. | S | 4 |
| FR-P7 | Every alert and score displays its reason, inputs and thresholds. | M | 1 |
| FR-P8 | Display a "not investment advice" disclaimer on all outputs. | M | 1 |

---

## 6. Data requirements

### 6.1 Sources (candidates, subject to terms of use)
| Data | Candidate source | Notes |
|---|---|---|
| Prices, volume | yfinance (unofficial wrapper around Yahoo Finance) or an exchange-licensed feed | Prices may be delayed; verify accuracy of adjustments; verify terms |
| Filings and announcements | NSE and BSE corporate filings pages (announcements, results, insider trading, shareholding patterns, board meetings, event calendar) | Official source; automated access must respect the sites' terms and rate limits; paid third-party scrapers exist but are not the default |
| Market cap | Derived from price and shares outstanding (source of shares data to be chosen) | |
| Macro and flows | RBI, exchange and index provider publications | Sources to be selected |
| News | Free news feeds or APIs | To be selected; keep timestamps |

### 6.2 Core entities (logical data model)
- `symbol` (symbol, isin, exchange, sector, industry)
- `price_daily` (symbol, date, open, high, low, close, adj_close, volume, ingested_at)
- `filing` (id, symbol, published_at, ingested_at, category, headline, body_ref, source_url)
- `news_item` (id, symbol_or_null, published_at, ingested_at, source, headline, url)
- `text_score` (item_id, model_version, sentiment, p_pos, p_neg, p_neu, event_type, importance, evidence_span)
- `signal_l1` (symbol, date, divergence)
- `mst_edge` (window_end, symbol_a, symbol_b, distance)
- `attribution` (symbol, date, market_part, sector_part, idio_part)
- `forecast` (symbol_or_portfolio, made_at, horizon, target, value, model_version)
- `alert` (id, created_at, subject, type, reason, inputs_ref, score)
- `portfolio` and `holding` (user-owned; stored locally)

### 6.3 Point-in-time rule
A record is usable in a computation for date *t* only if its `ingested_at` (or true publication time) is not later than *t*. Filings published after market close affect the next trading day. Violating this makes results look better than they are.

---

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Explainability:** every score, alert and forecast is traceable to inputs and a stated method. |
| NFR-2 | **Reproducibility:** given the same data snapshot and model version, results are identical; model versions and parameters are logged. |
| NFR-3 | **Modularity:** layers communicate only through documented interfaces so they can be built and tested independently. |
| NFR-4 | **Performance (targets, to be tuned):** the daily batch for the chosen universe completes within one hour on a laptop-class machine; dashboard views over precomputed data respond within a few seconds. |
| NFR-5 | **Cost:** the baseline system runs on free or open-source software and data. |
| NFR-6 | **Compliance:** each data source is used within its terms; no redistribution of restricted data. |
| NFR-7 | **Privacy:** portfolio data stays on the user's machine or account; no credentials are stored in the repository. |
| NFR-8 | **Testing:** unit tests for each layer's interface; data-quality checks run on every ingestion. |
| NFR-9 | **Maintainability:** clear repository structure, documented setup, and a changelog. |

---

## 8. Validation and evaluation framework

Built in Phase 0 and used by every later phase.

1. **Time-ordered evaluation only.** Never shuffle time series. Use walk-forward splits, and for models with overlapping labels use purged cross-validation with an embargo period so that information does not leak between training and test data.
2. **Baselines are mandatory.** Volatility: EWMA and GARCH-type models. Sentiment: simple lexicon or exchange category rules. Graph model: the same model without the graph. A component is kept only if it beats its baseline out of sample.
3. **Metrics by task.**
   - Volatility forecasts: forecast error against realised volatility.
   - Sentiment and event classification: accuracy and per-class precision and recall on a labelled Indian-filings sample.
   - Alerts and early warnings: hit rate, false alarm rate and lead time.
   - Regime detector: stability and usefulness (does portfolio risk differ by regime).
4. **Multiple-testing discipline.** Log how many model or parameter variants were tried. If any trading-style performance metric is reported, adjust for the number of trials (for example with a deflated Sharpe ratio). A strong result from the best of many attempts is not evidence by itself.
5. **Report failures.** The validation dashboard (FR-P6) shows weak signals honestly.

---

## 9. Phased plan

| Phase | Goal | Layers and features | Exit criteria |
|---|---|---|---|
| **0. Foundations** | Reliable data and a safe way to measure | Layer 0 (FR-D1, D2, D6, D7, D8); integrate frozen Layers 1-2 (FR-L1, FR-L2, interface contracts in 2.4); validation framework skeleton; repository and setup | Clean point-in-time price store for the universe; Layers 1-2 run on it; documented interfaces; validation utilities and baselines in place |
| **1. Portfolio insight from the base layers** | Deliver value without ML | FR-P1, P2, P5, P7, P8; FR-I1 diversification check; FR-I2 shock simulator; FR-L2d stability diagnostic | A user can upload a portfolio and see clusters, a diversification verdict and a shock simulation, each with reasons |
| **2. Text intelligence** | Understand what is happening in the companies | FR-D3, D5; Layer 3 (FR-T1 to T6); FR-I3 stock dossier | Filings and news are ingested, scored and linked; dossier shows a merged timeline; sentiment and event classification evaluated on a labelled sample |
| **3. Attribution and risk forecasting** | Explain moves and forecast risk | FR-D4; FR-F1 to F5; FR-P3, P4 | Return attribution for every stock; volatility model compared against baselines; alerts, watchlists and digests working |
| **4. Advanced ML and polish** | Add the ambitious parts only if justified | FR-F6 graph model; FR-F7 experimental direction models; FR-I4 early-warning score; FR-T7, T8; FR-P6 validation dashboard | Advanced components either beat baselines and are kept, or are documented as negative results; final documentation and demo |

**Dependencies:** Phase 1 needs Phase 0. Phase 2 needs Phase 0. Phase 3 needs Phases 0 and 2. Phase 4 needs Phase 3. Phases 1 and 2 can run in parallel if the team is split.

**Stopping rule:** each phase ends in a usable system. If time runs short, stop after any phase; Phases 0 to 2 already form a complete, defensible product.

---

## 10. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Data leakage or overfitting inflates results | Misleading claims | Section 8 framework from Phase 0; purged validation; baselines; log all experiments |
| MST is unstable because correlations from limited history are noisy | Shock simulator, diversification check and graph model become unreliable | Frozen layers stay as is; use FR-L2d stability diagnostic; show users a confidence note; if needed, propose an optional add-on outside the layers |
| News and filings are priced in quickly | Sentiment signals arrive late | Position text signals as background and explanation, not as trading signals |
| Data access is brittle (site changes, blocking, delays) | Pipeline breaks | Official sources first, caching, retries, monitoring, alternative sources |
| FinBERT mismatch with Indian phrasing and long legal filings | Weak sentiment scores | Chunking, evaluation on a local labelled sample, fine-tuning later (FR-T7) |
| Scope creep | Nothing finished | Phase gates and stopping rule in Section 9 |
| Licensing and terms of data sources | Legal or access problems | Review terms before ingestion; do not redistribute restricted data |
| Overclaiming prediction ability | Loss of credibility | Focus on risk, explanation and validated results; label experiments |

---

## 11. Out of scope

- Order execution, brokerage integration, or automated trading.
- Guarantees or marketing claims about predicting price direction.
- Personalised investment advice.
- Social media scraping (deferred: noisy and costly relative to its value).
- Derivatives and options analytics.
- Non-Indian markets (possible later extension).

---

## 12. Decisions log and open questions

### 12.1 Decided
| # | Decision |
|---|---|
| D1 | Layer 1 and Layer 2 remain unchanged. New features build on top of them. |
| D2 | Machine learning and AI are allowed and encouraged in new layers. |
| D3 | FinBERT is included for filing and news sentiment scoring. |
| D4 | The extended feature list in Section 5 is adopted as the plan. |

### 12.2 Open questions
| # | Question | Notes |
|---|---|---|
| OQ-1 | Which stock universe to start with? | Proposal: begin with a large-cap index, then expand |
| OQ-2 | Final technology stack and hosting? | Section 3.2 is a proposal only |
| OQ-3 | Team roles and ownership (Section 3.4)? | |
| OQ-4 | Exact interface contracts of Layers 1-2? | Owner to document (Section 2.4) |
| OQ-5 | News source and budget for data? | |
| OQ-6 | Use of a large language model for summaries (FR-T8), and at what cost? | |
| OQ-7 | Intraday data needed, or daily only? | |
| OQ-8 | Definition of "importance" and "early-warning" weights? | Set after Phase 2 evaluation |

---

## 13. Glossary

- **Adjusted price:** price corrected for splits, bonus issues and dividends so returns are comparable over time.
- **Anomaly detection:** finding observations that deviate from normal patterns.
- **Attribution (return):** splitting a return into parts explained by the market, the sector and the company itself.
- **Baseline:** a simple reference method a complex model must beat.
- **Beta:** how strongly a stock's returns move with the market.
- **Cluster:** group of stocks that move together closely.
- **Correlation:** measure of how similar two return series are.
- **Embargo:** buffer of data dropped after a test period to prevent leakage.
- **EWMA / GARCH:** classic statistical models for forecasting volatility.
- **FII / DII:** foreign and domestic institutional investors.
- **FinBERT:** a language model (BERT further trained on financial text) that classifies text as positive, negative or neutral. Free and open source.
- **Graph neural network (GNN):** a neural network that learns from data arranged as nodes and edges.
- **Idiosyncratic return:** the part of a return specific to the company.
- **ISIN:** international identifier for a security.
- **Kruskal's algorithm / Union-Find:** the algorithm and data structure used to build the minimum spanning tree.
- **Market capitalisation:** share price multiplied by shares outstanding.
- **Minimum spanning tree (MST):** the set of edges that connects all nodes with the smallest total distance; used here to map the strongest links between stocks.
- **Point-in-time:** storing data with the time it became known so past computations only use what was knowable.
- **Purged cross-validation:** validation method that removes training data overlapping test data in time.
- **Regime:** a market state such as calm or stressed.
- **Sector divergence:** difference between a stock's behaviour and its sector's.
- **Variance-covariance matrix:** table of how the variances and co-movements of asset returns are related.
- **Volatility:** size of price fluctuations, a standard measure of risk.

---

## 14. References

1. Mantegna, R. N. (1999). *Hierarchical Structure in Financial Markets.* European Physical Journal B, 11, 193-197 (arXiv: cond-mat/9802256).
2. Araci, D. (2019). *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models* (arXiv: 1908.10063). Model: `ProsusAI/finbert`.
3. *Stock Market Prediction via Deep Learning Techniques: A Survey* (arXiv: 2212.12717).
4. Feng et al. (2019). *Temporal Relational Ranking for Stock Prediction.* ACM TOIS.
5. Kim et al. (2019). *HATS: A Hierarchical Graph Attention Network for Stock Movement Prediction* (arXiv: 1908.07999).
6. Chen and Robert (2021). *Graph-Based Learning for Stock Movement Prediction with Textual and Relational Data* (arXiv: 2107.10941).
7. Ledoit, O. and Wolf, M. (2003). *Improved estimation of the covariance matrix of stock returns.* Journal of Empirical Finance, 10(5).
8. Potters, Bouchaud and Laloux (2005). *Financial Applications of Random Matrix Theory* (arXiv: physics/0507111).
9. López de Prado, M. (2018). *Advances in Financial Machine Learning.* Wiley.
10. Sinha, S. and Pan, R. K. (2007). *Uncovering the internal structure of the Indian financial market: cross-correlation behavior in the NSE.*
11. NSE and BSE corporate filings pages (announcements, results, insider trading, shareholding patterns, event calendar).

---

_End of document. Update the version and date when requirements change, and record any change in Section 12._
