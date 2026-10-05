"""Run PRISM's configured APScheduler workflows, optionally for a bounded soak."""

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from backend.app.db.session import SessionLocal
from backend.app.operations.orchestration import DagTask, execute_daily_dag
from backend.app.operations.scheduler import build_scheduler
from backend.app.operations.service import load_operations_config


def _command(module: str, *arguments: str) -> Callable[[], dict[str, object]]:
    def action() -> dict[str, object]:
        completed = subprocess.run(  # noqa: S603
            [sys.executable, "-m", module, *arguments], check=True, capture_output=True, text=True
        )
        return {"exit_code": completed.returncode, "output_tail": completed.stdout[-500:]}

    return action


def run_daily() -> None:
    with SessionLocal() as session:
        config, _, fingerprint = load_operations_config(session)
        retry = dict(config["retry"])
        tasks = [
            DagTask("ingest_prices", _command("jobs.ingest_prices")),
            DagTask("crosscheck_prices", _command("jobs.crosscheck_prices")),
            DagTask("sector_divergence", _command("jobs.calculate_sector_divergence")),
            DagTask("mst", _command("jobs.calculate_mst")),
            DagTask("mst_diagnostics", _command("jobs.calculate_mst_diagnostics")),
            DagTask("macro", _command("jobs.ingest_macro")),
            DagTask("regime", _command("jobs.calculate_regime")),
            DagTask(
                "fundamentals_governance",
                _command("jobs.ingest_results", "--all-active", "--apply"),
            ),
            DagTask("stock_scores", _command("jobs.calculate_stock_scores")),
            DagTask("portfolio_reruns", _command("jobs.rerun_portfolios")),
            DagTask("alert_evaluation", _command("jobs.evaluate_alerts")),
        ]
        execute_daily_dag(
            session,
            tasks,
            configured_order=[str(item) for item in config["daily_dag"]],
            config_fingerprint=fingerprint,
            retry_attempts=int(retry["attempts"]),
            initial_wait_seconds=float(retry["initial_wait_seconds"]),
            max_wait_seconds=float(retry["max_wait_seconds"]),
        )


def run_poll() -> None:
    _command("jobs.run_incremental_poll")()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run the daily DAG once and exit")
    parser.add_argument("--soak-days", type=int, default=0, help="Keep scheduler alive for N days")
    args = parser.parse_args()
    if args.once:
        run_daily()
        return
    with SessionLocal() as session:
        config, _, _ = load_operations_config(session)
    scheduler = build_scheduler(config, run_daily, run_poll)
    scheduler.start()
    started = datetime.now(UTC)
    deadline = started + timedelta(days=args.soak_days) if args.soak_days else None
    print(f"Scheduler started at {started.isoformat()}; prices are end-of-day.")
    try:
        while deadline is None or datetime.now(UTC) < deadline:
            time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=True)


if __name__ == "__main__":
    main()
