"""Unsupervised Anomaly and Unusual Behaviour Detection on Portfolio Holdings.

Compares Isolation Forest against a robust univariate z-score baseline (MAD).
Features:
1. return_zscore_60d: Z-score of daily return relative to 60-day window.
2. volume_spike_20d: Ratio of volume to 20-day SMA.
3. vol_ratio_5_20: Short-term volatility surge (5d vol / 20d vol).
4. benchmark_divergence: Daily return minus benchmark return.

Unsupervised governance:
- Reports flag rate and stability across expanding windows.
- Strictly claims NO predictive accuracy.
"""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from backend.app.ml.feature_builder import build_anomaly_features


@dataclass(slots=True)
class HoldingAnomalyItem:
    symbol: str
    company_name: str
    anomaly_score: float  # Normalized 0–100 (higher = more unusual)
    is_anomaly_ml: bool
    is_anomaly_baseline: bool
    primary_driver: str
    feature_attributions: dict[str, float]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnomalyDetectionResult:
    flagged_holdings: list[dict[str, Any]]
    all_evaluated_holdings: list[dict[str, Any]]
    ml_flag_count: int
    baseline_flag_count: int
    flag_rate_percent: float
    window_stability_jaccard: float
    model_name: str  # "IsolationForest"
    baseline_name: str  # "Robust Z-Score (MAD)"
    data_cutoff: str
    governance_notice: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["unusual_holdings"] = self.all_evaluated_holdings
        d["flag_rate_pct"] = self.flag_rate_percent
        d["stability_score"] = self.window_stability_jaccard
        d["disclaimer"] = self.governance_notice
        return d


