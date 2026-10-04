"""Chronological walk-forward splitting that rejects shuffled time series."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

TimeValue = date | datetime


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]
    train_start: TimeValue
    train_end: TimeValue
    test_start: TimeValue
    test_end: TimeValue


def walk_forward_splits(
    observations: Sequence[TimeValue],
    *,
    minimum_train_size: int,
    test_size: int,
    step_size: int | None = None,
    purge_size: int = 0,
) -> tuple[WalkForwardSplit, ...]:
    """Return expanding chronological splits; unordered inputs are rejected, never sorted."""
    if minimum_train_size < 1 or test_size < 1:
        raise ValueError("minimum_train_size and test_size must be positive")
    if purge_size < 0:
        raise ValueError("purge_size cannot be negative")
    step = step_size or test_size
    if step < 1:
        raise ValueError("step_size must be positive")
    if any(left >= right for left, right in zip(observations, observations[1:], strict=False)):
        raise ValueError(
            "observations must be strictly increasing; shuffled evaluation is prohibited"
        )

    splits: list[WalkForwardSplit] = []
    test_start_index = minimum_train_size + purge_size
    while test_start_index < len(observations):
        train_stop = test_start_index - purge_size
        test_stop = min(test_start_index + test_size, len(observations))
        if train_stop < minimum_train_size or test_stop <= test_start_index:
            break
        train_indices = tuple(range(train_stop))
        test_indices = tuple(range(test_start_index, test_stop))
        splits.append(
            WalkForwardSplit(
                train_indices=train_indices,
                test_indices=test_indices,
                train_start=observations[train_indices[0]],
                train_end=observations[train_indices[-1]],
                test_start=observations[test_indices[0]],
                test_end=observations[test_indices[-1]],
            )
        )
        test_start_index += step
    return tuple(splits)
