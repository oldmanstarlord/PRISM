"""Daily artifact-only ML inference; this module never calls training code."""

import argparse
import json
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import ModelPrediction, ModelRun
from backend.app.db.session import SessionLocal
from backend.app.ml.artifacts import VolatilityArtifactBundle
from backend.app.ml.models.anomaly_detector import AnomalyDetector
from backend.app.ml.models.market_regime import MarketRegimeDetector
from backend.app.ml.registry import ModelRegistry
from backend.app.ml.training_data import load_validated_market_data


def _number(value: float | None) -> Decimal | None:
    return Decimal(str(value)).quantize(Decimal("0.000001")) if value is not None else None


def _latest_run(session: Session, name: str) -> ModelRun | None:
    return session.scalar(
        select(ModelRun)
        .where(ModelRun.model_name == name, ModelRun.status.in_(("ready", "baseline_selected")))
        .order_by(desc(ModelRun.trained_at))
        .limit(1)
    )


def _upsert_prediction(session: Session, **values: Any) -> None:
    row = session.scalar(
        select(ModelPrediction).where(
            ModelPrediction.run_id == values["run_id"],
            ModelPrediction.target_type == values["target_type"],
            ModelPrediction.symbol == values["symbol"],
            ModelPrediction.prediction_date == values["prediction_date"],
        )
    )
    if row is None:
        session.add(ModelPrediction(**values))
    else:
        for key, value in values.items():
            setattr(row, key, value)


def _base(run: ModelRun, target: str, symbol: str, prediction_date: date) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "target_type": target,
        "symbol": symbol,
        "prediction_date": prediction_date,
        "data_cutoff": prediction_date,
        "methodology_version": run.methodology_version,
        "model_version": run.model_version,
        "horizon_sessions": 21 if target == "volatility_21d" else None,
        "model_selected": run.model_selected or "unavailable",
        "predicted_value": None,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": None,
        "baseline_value": None,
        "status": "unavailable",
        "failure_reason": None,
        "quality_status": None,
        "explanation": {},
    }


