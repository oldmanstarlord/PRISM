"""Scheduled, point-in-time training and validation for PRISM risk models."""

import argparse
import json
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import select

from backend.app.db.models import ModelRun, StockMetricDaily
from backend.app.db.session import SessionLocal
from backend.app.ml.artifacts import VolatilityArtifactBundle
from backend.app.ml.models.anomaly_detector import AnomalyDetector
from backend.app.ml.models.market_regime import MarketRegimeDetector
from backend.app.ml.models.pooled_volatility import PooledVolatilityForecaster
from backend.app.ml.models.volatility_forecast import VolatilityForecaster
from backend.app.ml.registry import ModelCard, ModelRegistry
from backend.app.ml.risk_score_panel import validate_cross_sectional_panel
from backend.app.ml.training_data import cutoff_datetime, load_validated_market_data

LIBRARY_VERSIONS = {
    name: version(name) for name in ("numpy", "pandas", "scikit-learn", "statsmodels")
}


def _date(value: object | None) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value is not None else None


def _persist_run(session: Any, card: ModelCard) -> ModelRun:
    if card.data_cutoff is None:
        raise ValueError("model_run_requires_observed_data_cutoff")
    cutoff = _date(card.data_cutoff)
    if cutoff is None:
        raise ValueError("model_run_requires_observed_data_cutoff")
    run = ModelRun(
        model_name=card.name,
        model_version=card.version,
        model_type=card.type,
        data_cutoff=cutoff_datetime(cutoff),
        training_window_start=_date(card.training_start),
        training_window_end=_date(card.training_end),
        validation_window_start=_date(card.validation_start),
        validation_window_end=_date(card.validation_end),
        test_window_start=_date(card.test_start),
        test_window_end=_date(card.test_end),
        features=card.features,
        feature_schema_version=card.feature_schema_version,
        preprocessing=card.preprocessing,
        hyperparameters=card.hyperparameters,
        metrics=card.metrics_vs_baseline,
        baseline_comparison={
            "definition": card.baseline_definition,
            "selection_reason": card.selection_reason,
        },
        configuration_hash=card.configuration_hash,
        methodology_version=card.methodology_version,
        source_data_version=card.source_data_version,
        artifact_path=card.artifact_path,
        artifact_checksum=card.artifact_checksum,
        library_versions=card.library_versions,
        model_selected=card.model_selected,
        selection_reason=card.selection_reason,
        status=card.status,
        trained_at=datetime.fromisoformat(card.trained_at),
        completed_at=datetime.now(UTC),
        error_summary=card.failure_reason,
    )
    session.add(run)
    session.flush()
    return run


def _decorate(metadata: dict[str, Any], source_version: str) -> dict[str, Any]:
    cutoff = metadata.get("data_cutoff")
    base_version = str(metadata.get("version", "2.0.0"))
    version = (
        f"{base_version}-{str(cutoff)[:10].replace('-', '')}"
        if cutoff is not None
        else base_version
    )
    return {
        **metadata,
        "version": version,
        "source_data_version": source_version,
        "library_versions": LIBRARY_VERSIONS,
    }


