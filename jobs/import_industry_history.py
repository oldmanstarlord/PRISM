"""Import effective-dated security industry history from a reviewed CSV file."""

import argparse
import csv
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.db.models import SecurityAlias, SecurityIndustryHistory
from backend.app.db.session import SessionLocal


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value.strip() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Commit after validation")
    args = parser.parse_args()
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    required = {"symbol", "industry", "valid_from", "valid_to", "source", "known_at"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"CSV must contain columns: {', '.join(sorted(required))}")
    inserted = 0
    with SessionLocal() as session:
        for row in rows:
            symbol = row["symbol"].strip().upper()
            valid_from = _date(row["valid_from"])
            valid_to = _date(row["valid_to"])
            if valid_from is None or (valid_to is not None and valid_to < valid_from):
                raise ValueError(f"Invalid effective dates for {symbol}")
            alias = session.scalar(
                select(SecurityAlias)
                .where(
                    SecurityAlias.symbol == symbol,
                    SecurityAlias.exchange == "NSE",
                    SecurityAlias.valid_from <= valid_from,
                    (SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= valid_from)),
                )
                .limit(1)
            )
            if alias is None:
                raise ValueError(f"No effective NSE alias found for {symbol} on {valid_from}")
            existing = session.scalar(
                select(SecurityIndustryHistory).where(
                    SecurityIndustryHistory.security_id == alias.security_id,
                    SecurityIndustryHistory.valid_from == valid_from,
                )
            )
            values = {
                "industry": row["industry"].strip(),
                "sector": row.get("sector", "").strip() or None,
                "valid_to": valid_to,
                "source": row["source"].strip(),
            }
            known_at = datetime.fromisoformat(row["known_at"].strip().replace("Z", "+00:00"))
            if known_at.tzinfo is None or known_at.utcoffset() is None:
                raise ValueError(f"known_at must be timezone-aware for {symbol}")
            if not values["industry"] or not values["source"]:
                raise ValueError(f"Industry and source are required for {symbol}")
            if existing:
                if any(getattr(existing, key) != value for key, value in values.items()):
                    raise ValueError(f"Conflicting existing industry history for {symbol}")
                continue
            session.add(
                SecurityIndustryHistory(
                    security_id=alias.security_id,
                    valid_from=valid_from,
                    # `known_at` is the source publication/observation timestamp,
                    # not the time this import command happened to run.
                    ingested_at=known_at.astimezone(UTC),
                    **values,
                )
            )
            inserted += 1
        if args.apply:
            session.commit()
        else:
            session.rollback()
    print(f"Validated {len(rows)} rows; {'inserted' if args.apply else 'would insert'} {inserted}.")


if __name__ == "__main__":
    main()
