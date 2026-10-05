# Fundamental classification and model operations

The final `Fundamental` label is the contextual financial policy. `Model_Label` is a learned
approximation of that policy, retained separately because the current validation does not support
using it as the authority. `Limited Assessment` means insufficient relevant evidence; it is not
included as a sixth health class in training. Banks/lenders/insurers remain limited until their
specialist asset-quality, capital, liquidity or solvency inputs are collected.

## Current experiment

The improved advisory model adds row-wise financial relationships and selects a compact financial
representation. A paired evaluation on identical splits compares the previous model configuration
against the new training procedure:

| Five-fold CV, two repeats, same 156 stocks | Previous | Improved |
| --- | --- | --- |
| Accuracy | 69.87% | **74.04%** |
| Macro F1 | 52.98% | **55.88%** |
| Balanced accuracy | 50.79% | **53.17%** |
| Strong recall | 35.48% | **50.00%** |
| Weak recall | 0% | 0% |

This is a 4.17 percentage point accuracy improvement: 231/312 validation appearances correct,
versus 218/312 previously. Each stock appears in validation twice; this is 156 unique stocks,
not 312 independent companies. The original 68.75% holdout score below remains the original
experiment's result and is not a directly comparable before/after figure for this new evaluation.
Previously examined data is reused, so these remain cross-validation estimates on the current
snapshot, not new external-test or future-period accuracy.

The new procedure uses five outer folds with two repeats and a fixed seed written to a split manifest
before training. Every outer training fold chooses the feature view, feature-selection setting,
algorithm and parameters using only its own three inner folds. The previous configuration is also
refitted separately inside each identical outer training fold. Stock-wise paired bootstrap results
are recorded in the JSON report; they are descriptive and do not fully remove CV dependence or
prior-development uncertainty. No seeds are searched to obtain a better accuracy.

There are 120 candidate configurations spanning Extra Trees, balanced histogram gradient boosting,
balanced XGBoost, cumulative ordinal classification and soft voting. A further 24 ordered regression
configurations were screened on the original development stocks, with a best selection accuracy of
64.53%. This exploratory screen is recorded separately and is not a new test result or part of the
paired headline evaluation. The selected final model remains
Extra Trees: 220 trees, balanced class weights, unlimited depth, one stock per leaf, `sqrt` features,
the compact financial representation and all its encoded features. The final selection CV score
is a tuning diagnostic; the paired outer CV result is the reported evaluation.

New calculations include cash/debt, profit/equity, profit margins, cash-adjusted leverage,
cash/return interactions, historical positive-profit/cash fractions and parent cash supplements.
They preserve missing values and real zeroes. They do not use scores, actual rule grades or stock
identity. The final `Fundamental` target and five label definitions are unchanged.

Weak recall remains zero in this learned model. Seven heterogeneous Weak examples are insufficient
to support reliable detection of that category. The improved model remains advisory: the contextual
policy continues to publish the final label, including its debt/cash, pledge and loss safeguards.

Artifacts are in `data/models/fundamentals/2026-10-05-improved/`. `improvement_report.json` contains
all candidate parameters, class-level results, fold choices and comparison intervals;
`out_of_fold_predictions.json` contains the two validation predictions for each assessable stock.
The original model and reports are retained. The local `active_model.json` pointer selects the new
advisory model by path and checksum; explicit `--model` arguments can select the old artifact.

