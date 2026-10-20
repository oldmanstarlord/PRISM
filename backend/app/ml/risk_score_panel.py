"""Cross-sectional month-end validation for the analytical five-factor score."""

import math
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from scipy import stats  # type: ignore[import-untyped]

from backend.app.ml.metrics import quintile_spread, roc_auc_worst_quintile, spearman_ic


def _mean_tstat(values: list[float]) -> tuple[float | None, float | None]:
    clean = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if len(clean) < 2:
        return None, None
    mean = float(np.mean(clean))
    standard_error = float(stats.sem(clean))
    return mean, mean / standard_error if standard_error > 0 else None


def validate_cross_sectional_panel(panel: pd.DataFrame) -> dict[str, Any]:
    """Evaluate fixed, volatility-only, and equal-weight scores on a later untouched period."""
    required = {
        "evaluation_date",
        "symbol",
        "score",
        "volatility_only_score",
        "equal_weight_score",
        "forward_volatility_21d",
        "forward_volatility_63d",
        "forward_drawdown_21d",
        "forward_drawdown_63d",
    }
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"validation panel missing columns: {sorted(missing)}")
    complete = panel.dropna(subset=list(required)).copy()
    dates = sorted(complete["evaluation_date"].unique())
    if len(dates) < 12:
        return {
            "status": "insufficient_data",
            "reason": f"requires_12_complete_month_ends; found_{len(dates)}",
            "eligible_rows": len(complete),
        }
    split = max(1, int(len(dates) * 0.70))
    purge_months = 3
    training_dates = dates[: max(0, split - purge_months)]
    test_dates = set(dates[split:])
    test = complete[complete["evaluation_date"].isin(test_dates)]
    if len(test_dates) < 3 or not training_dates:
        return {
            "status": "insufficient_data",
            "reason": "requires_at_least_3_untouched_test_months",
            "eligible_rows": len(complete),
        }

    model_columns = {
        "five_factor_fixed_weights": "score",
        "volatility_only": "volatility_only_score",
        "equal_weight_factors": "equal_weight_score",
    }
    outcomes = {
        "volatility_21d": "forward_volatility_21d",
        "volatility_63d": "forward_volatility_63d",
        "drawdown_21d": "forward_drawdown_21d",
        "drawdown_63d": "forward_drawdown_63d",
    }
    results: dict[str, Any] = {}
    for model_name, score_column in model_columns.items():
        metrics: dict[str, Any] = {}
        for outcome_name, outcome_column in outcomes.items():
            monthly_ic: list[float] = []
            monthly_spread: list[float] = []
            for _, cross_section in test.groupby("evaluation_date"):
                if len(cross_section) < 10:
                    continue
                scores = cross_section[score_column].to_numpy(dtype=float)
                values = cross_section[outcome_column].to_numpy(dtype=float)
                monthly_ic.append(spearman_ic(scores, values))
                monthly_spread.append(quintile_spread(scores, values)["spread"])
            ic_mean, ic_tstat = _mean_tstat(monthly_ic)
            spread_mean, _ = _mean_tstat(monthly_spread)
            metrics[outcome_name] = {
                "mean_monthly_spearman_ic": ic_mean,
                "ic_month_count": len(monthly_ic),
                "ic_t_statistic": ic_tstat,
                "mean_top_minus_bottom_quintile_spread": spread_mean,
            }
        aucs = []
        for _, cross_section in test.groupby("evaluation_date"):
            if len(cross_section) >= 10:
                aucs.append(
                    roc_auc_worst_quintile(
                        cross_section[score_column].to_numpy(dtype=float),
                        cross_section["forward_drawdown_21d"].to_numpy(dtype=float),
                    )
                )
        metrics["worst_quintile_drawdown_21d_auc"] = (
            float(np.nanmean(aucs)) if aucs else None
        )
        results[model_name] = metrics

    fixed = results["five_factor_fixed_weights"]["volatility_21d"][
        "mean_monthly_spearman_ic"
    ]
    comparisons = {}
    for baseline in ("volatility_only", "equal_weight_factors"):
        baseline_value = results[baseline]["volatility_21d"][
            "mean_monthly_spearman_ic"
        ]
        if fixed is None or baseline_value is None:
            verdict = "not_estimable"
        elif fixed > baseline_value:
            verdict = "outperforms"
        elif fixed < baseline_value:
            verdict = "underperforms"
        else:
            verdict = "matches"
        comparisons[baseline] = {
            "selection_metric": "mean_monthly_spearman_ic_volatility_21d_maximize",
            "verdict": verdict,
            "fixed_score_value": fixed,
            "baseline_value": baseline_value,
        }
    return {
        "status": "ready",
        "training_period": [str(training_dates[0]), str(training_dates[-1])],
        "test_period": [str(dates[split]), str(dates[-1])],
        "purge_months": purge_months,
        "eligible_rows": len(complete),
        "test_rows": len(test),
        "test_months": len(test_dates),
        "tie_policy": "average ranks via scipy.stats.spearmanr",
        "missing_policy": "complete cases only; no imputation",
        "auc_positive_class": "top 20 percent forward 21-session drawdown within month",
        "dependence_qualification": (
            "Monthly cross-sections can remain serially dependent; t-statistics are descriptive."
        ),
        "models": results,
        "baseline_comparisons": comparisons,
    }
