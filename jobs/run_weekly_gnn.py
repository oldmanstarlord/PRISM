"""Build a point-in-time graph, infer latest structural drift and persist it."""

import argparse
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from backend.app.db.models import PriceDailyAdjusted
from backend.app.db.session import SessionLocal
from backend.app.gnn.config import GraphConfig
from backend.app.gnn.dataset import load_from_database
from backend.app.gnn.inference import infer_latest
from backend.app.gnn.persistence import persist_latest_inference


def run(start: date, run_dir: Path, calibration: Path, device: str = "cpu") -> str:
    with SessionLocal() as session:
        end = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))
        if end is None:
            raise ValueError("No adjusted market data is available")
        dataset = load_from_database(session, start, end, GraphConfig())
        payload = infer_latest(dataset, run_dir, calibration, device_name=device)
        model_run = persist_latest_inference(session, run_dir, payload)
        session.commit()
    return f"Persisted {payload['date']} structural drift for {model_run.model_version}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    print(run(args.start, args.run, args.calibration, args.device))


if __name__ == "__main__":
    main()
