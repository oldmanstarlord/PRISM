"""EWMA Realised Volatility component (dimension: market)."""

from datetime import date
from uuid import UUID

import numpy as np

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import get_adjusted_prices_map


class EwmaVolatilityComponent:
    """Computes annualised EWMA volatility of daily log returns with configurable decay."""

    key = "ewma_volatility"
    dimension = "market"
    direction = "higher_is_riskier"
    required_inputs = ["price_daily_adjusted"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        prices_map = get_adjusted_prices_map(context, universe, lookback_days=180)
        lam = float(context.config.get("ewma_lambda", 0.94))
        ann_factor = float(context.config.get("volatility_annualisation_factor", 252))

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

            rets = np.log(prices / prices.shift(1)).dropna().to_numpy(dtype=float)
            if len(rets) < 20:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="insufficient",
                        data_as_of=last_date,
                        data_age_days=age_days,
                        evidence_ref={"observations": len(rets), "required": 20},
                    )
                )
                continue

            # Exponentially weighted moving average of squared returns
            n = len(rets)
            weights = (1.0 - lam) * (lam ** np.arange(n - 1, -1, -1))
            weights /= weights.sum()
            ewma_var = float(np.sum(weights * (rets**2)))
            ewma_vol_annual = float(np.sqrt(ewma_var * ann_factor))

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(ewma_vol_annual, 6),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "observations": len(rets),
                        "lambda": lam,
                        "annualisation_factor": ann_factor,
                        "raw_volatility": round(ewma_vol_annual, 6),
                    },
                )
            )

        return results
