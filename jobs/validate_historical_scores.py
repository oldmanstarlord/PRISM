"""Validate historical PRISM scores, baselines, ablations, confidence, and Layer 1 bands."""

import argparse
from datetime import date

from backend.app.db.session import SessionLocal
from backend.app.validation.service import SURVIVORSHIP_WARNING, run_validation


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--score-config-version", default="1.0.0")
    parser.add_argument("--validation-config-version", default="1.0.0")
    parser.add_argument("--skip-ablation", action="store_true")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")

    print(f"SURVIVORSHIP WARNING: {SURVIVORSHIP_WARNING}")
    with SessionLocal() as session:
        result = run_validation(
            session,
            args.start,
            args.end,
            score_config_version=args.score_config_version,
            validation_config_version=args.validation_config_version,
            run_ablation=not args.skip_ablation,
        )
    print(
        f"ValidationRun {result.id}: status={result.status}, period={result.period}, "
        f"metrics={len(result.results)}"
    )
    failures = result.notes.get("failures", [])
    if isinstance(failures, list):
        for failure in failures:
            print(f"FAILURE: {failure}")


if __name__ == "__main__":
    main()
