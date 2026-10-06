# Fundamental score regression and model operations

The active model predicts `Fundamental_Score` as a continuous 0–100 value. Its rounded predicted
score determines the published `Fundamental` label. `Rule_Fundamental_Score` and `Rule_Fundamental`
retain the contextual financial assessment for comparison; `Rule_Reason` explains that assessment.
`Limited Assessment` means insufficient relevant evidence. Those stocks have blank scores and
bypass regression. Banks/lenders/insurers remain limited until specialist asset-quality, capital,
liquidity or solvency inputs are collected. The historical source CSV remains unchanged.

## Historical Yahoo/NSE regression experiment

The historical experiment is separate from the active Screener-based production model. Yahoo
prices and statement tables were retrieved for the exact 200-symbol input universe, using `.NS`
tickers. The raw cache is `data/raw/fundamentals/history-yahoo-2026-10-06/`. Price history starts
in January 2021; annual/quarterly statement coverage varies by issuer. Yahoo returned no quarterly
cash-flow statements for 188 issuers. Annual cash statements supply the cash-flow checks.

Yahoo does not provide the required historical Indian ownership categories. There are 2,772
dated NSE ownership filings in the supplemental cache. Actual broadcast/submission dates gate
ownership availability, including revisions. Legacy combined pledged/encumbered shares establish
zero pledges only when their combined count is zero; positive combined counts cannot establish
the exact pledge amount. Missing values remain missing. Current ownership, scores and labels are
never copied backward into historical price rows.

The reconstructed panel contains 3,000 rows: all 200 symbols at 15 quarterly snapshots from
March 2023 through September 2026. There are 1,794 assessable changed fundamental states:
1,639 earlier-period training/development rows and 155 September 2026 holdout stocks. All 200
latest rows remain in the panel; 45 bypass regression as Limited Assessment. Assessable stocks
can differ from the earlier single-source snapshot because vendor coverage differs. Price-only
repeats do not become additional fundamental training examples. The target is the independently
recomputed numeric `Fundamental_Score`, under the existing contextual policy and fixed bands.

These are delayed historical reconstructions from current data vintages. Annual statements are
admitted 90 days after their period end; quarterly statements after 60 days. Yahoo does not
provide original filing/release dates or original vintages for these tables, so actual release
dates can differ and later restatements can affect the reconstruction. Older cached Screener
periods supplement Yahoo only before the first usable Yahoo period of that section and only on
the consolidated basis. The current Nifty 200 membership introduces survivorship bias.
Reported fiscal-period durations override API frequency defaults: ENRIN's eight-month year and
TMCV's ten-month year cannot support full-year growth comparisons. The duration-audited panel is
`data/processed/fundamentals/history-yahoo-2026-10-06-duration-verified/historical_panel.json`.
The experiment measures imitation of fundamental assessment rules, not future stock returns or a
certified point-in-time investment backtest. It does not establish accuracy on unseen companies.

Yahoo ratios use total debt including leases / stockholders equity for D/E, operating EBIT /
(total assets minus current liabilities) for ROCE, and operating income plus depreciation /
revenue for OPM. Historical market cap uses available dated filed shares, adjusted for splits;
intervening share issues/buybacks can make it approximate. Yahoo and Screener ratios differ, so
this artifact is not automatically substituted for the production model.

The finite grid tests every declared combination, with both compact and rich financial feature
views. It has 1,124 scalar regression configurations. Mean/median tree candidates share identical
fitted trees when possible; all candidate predictions are still measured separately.

| Family | Configurations across both views | Exhaustive tuning values |
| --- | --- | --- |
| Extra Trees | 256 | Trees 220/400; features 0.6/1.0; depth None/12; leaf 1/3; split 2/8; bootstrap false/true; mean/median |
| Random forest | 256 | Same grid as Extra Trees |
| Histogram gradient boosting | 96 | Iterations 180/350; leaves 7/15/31; leaf samples 3/8; learning rate 0.04/0.1; L2 1/5 |
| XGBoost | 384 | Trees 180/350; depth 2/3/5; learning rate 0.03/0.1; lambda 1/5; row/column sampling 0.8/1.0; child weight 1/3 |
| CatBoost | 96 | Depth 3/5/7; iterations 350/600; learning rate 0.04/0.1; loss RMSE/MAE; L2 1/5 |
| Ridge | 12 | Alpha 0.01/0.1/1/10/100/1000 |
| SVR | 24 | C 10/100/1000; epsilon 0.1/1; gamma scale/0.01 |

Each configuration is checked on four forward folds: September 2025, December 2025, March 2026
and June 2026, trained exclusively on earlier snapshots. Imputation, missing indicators, signed
log scaling, standardization and industry/sector one-hot encoding are fitted within each training
fold. Identity columns, score/label fields, rule components and future returns are excluded from
inputs. Regressors fit continuous untransformed scores; there are no classifier targets.