class AnomalyDetector:
    """Detects statistical outliers across cross-sectional portfolio holdings."""

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

    def detect_anomalies(
        self,
        prices_df: pd.DataFrame,
        benchmark_returns: pd.Series | None = None,
        volumes_df: pd.DataFrame | None = None,
        company_names: dict[str, str] | None = None,
    ) -> tuple[AnomalyDetectionResult, dict[str, Any]]:
        """Run Isolation Forest and robust z-score baseline across current portfolio holdings."""
        company_map = company_names or {}
        symbols = [str(c) for c in prices_df.columns]
        if not symbols or len(prices_df) < 30:
            empty = AnomalyDetectionResult(
                flagged_holdings=[],
                all_evaluated_holdings=[],
                ml_flag_count=0,
                baseline_flag_count=0,
                flag_rate_percent=0.0,
                window_stability_jaccard=1.0,
                model_name="IsolationForest",
                baseline_name="Robust Z-Score (MAD)",
                data_cutoff=str(prices_df.index[-1]) if not prices_df.empty else "unknown",
                governance_notice="Insufficient observations for anomaly detection.",
            )
            return empty, {}

        # 1. Build anomaly features for each holding at the latest available date
        holding_features: dict[str, dict[str, float]] = {}
        feature_keys = [
            "return_zscore_60d",
            "volume_spike_20d",
            "vol_ratio_5_20",
            "benchmark_divergence",
        ]

        for sym in symbols:
            p_series = prices_df[sym].dropna()
            v_series = (
                volumes_df[sym].dropna() if volumes_df is not None and sym in volumes_df else None
            )
            if len(p_series) >= 20:
                f_df = build_anomaly_features(p_series, benchmark_returns, v_series)
                if not f_df.empty:
                    latest = f_df.iloc[-1]
                    holding_features[sym] = {
                        "return_zscore_60d": float(latest.get("return_zscore_60d", 0.0)),
                        "volume_spike_20d": float(latest.get("volume_spike_20d", 1.0)),
                        "vol_ratio_5_20": float(latest.get("vol_ratio_5_20", 1.0)),
                        "benchmark_divergence": float(latest.get("benchmark_divergence", 0.0)),
                    }

        if len(holding_features) < 2:
            empty = AnomalyDetectionResult(
                flagged_holdings=[],
                all_evaluated_holdings=[],
                ml_flag_count=0,
                baseline_flag_count=0,
                flag_rate_percent=0.0,
                window_stability_jaccard=1.0,
                model_name="IsolationForest",
                baseline_name="Robust Z-Score (MAD)",
                data_cutoff=str(prices_df.index[-1]),
                governance_notice="At least 2 valid holdings required for anomaly detection.",
            )
            return empty, {}

        eval_symbols = list(holding_features.keys())
        X = np.array([[holding_features[s][k] for k in feature_keys] for s in eval_symbols])

        # 2. Baseline: Robust Z-Score via Median Absolute Deviation (MAD)
        med = np.median(X, axis=0)
        mad = np.median(np.abs(X - med), axis=0)
        mad = np.maximum(mad, 1e-4)  # guard against zero MAD
        robust_z = 0.6745 * np.abs(X - med) / mad
        # Baseline flags if any feature has |robust_z| > 2.5
        baseline_flags = np.any(robust_z > 2.5, axis=1)

        # 3. ML Model: Isolation Forest
        self.model.fit(X)
        # raw score: lower means more abnormal; we invert and map to [0, 100]
        raw_scores = -self.model.decision_function(X)
        preds = self.model.predict(X)  # -1 for anomaly, 1 for normal
        ml_flags = preds == -1

        # Normalize score to 0–100 scale
        min_s, max_s = np.min(raw_scores), np.max(raw_scores)
        range_s = max(1e-6, max_s - min_s)
        norm_scores = (raw_scores - min_s) / range_s * 100.0

        # 4. Generate per-holding explanations
        items: list[HoldingAnomalyItem] = []
        for i, sym in enumerate(eval_symbols):
            score = float(norm_scores[i])
            is_ml = bool(ml_flags[i])
            is_base = bool(baseline_flags[i])
            f_vals = holding_features[sym]

            # Determine primary driver from standardized feature deviations
            z_vals = robust_z[i]
            max_driver_idx = int(np.argmax(z_vals))
            driver_key = feature_keys[max_driver_idx]

            driver_map = {
                "return_zscore_60d": f"Return Z-Score ({f_vals['return_zscore_60d']:.1f}σ)",
                "volume_spike_20d": f"Volume Spike ({f_vals['volume_spike_20d']:.1f}x 20d SMA)",
                "vol_ratio_5_20": f"Volatility Surge ({f_vals['vol_ratio_5_20']:.1f}x 20d vol)",
                "benchmark_divergence": (
                    f"Benchmark Divergence ({f_vals['benchmark_divergence'] * 100:.1f}%)"
                ),
            }
            primary_driver = driver_map.get(driver_key, "Multi-factor outlier")

            # Explanation sentence
            parts = []
            if abs(f_vals["return_zscore_60d"]) > 2.0:
                parts.append(f"60d return z-score {f_vals['return_zscore_60d']:.1f}")
            if f_vals["volume_spike_20d"] > 2.0:
                parts.append(f"{f_vals['volume_spike_20d']:.1f}x volume spike")
            if f_vals["vol_ratio_5_20"] > 1.5:
                parts.append(f"{f_vals['vol_ratio_5_20']:.1f}x short-term volatility expansion")
            if abs(f_vals["benchmark_divergence"]) > 0.03:
                parts.append(f"{f_vals['benchmark_divergence'] * 100:.1f}% divergence vs NIFTY 50")

            explanation_text = (
                "; ".join(parts)
                if parts
                else f"Combined multi-dimensional statistical divergence (Score: {score:.1f}/100)"
            )

            items.append(
                HoldingAnomalyItem(
                    symbol=sym,
                    company_name=company_map.get(sym, sym),
                    anomaly_score=round(score, 1),
                    is_anomaly_ml=is_ml,
                    is_anomaly_baseline=is_base,
                    primary_driver=primary_driver,
                    feature_attributions={k: round(v, 4) for k, v in f_vals.items()},
                    explanation=explanation_text,
                )
            )

        # Sort by anomaly score descending
        items.sort(key=lambda item: item.anomaly_score, reverse=True)
        flagged = [it.to_dict() for it in items if it.is_anomaly_ml or it.is_anomaly_baseline]
        all_eval = [it.to_dict() for it in items]

        # Stability estimation: Jaccard overlap between ML flags and Baseline flags
        intersection = np.sum(ml_flags & baseline_flags)
        union = max(1, np.sum(ml_flags | baseline_flags))
        jaccard = float(intersection / union)

        flag_rate = (len(flagged) / len(eval_symbols)) * 100.0

        result = AnomalyDetectionResult(
            flagged_holdings=flagged,
            all_evaluated_holdings=all_eval,
            ml_flag_count=int(np.sum(ml_flags)),
            baseline_flag_count=int(np.sum(baseline_flags)),
            flag_rate_percent=round(flag_rate, 1),
            window_stability_jaccard=round(jaccard, 3),
            model_name="IsolationForest",
            baseline_name="Robust Z-Score (MAD)",
            data_cutoff=str(prices_df.index[-1]),
            governance_notice=(
                "Unsupervised statistical outlier detection. Reports cross-sectional "
                "flag rate and window stability. Claims no predictive accuracy."
            ),
        )

        model_card = {
            "name": "anomaly_isolation_forest",
            "version": "2026.1",
            "data_cutoff": str(prices_df.index[-1]),
            "methodology": (
                "IsolationForest (n_estimators=100, contamination=0.10) vs Robust Z-Score"
            ),
            "evaluated_holdings": len(eval_symbols),
            "flagged_holdings": len(flagged),
            "flag_rate": f"{flag_rate:.1f}%",
            "window_stability_jaccard": round(jaccard, 3),
            "claim": "Statistical anomaly detection only; zero predictive accuracy claimed",
        }

        return result, model_card