def _train_volatility(data: Any, registry: ModelRegistry) -> ModelCard:
    benchmark_returns = data.benchmark_prices.pct_change(fill_method=None).dropna()
    per_stock: dict[str, VolatilityForecaster] = {}
    per_stock_cards: dict[str, dict[str, Any]] = {}
    unavailable = dict(data.excluded_reasons)
    for symbol in sorted(data.prices.columns):
        forecaster = VolatilityForecaster(min_train_size=252, test_size=63)
        result, card = forecaster.train_and_evaluate(
            data.prices[symbol].dropna(),
            benchmark_returns,
            data.volumes[symbol].dropna() if symbol in data.volumes else None,
        )
        if result.status in {"ready", "baseline_selected"}:
            per_stock[symbol] = forecaster
            per_stock_cards[symbol] = card
        else:
            unavailable[symbol] = result.failure_reason or "insufficient_data"
    pooled: PooledVolatilityForecaster | None = PooledVolatilityForecaster()
    try:
        pooled_card = pooled.fit(data.prices, data.volumes, benchmark_returns)
    except (TypeError, ValueError) as exc:
        pooled = None
        pooled_card = {
            "status": "insufficient_data",
            "failure_reason": f"{type(exc).__name__}: {exc}",
            "features": [],
            "training_start": None,
            "training_end": None,
            "validation_start": None,
            "validation_end": None,
            "test_start": None,
            "test_end": None,
        }
    if not per_stock and pooled is None:
        raise ValueError("no_individual_or_pooled_volatility_model_passed_validation")
    selection: dict[str, str] = {}
    for symbol in per_stock:
        card = per_stock_cards[symbol]
        selected = str(card["model_selected"])
        individual_qlike = float(
            card["metrics_vs_baseline"]["validation"][selected]["qlike"]
        )
        pooled_qlike = (
            pooled.validation_qlike_by_symbol.get(symbol) if pooled is not None else None
        )
        selection[symbol] = (
            "individual"
            if pooled_qlike is None or individual_qlike <= pooled_qlike
            else "pooled"
        )
    if pooled is not None:
        for symbol in pooled.symbols:
            if symbol not in selection:
                selection[symbol] = "pooled"
                unavailable.pop(symbol, None)
    bundle = VolatilityArtifactBundle(per_stock, pooled, selection, unavailable)
    statuses = [str(card["status"]) for card in per_stock_cards.values()]
    status = (
        "ready"
        if "ready" in statuses or pooled_card["status"] == "ready"
        else "baseline_selected"
    )
    metadata = _decorate(
        {
            "name": "volatility_forecast_21d",
            "version": "2.0.0",
            "type": "individual and pooled supervised volatility regressors",
            "status": status,
            "data_cutoff": str(data.data_cutoff),
            "training_start": pooled_card["training_start"] or min(
                card["training_start"] for card in per_stock_cards.values()
            ),
            "training_end": pooled_card["training_end"] or max(
                card["training_end"] for card in per_stock_cards.values()
            ),
            "validation_start": pooled_card["validation_start"],
            "validation_end": pooled_card["validation_end"],
            "test_start": pooled_card["test_start"],
            "test_end": pooled_card["test_end"],
            "features": pooled_card["features"] or sorted(
                {feature for card in per_stock_cards.values() for feature in card["features"]}
            ),
            "feature_schema_version": "volatility-features-v2",
            "preprocessing": {"imputation": None, "scaling": None},
            "hyperparameters": {"random_seed": 42, "horizon": 21},
            "random_seed": 42,
            "baseline_definition": ["trailing_21d", "ewma_0.94", "har_1d_5d_21d"],
            "metrics_vs_baseline": {
                "pooled": pooled_card,
                "per_symbol_feature_schemas": {
                    symbol: card["features"]
                    for symbol, card in sorted(per_stock_cards.items())
                },
                "individual_models_ready": len(per_stock),
                "individual_selected": sum(value == "individual" for value in selection.values()),
                "pooled_selected": sum(value == "pooled" for value in selection.values()),
                "insufficient_data": unavailable,
            },
            "model_selected": "per_symbol_validation_selection",
            "selection_reason": "minimum validation QLIKE; test period untouched",
            "methodology_version": "ml-risk-v2",
        },
        data.source_data_version,
    )
    return registry.save_artifact_and_card(bundle, metadata)


def _regime_stability(returns: Any) -> float | None:
    if len(returns) < 300:
        return None
    left, _ = MarketRegimeDetector().fit_predict(returns.iloc[:-21])
    right, _ = MarketRegimeDetector().fit_predict(returns.iloc[21:])
    if left.status != "ready" or right.status != "ready":
        return None
    left_states = {item["date"]: item["regime"] for item in left.recent_timeline}
    right_states = {item["date"]: item["regime"] for item in right.recent_timeline}
    common = sorted(left_states.keys() & right_states.keys())
    if not common:
        return None
    return float(np.mean([left_states[day] == right_states[day] for day in common]))


