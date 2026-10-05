"""Export key operational tables to timestamped CSV files without secrets."""

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import MetaData, select

from backend.app.db.session import engine

ALLOWED_TABLES = (
    "pipeline_run",
    "data_freshness",
    "alert",
    "watchlist",
    "watchlist_item",
    "score_run",
    "stock_risk_result",
    "portfolio",
    "portfolio_holding",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("exports"))
    args = parser.parse_args()
    target = args.output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target.mkdir(parents=True, exist_ok=False)
    metadata = MetaData()
    metadata.reflect(engine, only=list(ALLOWED_TABLES))
    with engine.connect() as connection:
        for name in ALLOWED_TABLES:
            table = metadata.tables[name]
            rows = connection.execute(select(table)).mappings().all()
            with (target / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=[column.name for column in table.columns]
                )
                writer.writeheader()
                writer.writerows(
                    {key: str(value) if value is not None else "" for key, value in row.items()}
                    for row in rows
                )
    print(f"Exported {len(ALLOWED_TABLES)} tables to {target}")


if __name__ == "__main__":
    main()
