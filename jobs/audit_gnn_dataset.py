"""Audit a frozen GNN dataset for leakage, coverage and production readiness."""

import argparse
import json
from pathlib import Path

from backend.app.gnn.audit import audit_dataset
from backend.app.gnn.dataset import read_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_dataset(read_dataset(args.dataset))
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    if not result["production_eligible"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