The best validation configuration per family supplies seven sets of forward-validation predictions.
Blend selection tests all 8,008 nonnegative 0.1-step weight vectors summing to one, plus mean and
median for all 127 nonempty subsets: 8,262 blend evaluations, including overlapping definitions.
Category accuracy selects the model/weights; score MAE breaks ties. All choices are locked before
the September 2026 holdout is predicted. The old 220-tree median configuration is retrained on
the same historical cohort for a comparable baseline. Carrying forward the prior quarter's score
is also reported. The previous snapshot's 74.04% nested-CV result uses a different protocol and
is not a direct historical-holdout baseline.

The evaluated pre-holdout model and final all-history refit are saved separately. Only the former
provides held-out performance. The latter includes September training targets and its fitted
predictions must not be described as test accuracy. Search definitions, weights, per-candidate
validation predictions, holdout predictions, metrics and complete selected parameters are saved
under `data/models/fundamentals/2026-10-06-historical-blend/`.

Reproduce the data from the cache and run into a new output directory:

```sh
uv run python -m jobs.acquire_fundamental_history
uv run python -m jobs.build_historical_fundamentals
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.train_historical_fundamentals \
  --output data/models/fundamentals/2026-10-06-historical-blend-rerun --workers 8
```

The grid is exhaustive within its declared finite ranges; every possible real-valued setting
cannot be enumerated. Training can resume an unfinished output only when its panel hash, fixed
candidate definitions and temporal plan match. A completed artifact is never overwritten.

### Completed historical experiment results

The locked historical selection achieved **93.55% (145/155)**
derived-category accuracy on the September 2026 holdout, **1.2972** score MAE,
**5.0679** RMSE and **0.9005** R². The previous configuration retrained on
the identical historical cohort achieved **93.55%** category accuracy
and **1.3010** MAE. Selected members are
ExtraTrees (0.3333333333333333), RandomForest (0.3333333333333333), SVR (0.3333333333333333) with
`median` aggregation. All 1,124 configurations and 8,262 blend evaluations
completed. Full metrics, settings, evidence and limitations are in
`data/models/fundamentals/2026-10-06-historical-blend/RESULTS.md`.
The production model remains separate because financial source formulas differ.

## Current improved score regression

The active model remains a genuine scalar regressor targeting `Fundamental_Score`. The original
score labels and thresholds are unchanged. The earlier search minimized point error alone; 55
training stocks have an observed score of 74, so averaging nearby tree predictions frequently
crossed the Strong threshold at 75. The improved search selects by derived-category accuracy
inside training CV, breaking exact ties by lower score MAE. All fits still receive numeric scores,
including their fractional parts, rather than encoded labels.

| Identical nested-CV splits: 156 stocks, two appearances each | Original regression | Improved |
| --- | --- | --- |
| Category accuracy | 51.60% (161/312) | **74.04% (231/312)** |
| Mean absolute score error | 6.53 points | **4.97 points** |
| RMSE | 10.09 points | **9.65 points** |
| R² | 0.600 | **0.634** |
| Macro F1 | 44.27% | **60.11%** |
| Balanced category accuracy | 43.87% | **57.06%** |

The category gain is 22.44 percentage points. Stock-wise paired bootstrap intervals are descriptive
because repeated CV fits are dependent: the reported accuracy interval is 67.31%–80.45%, and the
gain interval is 15.06–29.81 percentage points. These are estimates on the same previously examined
rule-scored snapshot, not new independent-test or future-period accuracy. Weak recall remains only
14.29% with seven unique examples; the overall accuracy does not establish reliable Weak detection.
The earlier classifier also achieved 74.04% overall, but its macro F1 was 55.88%, against 60.11%
for the score regressor. The two models do not make identical validation predictions.

There are 112 configurations across numeric Extra Trees, random forest, histogram gradient boosting,
XGBoost, CatBoost, Ridge and SVR. The search tests mean/median tree aggregation, fold-local continuous
score feature selection, and an optional reversible target transform that spaces the fixed score
boundaries. The transform preserves numeric differences within bands and converts predictions back
to 0–100 scores. It is tested as a regression alternative, never used as a score input. No class
targets, changed thresholds, synthetic observations or seed searches are introduced.

The final winner uses the **original untransformed score target** and median aggregation of 220
Extra Trees regressors. Each tree is fitted to numeric scores and produces a numeric prediction;
their median is the predicted score. Settings: squared-error tree splits, `max_features=1.0`,
unlimited depth, minimum one sample per leaf, minimum two samples per split, no bootstrap, and seed
20261006. The compact financial representation and all 143 encoded features are retained. The
score is bounded and rounded to two decimals before category conversion. No classifier is used.

