"""Market Regime Detection on Benchmark (NIFTY 50).

Uses a 2-state Markov-switching Gaussian regime model.
CRITICAL CONSTRAINT: Uses FILTERED probabilities only.
Smoothed probabilities leak future observations and are strictly forbidden.
Outputs:
- Current filtered regime probabilities (Calm vs Stressed)
- Regime-conditional volatility and average correlation
- Expected regime duration and transition matrix
- Point-in-time historical regime sequence
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from statsmodels.tsa.regime_switching.markov_regression import (  # type: ignore[import-untyped]
    MarkovRegression,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RegimeTimelinePoint:
    date: str
    calm_prob: float
    stressed_prob: float
    regime: str  # "Calm" | "Stressed"


@dataclass(slots=True)
class MarketRegimeResult:
    current_regime: str | None  # "Calm" | "Stressed"
    calm_probability: float | None
    stressed_probability: float | None
    calm_volatility_annualized: float | None
    stressed_volatility_annualized: float | None
    calm_expected_duration_days: float | None
    stressed_expected_duration_days: float | None
    transition_matrix: list[list[float]]  # 2x2 matrix [[P_cc, P_cs], [P_sc, P_ss]]
    state_stability_score: float | None  # Persistence metric (0 to 1)
    is_interpretable: bool  # True if stressed vol > calm vol
    regime_conditional_correlation_calm: float | None
    regime_conditional_correlation_stressed: float | None
    calm_mean_return: float | None
    stressed_mean_return: float | None
    data_cutoff: str
    sample_sessions: int
    recent_timeline: list[dict[str, Any]]
    status: str = "ready"
    failure_reason: str | None = None

    @property
    def active_regime_name(self) -> str:
        if self.current_regime is None:
            return "Unavailable"
        return "Calm / Normal" if "calm" in self.current_regime.lower() else "Turbulent / Stressed"

    @property
    def filtered_probability(self) -> float | None:
        if self.current_regime is None:
            return None
        return (
            self.calm_probability
            if "calm" in self.current_regime.lower()
            else self.stressed_probability
        )

    @property
    def regime_conditional_volatilities(self) -> dict[str, float | None]:
        return {
            "Calm / Normal": self.calm_volatility_annualized / 100.0
            if self.calm_volatility_annualized is not None
            else None,
            "Turbulent / Stressed": self.stressed_volatility_annualized / 100.0
            if self.stressed_volatility_annualized is not None
            else None,
        }

    @property
    def regime_conditional_correlations(self) -> dict[str, float | None]:
        return {
            "Calm / Normal": self.regime_conditional_correlation_calm,
            "Turbulent / Stressed": self.regime_conditional_correlation_stressed,
        }

    @property
    def expected_durations_days(self) -> dict[str, float | None]:
        return {
            "Calm / Normal": self.calm_expected_duration_days,
            "Turbulent / Stressed": self.stressed_expected_duration_days,
        }

    @property
    def regime_timeline(self) -> list[dict[str, Any]]:
        return self.recent_timeline

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["active_regime_name"] = self.active_regime_name
        d["filtered_probability"] = self.filtered_probability
        d["regime_conditional_volatilities"] = self.regime_conditional_volatilities
        d["regime_conditional_correlations"] = self.regime_conditional_correlations
        d["expected_durations_days"] = self.expected_durations_days
        d["regime_timeline"] = self.regime_timeline
        d["regime_conditional_mean_returns"] = {
            "Calm / Normal": self.calm_mean_return,
            "Turbulent / Stressed": self.stressed_mean_return,
        }
        return d


class MarketRegimeDetector:
    """Estimates filtered market regimes from benchmark index returns."""

    def __init__(self, k_regimes: int = 2) -> None:
        self.k_regimes = k_regimes
        self.fitted_params: np.ndarray | None = None
        self.calm_idx: int | None = None
        self.stressed_idx: int | None = None
        self.training_result: MarketRegimeResult | None = None

    def fit_predict(
        self,
        benchmark_returns: pd.Series,
        stock_returns_matrix: pd.DataFrame | None = None,
    ) -> tuple[MarketRegimeResult, dict[str, Any]]:
        """Fit Markov Switching model on benchmark returns and produce filtered regime state."""
        b_rets = benchmark_returns.dropna()
        n_obs = len(b_rets)
        if n_obs < 60:
            unavailable = MarketRegimeResult(
                current_regime=None,
                calm_probability=None,
                stressed_probability=None,
                calm_volatility_annualized=None,
                stressed_volatility_annualized=None,
                calm_expected_duration_days=None,
                stressed_expected_duration_days=None,
                transition_matrix=[],
                state_stability_score=None,
                is_interpretable=False,
                regime_conditional_correlation_calm=None,
                regime_conditional_correlation_stressed=None,
                calm_mean_return=None,
                stressed_mean_return=None,
                data_cutoff=str(b_rets.index[-1]) if n_obs > 0 else "unknown",
                sample_sessions=n_obs,
                recent_timeline=[],
                status="insufficient_data",
                failure_reason="requires_at_least_60_benchmark_returns",
            )
            return unavailable, {
                "name": "market_regime_nifty50",
                "version": "2.0.0",
                "status": "insufficient_data",
                "failure_reason": unavailable.failure_reason,
            }

        # 1. Fit 2-state Markov Switching model with switching variance
        try:
            model = MarkovRegression(
                endog=b_rets.values,
                k_regimes=self.k_regimes,
                switching_variance=True,
            )
            res = model.fit(disp=False, maxiter=200)
            self.fitted_params = np.asarray(res.params, dtype=float)

            # Filtered probabilities array of shape (T, 2)
            filtered_probs = res.filtered_marginal_probabilities
            p_matrix = res.regime_transition  # shape (2, 2)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            failed = MarketRegimeResult(
                current_regime=None,
                calm_probability=None,
                stressed_probability=None,
                calm_volatility_annualized=None,
                stressed_volatility_annualized=None,
                calm_expected_duration_days=None,
                stressed_expected_duration_days=None,
                transition_matrix=[],
                state_stability_score=None,
                is_interpretable=False,
                regime_conditional_correlation_calm=None,
                regime_conditional_correlation_stressed=None,
                calm_mean_return=None,
                stressed_mean_return=None,
                data_cutoff=str(b_rets.index[-1]),
                sample_sessions=n_obs,
                recent_timeline=[],
                status="failed",
                failure_reason=reason,
            )
            return failed, {
                "name": "market_regime_nifty50",
                "version": "2.0.0",
                "status": "failed",
                "failure_reason": reason,
            }

        # 2. Interpretability Alignment: Map lower-volatility state to "Calm", higher to "Stressed"
        # Compute empirical return standard deviation in each regime
        prob_state_0 = filtered_probs[:, 0]
        prob_state_1 = filtered_probs[:, 1]

        # Weighted volatility
        w_var_0 = np.average((b_rets.values - np.mean(b_rets.values)) ** 2, weights=prob_state_0)
        w_var_1 = np.average((b_rets.values - np.mean(b_rets.values)) ** 2, weights=prob_state_1)

        vol_0 = float(np.sqrt(max(1e-8, w_var_0)) * np.sqrt(252.0))
        vol_1 = float(np.sqrt(max(1e-8, w_var_1)) * np.sqrt(252.0))

        if vol_0 <= vol_1:
            calm_idx, stressed_idx = 0, 1
            calm_vol, stressed_vol = vol_0, vol_1
        else:
            calm_idx, stressed_idx = 1, 0
            calm_vol, stressed_vol = vol_1, vol_0
        self.calm_idx = calm_idx
        self.stressed_idx = stressed_idx

        p_calm_series = filtered_probs[:, calm_idx]
        p_stressed_series = filtered_probs[:, stressed_idx]
        calm_mean = float(np.average(b_rets.values, weights=p_calm_series))
        stressed_mean = float(np.average(b_rets.values, weights=p_stressed_series))

        # Transition matrix mapped to Calm (0) and Stressed (1)
        p_arr = np.array(p_matrix)
        while p_arr.ndim > 2:
            p_arr = p_arr[:, :, -1]
        p_cc = float(p_arr[calm_idx, calm_idx])
        p_cs = float(p_arr[stressed_idx, calm_idx])
        p_sc = float(p_arr[calm_idx, stressed_idx])
        p_ss = float(p_arr[stressed_idx, stressed_idx])

        # Row-normalize so rows sum to exactly 1.0
        c_sum = p_cc + p_cs
        s_sum = p_sc + p_ss
        if c_sum > 0:
            p_cc, p_cs = p_cc / c_sum, p_cs / c_sum
        if s_sum > 0:
            p_sc, p_ss = p_sc / s_sum, p_ss / s_sum

        # Expected durations (in days)
        dur_calm = float(1.0 / max(0.001, 1.0 - p_cc))
        dur_stressed = float(1.0 / max(0.001, 1.0 - p_ss))

        # Current regime probabilities at the latest session T
        curr_calm_p = float(p_calm_series[-1])
        curr_stressed_p = float(p_stressed_series[-1])
        current_regime = "Stressed" if curr_stressed_p > 0.50 else "Calm"

        # State stability score: average self-transition probability
        stability = (p_cc + p_ss) / 2.0

        # 3. Regime-conditional correlations if stock matrix available
        corr_calm: float | None = None
        corr_stressed: float | None = None
        if stock_returns_matrix is not None and not stock_returns_matrix.empty:
            common_dates = b_rets.index.intersection(stock_returns_matrix.index)
            if len(common_dates) > 30:
                s_mat = stock_returns_matrix.loc[common_dates]
                calm_probability = pd.Series(p_calm_series, index=b_rets.index)
                stressed_probability = pd.Series(p_stressed_series, index=b_rets.index)
                calm_mask = calm_probability.reindex(common_dates).to_numpy() > 0.50
                stressed_mask = stressed_probability.reindex(common_dates).to_numpy() > 0.50

                if np.sum(calm_mask) > 10:
                    c_mat = s_mat[calm_mask].corr().values
                    # Average off-diagonal correlation
                    corr_calm = float(np.mean(c_mat[np.triu_indices_from(c_mat, k=1)]))
                if np.sum(stressed_mask) > 5:
                    s_corr = s_mat[stressed_mask].corr().values
                    corr_stressed = float(np.mean(s_corr[np.triu_indices_from(s_corr, k=1)]))

        # 4. Build recent regime timeline (last 60 sessions)
        dates_list = [str(d) for d in b_rets.index]
        timeline = []
        lookback_timeline = min(60, len(dates_list))
        for i in range(len(dates_list) - lookback_timeline, len(dates_list)):
            p_c = float(p_calm_series[i])
            p_s = float(p_stressed_series[i])
            timeline.append(
                {
                    "date": dates_list[i],
                    "calm_prob": round(p_c, 4),
                    "stressed_prob": round(p_s, 4),
                    "regime": "Stressed" if p_s > 0.50 else "Calm",
                }
            )

        result = MarketRegimeResult(
            current_regime=current_regime,
            calm_probability=round(curr_calm_p, 4),
            stressed_probability=round(curr_stressed_p, 4),
            calm_volatility_annualized=round(calm_vol * 100.0, 2),
            stressed_volatility_annualized=round(stressed_vol * 100.0, 2),
            calm_expected_duration_days=round(dur_calm, 1),
            stressed_expected_duration_days=round(dur_stressed, 1),
            transition_matrix=[
                [round(p_cc, 4), round(p_cs, 4)],
                [round(p_sc, 4), round(p_ss, 4)],
            ],
            state_stability_score=round(stability, 4),
            is_interpretable=stressed_vol > calm_vol,
            regime_conditional_correlation_calm=round(corr_calm, 4)
            if corr_calm is not None
            else None,
            regime_conditional_correlation_stressed=round(corr_stressed, 4)
            if corr_stressed is not None
            else None,
            calm_mean_return=calm_mean,
            stressed_mean_return=stressed_mean,
            data_cutoff=dates_list[-1],
            sample_sessions=n_obs,
            recent_timeline=timeline,
        )

        self.training_result = result
        model_card = {
            "name": "market_regime_nifty50",
            "version": "2.0.0",
            "type": "two-state Markov switching Gaussian model",
            "status": "ready",
            "data_cutoff": dates_list[-1],
            "training_start": str(b_rets.index[0]),
            "training_end": str(b_rets.index[-1]),
            "features": ["nifty50_simple_return"],
            "feature_schema_version": "regime-return-v2",
            "preprocessing": {"imputation": None, "scaling": None},
            "hyperparameters": {"k_regimes": self.k_regimes, "switching_variance": True},
            "metrics_vs_baseline": {
                "transition_matrix": [[p_cc, p_cs], [p_sc, p_ss]],
                "state_stability_score": round(stability, 4),
                "regime_conditional_mean_returns": {
                    "calm": calm_mean,
                    "stressed": stressed_mean,
                },
            },
            "model_selected": "markov_switching",
            "methodology_version": "ml-risk-v2",
            "no_leakage_guarantee": (
                "Filtered marginal probabilities condition strictly on R_1..R_t"
            ),
        }

        return result, model_card

    def predict_filtered(self, benchmark_returns: pd.Series) -> MarketRegimeResult:
        """Apply fitted parameters and calculate filtered probabilities without re-estimation."""
        if (
            self.fitted_params is None
            or self.calm_idx is None
            or self.stressed_idx is None
            or self.training_result is None
        ):
            raise RuntimeError("Regime artifact is not fitted")
        returns = benchmark_returns.dropna().sort_index()
        model = MarkovRegression(
            endog=returns.to_numpy(dtype=float),
            k_regimes=self.k_regimes,
            switching_variance=True,
        )
        result = model.filter(self.fitted_params)
        probabilities = np.asarray(result.filtered_marginal_probabilities)
        calm = probabilities[:, self.calm_idx]
        stressed = probabilities[:, self.stressed_idx]
        timeline = [
            {
                "date": str(day),
                "calm_prob": round(float(calm[index]), 4),
                "stressed_prob": round(float(stressed[index]), 4),
                "regime": "Stressed" if stressed[index] > 0.5 else "Calm",
            }
            for index, day in enumerate(returns.index[-60:], start=max(len(returns) - 60, 0))
        ]
        training = self.training_result
        return MarketRegimeResult(
            current_regime="Stressed" if stressed[-1] > 0.5 else "Calm",
            calm_probability=round(float(calm[-1]), 4),
            stressed_probability=round(float(stressed[-1]), 4),
            calm_volatility_annualized=training.calm_volatility_annualized,
            stressed_volatility_annualized=training.stressed_volatility_annualized,
            calm_expected_duration_days=training.calm_expected_duration_days,
            stressed_expected_duration_days=training.stressed_expected_duration_days,
            transition_matrix=training.transition_matrix,
            state_stability_score=training.state_stability_score,
            is_interpretable=training.is_interpretable,
            regime_conditional_correlation_calm=training.regime_conditional_correlation_calm,
            regime_conditional_correlation_stressed=(
                training.regime_conditional_correlation_stressed
            ),
            calm_mean_return=training.calm_mean_return,
            stressed_mean_return=training.stressed_mean_return,
            data_cutoff=str(returns.index[-1]),
            sample_sessions=len(returns),
            recent_timeline=timeline,
        )