def _train_regime(data: Any, registry: ModelRegistry) -> ModelCard:
    returns = data.benchmark_prices.pct_change(fill_method=None).dropna()
    detector = MarketRegimeDetector()
    result, metadata = detector.fit_predict(
        returns,
        data.prices.pct_change(fill_method=None),
    )
    metadata = _decorate(metadata, data.source_data_version)
    metadata["metrics_vs_baseline"] = {
        **dict(metadata.get("metrics_vs_baseline", {})),
        "shifted_window_state_agreement": _regime_stability(returns),
        "current_filtered_probabilities": {
            "calm": result.calm_probability,
            "stressed": result.stressed_probability,
        },
    }
    if result.status != "ready":
        metadata["failure_reason"] = result.failure_reason
        return registry.save_failed_card(metadata)
    return registry.save_artifact_and_card(detector, metadata)


def _train_anomaly(data: Any, registry: ModelRegistry) -> ModelCard:
    detector = AnomalyDetector()
    benchmark = data.benchmark_prices.pct_change(fill_method=None).dropna()
    metadata = detector.fit(data.prices, benchmark, data.volumes, data.sectors)
    return registry.save_artifact_and_card(
        detector, _decorate(metadata, data.source_data_version)
    )


def _train_risk_validation(session: Any, data: Any, registry: ModelRegistry) -> ModelCard:
    rows = session.scalars(
        select(StockMetricDaily)
        .where(
            StockMetricDaily.score.is_not(None),
            StockMetricDaily.metric_date <= data.data_cutoff,
        )
        .order_by(StockMetricDaily.metric_date, StockMetricDaily.symbol)
    ).all()
    by_month_symbol: dict[tuple[int, int, str], StockMetricDaily] = {}
    for row in rows:
        key = (row.metric_date.year, row.metric_date.month, row.symbol)
        existing = by_month_symbol.get(key)
        if existing is None or row.metric_date > existing.metric_date:
            by_month_symbol[key] = row
    month_rows = list(by_month_symbol.values())
    month_dates = sorted({row.metric_date for row in month_rows})
    metadata = _decorate(
        {
            "name": "risk_score_calibration",
            "version": "2.0.0",
            "type": "historical validation of analytical five-factor score",
            "status": "insufficient_data",
            "data_cutoff": str(data.data_cutoff),
            "training_start": str(month_dates[0]) if month_dates else None,
            "training_end": str(month_dates[-1]) if month_dates else None,
            "features": [
                "volatility",
                "downside_volatility",
                "max_drawdown",
                "absolute_beta",
                "instability",
            ],
            "feature_schema_version": "risk-score-percentile-v1",
            "preprocessing": {"imputation": None, "monthly_cross_section": True},
            "hyperparameters": {
                "weights": [0.30, 0.25, 0.20, 0.15, 0.10],
                "forward_horizons": [21, 63],
            },
            "metrics_vs_baseline": {},
            "baseline_definition": ["volatility_only", "equal_weight_factors"],
            "model_selected": None,
            "selection_reason": None,
            "methodology_version": "ml-risk-v2",
            "failure_reason": (
                "requires_point_in_time_month_end_score_cross_sections_across_history; "
                f"found_{len(month_dates)}_dates"
            ),
        },
        data.source_data_version,
    )
    if len(month_dates) < 12:
        return registry.save_failed_card(metadata)

    records: list[dict[str, Any]] = []
    for row in month_rows:
        if row.symbol not in data.prices:
            continue
        prices = data.prices[row.symbol].dropna().sort_index()
        available_dates = [day for day in prices.index if day <= row.metric_date]
        if not available_dates:
            continue
        position = prices.index.get_loc(available_dates[-1])
        if not isinstance(position, (int, np.integer)) or position + 63 >= len(prices):
            continue
        current = float(prices.iloc[position])

        def targets(
            horizon: int,
            series: pd.Series = prices,
            start_position: int = int(position),
            current_price: float = current,
        ) -> tuple[float, float]:
            future = series.iloc[start_position : start_position + horizon + 1].astype(float)
            returns = future.pct_change(fill_method=None).dropna().to_numpy(dtype=float)
            volatility = float(np.sqrt(np.mean(np.square(returns))) * np.sqrt(252.0))
            wealth = future.to_numpy(dtype=float) / current_price
            drawdown = float(abs(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)))
            return volatility, drawdown

        vol21, drawdown21 = targets(21)
        vol63, drawdown63 = targets(63)
        factors = [
            row.factor_volatility,
            row.factor_downside,
            row.factor_drawdown,
            row.factor_beta,
            row.factor_instability,
        ]
        if any(value is None for value in factors):
            continue
        records.append(
            {
                "evaluation_date": row.metric_date,
                "symbol": row.symbol,
                "score": float(row.score),
                "volatility_only_score": float(row.factor_volatility),
                "equal_weight_score": float(np.mean([float(value) for value in factors])),
                "forward_volatility_21d": vol21,
                "forward_volatility_63d": vol63,
                "forward_drawdown_21d": drawdown21,
                "forward_drawdown_63d": drawdown63,
            }
        )
    validation = validate_cross_sectional_panel(pd.DataFrame(records))
    metadata["metrics_vs_baseline"] = validation
    metadata["status"] = validation["status"]
    metadata["failure_reason"] = validation.get("reason")
    if validation["status"] == "ready":
        metadata["training_start"], metadata["training_end"] = validation[
            "training_period"
        ]
        metadata["test_start"], metadata["test_end"] = validation["test_period"]
    metadata["selection_reason"] = (
        "Fixed weights were declared before the untouched test period; no weights refitted."
        if validation["status"] == "ready"
        else None
    )
    if validation["status"] != "ready":
        return registry.save_failed_card(metadata)
    # Validation has no inference artifact; persist the complete panel as the auditable artifact.
    return registry.save_artifact_and_card(pd.DataFrame(records), metadata)


