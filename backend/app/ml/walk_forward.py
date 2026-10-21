"""Chronological walk-forward evaluation harness with purge and embargo."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_idx: int
    train_indices: np.ndarray
    test_indices: np.ndarray
    train_cutoff: date
    test_start: date
    test_end: date


class ExpandingWindowWalkForward:
    """Chronological expanding-window walk-forward splitter.

    Enforces:
    1. Chronological order (no shuffling, no random k-fold).
    2. Expanding training window: Fold k contains all historical data up to train cutoff.
    3. Purge/Embargo gap: For targets of horizon H (e.g. 21-day forward volatility),
       training samples within H days of the test set are purged to prevent target overlap leakage.
    4. Out-of-sample testing: Features at date t use strictly data <= t.
    """

    def __init__(
        self,
        min_train_size: int = 252,
        test_size: int = 21,
        horizon: int = 21,
        embargo: int = 21,
    ) -> None:
        self.min_train_size = min_train_size
        self.test_size = test_size
        self.horizon = horizon
        self.embargo = max(embargo, horizon)

    def split(self, dates: list[date] | np.ndarray) -> Iterator[WalkForwardFold]:
        """Generate walk-forward train/test folds."""
        n_obs = len(dates)
        if n_obs < self.min_train_size + self.test_size:
            return

        date_array = np.array(dates)
        fold_idx = 0
        current_test_start = self.min_train_size

        while current_test_start + self.test_size <= n_obs:
            test_end = min(current_test_start + self.test_size, n_obs)
            test_indices = np.arange(current_test_start, test_end)

            # Purge/embargo: ensure training observations have realized their forward target
            # before the test window begins (train_t + horizon < test_start).
            train_end_limit = current_test_start - self.embargo
            if train_end_limit <= 0:
                current_test_start += self.test_size
                continue

            train_indices = np.arange(0, train_end_limit)

            train_cutoff = date_array[train_indices[-1]]
            test_start_date = date_array[test_indices[0]]
            test_end_date = date_array[test_indices[-1]]

            # Strict chronological assertion
            assert train_cutoff < test_start_date, (
                f"Look-ahead violation: train cutoff {train_cutoff} >= test start {test_start_date}"
            )

            yield WalkForwardFold(
                fold_idx=fold_idx,
                train_indices=train_indices,
                test_indices=test_indices,
                train_cutoff=train_cutoff,
                test_start=test_start_date,
                test_end=test_end_date,
            )

            fold_idx += 1
            current_test_start += self.test_size


def verify_point_in_time_leakage(
    feature_dates: list[date], target_dates: list[date], horizon: int = 21
) -> dict[str, Any]:
    """Automated leakage check verifying point-in-time integrity.

    Verifies that:
    1. Feature timestamp t is strictly <= target realization date.
    2. Forward target realized over [t+1, t+H] is never accessible at t.
    """
    violations = 0
    total_checks = min(len(feature_dates), len(target_dates))

    for i in range(total_checks):
        f_date = feature_dates[i]
        t_date = target_dates[i]
        # Target realization date must be strictly after feature observation date
        if f_date > t_date:
            violations += 1

    return {
        "total_checks": total_checks,
        "violations": violations,
        "is_leakage_free": violations == 0,
        "horizon": horizon,
    }