def run_daily_inference(
    *, cutoff: date | None = None, models_dir: Any = None
) -> dict[str, Any]:
    registry = ModelRegistry(models_dir=models_dir)
    summary: dict[str, Any] = {}
    with SessionLocal() as session:
        data = load_validated_market_data(session, cutoff=cutoff)
        benchmark_returns = data.benchmark_prices.pct_change(fill_method=None).dropna()

        volatility_run = _latest_run(session, "volatility_forecast_21d")
        vol_counts = {"ready": 0, "failed": 0, "insufficient_data": 0}
        if volatility_run is not None:
            try:
                card = registry.load_model_card("volatility_forecast_21d")
                if card is None or card.version != volatility_run.model_version:
                    raise RuntimeError("database_and_artifact_card_version_mismatch")
                bundle = registry.load_artifact(
                    card, expected_feature_schema="volatility-features-v2"
                )
                if not isinstance(bundle, VolatilityArtifactBundle):
                    raise TypeError("unexpected_volatility_artifact_type")
                all_symbols = sorted(data.universe_security_ids)
                for symbol in all_symbols:
                    values = _base(
                        volatility_run, "volatility_21d", symbol, data.data_cutoff
                    )
                    values["security_id"] = data.universe_security_ids.get(symbol)
                    reason = data.excluded_reasons.get(
                        symbol
                    ) or bundle.unavailable_reasons.get(symbol)
                    if reason:
                        values.update(
                            status="insufficient_data",
                            failure_reason=reason,
                            predicted_value=None,
                            quality_status="unavailable",
                        )
                        vol_counts["insufficient_data"] += 1
                    else:
                        try:
                            if bundle.selection_by_symbol.get(symbol) == "individual":
                                prediction = bundle.per_stock[symbol].predict(
                                    data.prices[symbol].dropna(),
                                    benchmark_returns,
                                    data.volumes[symbol].dropna(),
                                )
                                point = prediction.predicted_volatility
                                lower = prediction.lower_bound_90
                                upper = prediction.upper_bound_90
                                baseline = prediction.baseline_trailing_vol
                                selected = prediction.model_selected
                            else:
                                if bundle.pooled is None:
                                    raise RuntimeError("pooled_volatility_artifact_unavailable")
                                pooled_prediction = bundle.pooled.predict(
                                    symbol,
                                    data.prices[symbol].dropna(),
                                    data.volumes[symbol].dropna(),
                                    benchmark_returns,
                                )
                                point, lower, upper, baseline, selected = (
                                    pooled_prediction.value,
                                    pooled_prediction.lower,
                                    pooled_prediction.upper,
                                    pooled_prediction.trailing,
                                    pooled_prediction.model_selected,
                                )
                            if selected is None:
                                raise RuntimeError("volatility_model_selection_unavailable")
                            values.update(
                                status=(
                                    "baseline_selected"
                                    if selected.startswith("baseline_")
                                    else "ready"
                                ),
                                failure_reason=None,
                                predicted_value=_number(point),
                                lower_bound=_number(lower),
                                upper_bound=_number(upper),
                                confidence_level=Decimal("0.9000"),
                                baseline_value=_number(baseline),
                                model_selected=selected,
                                quality_status="pass",
                                explanation={
                                    "selection_scope": bundle.selection_by_symbol.get(symbol),
                                    "interval_method": (
                                        "90th percentile absolute validation residual"
                                    ),
                                },
                            )
                            vol_counts["ready"] += 1
                        except Exception as exc:
                            values.update(
                                status="failed",
                                failure_reason=f"{type(exc).__name__}: {exc}",
                                predicted_value=None,
                                quality_status="failed",
                            )
                            vol_counts["failed"] += 1
                    _upsert_prediction(session, **values)
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                all_symbols = sorted(data.universe_security_ids)
                for symbol in all_symbols:
                    values = _base(
                        volatility_run, "volatility_21d", symbol, data.data_cutoff
                    )
                    values.update(
                        security_id=data.universe_security_ids.get(symbol),
                        status="failed",
                        failure_reason=reason,
                        predicted_value=None,
                        quality_status="failed",
                    )
                    _upsert_prediction(session, **values)
                vol_counts["failed"] = len(all_symbols)
                summary["volatility_error"] = reason
        else:
            summary["volatility_error"] = "no_validated_volatility_model_run"
        summary["volatility"] = vol_counts

        regime_run = _latest_run(session, "market_regime_nifty50")
        if regime_run is not None:
            values = _base(regime_run, "market_regime", "^NSEI", data.data_cutoff)
            try:
                card = registry.load_model_card("market_regime_nifty50")
                if card is None or card.version != regime_run.model_version:
                    raise RuntimeError("database_and_artifact_card_version_mismatch")
                artifact = registry.load_artifact(card, expected_feature_schema="regime-return-v2")
                if not isinstance(artifact, MarketRegimeDetector):
                    raise TypeError("unexpected_regime_artifact_type")
                result = artifact.predict_filtered(benchmark_returns)
                values.update(
                    status="ready",
                    failure_reason=None,
                    predicted_value=_number(result.stressed_probability),
                    quality_status="pass",
                    explanation=result.to_dict(),
                )
                summary["regime"] = "ready"
            except Exception as exc:
                values.update(
                    status="failed",
                    failure_reason=f"{type(exc).__name__}: {exc}",
                    predicted_value=None,
                    quality_status="failed",
                )
                summary["regime"] = "failed"
            _upsert_prediction(session, **values)
        else:
            summary["regime"] = "untrained"
            summary["regime_error"] = "no_validated_regime_model_run"

        anomaly_run = _latest_run(session, "anomaly_isolation_forest")
        anomaly_counts = {"ready": 0, "failed": 0, "insufficient_data": 0}
        if anomaly_run is not None:
            try:
                card = registry.load_model_card("anomaly_isolation_forest")
                if card is None or card.version != anomaly_run.model_version:
                    raise RuntimeError("database_and_artifact_card_version_mismatch")
                artifact = registry.load_artifact(
                    card, expected_feature_schema="anomaly-features-v3"
                )
                if not isinstance(artifact, AnomalyDetector):
                    raise TypeError("unexpected_anomaly_artifact_type")
                anomaly_result = artifact.predict(
                    data.prices,
                    benchmark_returns,
                    data.volumes,
                    data.sectors,
                    as_of=data.data_cutoff,
                )
                result_by_symbol = {
                    str(item["symbol"]): item for item in anomaly_result.all_evaluated_holdings
                }
                unavailable = {
                    item["symbol"]: item["reason"] for item in anomaly_result.unavailable_holdings
                }
                for symbol in sorted(data.universe_security_ids):
                    values = _base(
                        anomaly_run, "anomaly_score", symbol, data.data_cutoff
                    )
                    values["security_id"] = data.universe_security_ids.get(symbol)
                    item = result_by_symbol.get(symbol)
                    reason = data.excluded_reasons.get(symbol) or unavailable.get(symbol)
                    if item is None:
                        values.update(
                            status="insufficient_data",
                            failure_reason=reason or "anomaly_features_unavailable",
                            predicted_value=None,
                            quality_status="unavailable",
                        )
                        anomaly_counts["insufficient_data"] += 1
                    else:
                        values.update(
                            status="ready",
                            failure_reason=None,
                            predicted_value=_number(float(item["anomaly_score"])),
                            baseline_value=_number(
                                1.0 if item["is_anomaly_baseline"] else 0.0
                            ),
                            quality_status="pass",
                            explanation=item,
                        )
                        anomaly_counts["ready"] += 1
                    _upsert_prediction(session, **values)
                anomaly_run.metrics = {
                    **anomaly_run.metrics,
                    "latest_flag_rate_pct": anomaly_result.flag_rate_percent,
                    "temporal_stability_jaccard": anomaly_result.window_stability_jaccard,
                }
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                all_symbols = sorted(data.universe_security_ids)
                for symbol in all_symbols:
                    values = _base(
                        anomaly_run, "anomaly_score", symbol, data.data_cutoff
                    )
                    values.update(
                        security_id=data.universe_security_ids.get(symbol),
                        status="failed",
                        failure_reason=reason,
                        predicted_value=None,
                        quality_status="failed",
                    )
                    _upsert_prediction(session, **values)
                anomaly_counts["failed"] = len(all_symbols)
                summary["anomaly_error"] = reason
        else:
            summary["anomaly_error"] = "no_validated_anomaly_model_run"
        summary["anomaly"] = anomaly_counts
        session.commit()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=date.fromisoformat)
    args = parser.parse_args()
    print(json.dumps(run_daily_inference(cutoff=args.cutoff), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
