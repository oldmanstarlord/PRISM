import argparse
from datetime import date
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.universe.nifty200 import (
    NIFTY_200_URL,
    fetch_constituent_csv,
    import_constituents,
    parse_constituents,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the official current NIFTY 200 snapshot")
    parser.add_argument(
        "--effective-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Date on which PRISM first treats this observed composition as effective",
    )
    args = parser.parse_args()

    csv_text = fetch_constituent_csv()
    constituents = parse_constituents(csv_text)

    snapshot_path = Path("data/raw/nifty200") / f"{args.effective_date.isoformat()}.csv"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(csv_text, encoding="utf-8")

    with SessionLocal.begin() as session:
        result = import_constituents(
            session,
            constituents,
            effective_date=args.effective_date,
            source=NIFTY_200_URL,
        )
    print(result)


if __name__ == "__main__":
    main()

