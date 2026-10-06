"""Meaningful temporal/source checks for reconstructed score-regression panels."""

import gzip
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor

from backend.app.fundamentals.historical_regression import (
    ScoreBlendRegressor,
    blend_search,
    candidates,
    fit_candidate,
    forward_splits,
    simplex_weights,
)
from backend.app.fundamentals.score_estimators import TreeScoreRegressor
from jobs.build_fundamentals import xbrl_row
from jobs.build_historical_fundamentals import history_at, ownership_at


def test_statements_respect_release_delay_and_do_not_copy_current_ttm() -> None:
    original = {
        "Financial_Basis": "Standalone",
        "_financial_history": {"ttm": {"net": 99999}},
    }
    yahoo = {
        "statements": {
            "yearly_income": {
                "2025-03-31": {"TotalRevenue": 1e9, "NetIncome": 1e8},
                "2026-03-31": {"TotalRevenue": 2e9, "NetIncome": 2e8},
            }
        }
    }
    early = history_at(yahoo, original, date(2026, 6, 28))
    released = history_at(yahoo, original, date(2026, 6, 29))
    assert "2026-03-31" not in early["annual"]
    assert released["annual"]["2026-03-31"]["net"] == 20
    assert "ttm" not in released


def test_ownership_uses_actual_release_and_does_not_backfill_revisions() -> None:
    filings = [
        {
            "period": "2026-03-31",
            "release_date": "2026-04-15",
            "record_id": "1",
            "facts": {"Promoter_Pledge": 0},
        },
        {
            "period": "2026-03-31",
            "release_date": "2026-07-15",
            "record_id": "2",
            "facts": {"Promoter_Pledge": 40},
        },
    ]
    assert not ownership_at(filings, date(2026, 4, 14))
    assert ownership_at(filings, date(2026, 6, 30))["2026-03-31"]["facts"]["Promoter_Pledge"] == 0
    assert ownership_at(filings, date(2026, 9, 30))["2026-03-31"]["facts"]["Promoter_Pledge"] == 40


def test_yearly_api_table_does_not_turn_a_stub_year_into_twelve_months() -> None:
    from jobs.fundamental_context import metrics

    original = {
        "Financial_Basis": "Standalone",
        "_financial_history": {"annual": {"2025-03-31": {"months": 10}}},
    }
    yahoo = {
        "statements": {
            "yearly_income": {
                "2025-03-31": {"TotalRevenue": 1e9, "NetIncome": 1e8},
                "2026-03-31": {"TotalRevenue": 2e9, "NetIncome": 2e8},
            }
        }
    }
    history = history_at(yahoo, original, date(2026, 9, 30))
    assert history["annual"]["2025-03-31"]["months"] == 10
    context = metrics(history)
    assert context["Profit_History_Years"] == 1
    assert context["Profit_Growth_YoY"] is None


def test_temporal_splits_train_only_on_earlier_periods() -> None:
    dates = np.array(["2025-03-31", "2025-03-31", "2025-06-30", "2025-09-30"])
    splits = forward_splits(dates, ["2025-06-30", "2025-09-30"], minimum_training=2)
    for train, valid in splits:
        assert max(dates[train]) < min(dates[valid])
    with pytest.raises(ValueError):
        forward_splits(dates, ["2025-03-31"], minimum_training=1)


def test_blends_use_scalar_scores_and_exhaust_all_declared_weights() -> None:
    weights = list(simplex_weights(3))
    assert len(weights) == 66
    assert all(np.isclose(sum(w), 1) and min(w) >= 0 for w in weights)
    actual = np.array([40.2, 59.3, 74.1, 89.7])
    predictions = np.column_stack([actual, actual + 10, actual - 10])
    best, trials = blend_search(actual, predictions)
    assert len(trials) == 66 + 2 * (2**3 - 1)
    assert best["accuracy"] == 1 and best["mae"] == 0
    model = ScoreBlendRegressor(
        [
            ("low", DummyRegressor(strategy="constant", constant=41.1)),
            ("high", DummyRegressor(strategy="constant", constant=83.3)),
        ],
        [0.3, 0.7],
    ).fit(np.zeros((4, 1)), actual)
    assert np.allclose(model.predict(np.zeros((2, 1))), 70.64)


def test_candidate_grid_is_fixed_and_contains_regressors_only() -> None:
    grid = candidates()
    assert len(grid) == 1124
    assert {c["family"] for c in grid} == {
        "ExtraTrees",
        "RandomForest",
        "HistGradientBoosting",
        "XGBoost",
        "CatBoost",
        "Ridge",
        "SVR",
    }
    assert all(c["model"].__sklearn_tags__().estimator_type == "regressor" for c in grid)


@pytest.mark.parametrize("combined,pledged,encumbered", [(0, 0, 0), (6, None, 10)])
def test_legacy_combined_encumbrance_does_not_invent_exact_pledges(
    tmp_path: Path, combined: int, pledged: float | None, encumbered: float
) -> None:
    members = {
        "Total": "ShareholdingPattern",
        "Prom": "ShareholdingOfPromoterAndPromoterGroup",
        "F1": "InstitutionsForeignPortfolioInvestorCatergoryOne",
        "F2": "InstitutionsForeignPortfolioInvestorCatergoryTwo",
    }
    contexts = "".join(
        f'<context id="{context}"><explicitMember>n:{member}Member</explicitMember></context>'
        for context, member in members.items()
    )
    observations = [
        ("NumberOfShares", "Total", 100),
        ("ShareholdingAsAPercentageOfTotalNumberOfShares", "Total", 100),
        ("NumberOfShares", "Prom", 60),
        ("ShareholdingAsAPercentageOfTotalNumberOfShares", "Prom", 60),
        ("PledgedOrEncumberedNumberOfShares", "Prom", combined),
        ("ShareholdingAsAPercentageOfTotalNumberOfShares", "F1", 7),
        ("ShareholdingAsAPercentageOfTotalNumberOfShares", "F2", 3),
    ]
    facts = "".join(
        f'<{tag} contextRef="{context}">{value}</{tag}>' for tag, context, value in observations
    )
    path = tmp_path / "legacy.xml.gz"
    path.write_bytes(gzip.compress(f"<xbrl>{contexts}{facts}</xbrl>".encode()))
    row = xbrl_row(path)
    assert row["Promoter_Pledge"] == pledged
    assert row["Promoter_Encumbrance"] == encumbered
    assert row["FII_Holding"] == 10


def test_sharing_tree_fits_preserves_independent_aggregation_predictions(tmp_path: Path) -> None:
    import json

    x = np.arange(60, dtype=float).reshape(20, 3)
    y = np.linspace(41.1, 89.4, 20)
    train, valid = np.arange(12), np.arange(12, 20)
    models = [
        TreeScoreRegressor(ExtraTreesRegressor(n_estimators=7, random_state=5), aggregation)
        for aggregation in ["mean", "median"]
    ]
    entries = [
        {
            "index": i,
            "family": "ExtraTrees",
            "view": "compact",
            "model": m,
            "definition": {"aggregation": m.aggregation},
        }
        for i, m in enumerate(models)
    ]
    fit_candidate(
        entries[0], {"compact": [(x[train], x[valid])]}, y, [(train, valid)], tmp_path, entries[1]
    )
    for i, model in enumerate(models):
        cached = json.loads((tmp_path / f"{i:04d}.json").read_text())
        independent = model.fit(x[train], y[train]).predict(x[valid])
        assert np.array_equal(cached["predictions"], independent)
