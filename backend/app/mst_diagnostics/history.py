"""History orchestration job computing rolling weekly MSTs and stability tracking."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import persist_mst
from backend.app.db.models import MstStability, PriceDailyAdjusted
from backend.app.mst_diagnostics.config import load_mst_diagnostics_config
from backend.app.mst_diagnostics.service import (
    compute_and_persist_diagnostics,
    persist_residual_mst,
)


@dataclass(frozen=True, slots=True)
class HistoryWindowStat:
    window_end: date
    run_id: UUID
    variant: str
    edge_persistence: float | None
    node_overlap: float | None
    window_gap_days: int | None
    grade: str | None


@dataclass(frozen=True, slots=True)
class VariantHistoryReport:
    variant: str
    total_runs_evaluated: int
    transitions_count: int
    average_edge_persistence: float
    worst_edge_persistence: float
    worst_window_end: date | None
    windows: list[HistoryWindowStat]


@dataclass(frozen=True, slots=True)
class HistoryJobResult:
    windows_requested: int
    raw_report: VariantHistoryReport
    residual_report: VariantHistoryReport | None
    comparison: dict[str, Any]


def get_available_anchor_date(session: Session) -> date:
    """Find the latest adjusted close date available in the database."""
    latest = session.scalar(
        select(PriceDailyAdjusted.trade_date).order_by(desc(PriceDailyAdjusted.trade_date)).limit(1)
    )
    if latest is not None:
        return latest
    return date.today()


def run_mst_history_job(
    session: Session,
    *,
    windows_count: int | None = None,
    run_residual: bool = True,
    anchor_date: date | None = None,
) -> HistoryJobResult:
    """Execute weekly rolling MST runs, compute stability diagnostics, and compare variants."""
    config = load_mst_diagnostics_config(session)
    n_windows = windows_count or config.history_windows_count

    end_anchor = anchor_date or get_available_anchor_date(session)

    # Generate N weekly window ends, sorted chronologically from oldest to newest
    window_ends = [end_anchor - timedelta(days=7 * i) for i in reversed(range(n_windows))]

    raw_run_ids: list[tuple[date, UUID]] = []
    residual_run_ids: list[tuple[date, UUID]] = []

    for w_end in window_ends:
        lookback_start = w_end - timedelta(days=365)
        cutoff = datetime.combine(w_end, time(23, 59, 59), tzinfo=UTC)

        # 1. Raw variant
        try:
            persisted_raw = persist_mst(
                session,
                window_end=w_end,
                lookback_start=lookback_start,
                data_cutoff=cutoff,
            )
            compute_and_persist_diagnostics(session, persisted_raw.run_id, config=config)
            raw_run_ids.append((w_end, persisted_raw.run_id))
        except Exception:
            # Skip window if data insufficient
            pass

        # 2. Residual variant
        if run_residual:
            try:
                persisted_res = persist_residual_mst(
                    session,
                    window_end=w_end,
                    lookback_start=lookback_start,
                    data_cutoff=cutoff,
                )
                compute_and_persist_diagnostics(session, persisted_res.run_id, config=config)
                residual_run_ids.append((w_end, persisted_res.run_id))
            except Exception:
                pass

    def build_report_for_runs(
        variant_name: str,
        run_items: list[tuple[date, UUID]],
    ) -> VariantHistoryReport:
        window_stats: list[HistoryWindowStat] = []
        persistences: list[float] = []
        worst_p = 1.0
        worst_dt: date | None = None

        for w_dt, r_id in run_items:
            stab = session.scalar(select(MstStability).where(MstStability.run_id == r_id))
            if stab is not None:
                p_val = float(stab.edge_persistence)
                persistences.append(p_val)
                if p_val < worst_p:
                    worst_p = p_val
                    worst_dt = w_dt

                window_stats.append(
                    HistoryWindowStat(
                        window_end=w_dt,
                        run_id=r_id,
                        variant=variant_name,
                        edge_persistence=p_val,
                        node_overlap=float(stab.node_overlap),
                        window_gap_days=stab.window_gap_days,
                        grade=str(stab.details.get("grade"))
                        if isinstance(stab.details, dict) and "grade" in stab.details
                        else None,
                    )
                )
            else:
                window_stats.append(
                    HistoryWindowStat(
                        window_end=w_dt,
                        run_id=r_id,
                        variant=variant_name,
                        edge_persistence=None,
                        node_overlap=None,
                        window_gap_days=None,
                        grade=None,
                    )
                )

        avg_p = sum(persistences) / len(persistences) if persistences else 0.0
        worst_val = worst_p if persistences else 0.0

        return VariantHistoryReport(
            variant=variant_name,
            total_runs_evaluated=len(run_items),
            transitions_count=len(persistences),
            average_edge_persistence=round(avg_p, 4),
            worst_edge_persistence=round(worst_val, 4),
            worst_window_end=worst_dt,
            windows=window_stats,
        )

    raw_report = build_report_for_runs("raw", raw_run_ids)
    residual_report = build_report_for_runs("residual", residual_run_ids) if run_residual else None

    comparison: dict[str, Any] = {
        "raw_average_persistence": raw_report.average_edge_persistence,
        "raw_worst_persistence": raw_report.worst_edge_persistence,
    }
    if residual_report is not None:
        comparison["residual_average_persistence"] = residual_report.average_edge_persistence
        comparison["residual_worst_persistence"] = residual_report.worst_edge_persistence
        comparison["persistence_delta_residual_minus_raw"] = round(
            residual_report.average_edge_persistence - raw_report.average_edge_persistence,
            4,
        )
        comparison["more_stable_variant"] = (
            "residual"
            if residual_report.average_edge_persistence > raw_report.average_edge_persistence
            else "raw"
        )
        comparison["configured_default_variant"] = config.default_variant

    return HistoryJobResult(
        windows_requested=n_windows,
        raw_report=raw_report,
        residual_report=residual_report,
        comparison=comparison,
    )
