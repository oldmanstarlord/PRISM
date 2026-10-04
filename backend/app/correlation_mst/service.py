"""Reproducible persistence and read helpers for correlation MST runs."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.calculator import (
    MINIMUM_PAIRED_OBSERVATIONS,
    calculate_mst,
)
from backend.app.correlation_mst.inputs import (
    FORMULA_VERSION,
    LOOKBACK_RETURNS,
    MstInputs,
    load_inputs,
)
from backend.app.db.models import MstEdge, MstRun, Universe
from backend.app.db.models import MstNode as StoredMstNode


@dataclass(frozen=True, slots=True)
class PersistedMst:
    run_id: UUID
    created: bool
    node_count: int
    edge_count: int
    exclusion_count: int


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def mst_configuration() -> dict[str, object]:
    return {
        "implementation_version": FORMULA_VERSION,
        "return_definition": "daily log return from versioned adjusted close",
        "lookback_returns": LOOKBACK_RETURNS,
        "minimum_pairwise_observations": MINIMUM_PAIRED_OBSERVATIONS,
        "correlation": "Pearson sample correlation on paired finite returns",
        "distance": "sqrt(2 * (1 - correlation))",
        "algorithm": "Kruskal with Union-Find",
        "tie_break": ["distance", "symbol_a", "symbol_b"],
        "missing_data": "no imputation; deterministic exclusion until complete valid graph",
    }


def mst_input_fingerprint(inputs: MstInputs) -> str:
    observations: list[list[object]] = []
    for trade_date, row in inputs.adjusted_closes.sort_index().iterrows():
        for symbol in sorted(inputs.security_ids):
            value = row[symbol]
            if value == value:
                observations.append(
                    [
                        trade_date.isoformat(), symbol, format(float(value), ".15g"),
                        str(inputs.adjustment_versions.at[trade_date, symbol]),
                        str(inputs.adjustment_times.at[trade_date, symbol]),
                    ]
                )
    return _canonical_hash(
        {
            "window_end": inputs.window_end,
            "data_cutoff": inputs.data_cutoff,
            "members": [
                [symbol, str(inputs.security_ids[symbol]), inputs.membership_sources[symbol]]
                for symbol in sorted(inputs.security_ids)
            ],
            "observations": observations,
        }
    )


def persist_mst(
    session: Session,
    *,
    window_end: date,
    lookback_start: date,
    data_cutoff: datetime,
    computed_at: datetime | None = None,
    commit: bool = True,
) -> PersistedMst:
    inputs = load_inputs(session, window_end, lookback_start, data_cutoff)
    configuration = mst_configuration()
    configuration_hash = _canonical_hash(configuration)
    fingerprint = mst_input_fingerprint(inputs)
    existing = session.scalar(
        select(MstRun).where(
            MstRun.window_end == window_end,
            MstRun.implementation_version == FORMULA_VERSION,
            MstRun.configuration_hash == configuration_hash,
            MstRun.input_fingerprint == fingerprint,
            MstRun.status == "completed",
        )
    )
    if existing is not None:
        return PersistedMst(
            existing.id, False, existing.included_symbol_count,
            existing.edge_count, existing.requested_symbol_count - existing.included_symbol_count,
        )

    universe_id = session.scalar(select(Universe.id).where(Universe.name == "NIFTY 200"))
    if universe_id is None:
        raise ValueError("NIFTY 200 universe is not seeded")
    calculation_time = computed_at or datetime.now(UTC)
    calculation = calculate_mst(inputs, computed_at=calculation_time)
    exclusions = {
        "items": [
            {
                "security_id": str(item.security_id),
                "symbol": item.symbol,
                "reason": item.reason,
                "details": item.details,
            }
            for item in calculation.exclusions
        ]
    }
    run = MstRun(
        universe_id=universe_id,
        window_start=calculation.window_start,
        window_end=calculation.window_end,
        data_cutoff=data_cutoff,
        requested_symbol_count=len(inputs.security_ids),
        included_symbol_count=len(calculation.nodes),
        edge_count=len(calculation.edges),
        is_connected=calculation.is_connected,
        is_acyclic=calculation.is_acyclic,
        exclusions=exclusions,
        configuration=configuration,
        configuration_hash=configuration_hash,
        input_fingerprint=fingerprint,
        status="completed",
        implementation_version=FORMULA_VERSION,
        computed_at=calculation_time,
    )
    session.add(run)
    session.flush()
    session.add_all(
        [
            StoredMstNode(
                mst_run_id=run.id,
                security_id=node.security_id,
                symbol=node.symbol,
                industry=node.industry,
                observations_used=node.observations_used,
                membership_source=node.membership_source,
            )
            for node in calculation.nodes
        ]
    )
    session.add_all(
        [
            MstEdge(
                mst_run_id=run.id,
                security_a_id=edge.security_a_id,
                security_b_id=edge.security_b_id,
                symbol_a=edge.symbol_a,
                symbol_b=edge.symbol_b,
                correlation=Decimal(str(edge.correlation)),
                distance=Decimal(str(edge.distance)),
                paired_observations=edge.paired_observations,
                edge_rank=edge.edge_rank,
            )
            for edge in calculation.edges
        ]
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return PersistedMst(
        run.id, True, run.included_symbol_count, run.edge_count, len(calculation.exclusions)
    )


def latest_completed_mst_query() -> Select[MstRun]:
    return (
        select(MstRun)
        .where(MstRun.status == "completed")
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
        .limit(1)
    )
