"""1-Year Maximum Drawdown component (dimension: market)."""

from datetime import date
from uuid import UUID

import numpy as np

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import get_adjusted_prices_map


class MaxDrawdown1yComponent:
    """Computes peak-to-trough maximum drawdown over trailing 250 trading days."""

    key = "max_drawdown_1y"
    dimension = "market"
    direction = "higher_is_riskier"
    required_inputs = ["price_daily_adjusted"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        lookback = int(context.config.get("drawdown_lookback_days", 250))
        minimums = context.config.get("minimum_observations", {})
        minimum = int(minimums.get(self.key, 30)) if isinstance(minimums, dict) else 30
        stale_days = int(context.config.get("stale_price_days_cap_threshold", 5))
        prices_map = get_adjusted_prices_map(context, universe, lookback_days=lookback)
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
            status = "stale" if age_days > stale_days else "ok"

            series_vals = prices.tail(lookback).to_numpy(dtype=float)
            if len(series_vals) < minimum:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="insufficient",
                        data_as_of=last_date,
                        data_age_days=age_days,
                        evidence_ref={"observations": len(series_vals), "required": minimum},
                    )
                )
                continue

            # Maximum Drawdown: (Peak - Trough) / Peak
            running_max = np.maximum.accumulate(series_vals)
            drawdowns = (running_max - series_vals) / running_max
            mdd = float(np.max(drawdowns))

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(mdd, 6),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={"max_drawdown": round(mdd, 6), "observations": len(series_vals)},
                )
            )

        return results
