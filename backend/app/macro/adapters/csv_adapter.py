"""Explicit CSV import adapter for macroeconomic series (FR-D9)."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, time
from pathlib import Path

from backend.app.macro.adapters.base import ParsedObservation


class CsvMacroAdapter:
    """Imports macro observations from an explicitly supplied CSV path."""

    def __init__(self, base_dir: Path | None = None, file_path: Path | None = None) -> None:
        if base_dir is None and file_path is None:
            raise ValueError("CSV import requires an explicit file path or base directory")
        self.base_dir = base_dir
        self.file_path = file_path

    @property
    def source_name(self) -> str:
        return "CSV_IMPORT"

    def fetch_observations(
        self,
        series_key: str,
        start_date: date | None = None,
        end_date: date | None = None,
        cutoff: datetime | None = None,
    ) -> list[ParsedObservation]:
        file_path = self.file_path or (
            self.base_dir / f"{series_key}.csv" if self.base_dir else None
        )
        if file_path is None:
            return []
        if not file_path.exists():
            return []

        observations: list[ParsedObservation] = []
        now = datetime.now(UTC)

        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_date = row.get("date") or row.get("obs_date")
                raw_val = row.get("value") or row.get("close")
                if not raw_date or raw_val is None:
                    continue

                try:
                    obs_date = date.fromisoformat(raw_date.strip())
                    val = float(raw_val.strip())
                except ValueError:
                    continue

                if start_date and obs_date < start_date:
                    continue
                if end_date and obs_date > end_date:
                    continue

                raw_pub = row.get("published_at")
                if raw_pub:
                    try:
                        published_at = datetime.fromisoformat(raw_pub.strip())
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=UTC)
                    except ValueError:
                        published_at = datetime.combine(obs_date, time(18, 0), tzinfo=UTC)
                else:
                    # Default EOD publication: 18:00 UTC on observation date
                    published_at = datetime.combine(obs_date, time(18, 0), tzinfo=UTC)

                if cutoff and published_at > cutoff:
                    continue

                version = int(row.get("version", 1))

                observations.append(
                    ParsedObservation(
                        series_key=series_key,
                        obs_date=obs_date,
                        value=val,
                        published_at=published_at,
                        ingested_at=now,
                        version=version,
                    )
                )

        observations.sort(key=lambda o: (o.obs_date, o.version))
        return observations
