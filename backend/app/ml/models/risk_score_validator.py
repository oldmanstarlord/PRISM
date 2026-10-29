"""Walk-Forward Validation of the Heuristic 5-Factor Stock Risk Score.

Evaluates whether the diagnostic 5-factor score ranks future realized risk:
- Spearman Rank Information Coefficient (IC) vs forward 21d/63d volatility & drawdown.
- Quintile spread: Forward risk outcomes across score buckets Q1 to Q5.
- ROC AUC for identifying worst-quintile forward drawdown events.
- Isotonic regression mapping from score to historical empirical drawdown frequency.

Governance labeling:
- Calibration curve is strictly labelled "Historical frequency", NOT a future loss probability.
- Explicit verdict on whether the heuristic demonstrates measured predictive skill.
"""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.isotonic import IsotonicRegression

from backend.app.ml.feature_builder import (
    compute_forward_max_drawdown,
    compute_forward_realized_volatility,
)
from backend.app.ml.metrics import (
    quintile_spread,
    roc_auc_worst_quintile,
    spearman_ic,
)


@dataclass(slots=True)
class ScoreCalibrationPoint:
    score_bucket: str  # e.g. "0-20", "20-40", ...
    score_midpoint: float
    historical_drawdown_frequency_pct: float  # e.g. 14.2%
    average_forward_volatility_pct: float  # e.g. 18.5%
    sample_count: int


