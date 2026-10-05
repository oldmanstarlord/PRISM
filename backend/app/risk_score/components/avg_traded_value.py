"""Average Daily Traded Value component (dimension: liquidity, direction: lower_is_riskier)."""

from datetime import date
from uuid import UUID

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import get_raw_prices_map


class AvgTradedValueComponent:
    """Computes rolling 20-day mean of daily rupee traded value (close * volume)."""

    key = "avg_traded_value"
    dimension = "liquidity"
    direction = "lower_is_riskier"
    required_inputs = ["price_daily_raw"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        lookback = int(context.config.get("adv_lookback_days", 20))
        minimums = context.config.get("minimum_observations", {})
        minimum = int(minimums.get(self.key, 5)) if isinstance(minimums, dict) else 5
        stale_days = int(context.config.get("stale_price_days_cap_threshold", 5))
        raw_map = get_raw_prices_map(context, universe, lookback_days=lookback)

        results: list[ComponentValue] = []

        for sec_id, symbol, _ in universe:
            df = raw_map.get(sec_id)
            if df is None or df.empty:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={"reason": "no_raw_price_data"},
                    )
                )
                continue

            last_date = df.index[-1]
            age_days = (as_of - last_date).days
            status = "stale" if age_days > stale_days else "ok"

            tail_df = df.tail(lookback)
            if len(tail_df) < minimum:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="insufficient",
                        data_as_of=last_date,
                        data_age_days=age_days,
                        evidence_ref={"observations": len(tail_df), "required": minimum},
                    )
                )
                continue

            # Daily rupee traded value = close * volume
            traded_value = tail_df["close"] * tail_df["volume"]
            mean_turnover = float(traded_value.mean())

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(mean_turnover, 2),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "window_days": len(tail_df),
                        "mean_turnover_inr": round(mean_turnover, 2),
                        "last_day_turnover_inr": round(float(traded_value.iloc[-1]), 2),
                    },
                )
            )

        return results
