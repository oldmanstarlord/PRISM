# PRISM viva questions and defensible answers

## Why Kruskal and Union-Find for the MST?

Layer 2 converts approved Pearson correlations to Mantegna distance and needs a
deterministic minimum spanning tree. Kruskal sorts edges by the approved tie-break;
Union-Find efficiently rejects cycles. A valid run is connected, acyclic and has
`N-1` edges. The tree summarizes association and is never described as causal.

## Why shrinkage covariance?

With roughly 200 securities and finite daily history, the sample covariance matrix
is noisy and may be ill-conditioned. Ledoit-Wolf shrinkage moves it toward a stable
target while retaining observed co-movement. PRISM exposes the shrinkage intensity,
window, assumptions and limitations.

## Why percentile ranks instead of a fitted score model?

Percentiles are deterministic, comparable across differently scaled components,
and explainable as peer-relative position. They avoid claiming predictive learning
before sufficient point-in-time validation exists. The trade-off is dependence on
peer coverage and the current-universe survivorship limitation.

## What does confidence mean?

Confidence is data integrity and evidential support, not probability of a market
outcome. Its six configured factors are coverage, freshness, source agreement,
signal agreement, model stability and evidence volume. Stale prices and low
coverage impose hard caps.

## What does Layer 1 do?

`sector-divergence-v1` estimates each stock’s residual divergence from its official
industry peers after the approved market relationship, over approved 1/5/20-day
horizons. It is descriptive risk context, not a directional price forecast.

## Did validation prove the score works?

Not yet. The validation framework is implemented, but the production historical
run is blocked because known fixture-derived rows must be cleaned first. Any answer
claiming successful empirical validation would be false. The UI reports failures,
baselines and limitations plainly once a clean run exists.

## Is the system real-time?

No. Prices are end-of-day. Filings/news are scheduled for configured polling (30
minutes in operations config), subject to source availability and publication lag.

## What are the largest honest limitations?

Current rather than historical index membership, prototype price sourcing, source
gaps, missing shares-outstanding history, correlation non-causality, short validation
history, and an uncompleted independent recovery sign-off and seven-day soak.
