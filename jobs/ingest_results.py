"""Incremental and idempotent ingestion job for financial results (FR-D9, D4, D6).

Quality checks:
- Negative equity flag
- Non-negative assets check
- Scale and sign checks
- Point-in-time versioning: restatements create new version rows, never overwrite
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.model_config import FundamentalAnalysisConfig, load_model_config
from backend.app.db.models import (
    FundamentalPeriod,
    PipelineRun,
    Security,
    SecurityAlias,
    SourceDocument,
)
from backend.app.db.session import SessionLocal
from backend.app.fundamentals.adapters.base import ResultAdapter
from backend.app.fundamentals.adapters.file_import import CsvResultAdapter, JsonResultAdapter
from backend.app.fundamentals.adapters.yfinance_adapter import YfinanceFundamentalsAdapter
from backend.app.fundamentals.metrics import compute_ttm_metrics, save_fundamental_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def ingest_results_for_security(
    session: Session,
    security: Security,
    symbol: str,
    adapter: ResultAdapter,
    config: FundamentalAnalysisConfig,
    as_of: date,
    apply: bool = False,
) -> dict[str, int]:
    """Ingest results for a single security idempotently."""
    counts = {"documents": 0, "periods_created": 0, "periods_skipped": 0, "metrics_saved": 0}
    docs = adapter.fetch_results(symbol=symbol, isin=security.isin)
    if not docs:
        logger.info("No documents returned for %s (%s)", symbol, adapter.source_tag)
        return counts

    for doc in docs:
        content_hash = doc.content_hash
        # Check if source_document already exists
        doc_stmt = select(SourceDocument).where(
            SourceDocument.security_id == security.id,
            SourceDocument.content_hash == content_hash,
        )
        existing_doc = session.scalars(doc_stmt).first()
        if existing_doc:
            doc_id = existing_doc.id
        else:
            doc_id = uuid4()
            if apply:
                new_doc = SourceDocument(
                    id=doc_id,
                    security_id=security.id,
                    source=doc.source,
                    source_doc_id=doc.source_doc_id,
                    doc_type=doc.doc_type,
                    published_at=doc.published_at,
                    published_at_method=doc.published_at_method,
                    ingested_at=datetime.now(UTC),
                    url=doc.url,
                    content_hash=content_hash,
                    raw_path=doc.raw_path,
                )
                session.add(new_doc)
            counts["documents"] += 1

        for p in doc.periods:
            # Quality checks
            extra = dict(p.extra)
            if p.total_equity is not None and p.total_equity <= 0:
                extra["negative_equity_flag"] = True
            if p.total_assets is not None and p.total_assets < 0:
                extra["negative_assets_flag"] = True

            # Check existing periods for this security, period_end, period_type, and basis
            p_stmt = (
                select(FundamentalPeriod)
                .where(
                    FundamentalPeriod.security_id == security.id,
                    FundamentalPeriod.period_end == p.period_end,
                    FundamentalPeriod.period_type == p.period_type,
                    FundamentalPeriod.basis == p.basis,
                )
                .order_by(FundamentalPeriod.version.desc())
            )
            existing_periods = session.scalars(p_stmt).all()

            if existing_periods:
                latest = existing_periods[0]
                # Compare numeric values to check if this is an identical repeat or a restatement
                matches = (
                    latest.revenue == p.revenue
                    and latest.operating_profit == p.operating_profit
                    and latest.pat == p.pat
                    and latest.interest_expense == p.interest_expense
                    and latest.total_debt == p.total_debt
                    and latest.total_equity == p.total_equity
                    and latest.total_assets == p.total_assets
                    and latest.cash_from_operations == p.cash_from_operations
                )
                if matches:
                    counts["periods_skipped"] += 1
                    continue
                # Restatement: increment version row, never overwrite!
                version = latest.version + 1
            else:
                version = 1

            if apply:
                period_row = FundamentalPeriod(
                    security_id=security.id,
                    period_end=p.period_end,
                    period_type=p.period_type,
                    basis=p.basis,
                    published_at=p.published_at,
                    published_at_method=p.published_at_method,
                    ingested_at=datetime.now(UTC),
                    version=version,
                    source_document_id=doc_id,
                    revenue=p.revenue,
                    operating_profit=p.operating_profit,
                    pat=p.pat,
                    interest_expense=p.interest_expense,
                    total_debt=p.total_debt,
                    total_equity=p.total_equity,
                    total_assets=p.total_assets,
                    cash_from_operations=p.cash_from_operations,
                    extra=extra if extra else None,
                )
                session.add(period_row)
            counts["periods_created"] += 1

    if apply:
        session.flush()

        # Recompute derived metrics point-in-time as of as_of
        from backend.app.fundamentals.metrics import get_usable_periods

        usable = get_usable_periods(
            session, security.id, as_of=as_of, basis_preference=config.default_basis_preference
        )
        metrics = compute_ttm_metrics(
            security=security,
            periods=usable,
            as_of=as_of,
            config=config,
        )
        saved = save_fundamental_metrics(
            session, security_id=security.id, as_of=as_of, metrics=metrics
        )
        counts["metrics_saved"] = len(saved)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["yahoo", "csv", "json"],
        default="yahoo",
        help="Fundamentals source adapter (default: yahoo)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to CSV or JSON file (required if source is csv or json)",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated ticker symbols to ingest (e.g. TCS,INFY,HDFCBANK)",
    )
    parser.add_argument(
        "--all-active",
        action="store_true",
        help="Ingest all active securities in database",
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="As of date for metric calculation (default: today)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (default: dry-run)",
    )
    args = parser.parse_args()

    as_of_date = date.fromisoformat(args.as_of)
    session = SessionLocal()

    try:
        # Load config
        try:
            cfg_envelope = load_model_config(session, "fundamental_analysis", approved_only=False)
            config = FundamentalAnalysisConfig(**cfg_envelope.configuration)
        except Exception:
            config = FundamentalAnalysisConfig()

        # Initialize adapter
        adapter: ResultAdapter
        if args.source == "csv":
            if not args.file or not args.file.exists():
                logger.error("CSV source requires valid --file path")
                sys.exit(1)
            adapter = CsvResultAdapter(args.file)
        elif args.source == "json":
            if not args.file or not args.file.exists():
                logger.error("JSON source requires valid --file path")
                sys.exit(1)
            adapter = JsonResultAdapter(args.file)
        else:
            adapter = YfinanceFundamentalsAdapter(
                quarterly_lag_days=config.quarterly_reporting_lag_days,
                annual_lag_days=config.annual_reporting_lag_days,
            )

        # Resolve target securities
        if args.symbols:
            target_symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
            stmt = (
                select(Security, SecurityAlias.symbol)
                .join(SecurityAlias, SecurityAlias.security_id == Security.id)
                .where(SecurityAlias.symbol.in_(target_symbols))
            )
            rows = session.execute(stmt).all()
            sec_pairs = [(r[0], r[1]) for r in rows]
        elif args.all_active:
            stmt = (
                select(Security, SecurityAlias.symbol)
                .join(SecurityAlias, SecurityAlias.security_id == Security.id)
                .where(Security.is_active.is_(True))
            )
            rows = session.execute(stmt).all()
            sec_pairs = [(r[0], r[1]) for r in rows]
        else:
            logger.error("Specify --symbols or --all-active")
            sys.exit(1)

        logger.info(
            "Starting fundamentals ingestion: source=%s, targets=%d, mode=%s",
            adapter.source_tag,
            len(sec_pairs),
            "APPLY" if args.apply else "DRY-RUN",
        )

        total_counts = {
            "documents": 0,
            "periods_created": 0,
            "periods_skipped": 0,
            "metrics_saved": 0,
        }
        for sec, sym in sec_pairs:
            c = ingest_results_for_security(
                session=session,
                security=sec,
                symbol=sym,
                adapter=adapter,
                config=config,
                as_of=as_of_date,
                apply=args.apply,
            )
            for k in total_counts:
                total_counts[k] += c[k]

        if args.apply:
            # Record PipelineRun
            run = PipelineRun(
                pipeline_name="ingest_results",
                status="completed",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                manifest={
                    "source": adapter.source_tag,
                    "target_count": len(sec_pairs),
                    "counts": total_counts,
                    "as_of": as_of_date.isoformat(),
                },
            )
            session.add(run)
            session.commit()
            logger.info("Committed fundamentals run: %s", total_counts)
        else:
            session.rollback()
            logger.info("DRY-RUN completed (no rows written): %s", total_counts)

    finally:
        session.close()


if __name__ == "__main__":
    main()
