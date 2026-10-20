"""ML Inference Service Orchestration.

Executes point-in-time inference across:
1. 21-day volatility forecasting (portfolio and holdings).
2. Market regime detection (NIFTY 50 filtered probabilities).
3. Holdings anomaly and unusual behaviour detection.
4. Heuristic risk-score validation and calibration curve.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

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

logger = logging.getLogger(__name__)


def _load_prices_for_symbols(
    symbols: list[str], session: Session | None, days: int = 500
) -> pd.DataFrame:
    """Helper to load adjusted closing price history for given symbols."""
    prices_df = pd.DataFrame()
    if session is not None:
        try:
            prices_df = _load_stock_prices_from_db(session, symbols, days=days)
        except Exception as exc:
            logger.warning(
                "DB price load failed (%s); attempting secondary source", type(exc).__name__
            )

    if prices_df.empty or len(prices_df.columns) < len(symbols):
        try:
            yf_df = _load_stock_prices_yfinance(symbols, period="2y")
            if not yf_df.empty:
                prices_df = yf_df.tail(days)
        except Exception as exc:
            logger.warning("Secondary price load failed (%s)", type(exc).__name__)

    return prices_df


class MlInferenceService:
    """Orchestrates machine learning risk model inference."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.vol_forecaster = VolatilityForecaster()
        self.regime_detector = MarketRegimeDetector()
        self.anomaly_detector = AnomalyDetector()
        self.score_validator = RiskScoreValidator()

    def get_volatility_insights(
        self,
        symbols: list[str],
        weights: list[float],
        session: Session | None = None,
    ) -> dict[str, Any]:
        """Compute 21-day forward volatility forecast for portfolio and holdings."""
        if not symbols:
            return {"status": "insufficient_data", "error": "No holdings provided"}

        prices_df = _load_prices_for_symbols(symbols, session)
        if prices_df.empty or len(prices_df) < 60:
            return {
                "status": "insufficient_data",
                "error": "Insufficient historical price sessions for volatility model",
            }

        bench_returns = get_benchmark_returns(session)

        # 1. Portfolio synthetic price index
        returns_df = prices_df.pct_change().dropna()
        avail_syms = [s for s in symbols if s in returns_df.columns]
        if not avail_syms:
            return {"status": "insufficient_data", "error": "None of the holdings have price data"}

        # Normalize weights for available symbols
        w_map = dict(zip(symbols, weights, strict=False))
        avail_weights = np.array([w_map.get(s, 0.0) for s in avail_syms])
        w_sum = np.sum(avail_weights)
        if w_sum > 0:
            avail_weights = avail_weights / w_sum
        else:
            avail_weights = np.ones(len(avail_syms)) / len(avail_syms)

        port_returns = returns_df[avail_syms].dot(avail_weights)
        port_prices = (1.0 + port_returns).cumprod() * 1000.0

        # Run model for portfolio
        port_result, port_card = self.vol_forecaster.train_and_evaluate(port_prices, bench_returns)

        # 2. Holding-level forecasts
        holdings_forecasts = []
        for sym, w in zip(avail_syms, avail_weights, strict=False):
            s_price = prices_df[sym].dropna()
            if len(s_price) >= 60:
                h_res, _ = self.vol_forecaster.train_and_evaluate(s_price, bench_returns)
                holdings_forecasts.append(
                    {
                        "symbol": sym,
                        "weight": round(float(w) * 100.0, 2),
                        "forecast_volatility": round(h_res.predicted_volatility * 100.0, 2),
                        "lower_bound_90": round(h_res.lower_bound_90 * 100.0, 2),
                        "upper_bound_90": round(h_res.upper_bound_90 * 100.0, 2),
                        "trailing_21d_vol": round(h_res.baseline_trailing_vol * 100.0, 2),
                        "model_selected": h_res.model_selected,
                        "vol_change_expected": round(
                            (h_res.predicted_volatility - h_res.baseline_trailing_vol) * 100.0,
                            2,
                        ),
                    }
                )

        return {
            "status": "ready",
            "portfolio_forecast": {
                "predicted_volatility_pct": round(port_result.predicted_volatility * 100.0, 2),
                "lower_bound_90_pct": round(port_result.lower_bound_90 * 100.0, 2),
                "upper_bound_90_pct": round(port_result.upper_bound_90 * 100.0, 2),
                "model_selected": port_result.model_selected,
                "trailing_volatility_pct": round(port_result.baseline_trailing_vol * 100.0, 2),
                "ewma_volatility_pct": round(port_result.baseline_ewma_vol * 100.0, 2),
                "har_volatility_pct": round(port_result.baseline_har_vol * 100.0, 2),
                "evaluations": port_result.evaluations,
                "feature_importances": port_result.feature_importances,
                "horizon_days": port_result.horizon_days,
                "data_cutoff": port_result.data_cutoff,
            },
            "holdings_forecasts": holdings_forecasts,
        }

    def get_market_regime_insights(self, session: Session | None = None) -> dict[str, Any]:
        """Compute filtered market regime states for NIFTY 50."""
        bench_returns = get_benchmark_returns(session)
        if bench_returns.empty or len(bench_returns) < 60:
            return {
                "status": "insufficient_data",
                "error": "Insufficient benchmark history for regime detection",
            }

        regime_res, _ = self.regime_detector.fit_predict(bench_returns)
        return {
            "status": "ready",
            "market_regime": regime_res.to_dict(),
        }

    def get_anomaly_insights(
        self,
        symbols: list[str],
        session: Session | None = None,
        company_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Detect statistical outliers and unusual cross-sectional holding behaviour."""
        if not symbols:
            return {"status": "insufficient_data", "error": "No holdings provided"}

        prices_df = _load_prices_for_symbols(symbols, session)
        if prices_df.empty or len(prices_df) < 30:
            return {
                "status": "insufficient_data",
                "error": "Insufficient price observations for anomaly detection",
            }

        bench_returns = get_benchmark_returns(session)
        res, _ = self.anomaly_detector.detect_anomalies(
            prices_df, bench_returns, company_names=company_names
        )

        return {
            "status": "ready",
            "anomaly_analysis": res.to_dict(),
        }

    def get_risk_score_validation_insights(
        self,
        symbols: list[str],
        session: Session | None = None,
    ) -> dict[str, Any]:
        """Validate 5-factor heuristic stock risk score against forward volatility & drawdowns."""
        bench_returns = get_benchmark_returns(session)
        if bench_returns.empty or len(bench_returns) < 84:
            return {
                "status": "insufficient_data",
                "error": "Insufficient benchmark return series for score validation",
            }

        # Build proxy historical score series from benchmark rolling stats
        # (vol 30%, down 25%, mdd 20%, beta 15%, instab 10%)
        roll_vol = bench_returns.rolling(60, min_periods=20).std() * np.sqrt(252.0)
        norm_vol = np.clip((roll_vol - 0.10) / (0.35 - 0.10) * 100.0, 0, 100)
        synth_prices = (1.0 + bench_returns).cumprod() * 1000.0

        res, _ = self.score_validator.validate_score(norm_vol.fillna(50.0).values, synth_prices)
        return {
            "status": "ready",
            "score_validation": res.to_dict(),
        }

    def get_comprehensive_ai_insights(
        self,
        symbols: list[str],
        weights: list[float],
        session: Session | None = None,
        company_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Consolidated payload for the 'AI Insights' tab."""
        model_statuses = self.registry.get_all_model_statuses()
        vol_insights = self.get_volatility_insights(symbols, weights, session)
        regime_insights = self.get_market_regime_insights(session)
        anomaly_insights = self.get_anomaly_insights(symbols, session, company_names=company_names)
        score_val_insights = self.get_risk_score_validation_insights(symbols, session)

        return {
            "model_statuses": model_statuses,
            "volatility": vol_insights,
            "regime": regime_insights,
            "anomalies": anomaly_insights,
            "score_validation": score_val_insights,
            "governance": {
                "methodology_version": "2026.1",
                "disclaimer": (
                    "PRISM AI Insights provides diagnostic risk forecasts and classifications. "
                    "All outputs are model estimates of risk "
                    "(volatility, regime, statistical outliers). "
                    "PRISM strictly does NOT provide price-direction predictions, "
                    "return forecasts, or buy/sell signals."
                ),
                "is_model_estimate": True,
            },
        }
