"""Ingestion job for macroeconomic series (FR-D9, D4, D6)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import MacroObservation, MacroSeriesDefinition
from backend.app.db.session import SessionLocal
from backend.app.macro.adapters.base import MacroSeriesAdapter, ParsedObservation
from backend.app.macro.adapters.csv_adapter import CsvMacroAdapter
from backend.app.macro.adapters.yahoo_adapter import YahooMacroAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_macro_series(
    session: Session,
    series_keys: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    cutoff: datetime | None = None,
    adapters: list[MacroSeriesAdapter] | None = None,
) -> dict[str, int]:
    """Ingest macro observations for active series definitions.

    Returns mapping of series_key -> count of newly inserted rows.
    """
    cutoff_time = cutoff or datetime.now(UTC)

    # 1. Fetch active series from definition table
    query = select(MacroSeriesDefinition).where(MacroSeriesDefinition.is_active == True)  # noqa: E712
    if series_keys:
        query = query.where(MacroSeriesDefinition.series_key.in_(series_keys))

    series_defs = session.scalars(query).all()
    if not series_defs:
        logger.warning("No active macro series definitions found.")
        return {}

    active_keys = [s.series_key for s in series_defs]

    # Production default is Yahoo only. CSV is available only via explicit CLI input.
    adapter_chain: list[MacroSeriesAdapter] = adapters or [YahooMacroAdapter()]

    results: dict[str, int] = {k: 0 for k in active_keys}

    for key in active_keys:
        observations: list[ParsedObservation] = []
        selected_source: str | None = None
        for adapter in adapter_chain:
            try:
                obs = adapter.fetch_observations(
                    series_key=key,
                    start_date=start_date,
                    end_date=end_date,
                    cutoff=cutoff_time,
                )
                if obs:
                    observations = obs
                    selected_source = adapter.source_name
                    logger.info(
                        "Fetched %d observations for %s via %s",
                        len(obs),
                        key,
                        adapter.source_name,
                    )
                    break
            except Exception as exc:
                logger.warning("Adapter %s failed for %s: %s", adapter.source_name, key, exc)

        if not observations:
            logger.warning("No observations found for macro series %s across adapters", key)
            continue

        if selected_source not in {"YAHOO", "CSV_IMPORT"}:
            raise ValueError(f"Unsupported macro observation source: {selected_source}")

        # Load existing (obs_date, version) for idempotency (D6)
        existing_rows = session.execute(
            select(MacroObservation.obs_date, MacroObservation.version).where(
                MacroObservation.series_key == key
            )
        ).all()
        existing: set[tuple[date, int]] = {(r[0], r[1]) for r in existing_rows}

        inserted_count = 0
        for o in observations:
            if (o.obs_date, o.version) in existing:
                continue

            row = MacroObservation(
                series_key=o.series_key,
                obs_date=o.obs_date,
                value=o.value,
                published_at=o.published_at,
                ingested_at=o.ingested_at,
                source=selected_source,
                version=o.version,
            )
            session.add(row)
            existing.add((o.obs_date, o.version))
            inserted_count += 1

        session.commit()
        results[key] = inserted_count
        logger.info("Committed %d new observations for %s", inserted_count, key)

    return results


def main() -> None:
    """CLI entrypoint for macro series ingestion."""
    parser = argparse.ArgumentParser(description="Ingest macroeconomic series")
    parser.add_argument(
        "--source",
        choices=["yahoo", "csv"],
        default="yahoo",
        help="Data source (default: yahoo)",
    )
    parser.add_argument("--file", type=Path, help="Explicit CSV import file")
    parser.add_argument("--series", action="append", dest="series_keys")
    args = parser.parse_args()

    adapters: list[MacroSeriesAdapter]
    series_keys = args.series_keys
    if args.source == "csv":
        if args.file is None:
            parser.error("--source csv requires --file PATH")
        if not series_keys:
            series_keys = [args.file.stem]
        if len(series_keys) != 1:
            parser.error("An explicit CSV file can be imported for exactly one --series")
        adapters = [CsvMacroAdapter(file_path=args.file)]
    else:
        if args.file is not None:
            parser.error("--file is valid only with --source csv")
        adapters = [YahooMacroAdapter()]

    session = SessionLocal()
    try:
        counts = ingest_macro_series(session, series_keys=series_keys, adapters=adapters)
        logger.info("Macro ingestion finished: %s", counts)
    finally:
        session.close()


if __name__ == "__main__":
    main()