The same ten outer folds and source observations are verified against the earlier regression.
Every outer training fold performs its own three-fold search; final selection uses repeated
three-fold CV and refits on all 156 eligible stocks. Candidate definitions, full nested base-model
parameters, fold choices, class metrics and paired comparisons are in
`data/models/fundamentals/2026-10-05-regression-improved/regression_report.json`. The final refit's
200-stock predictions are in-sample; validation results come exclusively from
`out_of_fold_predictions.json`. The original regressors, classifiers and source CSV are retained.
The daily refresh loads the verified active regressor without retraining.

Reproduce into a new directory:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.improve_fundamental_regression \
  --output data/models/fundamentals/2026-10-05-regression-improved-rerun
```

Add `--activate` to activate only after category accuracy improves against the earlier regression.
CatBoost and its dependencies are pinned in `uv.lock` and the exported runtime requirements.
The winning Extra Trees artifact does not depend on CatBoost at inference. Regression alternatives
follow the [scikit-learn target-transform interface](https://scikit-learn.org/stable/modules/generated/sklearn.compose.TransformedTargetRegressor.html)
and [CatBoost regression interface](https://catboost.ai/docs/en/concepts/python-reference_catboostregressor).

## Broader parameter experiment

The expanded search did not improve held-out performance. The current 112-configuration search's
model remains active; the broader experiment is retained separately for review and reproduction.

| Same 156 stocks and ten outer folds | Current model search | Broader search |
| --- | --- | --- |
| Derived-category accuracy | **74.04% (231/312)** | 72.76% (227/312) |
| Mean absolute score error | **4.97 points** | 5.21 points |
| RMSE | **9.65 points** | 10.04 points |
| R² | **0.634** | 0.603 |
| Macro F1 | **60.11%** | 58.79% |

The wider search selected different configurations in some training folds, but these choices
produced four fewer correct held-out labels overall. Increasing the number of tuning candidates
does not guarantee better validation predictions. Neither the source CSV nor the active model
pointer is changed by this experiment.

The broader search's final inner-CV winner is an untransformed score regressor using median
aggregation of 400 Extra Trees, `max_features=0.8`, unlimited depth, one sample per leaf and
two per split. Bootstrap is disabled and squared-error splits are used. Its final selection CV
accuracy is 73.08%; this selected-candidate measurement is not the nested held-out result above.
The fitted artifact is preserved without activation. Weak recall remains 14.29% in both searches.

The broader search preserves the numeric `Fundamental_Score` target, the source observations,
the five score bands, and the same ten outer validation folds. Its 794 unique configurations
include every one of these 432 Extra Trees combinations, with median aggregation, the compact
financial representation and all encoded features:

| Parameter | Exhaustive values |
| --- | --- |
| Number of trees | 220, 400, 600 |
| Features considered per split | 0.6, 0.8, 1.0 |
| Maximum depth | None, 8, 12, 20 |
| Minimum samples per leaf | 1, 2, 3, 5 |
| Minimum samples per split | 2, 4, 8 |

The previous 112 candidates remain included. Additional fixed samples expand tree split criteria,
bootstrap sampling, pruning, maximum leaf counts and aggregation; boosting iterations, learning
rate, depth and regularization; SVR kernel, C, epsilon and gamma; Ridge regularization; financial
representations, fold-local feature selection and reversible continuous target spacing. Duplicate
constructor settings are removed. The broader spaces are sampled, not exhaustively enumerated.
Sampling seeds are fixed before evaluation and never searched for a favorable accuracy result.

There are 556 Extra Trees, 64 random forest, 40 histogram gradient boosting, 48 XGBoost, 40 CatBoost,
14 Ridge and 32 SVR configurations. Every estimator fits numeric scores. Inner CV selects by
derived-category accuracy, with score MAE breaking ties. The complete evaluation involves 28,584
candidate-validation fits, plus the selected models' refits. Final selection uses repeated
three-fold CV on all eligible stocks. The original source CSV and prior artifacts are retained.

The complete predeclared configurations and source hashes are in
`data/models/fundamentals/2026-10-05-regression-broad/search_plan.json`. The completed report,
validation predictions, fold definitions and fitted model are saved beside it. Full winning
constructor settings for each fold are recovered using only its training CV when displayed
wrapper names are ambiguous; held-out predictions and reported metrics are never changed.

Reproduce into a new directory:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run python \
  -m jobs.tune_fundamental_regression --workers 6 \
  --output data/models/fundamentals/2026-10-05-regression-broad-rerun
```

Completed experiments cannot be overwritten. With `--activate`, the prior active model is retained
unless held-out category accuracy improves and mean absolute score error does not increase.
This is another experiment on the previously examined snapshot; it supplies no new independent
test or future-period accuracy.

## Original score regression

The training target is the contextual policy's score recomputed from cleaned financial evidence.
It is not the label code or a predicted score from a previous model. Symbol, company identity,
scores, rule grades, explanations and eligibility profiles never enter the feature matrix.
The data has 156 assessable stocks and 44 limited stocks; limited target scores are never imputed.

