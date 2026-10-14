# Portfolio Analytics Version 1 Contract

## Scope

`portfolio-analytics-v1` calculates a session-only weighted-portfolio analysis from
persisted PRISM market data. It performs no authentication, portfolio persistence or
database writes. Results are descriptive historical estimates, not forecasts or
investment recommendations.

## Input and observation envelope

- Input is one or more positive NIFTY 200 MST symbols with decimal weights.
- Duplicate symbols are aggregated. Aggregated weights must total `1.0` within `0.0001`.
- The latest completed Layer 2 run fixes the analysis date and point-in-time data cutoff.
- Adjusted-close revisions must have been available by that cutoff.
- Version 1 requests 250 daily returns and requires at least 60.
- Only dates with a valid adjusted close for every holding are retained.
- Prices and returns are never forward-filled, backward-filled or replaced with zero.
- Portfolio history assumes constant target weights rebalanced each trading day.

## Performance and risk

For adjusted close `P(i,t)`, daily log return is:

`r(i,t) = ln(P(i,t) / P(i,t-1))`

For fixed portfolio weights `w(i)`, the daily portfolio log return is:

`r(p,t) = sum(w(i) * r(i,t))`

The displayed index starts at 100 and compounds the portfolio log-return series.
Annualized return is `exp(mean(r(p)) * 252) - 1`. Annualized volatility is sample
standard deviation multiplied by `sqrt(252)`. Downside volatility is the root mean
square of negative daily portfolio returns multiplied by `sqrt(252)`. Drawdown is the
percentage distance from the running portfolio-index peak; maximum drawdown is the
largest absolute drawdown.

The annual covariance matrix is the daily sample covariance multiplied by 252.
Portfolio volatility is `sqrt(w' Sigma w)`. Holding `i` has marginal risk
`(Sigma w)(i) / volatility` and percentage risk contribution
`w(i) * (Sigma w)(i) / portfolio_variance`. Contributions can be negative for a
historically hedging position and sum to approximately one when variance is positive.

## Concentration and effective exposures

- Holding HHI is `sum(w(i)^2)` and effective holdings is `1 / holding_HHI`.
- Industry weights aggregate holding weights; industry HHI and effective industries use
  the same formula.
- Risk effective bets use entropy of normalized positive risk contributions:
  `exp(-sum(p(i) * ln(p(i))))`.
- Correlation effective bets use the participation ratio of correlation eigenvalues:
  `(sum(lambda)^2) / sum(lambda^2)`.

## MST diagnostics

- Direct links are stored Layer 2 edges whose endpoints are both held.
- Every holding pair uses its unique path through the complete NIFTY 200 MST.
- The portfolio subtree is the deduplicated union of those paths. Its response edges retain
  the exact stored correlation and Mantegna distance used by the interactive visualization.
- A bridge stock is an internal path node; its count is the number of holding-pair paths
  that traverse it. A bridge can be held or non-held.
- Version 1 correlation clusters remove MST edges below correlation `0.50` and use the
  remaining connected components. Cluster weights, HHI and effective clusters use only
  portfolio holding weights, while component size reports all included MST nodes.
- Stability compares the current tree with up to four immediately preceding completed runs
  having the same universe, implementation version and configuration hash. Per-edge
  persistence is the fraction of compared trees containing that canonical symbol pair.
- Consecutive-window overlap is the mean adjacent-run edge intersection divided by the larger
  tree's edge count. Overall confidence is `high` at 80% mean current-edge persistence,
  `moderate` at 60%, and `low` below 60%. It is `unavailable` with fewer than two runs.
- Every subtree edge and holding-to-holding path exposes persistence and a confidence label.
  A path uses its least-persistent edge, preventing one unstable connector from being hidden by
  otherwise stable segments.
- MST relationships are sparse statistical summaries. Paths and bridges do not establish
  causal transmission or prove diversification.

## Stress scenarios

### Selected holding

For shocked holding `s`, sensitivity of holding `j` is the trailing sample regression
beta `Cov(r(j), r(s)) / Var(r(s))`. The selected holding has sensitivity one. Estimated
holding return is `beta(j,s) * shock`, and portfolio impact is the weighted sum. The shock
range is -30% to +30%, excluding zero.

### Selected industry

Every portfolio holding in the selected industry receives the exact parallel shock;
holdings outside it receive zero. Version 1 intentionally does not invent cross-industry
propagation.

Both scenarios exclude liquidity, feedback effects, execution costs, independent
simultaneous shocks and parameter instability. They are scenario estimates, not
predictions.

## Export

The browser can download the full response as JSON and print the formatted report to PDF.
Export does not persist the portfolio in PRISM or Supabase.
