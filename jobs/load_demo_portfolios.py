"""Load all synthetic data/demo portfolios through the public local API."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--fixture-dir", type=Path, default=Path("data/demo"))
    args = parser.parse_args()
    for path in sorted(args.fixture_dir.glob("*.csv")):
        payload = json.dumps(
            {
                "name": f"Demo - {path.stem.replace('_', ' ').title()}",
                "description": "Synthetic demonstration fixture; not investment advice.",
                "csv_content": path.read_text(encoding="utf-8"),
            }
        ).encode()
        request = Request(
            f"{args.api.rstrip('/')}/portfolios/import-csv",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit local API
            result = json.loads(response.read())
        if result.get("errors"):
            raise RuntimeError(f"{path.name}: {result['errors']}")
        print(f"Loaded {path.name}")


if __name__ == "__main__":
    main()