def train_all_models(
    cutoff_date: date | None = None,
    save_to_db: bool = True,
    models_dir: Path | None = None,
) -> dict[str, object]:
    registry = ModelRegistry(models_dir=models_dir)
    results: dict[str, object] = {}
    with SessionLocal() as session:
        data = load_validated_market_data(session, cutoff=cutoff_date)
        trainers = {
            "volatility_forecast": lambda: _train_volatility(data, registry),
            "market_regime": lambda: _train_regime(data, registry),
            "anomaly_detector": lambda: _train_anomaly(data, registry),
            "risk_score_validator": lambda: _train_risk_validation(session, data, registry),
        }
        for key, trainer in trainers.items():
            try:
                card = trainer()
            except Exception as exc:
                metadata = _decorate(
                    {
                        "name": {
                            "volatility_forecast": "volatility_forecast_21d",
                            "market_regime": "market_regime_nifty50",
                            "anomaly_detector": "anomaly_isolation_forest",
                            "risk_score_validator": "risk_score_calibration",
                        }[key],
                        "version": "2.0.0",
                        "status": "failed",
                        "data_cutoff": str(data.data_cutoff),
                        "training_start": str(data.benchmark_prices.index.min()),
                        "training_end": str(data.benchmark_prices.index.max()),
                        "features": [],
                        "hyperparameters": {},
                        "failure_reason": f"{type(exc).__name__}: {exc}",
                    },
                    data.source_data_version,
                )
                card = registry.save_failed_card(metadata)
            results[key] = card.to_dict()
            if save_to_db:
                _persist_run(session, card)
                session.commit()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=date.fromisoformat)
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args()
    result = train_all_models(args.cutoff, not args.no_db)
    print(json.dumps(result, indent=2, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
