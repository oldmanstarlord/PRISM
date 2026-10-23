# Temporal heterogeneous GNN (analysis experiment)

This is an **offline research pipeline**, separate from the production API. It does not
download data, train automatically, make price forecasts, or place trades. News is on hold.

## What it models

Each weekly snapshot has stock, industry, and market nodes. Stock nodes have trailing
five-day adjusted return, 20-day realized volatility, a 20-day volume change, and
60-day drawdown. Industry and market nodes aggregate the current stock cross-section.
Relations include stock–stock maximum-correlation spanning-tree edges, additional
strong-correlation edges, stock–industry membership, and industry–market membership.
The spatial encoder has two relation-specific GraphSAGE layers. A GRU processes eight
successive snapshots with stock identities aligned across time. Training masks current
stock features and 20% of current MST links, then reconstructs those features and
distinguishes withheld links from sampled non-links. Withheld MST links are removed
from both stock-edge relations. Industry and market aggregates are recomputed without
masked stocks to reduce direct target leakage.

The output is *descriptive* embedding drift. A stock marked above the train-period
95th percentile has changed its learned graph representation unusually much compared
with train-period week-to-week changes. It is **not** a probability of loss or a
validated trading signal. MST structure is based on positive correlation, not a
causal relationship. A high edge-reconstruction score does not establish economic
causality.

## Production gate

The trained graph is not selected merely because reconstruction loss falls. Promotion
requires all of the following:

1. `source_time_filtered_historical_industry` data passes `audit_gnn_dataset`.
2. Drift beats robust feature change, PCA reconstruction, a non-graph temporal score,
   and a relational aggregate by at least 0.02 held-out ROC AUC.
3. Three training seeds have held-out AUC standard deviation no greater than 0.03.
4. MST, correlation, industry, market, stock-only and non-graph relation ablations finish.
5. The selected run is published with its dataset fingerprint, artifact checksum,
   training cutoff, evaluation and limitations.

If any gate fails, the API exposes `research_only`; weekly production inference refuses
to persist against that run.

## Prepare data

Use the existing PostgreSQL database and project environment, then run from the
repository root in PowerShell:

```powershell
uv run python -m jobs.build_gnn_dataset --start 2024-01-01 --end 2026-10-21 --output data/processed/gnn_v1 --research-fixed-universe
```

The explicit `--research-fixed-universe` mode uses membership valid at `--end` and
price revisions known at build time over older dates. It is useful if the database
was populated retrospectively, but has **survivorship and revision look-ahead bias**.
Do not use it for backtest or live-signal claims. Without the flag, membership and
aliases must have been ingested by each graph date, and daily price/volume records
must have existed by their trade date. Industry classifications are stored as current
attributes, not fully versioned history, so even this mode is **not guaranteed fully
point-in-time**. Insufficient history or membership coverage will fail explicitly.

The build needs at least 121 trading days of lookback, at least 20 eligible stocks per
snapshot, and enough weekly snapshots for eight-step sequences plus chronological
train/validation/test splits with a seven-snapshot embargo. Extend the date range or
lower `--min-stocks` only for a clearly labelled exploratory run. The build does not
fetch data from the internet; run the existing ingestion jobs first if the database
lacks prices or universe records.

## Train when ready

```powershell
uv run python -m jobs.train_temporal_gnn --dataset data/processed/gnn_v1 --output data/models/gnn_v1 --epochs 30 --device auto
```

Training writes `best_model.pt` and `report.json` into a **new** output directory;
it never overwrites an existing run. The report includes exact split dates/counts,
training-only normalization statistics, loss history, and one held-out test result.
The test set is never used for early stopping. `--device cpu` forces CPU; `auto`
uses CUDA only if installed and available. Runtime depends on snapshot count, node
count, and hardware. Start with `--epochs 2` on a *new* trial output directory for
a timing check, then choose a full run. A trial is still training.

## Analyze after training

```powershell
uv run python -m jobs.analyze_temporal_gnn --dataset data/processed/gnn_v1 --run data/models/gnn_v1 --output data/processed/gnn_analysis_v1
```

Outputs are `stock_drift.csv`, `market_drift.csv`, and `analysis.json`. Analysis
rejects a dataset whose fingerprint differs from the training dataset. Compare drift
with real events and standard baselines before interpreting it substantively. Since
the GNN is trained to reconstruct the same graph features used to build MST and
correlation edges, its training metrics should not be treated as independent evidence
of predictive power.

The stock output also includes a training-period percentile, alert level, and the
largest observed normalized input or relationship change. This driver is diagnostic;
it is not a causal explanation.

