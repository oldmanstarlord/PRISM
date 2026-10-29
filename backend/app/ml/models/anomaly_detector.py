"""Cross-sectional anomaly detection with explicit feature availability."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

FEATURES = [
    "daily_return",
    "realized_volatility_change_20d",
    "beta_change_60d",
    "volume_spike_20d",
    "sector_return_divergence",
]


@dataclass(slots=True)
class HoldingAnomalyItem:
    symbol: str
    company_name: str
    anomaly_score: float
    is_anomaly_ml: bool
    is_anomaly_baseline: bool
    primary_driver: str
    feature_attributions: dict[str, float]
    explanation: str
    status: str = "ready"
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnomalyDetectionResult:
    flagged_holdings: list[dict[str, Any]]
    all_evaluated_holdings: list[dict[str, Any]]
    unavailable_holdings: list[dict[str, str]]
    ml_flag_count: int
    baseline_flag_count: int
    flag_rate_percent: float | None
    window_stability_jaccard: float | None
    model_name: str
    baseline_name: str
    data_cutoff: str
    governance_notice: str
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unusual_holdings"] = self.all_evaluated_holdings
        payload["flag_rate_pct"] = self.flag_rate_percent
        payload["stability_score"] = self.window_stability_jaccard
        payload["disclaimer"] = self.governance_notice
        return payload


class AnomalyDetector:
    """Fit on historical feature rows and score a later cross-section without refitting."""

    def __init__(
        self,
        contamination: float = 0.10,
        random_state: int = 42,
        random_seed: int | None = None,
    ) -> None:
        self.contamination = contamination
        self.random_state = random_seed if random_seed is not None else random_state
        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        self.scaler = RobustScaler()
        self.training_median: np.ndarray | None = None
        self.training_mad: np.ndarray | None = None
        self.training_scores: np.ndarray | None = None

    def _feature_history(
        self,
        prices_df: pd.DataFrame,
        benchmark_returns: pd.Series,
        volumes_df: pd.DataFrame,
        sectors: dict[str, str | None],
    ) -> tuple[pd.DataFrame, dict[str, str]]:
        frames: list[pd.DataFrame] = []
        unavailable: dict[str, str] = {}
        returns = prices_df.pct_change(fill_method=None)
        benchmark = benchmark_returns.reindex(returns.index)
        sector_members: dict[str, list[str]] = {}
        for symbol in map(str, prices_df.columns):
            sector = sectors.get(symbol)
            if sector:
                sector_members.setdefault(sector, []).append(symbol)
        sector_returns = {
            sector: returns[members].mean(axis=1, skipna=True)
            for sector, members in sector_members.items()
            if len(members) >= 2
        }
        for symbol in map(str, prices_df.columns):
            if symbol not in volumes_df:
                unavailable[symbol] = "volume_history_missing"
                continue
            sector = sectors.get(symbol)
            if not sector:
                unavailable[symbol] = "sector_classification_missing"
                continue
            if sector not in sector_returns:
                unavailable[symbol] = "requires_at_least_two_sector_peers"
                continue
            stock_return = returns[symbol]
            realized_volatility = (
                stock_return.pow(2).rolling(20, min_periods=20).mean().pow(0.5)
                * np.sqrt(252.0)
            )
            benchmark_variance = benchmark.rolling(60, min_periods=60).var().replace(0, np.nan)
            beta = stock_return.rolling(60, min_periods=60).cov(benchmark) / benchmark_variance
            volume = volumes_df[symbol].reindex(returns.index)
            volume_average = volume.rolling(20, min_periods=20).mean().replace(0, np.nan)
            features = pd.concat(
                [
                    stock_return.rename("daily_return"),
                    realized_volatility.diff().rename("realized_volatility_change_20d"),
                    beta.diff().rename("beta_change_60d"),
                    (volume / volume_average).rename("volume_spike_20d"),
                    (stock_return - sector_returns[sector]).rename(
                        "sector_return_divergence"
                    ),
                ],
                axis=1,
            )
            complete = features.loc[:, FEATURES].dropna()
            if complete.empty:
                unavailable[symbol] = "complete_feature_rows_missing"
                continue
            complete = complete.assign(symbol=symbol)
            frames.append(complete)
        if not frames:
            return pd.DataFrame(columns=[*FEATURES, "symbol"]), unavailable
        return pd.concat(frames).sort_index(), unavailable

    def fit(
        self,
        prices_df: pd.DataFrame,
        benchmark_returns: pd.Series,
        volumes_df: pd.DataFrame,
        sectors: dict[str, str | None],
    ) -> dict[str, Any]:
        history, unavailable = self._feature_history(
            prices_df, benchmark_returns, volumes_df, sectors
        )
        dates = sorted(set(history.index))
        if len(dates) < 42:
            raise ValueError("requires_at_least_42_complete_feature_dates")
        evaluation_dates = set(dates[-21:])
        training = history[~history.index.isin(evaluation_dates)]
        evaluation = history[history.index.isin(evaluation_dates)]
        if len(training) < 100:
            raise ValueError("requires_at_least_100_training_feature_rows")
        values = training.loc[:, FEATURES].to_numpy(dtype=float)
        scaled = self.scaler.fit_transform(values)
        self.model.fit(scaled)
        self.training_median = np.median(values, axis=0)
        mad = np.median(np.abs(values - self.training_median), axis=0)
        self.training_mad = np.where(mad > 0, mad, np.nan)
        self.training_scores = np.sort(-self.model.decision_function(scaled))
        evaluation_flags = self.model.predict(
            self.scaler.transform(evaluation.loc[:, FEATURES].to_numpy(dtype=float))
        ) == -1
        evaluation_flag_rate = float(np.mean(evaluation_flags) * 100.0)
        flag_sets: list[set[str]] = []
        for _, cross_section in evaluation.assign(_flag=evaluation_flags).groupby(level=0):
            flag_sets.append(
                set(cross_section.loc[cross_section["_flag"], "symbol"].astype(str))
            )
        stability_values = []
        for previous, current in zip(flag_sets, flag_sets[1:], strict=False):
            union = previous | current
            if union:
                stability_values.append(len(previous & current) / len(union))
        evaluation_stability = (
            float(np.mean(stability_values)) if stability_values else None
        )
        return {
            "name": "anomaly_isolation_forest",
            "version": "2.1.0",
            "type": "unsupervised cross-sectional anomaly detector",
            "status": "ready",
            "data_cutoff": str(history.index[-1]),
            "training_start": str(training.index[0]),
            "training_end": str(training.index[-1]),
            "test_start": str(dates[-21]),
            "test_end": str(dates[-1]),
            "features": FEATURES,
            "feature_schema_version": "anomaly-features-v3",
            "preprocessing": {
                "scaler": "RobustScaler fitted on training rows only",
                "imputation": None,
            },
            "hyperparameters": {
                "n_estimators": 100,
                "contamination": self.contamination,
                "random_state": self.random_state,
            },
            "random_seed": self.random_state,
            "baseline_definition": "absolute robust z-score > 2.5",
            "metrics_vs_baseline": {
                "training_rows": len(training),
                "evaluation_rows": len(evaluation),
                "evaluation_flag_rate_pct": evaluation_flag_rate,
                "evaluation_temporal_stability_jaccard": evaluation_stability,
                "eligible_symbols": int(training["symbol"].nunique()),
                "unavailable_symbols": unavailable,
                "accuracy_claim": None,
                "independent_event_review": {
                    "status": "unavailable",
                    "reason": "no_independent_point_in_time_event_source_in_step_1",
                },
            },
            "model_selected": "isolation_forest",
            "selection_reason": "unsupervised detector; baseline retained as parallel diagnostic",
            "methodology_version": "ml-risk-v2",
        }

    def predict(
        self,
        prices_df: pd.DataFrame,
        benchmark_returns: pd.Series,
        volumes_df: pd.DataFrame,
        sectors: dict[str, str | None],
        *,
        company_names: dict[str, str] | None = None,
        as_of: object | None = None,
    ) -> AnomalyDetectionResult:
        if (
            self.training_median is None
            or self.training_mad is None
            or self.training_scores is None
        ):
            raise RuntimeError("Anomaly artifact is not fitted")
        company_map = company_names or {}
        history, unavailable = self._feature_history(
            prices_df, benchmark_returns, volumes_df, sectors
        )
        requested_date = as_of if as_of is not None else prices_df.index[-1]
        rows: list[pd.Series] = []
        symbols: list[str] = []
        for symbol in map(str, prices_df.columns):
            symbol_rows = history[history["symbol"] == symbol]
            symbol_rows = symbol_rows.loc[symbol_rows.index <= requested_date]
            if symbol_rows.empty:
                unavailable.setdefault(symbol, "no_complete_features_as_of_prediction_date")
                continue
            rows.append(symbol_rows.iloc[-1])
            symbols.append(symbol)
        if not rows:
            return AnomalyDetectionResult(
                flagged_holdings=[],
                all_evaluated_holdings=[],
                unavailable_holdings=[
                    {"symbol": symbol, "reason": reason}
                    for symbol, reason in sorted(unavailable.items())
                ],
                ml_flag_count=0,
                baseline_flag_count=0,
                flag_rate_percent=None,
                window_stability_jaccard=None,
                model_name="IsolationForest",
                baseline_name="Robust Z-Score (MAD)",
                data_cutoff=str(requested_date),
                governance_notice="No eligible complete feature rows; no scores fabricated.",
                status="insufficient_data",
            )

        values = np.vstack([row.loc[FEATURES].to_numpy(dtype=float) for row in rows])
        scaled = self.scaler.transform(values)
        raw_scores = -self.model.decision_function(scaled)
        flags = self.model.predict(scaled) == -1
        percentiles = np.searchsorted(self.training_scores, raw_scores, side="right")
        scores = percentiles / len(self.training_scores) * 100.0
        robust = 0.6745 * np.abs(values - self.training_median) / self.training_mad
        baseline = np.nanmax(robust, axis=1) > 2.5

        items: list[HoldingAnomalyItem] = []
        for index, symbol in enumerate(symbols):
            deviations = np.nan_to_num(robust[index], nan=0.0)
            order = np.argsort(deviations)[::-1][:3]
            total = float(np.sum(deviations[order]))
            contributions = {
                FEATURES[position]: float(deviations[position] / total) if total > 0 else 0.0
                for position in order
            }
            primary = FEATURES[int(order[0])]
            item = HoldingAnomalyItem(
                symbol=symbol,
                company_name=company_map.get(symbol, symbol),
                anomaly_score=round(float(scores[index]), 4),
                is_anomaly_ml=bool(flags[index]),
                is_anomaly_baseline=bool(baseline[index]),
                primary_driver=primary,
                feature_attributions=contributions,
                explanation=(
                    "Contribution shares are absolute robust deviations from the training "
                    "distribution; an anomaly is not a forecast of loss."
                ),
            )
            items.append(item)
        items.sort(key=lambda item: item.anomaly_score, reverse=True)
        all_items = [item.to_dict() for item in items]
        flagged = [
            item.to_dict()
            for item in items
            if item.is_anomaly_ml or item.is_anomaly_baseline
        ]
        stability: float | None = None
        prior_dates = sorted(day for day in set(history.index) if day < requested_date)
        if prior_dates:
            previous_date = prior_dates[-1]
            previous_rows: list[pd.Series] = []
            previous_symbols: list[str] = []
            for symbol in symbols:
                candidates = history[
                    (history["symbol"] == symbol) & (history.index <= previous_date)
                ]
                if not candidates.empty:
                    previous_rows.append(candidates.iloc[-1])
                    previous_symbols.append(symbol)
            if previous_rows:
                previous_values = np.vstack(
                    [row.loc[FEATURES].to_numpy(dtype=float) for row in previous_rows]
                )
                previous_flags = self.model.predict(
                    self.scaler.transform(previous_values)
                ) == -1
                current_set = {
                    symbol for symbol, flag in zip(symbols, flags, strict=False) if flag
                }
                previous_set = {
                    symbol
                    for symbol, flag in zip(
                        previous_symbols, previous_flags, strict=False
                    )
                    if flag
                }
                union = current_set | previous_set
                if union:
                    stability = len(current_set & previous_set) / len(union)
        return AnomalyDetectionResult(
            flagged_holdings=flagged,
            all_evaluated_holdings=all_items,
            unavailable_holdings=[
                {"symbol": symbol, "reason": reason}
                for symbol, reason in sorted(unavailable.items())
            ],
            ml_flag_count=int(np.sum(flags)),
            baseline_flag_count=int(np.sum(baseline)),
            flag_rate_percent=round(float(np.mean(flags) * 100.0), 4),
            window_stability_jaccard=stability,
            model_name="IsolationForest",
            baseline_name="Robust Z-Score (MAD)",
            data_cutoff=str(requested_date),
            governance_notice=(
                "Unsupervised statistical outlier detection; no predictive accuracy or event "
                "causality is claimed. Independent event-review coverage is not inferred."
            ),
        )

    def detect_anomalies(
        self,
        prices_df: pd.DataFrame,
        benchmark_returns: pd.Series | None = None,
        volumes_df: pd.DataFrame | None = None,
        company_names: dict[str, str] | None = None,
        sectors: dict[str, str | None] | None = None,
    ) -> tuple[AnomalyDetectionResult, dict[str, Any]]:
        if benchmark_returns is None or benchmark_returns.empty:
            raise ValueError("benchmark_returns_required")
        if volumes_df is None or volumes_df.empty:
            raise ValueError("volume_history_required")
        if not sectors:
            raise ValueError("sector_classification_required")
        card = self.fit(prices_df, benchmark_returns, volumes_df, sectors)
        result = self.predict(
            prices_df,
            benchmark_returns,
            volumes_df,
            sectors,
            company_names=company_names,
        )
        return result, card
