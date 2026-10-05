"""Benchmark Beta component (dimension: market)."""

from datetime import date
from uuid import UUID

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import (
    get_adjusted_prices_map,
    get_benchmark_returns,
)


class BetaToBenchmarkComponent:
    """Computes rolling OLS market beta to NIFTY 200 benchmark index."""

    key = "beta_to_benchmark"
    dimension = "market"
    direction = "higher_is_riskier"
    required_inputs = ["price_daily_adjusted", "benchmark_series"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        prices_map = get_adjusted_prices_map(context, universe, lookback_days=365)
        bench_rets = get_benchmark_returns(context, "NIFTY 200", lookback_days=365)

        # Fallback to equal-weighted average return if benchmark series unavailable
        if bench_rets.empty:
            all_rets: list[pd.Series] = []
            for p in prices_map.values():
                if len(p) >= 2:
                    all_rets.append(np.log(p / p.shift(1)).dropna())
            if all_rets:
                bench_rets = pd.concat(all_rets, axis=1).mean(axis=1)

        results: list[ComponentValue] = []

        for sec_id, symbol, _ in universe:
            prices = prices_map.get(sec_id)
            if prices is None or len(prices) < 2:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={"reason": "insufficient_price_history"},
                    )
                )
                continue

            last_date = prices.index[-1]
            age_days = (as_of - last_date).days
            status = "stale" if age_days > 5 else "ok"

            stk_rets = np.log(prices / prices.shift(1)).dropna()
            paired = pd.concat([stk_rets, bench_rets], axis=1).dropna()
            if len(paired) < 30:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="insufficient",
                        data_as_of=last_date,
                        data_age_days=age_days,
                        evidence_ref={"paired_observations": len(paired), "required": 30},
                    )
                )
                continue

            y = paired.iloc[:, 0].to_numpy(dtype=float)
            x = paired.iloc[:, 1].to_numpy(dtype=float)

            var_x = float(np.var(x, ddof=1))
            if var_x <= 1e-15:
                beta_val = 1.0
            else:
                beta_val = float(np.cov(x, y, ddof=1)[0, 1] / var_x)

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(beta_val, 4),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={"beta": round(beta_val, 4), "paired_observations": len(paired)},
                )
            )

        return results