## Audit, evaluate and run ablations

```powershell
uv run python -m jobs.audit_gnn_dataset --dataset data/processed/gnn_v1 --output data/processed/gnn_v1/audit.json
uv run python -m jobs.evaluate_temporal_gnn --dataset data/processed/gnn_v1 --analysis data/processed/gnn_analysis_v2 --output data/processed/gnn_analysis_v2/evaluation.json
uv run python -m jobs.run_gnn_experiments --dataset data/processed/gnn_v1_point_in_time --output data/models/gnn_experiments_v1 --epochs 30 --seeds 42 43 44
```

The experiment runner retrains the full model, every required relation ablation and
one ablation for each stock feature.
Its `experiment_summary.json` can be supplied to the evaluator. Do not substitute
inference-time edge removal for a trained ablation.

## Point-in-time industry history

Apply the Alembic migration and import reviewed effective-dated classifications:

```powershell
uv run alembic upgrade head
uv run python -m jobs.import_industry_history --csv data/raw/security_industry_history.csv
uv run python -m jobs.import_industry_history --csv data/raw/security_industry_history.csv --apply
```

Required CSV columns are `symbol`, `industry`, optional `sector`, `valid_from`,
`valid_to`, `source`, and timezone-aware `known_at`. The first command is a dry run.
`known_at` must be the source observation/publication timestamp, not an invented
backfill timestamp.

## Publish and serve

```powershell
uv run python -m jobs.publish_gnn_analysis --run data/models/gnn_v1_point_in_time --analysis data/processed/gnn_analysis_v1_point_in_time --evaluation data/processed/gnn_analysis_v1_point_in_time/evaluation.json
```

Published output is available through authenticated endpoints:

- `GET /api/v1/gnn/status`
- `POST /api/v1/gnn/portfolio-drift`
- `GET /api/v1/gnn/companies/{symbol}`
- `GET /api/v1/gnn/market-history`

The AI Insights and Company Detail views consume these persisted outputs. They display
research-only and stale states rather than silently treating them as valid signals.

## Weekly inference

Run explicitly with `jobs.run_weekly_gnn`. GNN inference is not scheduled by the API;
its background scheduler retains news and sector refresh. Weekly persistence is
permitted only for a published run whose validation status is `ready`.

```powershell
uv run python -m jobs.run_weekly_gnn --start 2020-01-01 --run data/models/gnn_v1_point_in_time --calibration data/processed/gnn_analysis_v1_point_in_time/analysis.json
```

## Current retrospective result (2026-10-22)

The existing retrospective run remains rejected. On 2,940 held-out stock-weeks its
drift achieved ROC AUC 0.514 for the documented next-snapshot adverse-change target,
below the best simple baseline (non-graph temporal score, ROC AUC 0.579). It also lacks
point-in-time inputs and completed multi-seed ablations. This is a negative result,
not a production model.

## Research display enabled (2026-10-23)

Published the existing `data/models/gnn_v1` checkpoint's
`data/processed/gnn_analysis_v2` outputs with their unchanged research-only evaluation.
The database now contains version `e24fde60d571-2026-10-13`, with 20,282 stock
observations and 107 market snapshots. The latest analysis covers 197 stocks on
2026-10-13. Portfolio, company and market services can serve these observations.
This publication does not promote the model or enable weekly production inference;
the production blockers above still apply. The portfolio panel displays the analysis
date and no longer reports a holdings mismatch when the entire analysis is unavailable.

## Portfolio explanations

The portfolio API also returns transparent supporting evidence:

- Diversification context compares equal-weight mean pairwise daily-return correlations
  over two disjoint 20-session windows ending at the analysis date. Each pair needs
  at least 15 overlapping returns in both windows; only the same eligible pairs enter
  both averages. Coverage, dates and the three largest absolute pair changes are shown.
- Peer comparison uses five-session adjusted returns against the median of at least
  three other stocks in the saved industry's latest snapshot. Named peers are shown;
  broad classifications are not necessarily close business comparables.
- Persistence counts consecutive elevated/high observations across the last eight
  saved snapshot dates. Missing stock observations break a streak. A streak reaching
  eight observations is bounded by that window, not evidence of its true start date.

Price revisions are restricted to the model's saved data cutoff, with trade dates no
later than the analysis date. Missing prices produce unavailable evidence rather
than zero scores. These price-based comparisons are not learned GNN attribution,
causal explanations, statistically significant divergence tests or portfolio risk
estimates. No portfolio weights enter the correlation summary.