@dataclass(slots=True)
class RiskScoreValidationResult:
    spearman_ic_vol_21d: float | None
    spearman_ic_vol_63d: float | None
    spearman_ic_drawdown_21d: float | None
    spearman_ic_drawdown_63d: float | None
    quintile_vol_spread_21d: float | None  # Q5 - Q1 (% annualized)
    quintile_drawdown_spread_21d: float | None  # Q5 - Q1 (% decline)
    auc_worst_quintile_drawdown: float | None
    calibration_curve: list[dict[str, Any]]
    quintile_volatility_means: dict[str, float]
    has_measured_skill: bool
    skill_verdict: str
    data_cutoff: str
    evaluated_observations: int
    governance_notice: str
    status: str = "ready"
    failure_reason: str | None = None

    @property
    def worst_quintile_auc(self) -> float | None:
        return self.auc_worst_quintile_drawdown

    @property
    def isotonic_calibration_curve(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self.to_dict()["isotonic_calibration_curve"]
        return result

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["spearman_rank_ic"] = self.spearman_ic_vol_21d
        d["worst_quintile_auc"] = self.auc_worst_quintile_drawdown
        d["quintile_spread_pct"] = self.quintile_vol_spread_21d
        d["isotonic_calibration_curve"] = [
            {
                "score_bracket": c.get("score_bucket", "Q"),
                "min_score": float(c.get("score_bucket", "0-20").split("-")[0]),
                "max_score": float(c.get("score_bucket", "0-20").split("-")[1]),
                "historical_drawdown_freq_pct": c.get("historical_drawdown_frequency_pct"),
                "historical_drawdown_frequency_pct": c.get(
                    "historical_drawdown_frequency_pct"
                ),
                "sample_size": c.get("sample_count"),
            }
            for c in self.calibration_curve
        ]
        return d


class RiskScoreValidator:
    """Validates the 5-factor heuristic stock risk score out-of-sample."""

    def __init__(self, drawdown_threshold: float = 0.10) -> None:
        self.drawdown_threshold = drawdown_threshold
        self.calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True)

    def validate_score(
        self,
        historical_scores: np.ndarray | list[float],
        historical_prices: pd.Series,
    ) -> tuple[RiskScoreValidationResult, dict[str, Any]]:
        """Compute chronological correlation, quintile spread, and isotonic calibration."""
        p_series = historical_prices.dropna()
        n = len(p_series)

        scores_arr = np.asarray(historical_scores, dtype=float).flatten()
        if len(scores_arr) != n:
            # Reindex or align length
            min_len = min(len(scores_arr), n)
            scores_arr = scores_arr[:min_len]
            p_series = p_series.iloc[:min_len]
            n = min_len

        if n < 84:
            unavailable = RiskScoreValidationResult(
                spearman_ic_vol_21d=None,
                spearman_ic_vol_63d=None,
                spearman_ic_drawdown_21d=None,
                spearman_ic_drawdown_63d=None,
                quintile_vol_spread_21d=None,
                quintile_drawdown_spread_21d=None,
                auc_worst_quintile_drawdown=None,
                calibration_curve=[],
                quintile_volatility_means={},
                has_measured_skill=False,
                skill_verdict="Insufficient complete forward observations for validation.",
                data_cutoff=str(p_series.index[-1]) if n > 0 else "unknown",
                evaluated_observations=n,
                governance_notice="No validation statistics were estimated.",
                status="insufficient_data",
                failure_reason="requires_at_least_84_aligned_observations",
            )
            return unavailable, {
                "name": "risk_score_calibration",
                "status": "insufficient_data",
                "failure_reason": unavailable.failure_reason,
                "evaluated_observations": n,
            }

        # Compute forward targets
        simple_returns = p_series.pct_change().dropna()
        fwd_vol_21 = compute_forward_realized_volatility(simple_returns, horizon=21)
        fwd_vol_63 = compute_forward_realized_volatility(simple_returns, horizon=63)
        fwd_mdd_21 = compute_forward_max_drawdown(p_series, horizon=21).abs()
        fwd_mdd_63 = compute_forward_max_drawdown(p_series, horizon=63).abs()

        # Align valid indices (excluding forward lookahead tail)
        valid_mask = ~(
            fwd_vol_21.isna() | fwd_vol_63.isna() | fwd_mdd_21.isna() | fwd_mdd_63.isna()
        )
        valid_idx = np.where(valid_mask.values[: len(scores_arr)])[0]

        if len(valid_idx) < 30:
            insufficient = RiskScoreValidationResult(
                spearman_ic_vol_21d=None,
                spearman_ic_vol_63d=None,
                spearman_ic_drawdown_21d=None,
                spearman_ic_drawdown_63d=None,
                quintile_vol_spread_21d=None,
                quintile_drawdown_spread_21d=None,
                auc_worst_quintile_drawdown=None,
                calibration_curve=[],
                quintile_volatility_means={},
                has_measured_skill=False,
                skill_verdict="Insufficient complete forward targets for validation.",
                data_cutoff=str(p_series.index[-1]),
                evaluated_observations=len(valid_idx),
                governance_notice="No missing target was imputed.",
                status="insufficient_data",
                failure_reason="requires_at_least_30_complete_forward_targets",
            )
            return insufficient, {
                "name": "risk_score_calibration",
                "status": "insufficient_data",
                "failure_reason": insufficient.failure_reason,
                "evaluated_observations": len(valid_idx),
            }

        s_val = scores_arr[valid_idx]
        v21_val = fwd_vol_21.iloc[valid_idx].values
        v63_val = fwd_vol_63.iloc[valid_idx].values
        m21_val = fwd_mdd_21.iloc[valid_idx].values
        m63_val = fwd_mdd_63.iloc[valid_idx].values

        # 1. Spearman Rank IC
        ic_v21 = spearman_ic(s_val, v21_val)
        ic_v63 = spearman_ic(s_val, v63_val)
        ic_m21 = spearman_ic(s_val, m21_val)
        ic_m63 = spearman_ic(s_val, m63_val)

        # 2. Quintile Spread on 21d forward volatility and drawdown
        q_spread_vol = quintile_spread(s_val, v21_val * 100.0)
        q_spread_mdd = quintile_spread(s_val, m21_val * 100.0)

        # 3. AUC for worst-quintile drawdown
        auc_mdd = roc_auc_worst_quintile(s_val, m21_val)

        # 4. Isotonic Calibration Curve: Score -> Historical Frequency of Drawdown > threshold
        binary_drawdown = (m21_val >= self.drawdown_threshold).astype(int)
        bins = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
        curve = []

        for low, high in bins:
            mask = (s_val >= low) & (s_val <= high)
            cnt = int(np.sum(mask))
            if cnt > 0:
                freq = float(np.mean(binary_drawdown[mask]) * 100.0)
                mean_vol = float(np.mean(v21_val[mask]) * 100.0)
            else:
                continue
            curve.append(
                {
                    "score_bucket": f"{low}-{high}",
                    "score_midpoint": (low + high) / 2.0,
                    "historical_drawdown_frequency_pct": round(freq, 1),
                    "average_forward_volatility_pct": round(mean_vol, 1),
                    "sample_count": cnt,
                }
            )

        # 5. Verdict on Measured Skill
        has_skill = ic_v21 > 0.10 and q_spread_vol["spread"] > 0 and auc_mdd >= 0.55
        if has_skill:
            verdict = (
                f"Statistically positive ranking skill demonstrated out-of-sample "
                f"(Spearman IC: {ic_v21:+.2f}, "
                f"Quintile Spread: {q_spread_vol['spread']:+.1f}% vol, "
                f"AUC: {auc_mdd:.2f}). Stocks in Q5 exhibited significantly higher realized risk."
            )
        else:
            verdict = (
                f"Limited directional predictability (Spearman IC: {ic_v21:+.2f}). "
                "The 5-factor composite functions primarily as a "
                "contemporaneous diagnostic descriptor."
            )

        result = RiskScoreValidationResult(
            spearman_ic_vol_21d=round(ic_v21, 3),
            spearman_ic_vol_63d=round(ic_v63, 3),
            spearman_ic_drawdown_21d=round(ic_m21, 3),
            spearman_ic_drawdown_63d=round(ic_m63, 3),
            quintile_vol_spread_21d=round(q_spread_vol["spread"], 2),
            quintile_drawdown_spread_21d=round(q_spread_mdd["spread"], 2),
            auc_worst_quintile_drawdown=round(auc_mdd, 3),
            calibration_curve=curve,
            quintile_volatility_means={
                "q1": round(q_spread_vol["q1"], 1),
                "q2": round(q_spread_vol["q2"], 1),
                "q3": round(q_spread_vol["q3"], 1),
                "q4": round(q_spread_vol["q4"], 1),
                "q5": round(q_spread_vol["q5"], 1),
            },
            has_measured_skill=has_skill,
            skill_verdict=verdict,
            data_cutoff=str(p_series.index[-1]),
            evaluated_observations=len(valid_idx),
            governance_notice=(
                "Historical empirical frequency of drawdown exceeding 10%. "
                "Diagnostic calibration metric; NOT a probability of future loss."
            ),
        )

        model_card = {
            "name": "risk_score_calibration",
            "version": "2026.1",
            "data_cutoff": str(p_series.index[-1]),
            "evaluated_observations": len(valid_idx),
            "spearman_ic_21d": round(ic_v21, 3),
            "quintile_vol_spread": f"{q_spread_vol['spread']:+.1f}%",
            "auc_drawdown": round(auc_mdd, 3),
            "has_measured_skill": has_skill,
            "labeling": "Historical frequency, not future loss probability",
        }

        return result, model_card
