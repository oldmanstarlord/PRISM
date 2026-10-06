from __future__ import annotations

import subprocess
from math import exp

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import Explanation, SectorDivergenceRun, SectorDivergenceScore
from backend.app.explain.sector import build_sector_overview
from backend.app.explain.sector_math import (
    constituent_period_returns,
    contribution_share,
    peer_median_daily_returns,
    persistence_count,
    trend_label,
    weak_absolute_percentile,
)
from backend.app.explain.service import (
    get_or_create_divergence_explanation,
    get_or_create_sector_explanation,
)
from backend.app.explain.templates import build_sentence
from backend.app.main import app
from backend.app.sector_divergence.calculator import calculate_sector_divergence
from backend.app.sector_divergence.inputs import load_inputs
from migrations.versions.c1d2e3f4a520_step_e3_sector_explain_config import CONFIG


def _prices(returns: list[float]) -> list[float]:
    values = [100.0]
    for item in returns:
        values.append(values[-1] * exp(item))
    return values


def test_hand_calculated_peer_median_and_trend_labels() -> None:
    dates = pd.date_range("2026-01-01", periods=4)
    panel = pd.DataFrame(
        {
            "A": _prices([0.01, 0.02, 0.03]),
            "B": _prices([0.03, 0.04, 0.05]),
            "C": _prices([0.02, 0.03, 0.04]),
            "D": _prices([0.04, 0.05, 0.06]),
        },
        index=dates,
    )
    median = peer_median_daily_returns(panel, ["A", "B", "C", "D"], 4)
    repeated = peer_median_daily_returns(panel, ["A", "B", "C", "D"], 4)
    pd.testing.assert_series_equal(median, repeated)
    assert list(median.dropna()) == pytest.approx([0.025, 0.035, 0.045])
    returns = constituent_period_returns(panel, ["A", "B", "C", "D"], 3)
    assert returns["A"] == pytest.approx(100 * (exp(0.06) - 1))
    assert trend_label(1.51, 1.5) == "up"
    assert trend_label(-1.51, 1.5) == "down"
    assert trend_label(1.5, 1.5) == "flat"


def test_absolute_z_percentile_persistence_and_contribution_share() -> None:
    assert weak_absolute_percentile(-2.0, [-3.0, -2.0, 0.5, 1.0]) == 75.0
    assert persistence_count([0.2, 1.1, -1.2, 0.9, 2.0], 1.0, 4) == (3, 4)
    assert contribution_share(40.0, 0.5, 80.0) == 25.0


def test_missing_peer_return_stays_unavailable() -> None:
    dates = pd.date_range("2026-01-01", periods=4)
    panel = pd.DataFrame(
        {
            "A": [100.0, 101.0, 102.0, 103.0],
            "B": [100.0, 101.0, float("nan"), 103.0],
            "C": [100.0, 101.0, 102.0, 103.0],
            "D": [100.0, 101.0, 102.0, 103.0],
        },
        index=dates,
    )
    median = peer_median_daily_returns(panel, list(panel.columns), 4)
    assert pd.isna(median.iloc[2])


def test_peer_median_has_no_lookahead_when_bounded_to_as_of() -> None:
    dates = pd.date_range("2026-01-01", periods=5)
    panel = pd.DataFrame(
        {
            symbol: _prices([0.01, 0.02, 0.03, future])
            for symbol, future in zip(["A", "B", "C", "D"], [0.9, -0.8, 0.7, -0.6], strict=True)
        },
        index=dates,
    )
    bounded = peer_median_daily_returns(panel.loc[: dates[-2]], list(panel.columns), 4)
    without_future = peer_median_daily_returns(panel.iloc[:-1], list(panel.columns), 4)
    pd.testing.assert_series_equal(bounded, without_future)


def test_risk_reading_template_requires_supporting_evidence() -> None:
    templates = CONFIG["templates"]
    assert isinstance(templates, dict)
    assert (
        build_sentence(
            str(templates["risk_supported"]),
            {"supporting_signal": "elevated historical-volatility evidence"},
            ["z_20", "supporting_signal"],
            CONFIG,
        )
        is not None
    )
    assert (
        build_sentence(
            str(templates["risk_supported"]),
            {},
            ["z_20"],
            CONFIG,
        )
        is None
    )


def test_e3_routes_are_registered() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/api/v1/explain/divergence/{symbol}" in paths
    assert "/api/v1/explain/sector/{industry}" in paths
    assert "/api/v1/sectors/overview" in paths


def test_recomputed_layer1_z_matches_stored_and_explanation_is_idempotent(
    session: Session,
) -> None:
    run = session.scalar(
        select(SectorDivergenceRun)
        .where(SectorDivergenceRun.status == "completed")
        .order_by(desc(SectorDivergenceRun.signal_date), desc(SectorDivergenceRun.completed_at))
        .limit(1)
    )
    if run is None:
        pytest.skip("no stored Layer 1 run")
    stored = session.scalar(
        select(SectorDivergenceScore)
        .where(SectorDivergenceScore.run_id == run.id, SectorDivergenceScore.horizon == 20)
        .order_by(SectorDivergenceScore.symbol)
        .limit(1)
    )
    if stored is None:
        pytest.skip("no stored Layer 1 score")
    inputs = load_inputs(session, run.signal_date, run.lookback_start, run.data_cutoff)
    recalculated = calculate_sector_divergence(inputs, computed_at=run.completed_at)
    recomputed = next(
        item
        for item in recalculated.scores
        if item.symbol == stored.symbol and item.horizon == stored.horizon
    )
    assert recomputed.divergence_value == pytest.approx(float(stored.divergence_value), abs=1e-10)
    assert recomputed.residual_value == pytest.approx(float(stored.residual_value), abs=1e-12)

    before = session.scalar(select(func.count(Explanation.id))) or 0
    first, reused_first, first_row = get_or_create_divergence_explanation(session, stored.symbol)
    second, reused_second, second_row = get_or_create_divergence_explanation(session, stored.symbol)
    assert reused_first is False
    assert reused_second is True
    assert first_row.id == second_row.id
    assert first == second
    assert (session.scalar(select(func.count(Explanation.id))) or 0) == before + 1
    evidence = {item.evidence_id: item for item in first.evidence}
    assert float(evidence["z_20"].value) == pytest.approx(float(stored.divergence_value))
    assert first.input_fingerprint

    overview = build_sector_overview(session, run.signal_date)
    overview_item = next(item for item in overview.items if item.industry == stored.industry)
    assert overview_item.stock_count > 0
    sector_payload, sector_reused, _ = get_or_create_sector_explanation(
        session, stored.industry, run.signal_date
    )
    assert sector_reused is False
    assert any(section.key == "flagged" for section in sector_payload.sections)


def test_layer_1_files_have_zero_git_diff() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "--",
            "backend/app/sector_divergence",
            "tests/sector_divergence",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