Seven regression families and 100 configurations were compared: Extra Trees, random forest,
histogram gradient boosting, conventional gradient boosting, XGBoost, Ridge and support vector
regression. Selection minimizes mean absolute score error using three inner folds. Five outer
folds with two repeats evaluate the complete selection procedure on the same fixed splits used
for the previous classifier. All feature processing is fitted inside each training fold. No
label thresholds, split seeds or test scores are tuned to raise reported accuracy.

| Nested CV measure | Result |
| --- | --- |
| Mean absolute score error | **6.53 points** |
| Root mean squared score error | **10.09 points** |
| R² | **0.600** |
| Scores within 5 points | 57.69% |
| Scores within 10 points | 77.56% |
| Derived-label accuracy | **51.60% (161/312)** |
| Previous classifier, same folds | 74.04% (231/312) |
| Training-fold median score baseline MAE | 12.08 points |

There are 156 unique stocks, each appearing twice in validation, not 312 independent stocks.
The expanded search does not improve category accuracy. Score regression smooths values across
hard boundaries, especially the policy's Moderate cap at 74 next to Strong at 75. Rule scores
remain visible because low point error does not ensure the correct category or preserve every
contextual risk cap. The initial six-family/76-configuration experiment is retained separately
under `2026-10-05-regression-initial-76`; its MAE was 6.34 points and label accuracy 52.56%.
Both runs use previously examined data and provide no new external-test or future accuracy.

The selected final model is `HistGradientBoostingRegressor`: 180 boosting iterations, learning
rate 0.1, squared-error loss, 15 maximum leaves, minimum 3 samples per leaf, L2 regularization 5,
and seed 20261006. It uses the compact financial representation. Its 66 raw/contextual inputs
become 60 financial fields and 143 encoded inputs after financial interactions, median imputation
with missing indicators, signed-log transformation, standardization and sector/industry one-hot
encoding. There are no class weights, oversampling or target-score normalization.

Inference clips predictions to [0, 100] and rounds to two decimals before applying these bands:

| Predicted score | Published label |
| --- | --- |
| Below 40 | Very Weak |
| 40 to below 60 | Weak |
| 60 to below 75 | Moderate |
| 75 to below 90 | Strong |
| 90–100 | Very Strong |
| Insufficient relevant evidence | Limited Assessment; blank score |

Nonfinite predictions stop publication and preserve the last successful generation. Scores are
estimates, not probabilities; `Model_Probability` is blank for regression. The final model is
refitted on all 156 eligible stocks after evaluation, so `stock_predictions.json` and the current
published training-date generation are in-sample predictions. Only `out_of_fold_predictions.json`
contains the validation predictions used for reported metrics.

Artifacts: `data/models/fundamentals/2026-10-05-regression/model.joblib`, `regression_report.json`,
`outer_splits.json`, `out_of_fold_predictions.json` and `stock_predictions.json`. The earlier pointer
selected this score regressor. The previous pointer is saved as `previous_active_model.json`, and
both earlier classifiers remain available. Source observations and original CSV bytes are retained.

Reproduce into a new directory, since training refuses to overwrite the active model:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m jobs.train_fundamental_regression \
  --output data/models/fundamentals/2026-10-05-regression-rerun
```

Add `--activate` to select a completed model after checksum and compatibility validation. Activation
and publication share the refresh lock. A new snapshot requires explicit `--csv`, `--raw` and a
new output directory. Use `--no-comparison` when there is no matching classifier evaluation, or
`--comparison` to provide one; comparison data and fold manifests are checked before fitting.
The fixed default inputs never recycle published model predictions as training targets.

## Previous classification experiment

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
broad-industry one-hot encoder. The improved classifier and regressor also apply signed logarithms.
Unknown future categories are accepted. The active regression target is the observed score. The
historical classifiers use target codes Very Weak 0, Weak 1, Moderate 2, Strong 3 and Very Strong 4.
Limited rows bypass all learned models.

The saved joblib artifact contains preprocessing, model, feature schema, score bands, policy
version, source hashes and package version. It is refitted on all 156 assessable stocks after
evaluation. `encoded_training.csv` is an export from that final refit, useful for inspection; it
must not be split again to claim unbiased accuracy. `stock_predictions.csv` is consequently
in-sample. Only `holdout_predictions.csv` contains the original untouched test predictions.
The historical classifier probabilities are uncalibrated outputs. Regression produces no probability.

## Historical classifier commands

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

## Daily refresh

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

Facts and comparison rule scores/labels are recomputed. The frozen active regressor predicts scores,
and the fixed score bands determine the final labels. Historical classifier overrides retain their
original rule-authoritative behavior. Daily refresh never trains on its own predicted scores.
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
