"""Sector Divergence component (dimension: relative, direction: higher_is_riskier)."""

from datetime import date
from uuid import UUID

from sqlalchemy import desc, select

from backend.app.db.models import SectorDivergenceRun, SectorDivergenceScore
from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)


class SectorDivergenceComponent:
    """Retrieves point-in-time absolute 20-day residual divergence score from Layer 1."""

    key = "sector_divergence"
    dimension = "relative"
    direction = "higher_is_riskier"
    required_inputs = ["sector_divergence_score", "sector_divergence_run"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        session = context.session
        horizon = int(context.config.get("sector_divergence_horizon", 20))
        max_age_days = int(context.config.get("sector_divergence_max_age_days", 5))

        # Retrieve the latest completed SectorDivergenceRun on or before as_of
        latest_run = session.scalars(
            select(SectorDivergenceRun)
            .where(
                SectorDivergenceRun.signal_date <= as_of,
                SectorDivergenceRun.completed_at <= context.data_cutoff,
                SectorDivergenceRun.status == "completed",
            )
            .order_by(
                desc(SectorDivergenceRun.signal_date),
                desc(SectorDivergenceRun.completed_at),
            )
            .limit(1)
        ).first()

        results: list[ComponentValue] = []

        if latest_run is None:
            for sec_id, symbol, _ in universe:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={"reason": "no_completed_divergence_run"},
                    )
                )
            return results

        signal_date = latest_run.signal_date
        age_days = (as_of - signal_date).days
        status_flag = "stale" if age_days > max_age_days else "ok"

        # Query scores for the target horizon
        scores = session.scalars(
            select(SectorDivergenceScore).where(
                SectorDivergenceScore.run_id == latest_run.id,
                SectorDivergenceScore.horizon == horizon,
            )
        ).all()
        score_by_sec = {s.security_id: s for s in scores}

        for sec_id, symbol, _ in universe:
            s = score_by_sec.get(sec_id)
            if s is None:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=signal_date,
                        data_age_days=age_days,
                        evidence_ref={
                            "run_id": str(latest_run.id),
                            "reason": "symbol_not_in_divergence_run",
                        },
                    )
                )
                continue

            # Absolute divergence value reflects magnitude of peer decoupling
            raw_val = abs(float(s.divergence_value))
            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(raw_val, 6),
                    status=status_flag,
                    data_as_of=signal_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "run_id": str(latest_run.id),
                        "horizon": horizon,
                        "raw_divergence_value": float(s.divergence_value),
                        "abs_divergence_value": round(raw_val, 6),
                        "industry_percentile": float(s.industry_percentile),
                        "interpretation": s.interpretation,
                    },
                )
            )

        return results
