# PRISM architecture

```text
Replaceable source adapters
  prices/actions | filings | news | macro | governance
          |
          v
Point-in-time PostgreSQL storage
  raw/versioned inputs -> quality/cross-check -> data_freshness
          |
          v
Approved deterministic layers
  Layer 1 sector-divergence-v1 -> Layer 2 correlation-mst-v1
          |
          v
Registered risk components + six-factor confidence
          |
          +--> stock score_run/result envelopes
          +--> portfolio risk/diversification/shock scenarios
          +--> validation runs/baselines/ablations
          |
          v
Operations
  APScheduler -> config-ordered DAG -> pipeline_run manifests
  filing/news poll -> affected-stock incremental child score_run
  freshness/risk/event/regime/MST rules -> deduplicated alert
          |
          v
FastAPI -> generic React views
  portfolio | stocks | MST | macro | validation | data health
  alerts | watchlists | limitations
```

Every derived path uses a configuration checksum and point-in-time cutoff. Existing
rows are not overwritten. Failed DAG steps keep their own failed manifest and do not
replace last-known-good outputs or stop independent later steps.

Key operational tables are `pipeline_run`, `data_freshness`, `alert`, `watchlist`,
and `watchlist_item`. Incremental `score_run` rows carry `parent_run_id` and
`run_kind=incremental`; components are ranked against the full eligible peer set but
only the affected stock is persisted in the child run.
