"""Tests for Step 4 MST endpoints: latest with variants, stability, clusters, and node metrics."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db.models import (
    MstCluster,
    MstEdge,
    MstNode,
    MstNodeMetric,
    MstRun,
    MstStability,
)
from backend.app.db.session import get_session
from backend.app.main import app


def _create_mock_mst_run(variant: str = "raw") -> MstRun:
    run_id = uuid4()
    return MstRun(
        id=run_id,
        universe_id=uuid4(),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 1, 15),
        data_cutoff=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
        requested_symbol_count=3,
        included_symbol_count=3,
        edge_count=2,
        is_connected=True,
        is_acyclic=True,
        exclusions={"items": []},
        configuration={"variant": variant},
        configuration_hash="hash123",
        input_fingerprint="fp123",
        status="completed",
        implementation_version="correlation-mst-v1",
        computed_at=datetime(2026, 1, 16, 2, 0, 0, tzinfo=UTC),
    )


def test_mst_latest_with_variants() -> None:
    raw_run = _create_mock_mst_run(variant="raw")
    sec_a = uuid4()
    sec_b = uuid4()
    sec_c = uuid4()

    mock_nodes = [
        MstNode(
            mst_run_id=raw_run.id,
            security_id=sec_a,
            symbol="INFY",
            industry="IT",
            observations_used=120,
            membership_source="NSE",
        ),
        MstNode(
            mst_run_id=raw_run.id,
            security_id=sec_b,
            symbol="TCS",
            industry="IT",
            observations_used=120,
            membership_source="NSE",
        ),
        MstNode(
            mst_run_id=raw_run.id,
            security_id=sec_c,
            symbol="WIPRO",
            industry="IT",
            observations_used=120,
            membership_source="NSE",
        ),
    ]

    mock_edges = [
        MstEdge(
            mst_run_id=raw_run.id,
            security_a_id=sec_a,
            security_b_id=sec_b,
            symbol_a="INFY",
            symbol_b="TCS",
            correlation=Decimal("0.75"),
            distance=Decimal("0.7071"),
            paired_observations=120,
            edge_rank=1,
        ),
        MstEdge(
            mst_run_id=raw_run.id,
            security_a_id=sec_b,
            security_b_id=sec_c,
            symbol_a="TCS",
            symbol_b="WIPRO",
            correlation=Decimal("0.65"),
            distance=Decimal("0.8366"),
            paired_observations=120,
            edge_rank=2,
        ),
    ]

    mock_session = MagicMock()

    def mock_scalars(statement):
        mock_result = MagicMock()
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstRun:
            mock_result.all.return_value = [raw_run]
        elif entity is MstNode:
            mock_result.all.return_value = mock_nodes
        elif entity is MstEdge:
            mock_result.all.return_value = mock_edges
        elif entity is MstNodeMetric:
            mock_result.all.return_value = [
                MstNodeMetric(
                    run_id=raw_run.id,
                    security_id=sec_b,
                    symbol="TCS",
                    degree=2,
                    weighted_centrality=Decimal("1.40"),
                    hub_rank=1,
                )
            ]
        elif entity is MstCluster:
            mock_result.all.return_value = [
                MstCluster(
                    run_id=raw_run.id,
                    security_id=sec_a,
                    symbol="INFY",
                    cluster_id="CLUST-01",
                    cluster_rule_version="longest-k-edges-v1",
                    cluster_size=3,
                )
            ]
        else:
            mock_result.all.return_value = []
        return mock_result

    mock_session.scalars.side_effect = mock_scalars
    mock_session.scalar.return_value = None

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/mst/latest?variant=raw")
        assert res.status_code == 200
        data = res.json()
        assert data["variant"] == "raw"
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2
        assert "not causation" in data["limitations"][0]

        # TCS node has degree 2 and hub rank 1
        tcs_node = next(n for n in data["nodes"] if n["symbol"] == "TCS")
        assert tcs_node["degree"] == 2
        assert tcs_node["hub_rank"] == 1
    finally:
        app.dependency_overrides.clear()


def test_mst_stability_endpoint() -> None:
    raw_run = _create_mock_mst_run(variant="raw")
    prior_run_id = uuid4()

    mock_stability = MstStability(
        run_id=raw_run.id,
        prior_run_id=prior_run_id,
        edge_persistence=Decimal("0.6000"),
        node_overlap=Decimal("1.0000"),
        window_gap_days=7,
        details={"preserved_edge_count": 6},
    )

    mock_session = MagicMock()

    def mock_scalars(statement):
        mock_res = MagicMock()
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstRun:
            mock_res.all.return_value = [raw_run]
        elif entity is MstStability:
            mock_res.all.return_value = [mock_stability]
        else:
            mock_res.all.return_value = []
        return mock_res

    def mock_scalar(statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstStability:
            return mock_stability
        return None

    mock_session.scalars.side_effect = mock_scalars
    mock_session.scalar.side_effect = mock_scalar
    mock_session.get.return_value = raw_run

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/mst/stability/latest?variant=raw")
        assert res.status_code == 200
        data = res.json()
        assert data["variant"] == "raw"
        assert data["latest_stability"] is not None
        assert data["latest_stability"]["edge_persistence"] == 0.6
        assert data["latest_stability"]["grade"] == "MEDIUM"
        assert data["history_summary"]["windows_evaluated"] == 1
        assert len(data["limitations"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_mst_clusters_endpoint() -> None:
    raw_run = _create_mock_mst_run(variant="raw")
    sec_1 = uuid4()
    sec_2 = uuid4()

    mock_clusters = [
        MstCluster(
            run_id=raw_run.id,
            security_id=sec_1,
            symbol="INFY",
            cluster_id="CLUST-01",
            cluster_rule_version="longest-k-edges-v1",
            cluster_size=2,
        ),
        MstCluster(
            run_id=raw_run.id,
            security_id=sec_2,
            symbol="TCS",
            cluster_id="CLUST-01",
            cluster_rule_version="longest-k-edges-v1",
            cluster_size=2,
        ),
    ]

    mock_session = MagicMock()

    def mock_scalars(statement):
        mock_res = MagicMock()
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstRun:
            mock_res.all.return_value = [raw_run]
        elif entity is MstCluster:
            mock_res.all.return_value = mock_clusters
        else:
            mock_res.all.return_value = []
        return mock_res

    mock_session.scalars.side_effect = mock_scalars

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/mst/clusters/latest?variant=raw")
        assert res.status_code == 200
        data = res.json()
        assert data["variant"] == "raw"
        assert data["clusters_count"] == 1
        assert data["clusters"]["CLUST-01"] == ["INFY", "TCS"]
        assert len(data["members"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_mst_node_metrics_endpoint() -> None:
    raw_run = _create_mock_mst_run(variant="raw")
    sec_id = uuid4()
    other_sec_id = uuid4()

    mock_metric = MstNodeMetric(
        run_id=raw_run.id,
        security_id=sec_id,
        symbol="TCS",
        degree=3,
        weighted_centrality=Decimal("2.100000"),
        hub_rank=1,
    )
    mock_cluster = MstCluster(
        run_id=raw_run.id,
        security_id=sec_id,
        symbol="TCS",
        cluster_id="CLUST-01",
        cluster_rule_version="longest-k-edges-v1",
        cluster_size=2,
    )
    mock_peer_cluster = MstCluster(
        run_id=raw_run.id,
        security_id=other_sec_id,
        symbol="INFY",
        cluster_id="CLUST-01",
        cluster_rule_version="longest-k-edges-v1",
        cluster_size=2,
    )

    mock_edge = MstEdge(
        mst_run_id=raw_run.id,
        security_a_id=sec_id,
        security_b_id=other_sec_id,
        symbol_a="TCS",
        symbol_b="INFY",
        correlation=Decimal("0.85"),
        distance=Decimal("0.5477"),
        paired_observations=120,
        edge_rank=1,
    )

    mock_session = MagicMock()

    def mock_scalars(statement):
        mock_res = MagicMock()
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstRun:
            mock_res.all.return_value = [raw_run]
        elif entity is MstCluster:
            mock_res.all.return_value = [mock_peer_cluster]
        elif entity is MstEdge:
            mock_res.all.return_value = [mock_edge]
        else:
            mock_res.all.return_value = []
        return mock_res

    def mock_scalar(statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is MstRun:
            return raw_run
        if entity is MstNodeMetric:
            return mock_metric
        if entity is MstCluster:
            return mock_cluster
        return None

    mock_session.scalars.side_effect = mock_scalars
    mock_session.scalar.side_effect = mock_scalar

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/mst/nodes/TCS/metrics?variant=raw")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "TCS"
        assert data["degree"] == 3
        assert data["weighted_centrality"] == 2.1
        assert data["hub_rank"] == 1
        assert data["cluster_id"] == "CLUST-01"
        assert "INFY" in data["cluster_peers"]
        assert len(data["incident_edges"]) == 1
        assert data["incident_edges"][0]["neighbor_symbol"] == "INFY"
    finally:
        app.dependency_overrides.clear()
