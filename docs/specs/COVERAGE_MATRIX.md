# PRISM Step 12 Coverage Matrix

This matrix is the explicit eight-dimension coverage contract. An active component can
still return `missing` or `insufficient`; that status remains visible and lowers
confidence. No missing input is replaced with a synthetic value.

| Dimension | Registered active components | Current production availability |
|---|---|---|
| Market | `ewma_volatility`, `beta_to_benchmark`, `max_drawdown_1y`, `tail_loss` | Active; Yahoo price and benchmark data, with single-source limitation |
| Liquidity | `avg_traded_value`, `zero_volume_days` | Active from price/volume observations; shares-based turnover remains unavailable |
| Structure | `mst_centrality` | Active when a completed Layer 2 run exists |
| Relative | `sector_divergence` | Active when a completed Layer 1 run exists |
| Fundamentals | `fund_leverage`, `fund_coverage`, `fund_profit_trend`, `fund_cashflow_quality` | Active but unavailable when no point-in-time Yahoo fundamentals have been loaded |
| Governance | `gov_promoter_pledge`, `gov_promoter_holding_change`, `gov_institutional_flow`, `gov_insider_activity` | Explicitly unavailable: no verified production source is loaded |
| Events | `event_risk_pressure` | Explicitly unavailable: announcement source is TBD and no scraping is permitted |
| Macro | `macro_exposure`, `news_policy_pressure` | Partial: crude, USD/INR and India VIX verified through Yahoo; India 10Y and FII/DII TBD; RBI/SEBI RSS verified |

The score renormalises over dimensions with usable observations. The original configured
weight remains in the denominator of `data_coverage`, so unavailable dimensions lower
confidence and can trigger the low-coverage cap.
