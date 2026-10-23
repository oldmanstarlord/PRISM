"""Publish a validated GNN run and its immutable drift outputs to PostgreSQL."""

import argparse
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.gnn.persistence import publish_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    args = parser.parse_args()
    with SessionLocal() as session:
        model_run = publish_analysis(session, args.run, args.analysis, args.evaluation)
        session.commit()
    print(f"Published {model_run.model_name} {model_run.model_version} as {model_run.status}")


if __name__ == "__main__":
    main()
