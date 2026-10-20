"""Statistical and financial loss functions for risk model evaluation."""

import math

import numpy as np
from scipy import stats  # type: ignore[import-untyped]


def qlike_loss(y_true_vol: np.ndarray, y_pred_vol: np.ndarray) -> float:
    """Compute mean QLIKE (Quasi-Likelihood) loss between realized and forecasted volatility.

    QLIKE is strictly proper and robust to noise in realized volatility proxies (Patton 2011):
        L(sigma^2, s_hat^2) = (sigma^2 / s_hat^2) - ln(sigma^2 / s_hat^2) - 1.

    Args:
        y_true_vol: 1D array of realized volatilities (must be strictly positive).
        y_pred_vol: 1D array of forecasted volatilities (must be strictly positive).

    Returns:
        Mean QLIKE loss across observations (>= 0.0, 0.0 indicates perfect forecast).
    """
    y_true = np.asarray(y_true_vol, dtype=float).flatten()
    y_pred = np.asarray(y_pred_vol, dtype=float).flatten()
    if len(y_true) == 0:
        return float("nan")

    # Guard against non-positive inputs
    eps = 1e-6
    var_true = np.maximum(y_true**2, eps)
    var_pred = np.maximum(y_pred**2, eps)

    ratio = var_true / var_pred
    loss = ratio - np.log(ratio) - 1.0
    return float(np.mean(loss))


def mae_log_loss(y_true_vol: np.ndarray, y_pred_vol: np.ndarray) -> float:
    """Mean absolute error on log-volatility scale: mean(|ln(sigma) - ln(s_hat)|)."""
    y_true = np.asarray(y_true_vol, dtype=float).flatten()
    y_pred = np.asarray(y_pred_vol, dtype=float).flatten()
    if len(y_true) == 0:
        return float("nan")

    eps = 1e-6
    log_true = np.log(np.maximum(y_true, eps))
    log_pred = np.log(np.maximum(y_pred, eps))
    return float(np.mean(np.abs(log_true - log_pred)))


def mincer_zarnowitz(y_true_vol: np.ndarray, y_pred_vol: np.ndarray) -> dict[str, float]:
    """Run Mincer-Zarnowitz regression: sigma_true^2 = alpha + beta * sigma_pred^2 + epsilon.

    Evaluates forecast unbiasedness (alpha=0, beta=1) and predictive R^2.
    """
    y_true = np.asarray(y_true_vol, dtype=float).flatten()
    y_pred = np.asarray(y_pred_vol, dtype=float).flatten()
    if len(y_true) < 3:
        return {"r2": 0.0, "alpha": 0.0, "beta": 0.0}

    var_true = y_true**2
    var_pred = y_pred**2

    # Check for zero variance
    if np.allclose(var_pred, var_pred[0]) or np.allclose(var_true, var_true[0]):
        return {"r2": 0.0, "alpha": float(np.mean(var_true)), "beta": 0.0}

    slope, intercept, r_value, _, _ = stats.linregress(var_pred, var_true)
    r2 = max(0.0, float(r_value**2)) if not math.isnan(r_value) else 0.0
    return {
        "r2": r2,
        "alpha": float(intercept),
        "beta": float(slope),
    }


def interval_coverage(
    y_true: np.ndarray, lower_bound: np.ndarray, upper_bound: np.ndarray
) -> float:
    """Empirical coverage rate: fraction of observations falling within [lower, upper]."""
    y = np.asarray(y_true, dtype=float).flatten()
    lb = np.asarray(lower_bound, dtype=float).flatten()
    ub = np.asarray(upper_bound, dtype=float).flatten()
    if len(y) == 0:
        return 0.0

    covered = (y >= lb) & (y <= ub)
    return float(np.mean(covered) * 100.0)


def spearman_ic(predictions: np.ndarray, targets: np.ndarray) -> float:
    """Spearman rank correlation coefficient (Information Coefficient)."""
    p = np.asarray(predictions, dtype=float).flatten()
    t = np.asarray(targets, dtype=float).flatten()
    if len(p) < 3 or np.all(p == p[0]) or np.all(t == t[0]):
        return 0.0

    res = stats.spearmanr(p, t)
    corr = res.statistic if hasattr(res, "statistic") else res[0]
    return 0.0 if math.isnan(corr) else float(corr)


def quintile_spread(scores: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    """Sort observations by score into 5 quintiles and compute outcomes across buckets.

    Returns:
        dict containing mean outcomes per quintile Q1..Q5 and the spread Q5 - Q1.
    """
    s = np.asarray(scores, dtype=float).flatten()
    o = np.asarray(outcomes, dtype=float).flatten()
    if len(s) < 10:
        return {"q1": 0.0, "q2": 0.0, "q3": 0.0, "q4": 0.0, "q5": 0.0, "spread": 0.0}

    # Percentiles for 5 bins
    quantiles = np.quantile(s, [0.2, 0.4, 0.6, 0.8])
    b1 = o[s <= quantiles[0]]
    b2 = o[(s > quantiles[0]) & (s <= quantiles[1])]
    b3 = o[(s > quantiles[1]) & (s <= quantiles[2])]
    b4 = o[(s > quantiles[2]) & (s <= quantiles[3])]
    b5 = o[s > quantiles[3]]

    m1 = float(np.mean(b1)) if len(b1) > 0 else 0.0
    m2 = float(np.mean(b2)) if len(b2) > 0 else 0.0
    m3 = float(np.mean(b3)) if len(b3) > 0 else 0.0
    m4 = float(np.mean(b4)) if len(b4) > 0 else 0.0
    m5 = float(np.mean(b5)) if len(b5) > 0 else 0.0

    return {
        "q1": m1,
        "q2": m2,
        "q3": m3,
        "q4": m4,
        "q5": m5,
        "spread": m5 - m1,
    }


def roc_auc_worst_quintile(scores: np.ndarray, outcomes: np.ndarray) -> float:
    """Compute Area Under the ROC Curve for predicting worst-quintile risk outcomes.

    Positive class: outcome in top 20% worst outcomes (highest risk/drawdown).
    """
    s = np.asarray(scores, dtype=float).flatten()
    o = np.asarray(outcomes, dtype=float).flatten()
    if len(s) < 10:
        return 0.50

    threshold = np.quantile(o, 0.80)
    binary_y = (o >= threshold).astype(int)

    n_pos = np.sum(binary_y == 1)
    n_neg = np.sum(binary_y == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.50

    # Mann-Whitney U statistic calculation for AUC
    ranks = stats.rankdata(s)
    sum_ranks_pos = np.sum(ranks[binary_y == 1])
    u_stat = sum_ranks_pos - (n_pos * (n_pos + 1)) / 2.0
    auc = u_stat / (n_pos * n_neg)
    return float(np.clip(auc, 0.0, 1.0))
