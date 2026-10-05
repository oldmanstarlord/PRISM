"""Step 13 numeric, no-look-ahead, split, ablation, and idempotency tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db.models import Base, ModelConfig, ValidationRun
from backend.app.risk_score.components.base import ComponentValue
from backend.app.risk_score.registry import RegisteredComponentDefinition
from backend.app.risk_score.scorer import RiskScorer
from backend.app.validation.metrics import (
    construct_forward_targets,
    spearman_rank_correlation,
)
from backend.app.validation.service import run_validation
from backend.app.validation.splits import walk_forward_splits


def test_hand_calculated_spearman_rank_correlation() -> None:
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [30.0, 20.0, 10.0]) == pytest.approx(-1.0)
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]) == pytest.approx(1.0)
    assert spearman_rank_correlation([1.0, 1.0], [2.0, 3.0]) is None


def test_forward_targets_use_only_prices_strictly_after_as_of() -> None:
    as_of = date(2026, 1, 10)
    observations = [(as_of - timedelta(days=1), 1_000_000.0), (as_of, 100.0)]
    observations.extend(
        (as_of + timedelta(days=index), value)
        for index, value in enumerate([101.0, 102.0, 99.0, 98.0, 97.0], start=1)
    )
    targets = construct_forward_targets(observations, as_of, horizon=5, worst_window=2)

    assert targets is not None
    assert targets.observations == 5
    assert targets.max_drawdown_20d == pytest.approx((102.0 - 97.0) / 102.0)
    assert targets.worst_5d_return == pytest.approx(98.0 / 102.0 - 1.0)


def test_walk_forward_split_purity_for_monthly_validation() -> None:
    dates = [date(2024, month, 1) for month in range(1, 13)]
    folds = list(walk_forward_splits(dates, min_train=6, test_len=2, step=2, embargo=1))
    assert folds
    for train, test in folds:
        assert max(train) + 1 < min(test)
        assert dates[max(train)] < dates[min(test)]


def test_ablation_removes_only_target_component() -> None:
    securities = [(uuid4(), f"S{index}", "Tech") for index in range(5)]
    definitions = {
        key: RegisteredComponentDefinition(
            id=None,
            component_id=key,
            dimension="market",
            name=key,
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="test",
        )
        for key in ("target", "control")
    }
    values = {
        key: [
            ComponentValue(sec_id, symbol, key, float(index), "ok", date(2026, 1, 1), 0)
            for index, (sec_id, symbol, _) in enumerate(securities)
        ]
        for key in definitions
    }
    config = {"dimension_weights": {"market": 100.0}, "min_coverage_ratio": 0.0}
    full = RiskScorer(config, definitions).synthesize(securities, values)
    ablated = RiskScorer(config, {"control": definitions["control"]}).synthesize(
        securities, {"control": values["control"]}
    )
    for security_id, _, _ in securities:
        full_components = {item.component_id: item for item in full[security_id].components}
        ablated_components = {item.component_id: item for item in ablated[security_id].components}
        assert set(ablated_components) == {"control"}
        assert ablated_components["control"].points == full_components["control"].points


def test_validation_run_is_idempotent_when_no_labels_exist() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    validation_config = {
        "target_horizon_trading_days": 20,
        "worst_return_window_days": 5,
        "minimum_cross_section": 5,
        "random_seed": 13,
        "confidence_bin_edges": [0.0, 50.0, 101.0],
        "layer1_sigma_bands": [1.0, 2.0, 3.0],
        "walk_forward_min_train_periods": 2,
        "walk_forward_test_periods": 1,
        "walk_forward_step_periods": 1,
        "walk_forward_embargo_periods": 1,
        "survivorship_warning": "warning",
        "limitations": [],
    }
    with Session(engine) as session:
        session.add_all([
            ModelConfig(
                id=uuid4(), config_key="validation_parameters", version="1.0.0",
                status="draft", configuration=validation_config,
                configuration_hash="v" * 64, created_at=now, updated_at=now,
            ),
            ModelConfig(
                id=uuid4(), config_key="risk_engine_parameters", version="1.0.0",
                status="approved", configuration={"ablation": {}},
                configuration_hash="s" * 64, created_at=now, updated_at=now,
            ),
        ])
        session.commit()
        first = run_validation(
            session, date(2025, 1, 1), date(2025, 12, 31), run_ablation=False
        )
        second = run_validation(
            session, date(2025, 1, 1), date(2025, 12, 31), run_ablation=False
        )
        assert first.id == second.id
        assert len(session.scalars(select(ValidationRun)).all()) == 1
        assert "No valid forward labels" in str(first.notes["failures"])
