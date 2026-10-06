# Sector-Divergence Explanation Specification v1

## Scope and invariants

Step E3 explains stored `sector-divergence-v1` results for a stock and its official
Nifty Indices `Industry` group. The implementation does not modify Layer 1. It reads
persisted runs/scores and reconstructs peer series from the same point-in-time
adjusted-price envelope and leave-one-out peer rules.

All language comes from draft `explain_sector_rules:1.0.0`. Every sentence cites
stored evidence, unsupported sections are omitted, and the shared D8/D9 guardrails
apply. A divergence is never presented as a prediction, recommendation, causal
claim, or standalone risk verdict.

## Calculations

- Daily peer return for stock `i` is the contemporaneous median log return of the
  other eligible securities in its stored Industry group. At least four peers are
  required and missing returns are not imputed.
- Stock and peer trends use cumulative 1/5/20/60-trading-day returns. `up`, `down`,
  and `flat` labels use the versioned per-window thresholds in config.
- Breadth is the share of eligible peers with positive 20-day returns. Dispersion is
  the sample standard deviation of their 20-day returns.
- Expected one-day return is stored alpha plus stored beta times the reconstructed
  current peer return. R-squared is recomputed read-only on the same preceding
  60-session paired regression window; it is not currently a persisted Layer 1
  field. Stored residual and 1/5/20-day z-scores remain authoritative.
- Absolute-score historical percentile uses the stock's available completed runs
  through the selected cutoff. Peer percentile uses absolute 20-day scores from the
  same run and Industry. Ties use a weak empirical CDF.
- Persistence counts available dates with `|z20| > 1` in the configured last 20
  runs. Fewer available dates are disclosed as a limitation.
- Publication markers include only company events, linked news, and fundamental
  periods published and ingested by the Layer 1 data cutoff.
- Configured contribution share is exactly
  `100 * component_points * component_weight / total_risk_score`. It is omitted
  when the matching point-in-time risk run is unavailable.
- A risk-support sentence appears only for a negative divergence accompanied by a
  stored fundamental-risk or volatility percentile meeting its configured
  threshold. It does not change the stock score.

## Sector explanation and UI

The sector explainer reports the industry median trend, breadth, dispersion, stored
flag count, largest divergences, significant stored macro sensitivities, and linked
news/event count. `/sectors` provides the D3 overview and opens the same generic
evidence drawer used elsewhere.

Endpoints:

- `GET /api/v1/explain/divergence/{symbol}`
- `GET /api/v1/explain/sector/{industry}`
- `GET /api/v1/sectors/overview`

The stock dossier and Layer 1 company page display API-driven stock/peer trend
cards, a chart rebased to 100 with indexed separation shaded and dated publication
markers, flagged/risk/contribution sections, evidence provenance, limitations, and
the mandatory disclaimer.

## Assumptions requiring review

- **ASSUMPTION:** flat trend thresholds are 0.25%, 0.75%, 1.5%, and 3.0% for
  1/5/20/60 trading days respectively.
- **ASSUMPTION:** negative divergence requires a 75th-percentile fundamental-risk
  or historical-volatility component to support the optional risk reading.
- **ASSUMPTION:** publication coincidence uses a 60-calendar-day lookback. It is
  temporal overlap only and does not establish that the item explains the move.

