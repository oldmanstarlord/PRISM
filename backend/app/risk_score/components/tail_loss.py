"""Historical Tail Loss / Expected Shortfall component (dimension: market)."""

from datetime import date
from uuid import UUID

import numpy as np

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import get_adjusted_prices_map


class TailLossComponent:
    """Computes Historical Expected Shortfall (CVaR) at 95% confidence level."""

    key = "tail_loss"
    dimension = "market"
    direction = "higher_is_riskier"
    required_inputs = ["price_daily_adjusted"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        lookback = int(context.config.get("tail_loss_lookback_days", 250))
        alpha = float(context.config.get("tail_loss_alpha", 0.05))
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

            # Historical Expected Shortfall: average loss in the worst alpha fraction of days
            cutoff_return = float(np.percentile(rets, alpha * 100))
            tail_returns = rets[rets <= cutoff_return]
            if len(tail_returns) == 0:
                es = float(-cutoff_return)
            else:
                es = float(-np.mean(tail_returns))

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(es, 6),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "observations": len(rets),
                        "alpha": alpha,
                        "var_95": round(-cutoff_return, 6),
                        "expected_shortfall": round(es, 6),
                    },
                )
            )

        return results