Reproduce the improvement:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.improve_fundamentals
```

## Original experiment

The 5 October 2026 snapshot contains 200 stocks. Cleaning leaves 156 assessable stocks and 44 limited.
AUBANK's collected statements ended in 2017 and COLPAL's in 2010: stale earnings, profitability,
return and debt evidence is removed from the cleaned copy. COLPAL's previous Moderate label becomes
Limited Assessment. A malformed trailing CSV row containing only `b` is quarantined. Original source
files are retained unchanged.

Six model families were tested: logistic regression, SVM, random forest, extra trees, histogram
gradient boosting and XGBoost. Each family has eight parameter combinations. The search compares
the 20 requested numeric fields plus sector against a richer 60-input set adding ungraded earnings,
growth, cash, interest-coverage and return observations. It excludes symbol/company identity, the
fundamental score, rule grades, eligibility profile, explanations and other target-derived columns.

An 80/20 stratified split reserves 32 stocks for a single final test. The other 124 stocks select
features/model/parameters through repeated three-fold CV (two repeats). A separate three-fold nested
check on those 124 development stocks repeats both feature-set and parameter selection inside each
outer fold. No test-stock results are used to choose the model.

The best configuration by development CV is Extra Trees with 180 trees, balanced class weights,
unlimited depth, one observation per leaf and `sqrt` features. The model uses the contextual inputs.

| Measure | Result |
| --- | --- |
| Untouched test accuracy | 68.75% (22/32) |
| Test balanced accuracy | 55.56% |
| Test macro F1 | 51.11% |
| Majority-class test accuracy | 43.75% |
| Nested development CV accuracy | 63.71% (79/124) |
| Development selection CV accuracy | 64.12% |
| Test accuracy 95% Wilson interval | 51.43%–82.05% |

These measure agreement with generated policy labels, not SEBI certification, audited investment
quality or future stock returns. There is only one snapshot date, so no future-period accuracy can
be claimed. Minority classes each have seven stocks and test support is very small. No result is
presented as 100% accuracy. More independently reviewed labels and historical snapshots are needed
before promotion of the learned model to primary classification.

## Cleaning and encoding

Missing values remain missing in the cleaned data. True zero holdings/pledge/debt remain zero.
Impossible holding percentages, negative debt ratios, nonpositive P/E and nonfinite observations
are removed rather than converted to healthy zeroes. Ownership changes remain percentage points.
Negative profit, margin, return and cash-flow values are valid and retained.

Freshness checks are custom data controls: annual/cash statements 550 days, balance sheets 400 days,
quarters 220 days and shareholding 200 days. Future reporting periods are excluded. Missing fresh
statements or pledge evidence cannot support a health label. These limits are not regulator rating
thresholds. Dates and source provenance are retained in JSON outside the data-only CSV outputs.

Each CV fold fits its own median imputer with missing indicators, numerical standardizer and sector/
broad-industry one-hot encoder. Unknown future categories are accepted. Target codes are Very Weak
0, Weak 1, Moderate 2, Strong 3 and Very Strong 4. Limited rows bypass the learned classifier.

The saved joblib artifact contains preprocessing, model, feature schema, label mapping, policy
version, source hashes and package version. It is refitted on all 156 assessable stocks after
evaluation. `encoded_training.csv` is an export from that final refit, useful for inspection; it
must not be split again to claim unbiased accuracy. `stock_predictions.csv` is consequently
in-sample. Only `holdout_predictions.csv` contains the original untouched test predictions.
The model probabilities are uncalibrated model outputs, not a probability that a company is strong.

## Commands

Run from the repository directory with the locked Python 3.12 environment:

```sh
uv sync --locked --all-groups
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.train_fundamentals
```

The dated model and JSON reports are under `data/models/fundamentals/2026-10-05/`. Training writes
`csv_tables.json` as the intermediate used for the delivered CSV exports. The trained inference
pipeline is `model.joblib`; the full measured results and candidate parameters are in
`training_report.json`. Train explicitly on a new dated snapshot; daily prediction never silently
re-tunes the model.

Run the live refresh after close:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.refresh_fundamentals --scheduled
```

The scheduled path checks current NSE equity holidays and waits until at least 16:30 IST. It skips
weekends, holidays and already-published dates. A cached calendar is accepted for at most seven days
if the NSE calendar service is temporarily unavailable; an unknown year fails closed. Weekend or
Muhurat special sessions require an explicit manual run after the special session ends. The local
Codex heartbeat runs this command daily at 16:30 in the configured Asia/Calcutta timezone. The host
and app must be available for local execution; this is not a deployed always-on service.

Financial pages and NSE filings are fetched into dated caches. Obsolete consolidated histories
trigger standalone fallback. Previously selected standalone bases are preserved on refresh.
Industrial parents with financing subsidiaries receive refreshed parent cash supplements.
Manually verified VAML overrides are restricted to the historical snapshot date. MCX's previously
verified ownership can be retained at its actual period for up to 200 days when the NSE SHP index
does not contain it. It becomes limited when that evidence is too old; no fresh PDF data is invented.

Facts and rule labels are recomputed, and the frozen model generates a separate comparison label.
Daily refresh does not force a rating change: quarterly/annual evidence often stays unchanged.
The fixed universe is the user's `data/raw/nifty200/2026-09-30.csv`; membership is not silently changed.

A process lock prevents overlapping runs. A complete 200-stock generation is verified before an
atomic `latest.json` pointer update. Failures preserve the last successful generation and record a
failed status. Published JSON/CSV contains no URLs. Raw-source provenance stays in the raw cache.
Model compatibility checks require the training sklearn and policy versions.

Replay historical sources explicitly, retaining their true date:

```sh
uv run python -m jobs.refresh_fundamentals \
  --cached-raw data/raw/fundamentals/2026-10-05/parsed_snapshot.json
```

Read the last complete generation through `GET /api/v1/fundamentals/latest`,
`GET /api/v1/fundamentals/{symbol}` or `GET /api/v1/fundamentals/status`. Data is stored locally in
`data/processed/fundamentals/live/`; existing price pipelines and database tables are unchanged.

## Validation

```sh
uv run python -m pytest tests/fundamentals -q
uv run ruff check backend jobs tests
```

Tests cover missing versus zero, stale/future statements, bank exclusions, unknown pledge, duplicate
symbols, prohibited score/identity leakage, preprocessing on training data only, unseen sectors,
serialized inference, safe publication, concurrent refreshes, IST close times and holiday guards.

Method references: [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html),
[nested CV](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html),
[NSE timings and holidays](https://www.nseindia.com/resources/exchange-communication-holidays).
