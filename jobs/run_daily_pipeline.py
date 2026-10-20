"""Run the fail-closed daily PRISM ingestion and analysis workflow."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.pipeline.service import run_daily_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2015, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Publish from the latest stored validated snapshot without calling the provider",
    )
    parser.add_argument(
        "--skip-ml",
        action="store_true",
        help="Skip the ML risk models training/inference stage",
    )
    args = parser.parse_args()
    with SessionLocal() as session:
        result = run_daily_pipeline(
            session,
            start=args.start,
            end=args.end,
            snapshot_root=Path("data/raw/yfinance"),
            max_workers=args.workers,
            skip_ingestion=args.skip_ingestion,
        )
    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
    if result.status != "completed":
        raise SystemExit(1)

    if not args.skip_ml:
        from backend.app.db.models import PipelineRun
        from jobs.run_ml_inference import run_daily_inference

        try:
            ml_results = run_daily_inference(cutoff=result.published_market_date)
            failures = sum(
                int(value.get("failed", 0))
                for value in ml_results.values()
                if isinstance(value, dict)
            )
            errors = {key: value for key, value in ml_results.items() if key.endswith("_error")}
            if failures or errors:
                with SessionLocal() as session:
                    run = session.get(PipelineRun, result.run_id)
                    if run is not None:
                        run.status = "failed"
                        run.quality_summary = {
                            **(run.quality_summary or {}),
                            "stage": "ml_inference",
                            "published": False,
                        }
                        run.error_summary = json.dumps(ml_results, default=str, sort_keys=True)
                        session.commit()
                raise SystemExit(1)
            print(json.dumps({"ml_inference": ml_results}, indent=2, sort_keys=True))
        except Exception as exc:
            with SessionLocal() as session:
                run = session.get(PipelineRun, result.run_id)
                if run is not None:
                    run.status = "failed"
                    run.quality_summary = {
                        **(run.quality_summary or {}),
                        "stage": "ml_inference",
                        "published": False,
                    }
                    run.error_summary = f"{type(exc).__name__}: {exc}"
                    session.commit()
            raise


if __name__ == "__main__":
    main()
