"""Training and walk-forward validation CLI for PRISM ML risk models."""

import argparse
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from backend.app.db.models import ModelRun
from backend.app.db.session import SessionLocal
from backend.app.ml.models.anomaly_detector import AnomalyDetector
from backend.app.ml.models.market_regime import MarketRegimeDetector
from backend.app.ml.models.risk_score_validator import RiskScoreValidator
from backend.app.ml.models.volatility_forecast import VolatilityForecaster
from backend.app.ml.registry import ModelRegistry
from backend.app.portfolio_analytics.stock_risk import (
    _load_stock_prices_from_db,
    _load_stock_prices_yfinance,
    get_benchmark_returns,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_all_models(
    cutoff_date: date | None = None,
    save_to_db: bool = True,
    models_dir: Path | None = None,
) -> dict[str, object]:
    """Train, validate walk-forward, and persist model cards for all ML risk models."""
    registry = ModelRegistry(models_dir=models_dir)
    results: dict[str, object] = {}
    cutoff_dt = (
        datetime.now(UTC)
        if cutoff_date is None
        else datetime.combine(cutoff_date, datetime.min.time(), tzinfo=UTC)
    )

    with SessionLocal() as session:
        # Load benchmark returns
        logger.info("Loading benchmark returns for ML model evaluation...")
        bench_returns = get_benchmark_returns(session)
        if bench_returns.empty or len(bench_returns) < 84:
            logger.warning("Benchmark returns unavailable via DB; falling back to yfinance ^NSEI")
            yf_df = _load_stock_prices_yfinance(["^NSEI"], period="2y")
            if not yf_df.empty:
                bench_returns = yf_df["^NSEI"].pct_change().dropna()

        if bench_returns.empty:
            raise RuntimeError(
                "Cannot train models: benchmark return data is completely unavailable."
            )

        synth_prices = (1.0 + bench_returns).cumprod() * 1000.0

        # 1. Volatility Forecaster (Model A)
        logger.info("Evaluating Volatility Forecaster (Model A)...")
        vol_forecaster = VolatilityForecaster()
        vol_res, vol_card = vol_forecaster.train_and_evaluate(synth_prices, bench_returns)
        registry.save_card(vol_card)
        results["volatility_forecast"] = vol_card

        # 2. Market Regime Detector (Model B)
        logger.info("Evaluating Market Regime Detector (Model B)...")
        regime_detector = MarketRegimeDetector()
        regime_res, regime_card = regime_detector.fit_predict(bench_returns)
        registry.save_card(regime_card)
        results["market_regime"] = regime_card

        # 3. Anomaly Detector (Model C)
        logger.info("Evaluating Anomaly Detector (Model C)...")
        sample_symbols = [
            "RELIANCE",
            "TCS",
            "INFY",
            "HDFCBANK",
            "ICICIBANK",
            "ITC",
            "LT",
            "BHARTIARTL",
        ]
        prices_df = _load_stock_prices_from_db(session, sample_symbols, days=250)
        if prices_df.empty or len(prices_df.columns) < 3:
            prices_df = _load_stock_prices_yfinance(sample_symbols, period="1y")

        anomaly_detector = AnomalyDetector()
        if not prices_df.empty:
            anomaly_res, anomaly_card = anomaly_detector.detect_anomalies(prices_df, bench_returns)
            registry.save_card(anomaly_card)
            results["anomaly_detector"] = anomaly_card
        else:
            logger.warning("Prices df empty; skipping anomaly detector card persistence")

        # 4. Risk Score Validator (Model D)
        logger.info("Evaluating Heuristic Risk Score Validator (Model D)...")
        roll_vol = bench_returns.rolling(60, min_periods=20).std() * (252.0**0.5)
        norm_vol = (roll_vol - 0.10) / (0.35 - 0.10) * 100.0
        norm_vol = norm_vol.clip(0, 100).fillna(50.0).values

        score_validator = RiskScoreValidator()
        score_res, score_card = score_validator.validate_score(norm_vol, synth_prices)
        registry.save_card(score_card)
        results["risk_score_validator"] = score_card

        # Save to database if requested
        if save_to_db:
            logger.info("Recording model run records in database...")
            for model_key, card_dict in results.items():
                if isinstance(card_dict, dict):
                    m_run = ModelRun(
                        model_name=str(card_dict.get("model_name", model_key)),
                        model_version=str(card_dict.get("model_version", "1.0.0")),
                        data_cutoff=cutoff_dt,
                        training_window_start=date.fromisoformat(
                            str(card_dict.get("training_window_start", "2024-01-01"))
                        ),
                        training_window_end=date.fromisoformat(
                            str(card_dict.get("training_window_end", "2026-01-01"))
                        ),
                        features=list(card_dict.get("features", [])),
                        hyperparameters=dict(card_dict.get("hyperparameters", {})),
                        metrics=dict(card_dict.get("metrics_vs_baseline", {})),
                        configuration_hash=str(
                            card_dict.get("configuration_fingerprint", "default")
                        ),
                        status="completed",
                    )
                    session.add(m_run)
            session.commit()
            logger.info("Model run records committed successfully.")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cutoff", type=date.fromisoformat, default=None, help="Data cutoff date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--no-db", action="store_true", help="Do not write model run records to database"
    )
    args = parser.parse_args()

    results = train_all_models(cutoff_date=args.cutoff, save_to_db=not args.no_db)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
