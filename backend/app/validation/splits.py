"""Walk-forward and purged cross-validation split utilities.

PRISM SRS references
--------------------
- Section 16 item: "Walk-forward validation utilities prohibit shuffled evaluation."
- Section 19 risk: "Lookahead or survivorship bias — Mitigation: Walk-forward tests."
- Section 21 glossary: "Purged validation", "Embargo".

Design rules
------------
- NO look-ahead: every test fold contains only indices *after* all training indices.
- NO shuffling: functions accept sorted sequences and raise ValueError for unsorted input.
- NO ``shuffle`` argument: accepting one would be a design error.
- Embargo: a gap of ``embargo`` indices is removed between training and testing to
  prevent label leakage from overlapping return windows.
- Purging (purged_kfold only): training rows whose label horizon overlaps the test
  period are removed from the training fold.

Both functions return an iterator of (train_indices, test_indices) tuples where every
index is a positional integer into the input ``dates`` sequence.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date


def _assert_sorted(dates: list[date], caller: str) -> None:
    """Raise ValueError if *dates* is not strictly ascending."""
    for i in range(1, len(dates)):
        if dates[i] <= dates[i - 1]:
            raise ValueError(
                f"{caller}: dates must be strictly ascending; "
                f"found dates[{i - 1}]={dates[i - 1]!r} >= dates[{i}]={dates[i]!r}"
            )


def walk_forward_splits(
    dates: list[date],
    min_train: int,
    test_len: int,
    step: int,
    embargo: int = 0,
) -> Iterator[tuple[list[int], list[int]]]:
    """Yield (train_indices, test_indices) pairs using expanding-window walk-forward splits.

    Parameters
    ----------
    dates:
        Strictly ascending sequence of observation dates.  Raises ``ValueError`` if
        the sequence is empty, has fewer than ``min_train + embargo + 1`` entries, or
        is not strictly ascending.
    min_train:
        Minimum number of dates required in the initial training window.  Must be >= 1.
    test_len:
        Number of dates in each test fold.  Must be >= 1.
    step:
        Number of dates to advance the test window between folds.  Must be >= 1.
    embargo:
        Number of dates to exclude immediately after the last training date (before the
        test window begins).  Must be >= 0.  These dates are included in neither fold.

    Yields
    ------
    (train_indices, test_indices):
        Each is a list of positional integers into *dates*.  Every test index is
        strictly greater than every train index (plus embargo gap).

    Raises
    ------
    ValueError:
        - If *dates* is not strictly ascending (catches shuffled input).
        - If any computed test index would precede a training index.
        - If parameter values violate the constraints above.
    """
    if min_train < 1:
        raise ValueError(f"min_train must be >= 1, got {min_train}")
    if test_len < 1:
        raise ValueError(f"test_len must be >= 1, got {test_len}")
    if step < 1:
        raise ValueError(f"step must be >= 1, got {step}")
    if embargo < 0:
        raise ValueError(f"embargo must be >= 0, got {embargo}")
    if not dates:
        raise ValueError("dates must not be empty")

    _assert_sorted(dates, "walk_forward_splits")

    n = len(dates)
    # First test window begins after min_train training dates + embargo gap.
    # train = dates[0 : min_train]
    # embargo_gap = dates[min_train : min_train + embargo]  (excluded)
    # test = dates[min_train + embargo : min_train + embargo + test_len]

    test_start = min_train + embargo
    while test_start + test_len <= n:
        train_end = test_start - embargo  # exclusive upper bound on training
        train_indices = list(range(train_end))
        test_indices = list(range(test_start, min(test_start + test_len, n)))

        # Hard guard: no test index may precede any train index.
        if train_indices and test_indices:
            if test_indices[0] <= train_indices[-1]:
                raise ValueError(
                    f"walk_forward_splits: test index {test_indices[0]} precedes "
                    f"train index {train_indices[-1]}; look-ahead detected"
                )

        yield train_indices, test_indices
        test_start += step


def purged_kfold(
    dates: list[date],
    label_horizon: int,
    embargo: int = 0,
    n_splits: int = 5,
) -> Iterator[tuple[list[int], list[int]]]:
    """Yield (train_indices, test_indices) with purging and an optional embargo.

    The date range is divided into *n_splits* contiguous folds.  For each fold used
    as the test set, any training sample whose label window (of length *label_horizon*)
    overlaps the test window is purged from training.  An additional *embargo* of dates
    immediately following the test fold is excluded from training to prevent leakage
    from the start of the *next* test fold.

    Parameters
    ----------
    dates:
        Strictly ascending sequence of observation dates.  Raises ``ValueError`` if
        the sequence is unsorted or has fewer than *n_splits* + 1 entries.
    label_horizon:
        Number of *forward* dates the label spans (e.g. 5 for a 5-day return label).
        A training sample at index *i* is purged if ``i + label_horizon`` falls inside
        the test fold.  Must be >= 1.
    embargo:
        Number of dates immediately *after* the test fold to exclude from training.
        Must be >= 0.
    n_splits:
        Number of folds.  Must be >= 2.

    Yields
    ------
    (train_indices, test_indices):
        Positional integer indices into *dates*.  Every test index is strictly greater
        than every index in its corresponding training fold (purging only removes
        overlapping training samples; it never reorders folds).

    Raises
    ------
    ValueError:
        - If *dates* is not strictly ascending (catches shuffled input).
        - If any test index precedes a training index (safety guard).
        - If parameter values violate the constraints above.
    """
    if label_horizon < 1:
        raise ValueError(f"label_horizon must be >= 1, got {label_horizon}")
    if embargo < 0:
        raise ValueError(f"embargo must be >= 0, got {embargo}")
    if n_splits < 2:
        raise ValueError(f"n_splits must be >= 2, got {n_splits}")
    if len(dates) < n_splits + 1:
        raise ValueError(
            f"dates has {len(dates)} entries but n_splits={n_splits} requires at least "
            f"{n_splits + 1}"
        )

    _assert_sorted(dates, "purged_kfold")

    n = len(dates)
    # Divide indices into n_splits folds.  Remainder indices go to the last fold.
    fold_size, remainder = divmod(n, n_splits)
    fold_starts: list[int] = []
    start = 0
    for k in range(n_splits):
        fold_starts.append(start)
        start += fold_size + (1 if k < remainder else 0)
    fold_starts.append(n)  # sentinel

    for k in range(n_splits):
        test_start = fold_starts[k]
        test_end = fold_starts[k + 1]  # exclusive
        test_indices = list(range(test_start, test_end))

        # Embargo: exclude dates immediately after test fold.
        embargo_end = min(test_end + embargo, n)

        train_indices: list[int] = []
        for i in range(n):
            if test_start <= i < embargo_end:
                # Inside test fold or embargo window — skip.
                continue
            # Purge: if this training sample's label overlaps the test window.
            label_end = i + label_horizon  # exclusive, 0-indexed
            if label_end > test_start and i < test_end:
                # Overlaps test window.
                continue
            train_indices.append(i)

        # Hard guard: no test index may precede any train index within the test fold.
        # (Training samples *before* the test fold are always allowed.)
        post_test_train = [i for i in train_indices if i >= test_end]
        if post_test_train and test_indices:
            # All post-test training indices must be > every test index.
            if post_test_train[0] <= test_indices[-1]:
                raise ValueError(
                    f"purged_kfold fold {k}: post-test train index "
                    f"{post_test_train[0]} precedes test index {test_indices[-1]}"
                )

        yield train_indices, test_indices
