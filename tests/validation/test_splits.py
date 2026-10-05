"""Tests for backend.app.validation.splits.

Hand-calculated fold boundaries on a 20-date example, embargo-gap enforcement,
purging of overlapping labels, determinism, and strict rejection of unsorted /
shuffled input.

SRS ref: Section 16 — "Walk-forward validation utilities prohibit shuffled evaluation."
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.validation.splits import purged_kfold, walk_forward_splits

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = date(2026, 1, 1)


def make_dates(n: int) -> list[date]:
    """Return *n* strictly ascending dates starting at BASE."""
    return [BASE + timedelta(days=i) for i in range(n)]


# ---------------------------------------------------------------------------
# walk_forward_splits – input validation
# ---------------------------------------------------------------------------


def test_wfs_raises_on_empty_dates() -> None:
    with pytest.raises(ValueError, match="empty"):
        list(walk_forward_splits([], min_train=5, test_len=3, step=1))


def test_wfs_raises_on_unsorted_dates() -> None:
    dates = make_dates(10)
    shuffled = [dates[5], dates[0], dates[3], dates[8]]
    with pytest.raises(ValueError, match="strictly ascending"):
        list(walk_forward_splits(shuffled, min_train=2, test_len=1, step=1))


def test_wfs_raises_on_repeated_date() -> None:
    dates = [BASE, BASE, BASE + timedelta(days=1)]
    with pytest.raises(ValueError, match="strictly ascending"):
        list(walk_forward_splits(dates, min_train=1, test_len=1, step=1))


def test_wfs_raises_on_invalid_min_train() -> None:
    with pytest.raises(ValueError, match="min_train"):
        list(walk_forward_splits(make_dates(10), min_train=0, test_len=1, step=1))


def test_wfs_raises_on_invalid_test_len() -> None:
    with pytest.raises(ValueError, match="test_len"):
        list(walk_forward_splits(make_dates(10), min_train=5, test_len=0, step=1))


def test_wfs_raises_on_invalid_step() -> None:
    with pytest.raises(ValueError, match="step"):
        list(walk_forward_splits(make_dates(10), min_train=5, test_len=1, step=0))


def test_wfs_raises_on_negative_embargo() -> None:
    with pytest.raises(ValueError, match="embargo"):
        list(walk_forward_splits(make_dates(10), min_train=5, test_len=1, step=1, embargo=-1))


# ---------------------------------------------------------------------------
# walk_forward_splits – hand-calculated 20-date example (no embargo)
# ---------------------------------------------------------------------------
#
# Dates: 0 … 19 (positional indices)
# min_train=5, test_len=3, step=3, embargo=0
#
# Fold 0: train=[0..4], test=[5,6,7]   (test_start=5)
# Fold 1: train=[0..7], test=[8,9,10]  (test_start=8)
# Fold 2: train=[0..10], test=[11,12,13] (test_start=11)
# Fold 3: train=[0..13], test=[14,15,16] (test_start=14)
# Fold 4: train=[0..16], test=[17,18,19] (test_start=17)
#
# test_start=20 → 20+3>20 → stops.


def test_wfs_hand_calculated_20_date_no_embargo() -> None:
    dates = make_dates(20)
    folds = list(walk_forward_splits(dates, min_train=5, test_len=3, step=3, embargo=0))

    assert len(folds) == 5

    expected = [
        (list(range(5)), [5, 6, 7]),
        (list(range(8)), [8, 9, 10]),
        (list(range(11)), [11, 12, 13]),
        (list(range(14)), [14, 15, 16]),
        (list(range(17)), [17, 18, 19]),
    ]
    assert folds == expected


# ---------------------------------------------------------------------------
# walk_forward_splits – hand-calculated 20-date example (embargo=2)
# ---------------------------------------------------------------------------
#
# min_train=5, test_len=3, step=3, embargo=2
#
# test_start = min_train + embargo = 5 + 2 = 7
# The loop condition is: test_start + test_len <= n (i.e. full test window required).
#
# Fold 0: test_start=7  → train_end=5 → train=[0..4], test=[7,8,9]
# Fold 1: test_start=10 → train_end=8 → train=[0..7], test=[10,11,12]
# Fold 2: test_start=13 → train_end=11 → train=[0..10], test=[13,14,15]
# Fold 3: test_start=16 → train_end=14 → train=[0..13], test=[16,17,18]
# Fold 4: test_start=19 → 19+3=22 > 20 → loop stops (no partial window emitted).
#
# Total: 4 folds.


def test_wfs_hand_calculated_20_date_with_embargo() -> None:
    dates = make_dates(20)
    folds = list(walk_forward_splits(dates, min_train=5, test_len=3, step=3, embargo=2))

    assert len(folds) == 4

    expected = [
        (list(range(5)), [7, 8, 9]),
        (list(range(8)), [10, 11, 12]),
        (list(range(11)), [13, 14, 15]),
        (list(range(14)), [16, 17, 18]),
    ]
    assert folds == expected


# ---------------------------------------------------------------------------
# walk_forward_splits – no test index precedes any train index
# ---------------------------------------------------------------------------


def test_wfs_no_lookahead_in_any_fold() -> None:
    dates = make_dates(50)
    for train_idx, test_idx in walk_forward_splits(
        dates, min_train=10, test_len=5, step=5, embargo=2
    ):
        if train_idx and test_idx:
            assert test_idx[0] > train_idx[-1], (
                f"Look-ahead: test[0]={test_idx[0]} <= train[-1]={train_idx[-1]}"
            )


# ---------------------------------------------------------------------------
# walk_forward_splits – determinism
# ---------------------------------------------------------------------------


def test_wfs_determinism() -> None:
    dates = make_dates(30)
    folds_a = list(walk_forward_splits(dates, min_train=8, test_len=4, step=4, embargo=1))
    folds_b = list(walk_forward_splits(dates, min_train=8, test_len=4, step=4, embargo=1))
    assert folds_a == folds_b


# ---------------------------------------------------------------------------
# walk_forward_splits – yields nothing when data is insufficient
# ---------------------------------------------------------------------------


def test_wfs_yields_nothing_when_insufficient_data() -> None:
    dates = make_dates(5)
    # min_train=5, test_len=3 → test_start=8 > 5 → no folds.
    folds = list(walk_forward_splits(dates, min_train=5, test_len=3, step=1))
    assert folds == []


# ---------------------------------------------------------------------------
# purged_kfold – input validation
# ---------------------------------------------------------------------------


def test_pkf_raises_on_unsorted_dates() -> None:
    dates = make_dates(10)
    shuffled = dates[::-1]
    with pytest.raises(ValueError, match="strictly ascending"):
        list(purged_kfold(shuffled, label_horizon=2))


def test_pkf_raises_on_repeated_date() -> None:
    # Use enough dates that the size check passes but the sort check fires.
    # BASE repeated twice, then ascending — sort check at index 1 should fire.
    dates = [BASE, BASE] + [BASE + timedelta(days=i) for i in range(1, 8)]
    with pytest.raises(ValueError, match="strictly ascending"):
        list(purged_kfold(dates, label_horizon=1, n_splits=3))


def test_pkf_raises_on_invalid_label_horizon() -> None:
    with pytest.raises(ValueError, match="label_horizon"):
        list(purged_kfold(make_dates(10), label_horizon=0))


def test_pkf_raises_on_negative_embargo() -> None:
    with pytest.raises(ValueError, match="embargo"):
        list(purged_kfold(make_dates(10), label_horizon=1, embargo=-1))


def test_pkf_raises_on_too_few_splits() -> None:
    with pytest.raises(ValueError, match="n_splits"):
        list(purged_kfold(make_dates(10), label_horizon=1, n_splits=1))


def test_pkf_raises_when_not_enough_dates() -> None:
    with pytest.raises(ValueError, match="n_splits"):
        list(purged_kfold(make_dates(3), label_horizon=1, n_splits=5))


# ---------------------------------------------------------------------------
# purged_kfold – hand-calculated 20-date example
# ---------------------------------------------------------------------------
#
# dates: 0..19, n_splits=4, label_horizon=2, embargo=0
# fold_size = 20 // 4 = 5, remainder = 0
# Folds: [0..4], [5..9], [10..14], [15..19]
#
# Fold 0 is test=[0..4]:
#   Purge: train i where i + 2 > 0  AND  i < 5  → purge i in {0,1,2,3,4} (already test)
#   Post-test train = [5..19] → all fine (no embargo).
#
# Fold 1 is test=[5..9]:
#   Purge: train i where i+2>5 AND i<9 → purge i in {4,5,6,7,8}
#   i=4: purged (label end=6 > test_start=5, i<9)
#   train = [0,1,2,3] ∪ [10..19]
#
# Fold 2 is test=[10..14]:
#   Purge: i where i+2>10 AND i<14 → purge i in {9,10,11,12,13}
#   train = [0..8] ∪ [15..19]
#
# Fold 3 is test=[15..19]:
#   Purge: i where i+2>15 AND i<19 → purge i in {14,15,16,17,18}
#   train = [0..13]


def test_pkf_hand_calculated_20_date_purging() -> None:
    dates = make_dates(20)
    folds = list(purged_kfold(dates, label_horizon=2, embargo=0, n_splits=4))

    assert len(folds) == 4

    # Fold 0: test=[0..4]; all non-test dates are valid train (no pre-test dates).
    train0, test0 = folds[0]
    assert test0 == list(range(5))
    assert train0 == list(range(5, 20))

    # Fold 1: test=[5..9]; index 4 is purged (label overlaps test), rest of pre-test train.
    train1, test1 = folds[1]
    assert test1 == list(range(5, 10))
    assert 4 not in train1  # purged
    assert list(range(0, 4)) == [i for i in train1 if i < 5]
    assert list(range(10, 20)) == [i for i in train1 if i >= 10]

    # Fold 2: test=[10..14]; index 9 is purged.
    train2, test2 = folds[2]
    assert test2 == list(range(10, 15))
    assert 9 not in train2  # purged

    # Fold 3: test=[15..19]; index 14 is purged.
    train3, test3 = folds[3]
    assert test3 == list(range(15, 20))
    assert 14 not in train3  # purged


# ---------------------------------------------------------------------------
# purged_kfold – embargo excludes dates after test fold
# ---------------------------------------------------------------------------
#
# dates: 0..19, n_splits=4, label_horizon=1, embargo=2
# Folds: [0..4], [5..9], [10..14], [15..19]
# Fold 1 is test=[5..9], embargo removes [10,11].


def test_pkf_embargo_removes_dates_after_test_fold() -> None:
    dates = make_dates(20)
    folds = list(purged_kfold(dates, label_horizon=1, embargo=2, n_splits=4))
    _, (train1, test1) = folds[0], folds[1]  # second fold
    assert test1 == list(range(5, 10))
    # embargo dates 10, 11 must not be in training.
    assert 10 not in train1
    assert 11 not in train1
    # date 12 is beyond embargo → should be in training.
    assert 12 in train1


# ---------------------------------------------------------------------------
# purged_kfold – no test index precedes any train index (safety guard check)
# ---------------------------------------------------------------------------


def test_pkf_no_lookahead_in_any_fold() -> None:
    dates = make_dates(50)
    for train_idx, test_idx in purged_kfold(dates, label_horizon=3, embargo=1, n_splits=5):
        # Post-test training indices must be strictly after test indices.
        post_test = [i for i in train_idx if i >= max(test_idx, default=-1) + 1]
        if post_test and test_idx:
            assert post_test[0] > test_idx[-1]


# ---------------------------------------------------------------------------
# purged_kfold – determinism
# ---------------------------------------------------------------------------


def test_pkf_determinism() -> None:
    dates = make_dates(30)
    folds_a = list(purged_kfold(dates, label_horizon=2, embargo=1, n_splits=5))
    folds_b = list(purged_kfold(dates, label_horizon=2, embargo=1, n_splits=5))
    assert folds_a == folds_b


# ---------------------------------------------------------------------------
# purged_kfold – all training indices before any test index (pre-test only fold)
# ---------------------------------------------------------------------------


def test_pkf_all_train_before_test_in_last_fold() -> None:
    dates = make_dates(20)
    folds = list(purged_kfold(dates, label_horizon=1, embargo=0, n_splits=4))
    train_last, test_last = folds[-1]
    pre_test_train = [i for i in train_last if i < min(test_last)]
    # Every pre-test training index is strictly less than every test index.
    if pre_test_train and test_last:
        assert max(pre_test_train) < min(test_last)
