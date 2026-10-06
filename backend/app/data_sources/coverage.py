"""Honest live-data coverage calculations for the Data Health page and evidence report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, date, datetime
from statistics import median
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from backend.app.data_sources.schemas import (
    DataCoverageOut,
    DatasetCoverageOut,
    DimensionCoverageOut,
    ScoreCoverageSummaryOut,
)
from backend.app.data_sources.service import list_data_sources
from backend.app.db.models import (
    BenchmarkSeries,
    CorporateAction,
    EventItem,
    FundamentalPeriod,
    InsiderTrade,
    MacroObservation,
    NewsItem,
    PriceDailyRaw,
    ScoreComponentValue,
    ScoreRun,
    Security,
    SecurityShareCount,
    ShareholdingPattern,
    SourceDocument,
    StockRiskResult,
)
from backend.app.policy.provenance import VERIFIED_NEWS_SOURCE_MAP
from backend.app.risk_score.coverage import COVERAGE_MATRIX, REQUIRED_DIMENSIONS

VALID_COVERAGE_STATUSES = ("ok", "stale", "missing", "insufficient")


def combine_component_statuses(statuses: Iterable[str]) -> str:
    """Reduce component statuses to a stock/dimension coverage classification."""
    normalized = ["ok" if status == "flagged" else status for status in statuses]
    if not normalized or all(status == "missing" for status in normalized):
        return "missing"
    if any(status == "stale" for status in normalized):
        return "stale"
    if all(status == "ok" for status in normalized):
        return "ok"
    return "insufficient"


def summarize_status_counts(
    statuses: Iterable[str], total: int
) -> tuple[dict[str, int], dict[str, float]]:
    """Count canonical statuses and explicitly account for absent stocks as missing."""
    counts = Counter(statuses)
    observed = sum(counts[status] for status in VALID_COVERAGE_STATUSES)
    counts["missing"] += max(0, total - observed)
    count_map = {status: counts[status] for status in VALID_COVERAGE_STATUSES}
    shares = {
        status: round(count_map[status] / total, 4) if total else 0.0
        for status in VALID_COVERAGE_STATUSES
    }
    return count_map, shares


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _aggregate(
    session: Session,
    model: type,
    date_column: Any,
    *filters: Any,
    security_column: Any | None = None,
) -> tuple[int, date | None, date | None, int]:
    columns = [func.count(), func.min(date_column), func.max(date_column)]
    if security_column is not None:
        columns.append(func.count(distinct(security_column)))
    row = session.execute(select(*columns).select_from(model).where(*filters)).one()
    return int(row[0]), _as_date(row[1]), _as_date(row[2]), int(row[3]) if len(row) > 3 else 0


def _dataset_stats(
    session: Session, source_key: str, universe_size: int
) -> tuple[int, date | None, date | None, int, int, str | None]:
    """Return rows, dates, covered, minimum rows, and an explicit limitation."""
    if source_key == "universe_nifty200":
        count = int(
            session.scalar(
                select(func.count()).select_from(Security).where(Security.is_active.is_(True))
            )
            or 0
        )
        return (
            count,
            None,
            None,
            count,
            1,
            "Current membership only; historical survivorship remains unavailable.",
        )
    if source_key == "prices_yahoo":
        rows, first, last, covered = _aggregate(
            session,
            PriceDailyRaw,
            PriceDailyRaw.trade_date,
            PriceDailyRaw.source.in_(("yfinance", "YAHOO", "YAHOO_FINANCE")),
            security_column=PriceDailyRaw.security_id,
        )
        return rows, first, last, covered, 252, None
    if source_key == "benchmark_yahoo":
        rows, first, last, _ = _aggregate(
            session,
            BenchmarkSeries,
            BenchmarkSeries.trade_date,
            BenchmarkSeries.source.ilike("%yahoo%"),
        )
        return (
            rows,
            first,
            last,
            universe_size if rows else 0,
            252,
            "Yahoo benchmark failed the strict calendar/correlation/freshness import gate.",
        )
    if source_key == "corporate_actions_yahoo":
        rows, first, last, _ = _aggregate(
            session,
            CorporateAction,
            CorporateAction.ex_date,
            CorporateAction.source.in_(("yfinance", "YAHOO", "YAHOO_FINANCE")),
        )
        return (
            rows,
            first,
            last,
            universe_size if rows else 0,
            1,
            "No row is expected for a security with no corporate action.",
        )
    if source_key == "fundamentals_yahoo":
        stmt = (
            select(
                func.count(FundamentalPeriod.id),
                func.min(FundamentalPeriod.period_end),
                func.max(FundamentalPeriod.period_end),
                func.count(distinct(FundamentalPeriod.security_id)),
            )
            .join(SourceDocument, FundamentalPeriod.source_document_id == SourceDocument.id)
            .where(SourceDocument.source == "YAHOO_FUNDAMENTALS")
        )
        row = session.execute(stmt).one()
        return (
            int(row[0]),
            row[1],
            row[2],
            int(row[3]),
            4,
            "Publication dates from Yahoo are explicitly estimated.",
        )
    if source_key == "announcements_nse_manual":
        stmt = (
            select(
                func.count(EventItem.id),
                func.min(EventItem.published_at),
                func.max(EventItem.published_at),
                func.count(distinct(EventItem.security_id)),
            )
            .join(SourceDocument, EventItem.source_document_id == SourceDocument.id)
            .where(SourceDocument.source == "NSE_MANUAL_IMPORT")
        )
        row = session.execute(stmt).one()
        return (
            int(row[0]),
            _as_date(row[1]),
            _as_date(row[2]),
            int(row[3]),
            1,
            "Coverage is limited to the supplied official export window.",
        )
    if source_key == "shareholding_nse_manual":
        rows, first, last, covered = _aggregate(
            session,
            ShareholdingPattern,
            ShareholdingPattern.quarter_end,
            ShareholdingPattern.source.like("NSE_MANUAL_IMPORT%"),
            security_column=ShareholdingPattern.security_id,
        )
        return (
            rows,
            first,
            last,
            covered,
            2,
            "Requires the normalized fields documented in DATA_SOURCES.md.",
        )
    if source_key == "shares_outstanding_nse_manual":
        rows, first, last, covered = _aggregate(
            session,
            SecurityShareCount,
            SecurityShareCount.as_of,
            SecurityShareCount.source.like("NSE_MANUAL_IMPORT%"),
            security_column=SecurityShareCount.security_id,
        )
        return (
            rows,
            first,
            last,
            covered,
            1,
            "Requires an official export containing total shares outstanding.",
        )
    if source_key == "insider_trades_nse_manual":
        rows, first, last, covered = _aggregate(
            session,
            InsiderTrade,
            InsiderTrade.txn_date,
            InsiderTrade.source.like("NSE_MANUAL_IMPORT%"),
            security_column=InsiderTrade.security_id,
        )
        return (
            rows,
            first,
            last,
            covered,
            1,
            "Requires normalized transaction fields, not XBRL links alone.",
        )
    if source_key in {"news_rbi_rss", "news_sebi_rss", "news_pib_rss"}:
        source = {
            "news_rbi_rss": VERIFIED_NEWS_SOURCE_MAP["RBI"],
            "news_sebi_rss": VERIFIED_NEWS_SOURCE_MAP["SEBI"],
            "news_pib_rss": "PIB",
        }[source_key]
        rows, first, last, _ = _aggregate(
            session, NewsItem, NewsItem.published_at, NewsItem.source == source
        )
        if source == "PIB":
            return 0, None, None, 0, 1, "PIB is not enabled as a verified production feed."
        limitation = None
        return rows, first, last, universe_size if rows else 0, 1, limitation
    if source_key == "policy_finance_ministry":
        return (
            0,
            None,
            None,
            0,
            1,
            "A separately verified official feed or documented manual export is required.",
        )
    if source_key.startswith("macro_"):
        key = source_key.removeprefix("macro_").removesuffix("_yahoo")
        if source_key == "macro_fii_dii_manual":
            key = "fii_dii_net_flows"
            source_filter = MacroObservation.source == "CSV_IMPORT"
            limitation = (
                "A dated official monthly/daily export with publication timestamps is required."
            )
        else:
            source_filter = MacroObservation.source == "YAHOO"
            limitation = None
        rows, first, last, _ = _aggregate(
            session,
            MacroObservation,
            MacroObservation.obs_date,
            MacroObservation.series_key == key,
            source_filter,
        )
        return rows, first, last, universe_size if rows else 0, 30, limitation
    return 0, None, None, 0, 1, "No coverage mapping is implemented for this registered dataset."


def _score_summary(session: Session, run: ScoreRun) -> ScoreCoverageSummaryOut | None:
    rows = session.execute(
        select(StockRiskResult.total_score, StockRiskResult.confidence).where(
            StockRiskResult.run_id == run.id
        )
    ).all()
    if not rows:
        return None
    return ScoreCoverageSummaryOut(
        run_id=str(run.id),
        as_of_date=run.as_of_date,
        config_version=run.config_version,
        median_risk=round(float(median(float(row[0]) for row in rows)), 4),
        median_confidence=round(float(median(float(row[1]) for row in rows)), 4),
    )


def _dimension_coverage(
    session: Session, run: ScoreRun | None, universe_size: int
) -> list[DimensionCoverageOut]:
    if run is None:
        return [
            DimensionCoverageOut(
                dimension=dimension,
                total_stocks=universe_size,
                ok=0,
                stale=0,
                missing=universe_size,
                insufficient=0,
                shares={"ok": 0.0, "stale": 0.0, "missing": 1.0, "insufficient": 0.0},
            )
            for dimension in REQUIRED_DIMENSIONS
        ]

    rows = session.execute(
        select(
            ScoreComponentValue.security_id,
            ScoreComponentValue.component_id,
            ScoreComponentValue.status,
        ).where(ScoreComponentValue.run_id == run.id)
    ).all()
    by_security: dict[object, dict[str, list[str]]] = {}
    component_dimension = {
        component: dimension
        for dimension, coverage in COVERAGE_MATRIX.items()
        for component in coverage.active_components
    }
    for row_security_id, component_id, status in rows:
        dimension = component_dimension.get(component_id)
        if dimension:
            by_security.setdefault(row_security_id, {}).setdefault(dimension, []).append(status)

    output: list[DimensionCoverageOut] = []
    for dimension in REQUIRED_DIMENSIONS:
        stock_statuses: list[str] = []
        for covered_security_id in by_security:
            stock_statuses.append(
                combine_component_statuses(by_security[covered_security_id].get(dimension, []))
            )
        counts, shares = summarize_status_counts(stock_statuses, universe_size)
        output.append(
            DimensionCoverageOut(
                dimension=dimension,
                total_stocks=universe_size,
                ok=counts["ok"],
                stale=counts["stale"],
                missing=counts["missing"],
                insufficient=counts["insufficient"],
                shares=shares,
            )
        )
    return output


def build_data_coverage(session: Session) -> DataCoverageOut:
    universe_size = int(
        session.scalar(
            select(func.count()).select_from(Security).where(Security.is_active.is_(True))
        )
        or 0
    )
    registry = {item.source_key: item for item in list_data_sources(session)}
    datasets: list[DatasetCoverageOut] = []
    for source_key, item in sorted(registry.items(), key=lambda pair: (pair[1].dataset, pair[0])):
        rows, first, last, covered, minimum_rows, limitation = _dataset_stats(
            session, source_key, universe_size
        )
        data_status = "real" if rows else "missing"
        share = covered / universe_size if universe_size else 0.0
        if not rows:
            coverage_status = "missing"
        elif item.freshness_status == "stale":
            coverage_status = "stale"
        elif rows < minimum_rows or (
            covered < universe_size
            and source_key
            in {
                "fundamentals_yahoo",
                "announcements_nse_manual",
                "shareholding_nse_manual",
                "shares_outstanding_nse_manual",
            }
        ):
            coverage_status = "insufficient"
        else:
            coverage_status = "ok"
        datasets.append(
            DatasetCoverageOut(
                source_key=source_key,
                dataset=item.dataset,
                source=item.owner,
                data_status=data_status,
                coverage_status=coverage_status,
                rows=rows,
                first_date=first,
                last_date=last,
                universe_covered=min(covered, universe_size),
                universe_total=universe_size,
                universe_share=round(min(share, 1.0), 4),
                staleness=item.freshness_status,
                limitations=limitation or item.notes,
            )
        )

    latest_run = session.scalars(
        select(ScoreRun)
        .where(ScoreRun.status == "completed", ScoreRun.config_version == "1.0.0")
        .order_by(ScoreRun.completed_at.desc())
        .limit(1)
    ).first()
    previous_run = None
    if latest_run is not None:
        previous_run = session.scalars(
            select(ScoreRun)
            .where(
                ScoreRun.status == "completed",
                ScoreRun.config_version == "1.0.0",
                ScoreRun.as_of_date < latest_run.as_of_date,
            )
            .order_by(ScoreRun.as_of_date.desc(), ScoreRun.completed_at.desc())
            .limit(1)
        ).first()
    return DataCoverageOut(
        generated_at=datetime.now(UTC),
        universe_size=universe_size,
        datasets=datasets,
        dimensions=_dimension_coverage(session, latest_run, universe_size),
        previous_score=_score_summary(session, previous_run) if previous_run else None,
        latest_score=_score_summary(session, latest_run) if latest_run else None,
    )
