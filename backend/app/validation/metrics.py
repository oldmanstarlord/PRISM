"""Pure, deterministic metrics for honest time-ordered score validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

import numpy as np


@dataclass(frozen=True)
class ForwardTargets:
    realised_volatility_20d: float
    max_drawdown_20d: float
    worst_5d_return: float
    observations: int


class ConfidenceBin(TypedDict):
    lower: float
    upper: float
    n: int
    spearman: float | None
    rank_error: float | None


def average_ranks(values: list[float]) -> list[float]:
    """Return one-based average ranks with deterministic tie handling."""
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average = ((position + 1) + end) / 2.0
        for ordered_index in order[position:end]:
            ranks[ordered_index] = average
        position = end
    return ranks


def spearman_rank_correlation(left: list[float], right: list[float]) -> float | None:
    """Calculate Pearson correlation of average ranks; return None when undefined."""
    if len(left) != len(right):
        raise ValueError("rank correlation inputs must have equal length")
    if len(left) < 2:
        return None
    left_rank = np.asarray(average_ranks(left), dtype=float)
    right_rank = np.asarray(average_ranks(right), dtype=float)
    if float(np.std(left_rank)) == 0.0 or float(np.std(right_rank)) == 0.0:
        return None
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def construct_forward_targets(
    observations: list[tuple[date, float]],
    as_of: date,
    *,
    horizon: int = 20,
    worst_window: int = 5,
    annualisation_factor: int = 252,
) -> ForwardTargets | None:
    """Build labels only from sessions strictly after as_of plus the known as-of close."""
    if horizon < 2 or worst_window < 1 or worst_window > horizon:
        raise ValueError("invalid forward target window")
    ordered = sorted(observations, key=lambda item: item[0])
    if ordered != observations:
        raise ValueError("price observations must be sorted")
    as_of_rows = [item for item in ordered if item[0] == as_of]
    future = [item for item in ordered if item[0] > as_of][:horizon]
    if not as_of_rows or len(future) < horizon:
        return None
    prices = np.asarray([as_of_rows[-1][1], *[value for _, value in future]], dtype=float)
    if np.any(~np.isfinite(prices)) or np.any(prices <= 0):
        return None
    returns = np.diff(np.log(prices))
    realised = float(np.std(returns, ddof=1) * math.sqrt(annualisation_factor))
    running_peak = np.maximum.accumulate(prices)
    max_drawdown = float(np.max((running_peak - prices) / running_peak))
    window_returns = [
        math.exp(float(np.sum(returns[start : start + worst_window]))) - 1.0
        for start in range(0, len(returns) - worst_window + 1)
    ]
    return ForwardTargets(
        realised_volatility_20d=realised,
        max_drawdown_20d=max_drawdown,
        worst_5d_return=min(window_returns),
        observations=len(future),
    )


def cross_section_metrics(scores: list[float], targets: list[float]) -> dict[str, float | None]:
    """Compute rank correlation, decile spread, and top/bottom quintile target means."""
    if len(scores) != len(targets):
        raise ValueError("scores and targets must have equal length")
    if not scores:
        return {
            "spearman": None,
            "decile_spread": None,
            "top_quintile": None,
            "bottom_quintile": None,
        }
    order = sorted(range(len(scores)), key=lambda index: (scores[index], index))
    decile_n = max(1, len(scores) // 10)
    quintile_n = max(1, len(scores) // 5)
    bottom_decile = [targets[index] for index in order[:decile_n]]
    top_decile = [targets[index] for index in order[-decile_n:]]
    bottom_quintile = [targets[index] for index in order[:quintile_n]]
    top_quintile = [targets[index] for index in order[-quintile_n:]]
    return {
        "spearman": spearman_rank_correlation(scores, targets),
        "decile_spread": float(np.mean(top_decile) - np.mean(bottom_decile)),
        "top_quintile": float(np.mean(top_quintile)),
        "bottom_quintile": float(np.mean(bottom_quintile)),
    }


def confidence_calibration(
    rows: list[tuple[float, float, float]],
    bin_edges: list[float],
    *,
    reverse_target: bool = False,
) -> list[ConfidenceBin]:
    """Return correlation and mean absolute rank error for each confidence bin."""
    if len(bin_edges) < 2 or bin_edges != sorted(bin_edges):
        raise ValueError("confidence bin edges must be sorted")
    if not rows:
        return []
    score_ranks = average_ranks([row[0] for row in rows])
    target_values = [-row[2] if reverse_target else row[2] for row in rows]
    target_ranks = average_ranks(target_values)
    denominator = max(1, len(rows) - 1)
    output: list[ConfidenceBin] = []
    for lower, upper in zip(bin_edges[:-1], bin_edges[1:], strict=True):
        indices = [
            index for index, (_, confidence, _) in enumerate(rows) if lower <= confidence < upper
        ]
        correlations = spearman_rank_correlation(
            [rows[index][0] for index in indices],
            [target_values[index] for index in indices],
        )
        error = (
            float(
                np.mean(
                    [
                        abs(score_ranks[index] - target_ranks[index]) / denominator
                        for index in indices
                    ]
                )
            )
            if indices
            else None
        )
        output.append(
            {
                "lower": lower,
                "upper": upper,
                "n": len(indices),
                "spearman": correlations,
                "rank_error": error,
            }
        )
    return output


def layer1_band_rates(values: list[float], bands: list[float]) -> dict[float, float]:
    """Return empirical two-sided absolute-score exceedance rates."""
    if not values:
        return {band: 0.0 for band in bands}
    return {
        band: sum(abs(value) >= band for value in values) / len(values) for band in bands
    }
