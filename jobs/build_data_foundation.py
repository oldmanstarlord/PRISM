"""Build the verified, five-year NIFTY 200 data foundation and coverage report."""

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.db.models import PipelineRun, PriceDailyAdjusted, SecurityAlias
from backend.app.db.session import SessionLocal
from backend.app.market_data.foundation import (
    calculate_and_persist_daily_metrics,
    coverage_payload,
    fetch_and_persist_fundamentals,
    persist_coverage_report,
    reproducible_spot_checks,
)
from backend.app.market_data.service import ensure_nifty50_benchmark, ingest_nifty200_prices
from backend.app.market_data.yahoo import YahooFinanceClient
from backend.app.universe.nifty200 import (
    NIFTY_200_URL,
    fetch_constituent_csv,
    import_constituents,
    parse_constituents,
    verify_yfinance_aliases,
)


def five_year_start(end: date) -> date:
    try:
        return end.replace(year=end.year - 5)
    except ValueError:
        return end.replace(year=end.year - 5, day=28)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-fundamentals", action="store_true")
    args = parser.parse_args()
    client = YahooFinanceClient()

    csv_text = fetch_constituent_csv()
    constituents = parse_constituents(csv_text)
    snapshot = Path("data/raw/nifty200") / f"{args.as_of.isoformat()}.csv"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(csv_text, encoding="utf-8")

    with SessionLocal() as session:
        import_constituents(session, constituents, effective_date=args.as_of, source=NIFTY_200_URL)
        verification = verify_yfinance_aliases(session, as_of=args.as_of, client=client)
        benchmark = ensure_nifty50_benchmark(session, args.as_of)
        benchmark_alias = session.scalar(
            select(SecurityAlias).where(SecurityAlias.security_id == benchmark.security_id)
        )
        benchmark_ok, benchmark_reason = client.verify("^NSEI", args.as_of)
        if benchmark_alias is not None:
            benchmark_alias.verification_status = "verified" if benchmark_ok else "failed"
            benchmark_alias.verification_reason = benchmark_reason
            benchmark_alias.verified_at = datetime.now(UTC)
        session.commit()

        summary = ingest_nifty200_prices(
            session,
            start=five_year_start(args.as_of),
            end=args.as_of,
            snapshot_root=Path("data/raw/yfinance"),
            client=client,
            max_workers=args.workers,
        )
        if summary.run_id is None:
            raise RuntimeError("Ingestion did not return a pipeline run ID")
        run_id = summary.run_id
        try:
            calculate_and_persist_daily_metrics(session, run_id=run_id, as_of=args.as_of)
            fundamental_failures = (
                {item.symbol: "fundamentals_fetch_skipped" for item in constituents}
                if args.skip_fundamentals
                else fetch_and_persist_fundamentals(session, as_of=args.as_of, client=client)
            )
            instruments = {
                alias.symbol: alias.security_id
                for alias in session.scalars(
                    select(SecurityAlias).where(
                        SecurityAlias.symbol.in_([item.symbol for item in constituents]),
                        SecurityAlias.valid_to.is_(None),
                    )
                ).all()
            }
            latest_values: dict[str, float] = {}
            for symbol, security_id in instruments.items():
                row = session.scalar(
                    select(PriceDailyAdjusted)
                    .where(PriceDailyAdjusted.security_id == security_id)
                    .order_by(
                        PriceDailyAdjusted.trade_date.desc(), PriceDailyAdjusted.computed_at.desc()
                    )
                    .limit(1)
                )
                if row is not None:
                    latest_values[symbol] = float(row.adjusted_close)
            spot_checks = reproducible_spot_checks(
                list(instruments),
                as_of=args.as_of,
                second_source=None,
                primary_values=latest_values,
            )
            coverage = persist_coverage_report(
                session,
                run_id=run_id,
                as_of=args.as_of,
                spot_checks=spot_checks,
                fundamental_failures=fundamental_failures,
            )
            run = session.get(PipelineRun, run_id)
            if run is not None:
                run.quality_summary = {
                    **(run.quality_summary or {}),
                    "coverage": coverage_payload(coverage),
                    "verified_tickers": verification.verified,
                }
            session.commit()
        except Exception:
            session.rollback()
            run = session.get(PipelineRun, run_id)
            if run is not None:
                run.status = "failed"
                run.completed_at = datetime.now(UTC)
                run.error_summary = "Data-foundation publication failed; derived rows rolled back"
                session.commit()
            raise
        print(json.dumps(coverage_payload(coverage), default=str, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
