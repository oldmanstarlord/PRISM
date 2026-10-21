"""Read-only ML dashboard service backed by persisted runs and predictions."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import ModelPrediction, ModelRun

MODEL_TITLES = {
    "volatility_forecast_21d": "21-Session Volatility Forecast",
    "market_regime_nifty50": "NIFTY 50 Market Regime",
    "anomaly_isolation_forest": "NIFTY 200 Anomaly Detection",
    "risk_score_calibration": "Five-Factor Risk Score Validation",
}
USABLE_RUN_STATUSES = {"ready", "baseline_selected"}
FRESHNESS_DAYS = 7


def _latest_run(session: Session, model_name: str, *, usable: bool = False) -> ModelRun | None:
    statement = select(ModelRun).where(ModelRun.model_name == model_name)
    if usable:
        statement = statement.where(ModelRun.status.in_(USABLE_RUN_STATUSES))
    return session.scalar(statement.order_by(desc(ModelRun.trained_at)).limit(1))


def _display_status(run: ModelRun, prediction_date: date | None) -> str:
    if run.status in {"failed", "insufficient_data", "untrained", "unavailable"}:
        return run.status
    if prediction_date is not None and prediction_date < date.today() - timedelta(
        days=FRESHNESS_DAYS
    ):
        return "stale"
    if run.status == "baseline_selected":
        return "baseline_selected"
    return "ready"


def _prediction_payload(row: ModelPrediction) -> dict[str, Any]:
    return {
        "symbol": row.symbol,
        "status": row.status,
        "failure_reason": row.failure_reason,
        "prediction_date": row.prediction_date,
        "data_cutoff": row.data_cutoff,
        "predicted_value": float(row.predicted_value)
        if row.predicted_value is not None
        else None,
        "lower_bound": float(row.lower_bound) if row.lower_bound is not None else None,
        "upper_bound": float(row.upper_bound) if row.upper_bound is not None else None,
        "confidence_level": float(row.confidence_level)
        if row.confidence_level is not None
        else None,
        "baseline_value": float(row.baseline_value)
        if row.baseline_value is not None
        else None,
        "model_selected": row.model_selected,
        "model_version": row.model_version,
        "methodology_version": row.methodology_version,
        "horizon_sessions": row.horizon_sessions,
        "quality_status": row.quality_status,
        "created_at": row.created_at,
        "details": row.explanation,
    }


class MlInferenceService:
    """Dashboard queries only; training and artifact inference live in scheduled jobs."""

    def get_model_statuses(self, session: Session) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for model_name, title in MODEL_TITLES.items():
            latest = _latest_run(session, model_name)
            serving = _latest_run(session, model_name, usable=True)
            if latest is None:
                result[model_name] = {
                    "model_name": title,
                    "model_version": None,
                    "model_type": None,
                    "status": "untrained",
                    "data_cutoff": None,
                    "trained_at": None,
                    "last_successful_training_date": None,
                    "test_period": None,
                    "metrics_vs_baseline": {},
                    "failure_reason": "no_model_run_recorded",
                }
                continue
            prediction_date = session.scalar(
                select(func.max(ModelPrediction.prediction_date)).where(
                    ModelPrediction.run_id == (serving.id if serving else latest.id)
                )
            )
            result[model_name] = {
                "model_name": title,
                "model_version": latest.model_version,
                "model_type": latest.model_type,
                "status": _display_status(latest, prediction_date),
                "underlying_training_status": latest.status,
                "data_cutoff": latest.data_cutoff,
                "prediction_date": prediction_date,
                "trained_at": latest.trained_at,
                "last_successful_training_date": serving.trained_at if serving else None,
                "training_window": (
                    f"{latest.training_window_start} to {latest.training_window_end}"
                    if latest.training_window_start and latest.training_window_end
                    else None
                ),
                "test_period": (
                    f"{latest.test_window_start} to {latest.test_window_end}"
                    if latest.test_window_start and latest.test_window_end
                    else None
                ),
                "features_count": len(latest.features),
                "metrics_vs_baseline": latest.metrics,
                "baseline_comparison": latest.baseline_comparison,
                "model_selected": latest.model_selected,
                "model_selected_rationale": latest.selection_reason,
                "methodology_version": latest.methodology_version,
                "configuration_fingerprint": latest.configuration_hash,
                "artifact_checksum": latest.artifact_checksum,
                "failure_reason": latest.error_summary,
            }
        return result

    def _predictions(
        self,
        session: Session,
        model_name: str,
        target_type: str,
        symbols: list[str] | None = None,
    ) -> tuple[ModelRun | None, list[ModelPrediction]]:
        run = _latest_run(session, model_name, usable=True)
        if run is None:
            return None, []
        latest_date = session.scalar(
            select(func.max(ModelPrediction.prediction_date)).where(
                ModelPrediction.run_id == run.id,
                ModelPrediction.target_type == target_type,
            )
        )
        if latest_date is None:
            return run, []
        statement = select(ModelPrediction).where(
            ModelPrediction.run_id == run.id,
            ModelPrediction.target_type == target_type,
            ModelPrediction.prediction_date == latest_date,
        )
        if symbols is not None:
            statement = statement.where(ModelPrediction.symbol.in_(symbols))
        rows = session.scalars(statement.order_by(ModelPrediction.symbol)).all()
        return run, list(rows)

    def get_volatility_insights(
        self,
        symbols: list[str],
        weights: list[float],
        session: Session | None = None,
    ) -> dict[str, Any]:
        if session is None:
            return {"status": "unavailable", "error": "database_session_required"}
        run, rows = self._predictions(
            session, "volatility_forecast_21d", "volatility_21d", symbols
        )
        if run is None:
            return {"status": "untrained", "error": "no_validated_volatility_model"}
        by_symbol = {row.symbol: row for row in rows}
        weight_map = dict(zip(symbols, weights, strict=False))
        forecasts = []
        for symbol in symbols:
            row = by_symbol.get(symbol)
            if row is None:
                forecasts.append(
                    {
                        "symbol": symbol,
                        "weight": weight_map.get(symbol),
                        "status": "unavailable",
                        "failure_reason": "no_persisted_prediction_for_latest_model_run",
                    }
                )
                continue
            payload = _prediction_payload(row)
            payload.update(
                {
                    "weight": weight_map.get(symbol),
                    "forecast_volatility": payload["predicted_value"],
                    "lower_bound_90": payload["lower_bound"],
                    "upper_bound_90": payload["upper_bound"],
                    "trailing_21d_vol": payload["baseline_value"],
                }
            )
            forecasts.append(payload)
        prediction_dates = [row.prediction_date for row in rows]
        row_statuses = {row.status for row in rows}
        status = (
            next(iter(row_statuses))
            if len(row_statuses) == 1
            and next(iter(row_statuses)) in {"failed", "insufficient_data", "unavailable"}
            else _display_status(run, max(prediction_dates) if prediction_dates else None)
        )
        return {
            "status": status,
            "data_cutoff": run.data_cutoff,
            "portfolio_forecast": None,
            "portfolio_reason": (
                "Portfolio volatility remains on-demand and is not derived by summing "
                "stock forecasts."
            ),
            "holdings_forecasts": forecasts,
        }

    def get_market_regime_insights(self, session: Session | None = None) -> dict[str, Any]:
        if session is None:
            return {"status": "unavailable", "error": "database_session_required"}
        run, rows = self._predictions(
            session, "market_regime_nifty50", "market_regime", ["^NSEI"]
        )
        if run is None or not rows:
            return {"status": "untrained", "error": "no_persisted_regime_output"}
        row = rows[0]
        return {
            "status": (
                row.status
                if row.status in {"failed", "insufficient_data", "unavailable"}
                else _display_status(run, row.prediction_date)
            ),
            "market_regime": row.explanation,
            "error": row.failure_reason,
        }

    def get_anomaly_insights(
        self,
        symbols: list[str],
        session: Session | None = None,
        company_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        company_map = company_names or {}
        if session is None:
            return {"status": "unavailable", "error": "database_session_required"}
        run, rows = self._predictions(
            session, "anomaly_isolation_forest", "anomaly_score", symbols
        )
        if run is None:
            return {"status": "untrained", "error": "no_validated_anomaly_model"}
        present = {row.symbol for row in rows}
        results = []
        for row in rows:
            payload = _prediction_payload(row)
            details = dict(row.explanation or {})
            payload.update(details)
            payload["company_name"] = company_map.get(row.symbol or "", row.symbol)
            payload["anomaly_score"] = payload["predicted_value"]
            payload["is_anomaly"] = details.get("is_anomaly_ml")
            payload["rationale"] = details.get("explanation")
            results.append(payload)
        results.extend(
            {
                "symbol": symbol,
                "status": "unavailable",
                "failure_reason": "no_persisted_anomaly_result",
            }
            for symbol in symbols
            if symbol not in present
        )
        prediction_dates = [row.prediction_date for row in rows]
        row_statuses = {row.status for row in rows}
        output_status = (
            next(iter(row_statuses))
            if len(row_statuses) == 1
            and next(iter(row_statuses)) in {"failed", "insufficient_data", "unavailable"}
            else _display_status(run, max(prediction_dates) if prediction_dates else None)
        )
        return {
            "status": output_status,
            "anomaly_analysis": {
                "data_cutoff": run.data_cutoff,
                "methodology": run.methodology_version,
                "results": results,
                "unusual_holdings": results,
                "flag_rate_pct": run.metrics.get("latest_flag_rate_pct"),
                "stability_score": run.metrics.get("temporal_stability_jaccard"),
                "disclaimer": (
                    "Anomaly scores describe unusual observed behaviour and do not predict loss."
                ),
            },
        }

    def get_risk_score_validation_insights(
        self,
        symbols: list[str],
        session: Session | None = None,
    ) -> dict[str, Any]:
        del symbols
        if session is None:
            return {"status": "unavailable", "error": "database_session_required"}
        run = _latest_run(session, "risk_score_calibration")
        if run is None:
            return {"status": "untrained", "error": "no_risk_score_validation_run"}
        return {
            "status": run.status,
            "score_validation": run.metrics if run.status in USABLE_RUN_STATUSES else None,
            "error": run.error_summary,
        }

    def get_comprehensive_ai_insights(
        self,
        symbols: list[str],
        weights: list[float],
        session: Session | None = None,
        company_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if session is None:
            raise ValueError("database_session_required")
        return {
            "model_statuses": self.get_model_statuses(session),
            "volatility": self.get_volatility_insights(symbols, weights, session),
            "regime": self.get_market_regime_insights(session),
            "anomalies": self.get_anomaly_insights(
                symbols, session, company_names=company_names
            ),
            "score_validation": self.get_risk_score_validation_insights(symbols, session),
            "governance": {
                "methodology_version": "ml-risk-v2",
                "disclaimer": (
                    "Persisted point-in-time risk estimates only. PRISM does NOT forecast "
                    "price direction, returns, or trading actions."
                ),
                "is_model_estimate": True,
            },
        }
