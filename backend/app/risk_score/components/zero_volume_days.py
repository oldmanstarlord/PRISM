"""Zero Volume Days component (dimension: liquidity, direction: higher_is_riskier)."""

from datetime import date
from uuid import UUID

from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)
from backend.app.risk_score.components.helpers import get_raw_prices_map


class ZeroVolumeDaysComponent:
    """Computes count of non-trading or zero-volume days over trailing 60 trading days."""

    key = "zero_volume_days"
    dimension = "liquidity"
    direction = "higher_is_riskier"
    required_inputs = ["price_daily_raw"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        lookback = int(context.config.get("zero_volume_lookback_days", 60))
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
            status = "stale" if age_days > 5 else "ok"

            tail_df = df.tail(lookback)
            if len(tail_df) < 5:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="insufficient",
                        data_as_of=last_date,
                        data_age_days=age_days,
                        evidence_ref={"observations": len(tail_df), "required": 5},
                    )
                )
                continue

            # Zero volume days: volume <= 0
            zero_vol_count = int((tail_df["volume"] <= 0).sum())

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=float(zero_vol_count),
                    status=status,
                    data_as_of=last_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "window_days": len(tail_df),
                        "zero_volume_days": zero_vol_count,
                        "ratio": round(zero_vol_count / len(tail_df), 4),
                    },
                )
            )

        return results
