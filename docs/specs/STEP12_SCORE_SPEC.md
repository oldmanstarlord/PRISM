# Step 12 Full Score and Portfolio Synthesis

Status: implemented as `risk_engine_parameters` version `2.0.0`, `draft`.
It is not the default until the project owner explicitly approves it.

## Stock score coverage

The required dimensions are market, liquidity, structure, relative,
fundamentals, governance, events, and macro. The executable contract is
`backend/app/risk_score/coverage.py`; `COVERAGE_MATRIX.md` records current
availability. A dimension with no usable component is retained as `missing`,
excluded from score aggregation, retained in the configured-weight coverage
denominator, and therefore lowers confidence. No synthetic observation is used.

An ablation run supplies component IDs and/or dimension names to exclude. The
exclusion set is added to the effective configuration before its fingerprint is
computed, so ablated runs remain deterministic and cannot collide with full runs.

## Confidence factors

Each factor is in `[0, 1]`; final confidence is 100 times their config-weighted
mean before caps.

1. `data_coverage`: configured dimension-weight coverage multiplied by mean
   observed-history completeness. Missing history days are reported.
2. `data_freshness`: component-weighted linear freshness against each
   dimension's configured maximum age. Unknown age contributes zero.
3. `source_agreement`: `1 - mismatch_rate` from point-in-time `data_crosscheck`
   rows in the configured trailing window. No cross-check data contributes zero.
4. `signal_agreement`: fraction of usable component signals on the dominant
   side of the 50th-percentile risk point.
5. `model_stability`: mean of available Layer 2 edge persistence and EWMA
   volatility reliability. Volatility reliability is
   `1 - sqrt(1 / (2 * (n - 1)))` for `n > 1`. Missing evidence is not replaced.
6. `evidence_volume`: `1 - exp(-N / scale)`, where `N` is the point-in-time
   corporate-event plus matched-policy-event count.

Stale market prices trigger a 50 cap. Coverage below 0.70 triggers a 60 cap.
Both the factors and triggered caps are returned by the API.

## Portfolio score

ASSUMPTION pending owner approval:

- Holding risk is the normalized holding-weight average of current stock scores.
- Cluster-concentration risk is `100 * maximum_cluster_weight`.
- Effective-bet risk is `100 * (1 - min(1, ENB_entropy / holding_count))`.
- The structure score is the config-weighted mean of those two structural risks;
  draft v2 weights them 50/50.
- The final score weights holding risk at 80% and structure risk at 20%. If the
  structure inputs are absent, the available holding term is renormalized and
  score coverage/confidence are reduced.
- Portfolio confidence is holding-weighted confidence capped by the weakest
  holding whose normalized weight is at least 10%. Missing stock-score weight
  reduces coverage and confidence.

The API returns holding risk, structure risk, both structural inputs, final risk,
confidence, coverage, missing holdings, contributions, method version, and
limitations separately. These are descriptive risk summaries, not forecasts or
investment advice. MST-based structure is descriptive and non-causal.
