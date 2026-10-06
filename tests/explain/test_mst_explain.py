from __future__ import annotations

import subprocess
from math import exp, sqrt

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import Explanation, MstEdge, MstRun
from backend.app.explain.mst_math import (
    pair_statistics,
    persistence_summary,
    reconstruct_accepted_steps,
    tree_path,
)
from backend.app.explain.service import get_or_create_mst_edge_explanation
from backend.app.explain.templates import build_sentence
from backend.app.main import app
from migrations.versions.b0c1d2e3f419_step_e2_mst_explain_config_v1_2 import CONFIG


def _prices_from_returns(values: list[float]) -> list[float]:
    prices = [100.0]
    for value in values:
        prices.append(prices[-1] * exp(value))
    return prices


def test_hand_calculated_rho_distance_and_beta_on_four_stock_fixture() -> None:
    dates = pd.date_range("2026-01-01", periods=5)
    returns_a = [0.01, 0.02, 0.03, 0.04]
    panel = pd.DataFrame(
        {
            "A": _prices_from_returns(returns_a),
            "B": _prices_from_returns([value * 2 for value in returns_a]),
            "C": _prices_from_returns([-value for value in returns_a]),
            "D": _prices_from_returns([0.04, 0.01, 0.03, 0.02]),
        },
        index=dates,
    )
    result = pair_statistics(panel, "A", "B")
    repeated = pair_statistics(panel, "A", "B")
    assert repeated == result
    assert abs(result.correlation - 1.0) < 1e-12
    assert abs(result.distance - 0.0) < 1e-12
    assert abs(result.distance - sqrt(2 * (1 - result.correlation))) < 1e-12
    assert abs(result.beta_b_on_a - 2.0) < 1e-12
    assert abs(result.r_squared - 1.0) < 1e-12
    assert result.observations == 4


def test_kruskal_steps_reconstruct_persisted_tree_and_group_sizes() -> None:
    persisted = [
        ("A", "B", 0.1, 1),
        ("C", "D", 0.2, 2),
        ("B", "C", 0.3, 3),
    ]
    rebuilt = reconstruct_accepted_steps(["A", "B", "C", "D"], persisted)
    assert [(item.symbol_a, item.symbol_b) for item in rebuilt] == [
        (item[0], item[1]) for item in persisted
    ]
    assert [(item.step, item.left_size, item.right_size) for item in rebuilt] == [
        (1, 1, 1),
        (2, 1, 1),
        (3, 2, 2),
    ]


def test_pair_path_and_weakest_link_on_constructed_tree() -> None:
    edges = [
        ("A", "B", 0.9, 0.45),
        ("B", "C", 0.6, 0.89),
        ("C", "D", 0.4, 1.10),
    ]
    path = tree_path(edges, "A", "D")
    assert [item[:2] for item in path] == [("A", "B"), ("B", "C"), ("C", "D")]
    assert min(item[2] for item in path) == 0.4


def test_persistence_share_and_correlation_range_on_constructed_windows() -> None:
    summary = persistence_summary(
        [True, False, True, True],
        [0.2, 0.4, 0.6, 0.8],
    )
    assert summary.present_windows == 3
    assert summary.total_windows == 4
    assert summary.share == 0.75
    assert summary.minimum == 0.2
    assert summary.median == 0.5
    assert summary.maximum == 0.8


def test_pair_statistics_excludes_prices_after_as_of() -> None:
    dates = pd.date_range("2026-01-01", periods=6)
    base = pd.DataFrame(
        {
            "A": _prices_from_returns([0.01, 0.02, 0.03, 0.04, -0.5]),
            "B": _prices_from_returns([0.02, 0.04, 0.06, 0.08, 0.9]),
        },
        index=dates,
    )
    as_of = dates[-2].date()
    with_future = pair_statistics(base, "A", "B", as_of)
    without_future = pair_statistics(base.iloc[:-1], "A", "B", as_of)
    assert with_future == without_future


def test_e2_templates_never_use_because_and_missing_evidence_omits_sentence() -> None:
    templates = CONFIG["templates"]
    assert isinstance(templates, dict)
    assert all("because" not in str(template).lower() for template in templates.values())
    assert (
        build_sentence(
            str(templates["residual"]),
            {"a": "A", "b": "B", "residual_edge": "false"},
            ["residual"],
            CONFIG,
        )
        is None
    )
    limitations = CONFIG["limitations"]
    assert isinstance(limitations, list)
    assert any("not proof of a business relationship" in item for item in limitations)


def test_layer_2_files_have_zero_git_diff() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            "--",
            "backend/app/correlation_mst",
            "tests/correlation_mst",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_mst_explanation_routes_are_registered() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/api/v1/explain/mst/edge" in paths
    assert "/api/v1/explain/mst/node/{symbol}" in paths
    assert "/api/v1/explain/mst/pair" in paths


def test_edge_explanation_matches_stored_distance_and_reuses_fingerprint(
    session: Session,
) -> None:
    runs = session.scalars(
        select(MstRun).where(MstRun.status == "completed").order_by(desc(MstRun.window_end))
    ).all()
    run = next(
        (item for item in runs if (item.configuration or {}).get("variant", "raw") == "raw"),
        None,
    )
    if run is None:
        pytest.skip("no stored raw MST run")
    edge = session.scalar(
        select(MstEdge).where(MstEdge.mst_run_id == run.id).order_by(MstEdge.edge_rank).limit(1)
    )
    if edge is None or edge.symbol_a is None or edge.symbol_b is None:
        pytest.skip("no stored MST edge")
    before = session.scalar(select(func.count(Explanation.id))) or 0
    first, reused_first, first_row = get_or_create_mst_edge_explanation(
        session, run.id, edge.symbol_a, edge.symbol_b
    )
    second, reused_second, second_row = get_or_create_mst_edge_explanation(
        session, run.id, edge.symbol_a, edge.symbol_b
    )
    assert reused_first is False
    assert reused_second is True
    assert first_row.id == second_row.id
    assert first == second
    assert (session.scalar(select(func.count(Explanation.id))) or 0) == before + 1
    evidence = {item.evidence_id: item for item in first.evidence}
    assert abs(float(evidence["distance"].value) - float(edge.distance)) < 1e-8
    assert first.input_fingerprint
    rendered = " ".join(
        sentence.text for section in first.sections for sentence in section.sentences
    ).lower()
    assert "because" not in rendered
