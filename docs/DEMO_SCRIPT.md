# PRISM five-minute demonstration

Prerequisites: API on port 8000, frontend on port 5173, migrations at head, and
approved local data already ingested. Demo CSV weights are synthetic and are not
recommendations.

1. Run `uv run python -m jobs.load_demo_portfolios` to load the three fixtures
   through the local API, or upload `data/demo/diversified.csv` on `/portfolio`.
2. On Portfolio, show volatility, drawdown, shrinkage covariance, Euler
   contributions, diversification, assumptions, confidence, and limitations.
3. Open INFY from Stocks. Show total risk, six-factor confidence, the generic
   component breakdown, missing-data banner, fundamentals, governance, events, and
   publication/data-age evidence.
4. Open MST. Explain that Kruskal/Union-Find produces the deterministic minimum
   spanning tree from correlation distance; edges are association, not causation.
5. Open Validation. Show baselines, ablations, confidence calibration, survivorship
   warning, and any failures without hiding them.
6. Open Shock, select the demo portfolio and a stock, run a -10% hypothetical shock,
   and point to “scenario, not a forecast.”
7. Open Data Health and Alerts. Show source traffic lights, pipeline manifests,
   timestamps, rule thresholds and evidence links.
8. Finish on Limitations: daily prices, current-membership survivorship bias, source
   gaps, non-causality, and no investment advice.
