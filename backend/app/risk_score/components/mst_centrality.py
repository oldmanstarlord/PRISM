"""MST Graph Centrality component (dimension: structure, direction: higher_is_riskier)."""

from datetime import date
from uuid import UUID

from sqlalchemy import desc, select

from backend.app.db.models import MstNodeMetric, MstRun
from backend.app.risk_score.components.base import (
    ComponentValue,
    RiskContext,
)


class MstCentralityComponent:
    """Retrieves point-in-time weighted graph centrality from the latest completed MST run."""

    key = "mst_centrality"
    dimension = "structure"
    direction = "higher_is_riskier"
    required_inputs = ["mst_node_metric", "mst_run"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        session = context.session
        max_age_days = int(context.config.get("mst_max_age_days", 35))

        # Retrieve the latest completed MST run on or before as_of
        latest_mst_run = session.scalars(
            select(MstRun)
            .where(
                MstRun.window_end <= as_of,
                MstRun.computed_at <= context.data_cutoff,
                MstRun.status == "completed",
            )
            .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
            .limit(1)
        ).first()

        results: list[ComponentValue] = []

        if latest_mst_run is None:
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
                        evidence_ref={"reason": "no_completed_mst_run"},
                    )
                )
            return results

        mst_date = latest_mst_run.window_end
        age_days = (as_of - mst_date).days
        status_flag = "stale" if age_days > max_age_days else "ok"

        # Query all node metrics for this run
        metrics = session.scalars(
            select(MstNodeMetric).where(MstNodeMetric.run_id == latest_mst_run.id)
        ).all()
        metric_by_sec = {m.security_id: m for m in metrics}

        for sec_id, symbol, _ in universe:
            m = metric_by_sec.get(sec_id)
            if m is None:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=mst_date,
                        data_age_days=age_days,
                        evidence_ref={
                            "mst_run_id": str(latest_mst_run.id),
                            "reason": "node_not_in_mst",
                        },
                    )
                )
                continue

            centrality = float(m.weighted_centrality)
            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(centrality, 6),
                    status=status_flag,
                    data_as_of=mst_date,
                    data_age_days=age_days,
                    evidence_ref={
                        "mst_run_id": str(latest_mst_run.id),
                        "degree": m.degree,
                        "hub_rank": m.hub_rank,
                        "weighted_centrality": round(centrality, 6),
                    },
                )
            )

        return results
