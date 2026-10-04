from datetime import date, timedelta

import pytest

from backend.app.validation.walk_forward import walk_forward_splits


def test_walk_forward_is_expanding_chronological_and_purged() -> None:
    dates = [date(2026, 1, 1) + timedelta(days=index) for index in range(12)]

    splits = walk_forward_splits(
        dates, minimum_train_size=5, test_size=2, step_size=2, purge_size=1
    )

    assert len(splits) == 3
    assert splits[0].train_indices == (0, 1, 2, 3, 4)
    assert splits[0].test_indices == (6, 7)
    assert splits[1].train_indices == tuple(range(7))
    assert max(splits[1].train_indices) < min(splits[1].test_indices)


def test_walk_forward_rejects_shuffled_or_duplicate_time() -> None:
    with pytest.raises(ValueError, match="shuffled evaluation is prohibited"):
        walk_forward_splits(
            [date(2026, 1, 2), date(2026, 1, 1)],
            minimum_train_size=1,
            test_size=1,
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        walk_forward_splits(
            [date(2026, 1, 1), date(2026, 1, 1)],
            minimum_train_size=1,
            test_size=1,
        )
