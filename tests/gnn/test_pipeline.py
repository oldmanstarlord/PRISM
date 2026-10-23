"""Synthetic checks only; these tests do not train on user market data."""

import csv
from dataclasses import replace
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import torch

from backend.app.gnn.audit import audit_dataset
from backend.app.gnn.config import GraphConfig
from backend.app.gnn.dataset import (
    GraphDataset,
    build_snapshots,
    dataset_fingerprint,
    read_dataset,
    save_dataset,
    split_indices,
)
from backend.app.gnn.evaluation import evaluate
from backend.app.gnn.learning import Scaler, sample_task, to_heterodata
from backend.app.gnn.model import TemporalHeteroGNN


def _dataset() -> GraphDataset:
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2022-01-03", periods=650).date
    symbols = [f"S{i}" for i in range(6)]
    common = rng.normal(0, 0.008, len(dates))
    returns = common[:, None] + rng.normal(0, 0.005, (len(dates), len(symbols)))
    prices = pd.DataFrame(100 * np.exp(np.cumsum(returns, axis=0)), index=dates, columns=symbols)
    volumes = pd.DataFrame(rng.integers(1000, 5000, prices.shape), index=dates, columns=symbols)
    config = GraphConfig(min_stocks=4, sequence_length=4, embargo_snapshots=3)
    membership = {day: set(symbols) for day in dates}
    names, industries, snapshots = build_snapshots(
        prices,
        volumes,
        {symbol: "A" if index < 3 else "B" for index, symbol in enumerate(symbols)},
        membership,
        config,
    )
    dataset = GraphDataset(names, industries, snapshots, config, "synthetic", datetime.now(UTC), "")
    return GraphDataset(
        names,
        industries,
        snapshots,
        config,
        "synthetic",
        dataset.data_cutoff,
        dataset_fingerprint(dataset),
    )


def test_snapshot_split_and_serialization(tmp_path) -> None:
    dataset = _dataset()
    assert len(dataset.snapshots) > 80
    split = split_indices(len(dataset.snapshots), dataset.config)
    assert all(len(indices) for indices in split.values())
    assert split["validation"][0] - split["train"][-1] > dataset.config.embargo_snapshots
    assert all(
        len(snapshot.mst_edges) == int(snapshot.active.sum()) - 1 for snapshot in dataset.snapshots
    )
    save_dataset(dataset, tmp_path / "graphs")
    restored = read_dataset(tmp_path / "graphs")
    assert restored.symbols == dataset.symbols
    np.testing.assert_array_equal(restored.snapshots[0].mst_edges, dataset.snapshots[0].mst_edges)


def test_masked_graph_and_temporal_backward() -> None:
    dataset = _dataset()
    split = split_indices(len(dataset.snapshots), dataset.config)
    scaler = Scaler.fit(dataset, int(split["train"][-1]))
    current = dataset.snapshots[int(split["train"][3])]
    masked, positive, negative = sample_task(current, np.random.default_rng(7))
    device = torch.device("cpu")
    graphs = [to_heterodata(snapshot, scaler, device) for snapshot in dataset.snapshots[:3]]
    graphs.append(to_heterodata(current, scaler, device, masked, positive))
    assert torch.all(graphs[-1]["stock"].x[masked, :4] == 0)
    assert graphs[-1]["stock", "mst", "stock"].edge_index.shape[1] == 2 * (
        len(current.mst_edges) - len(positive)
    )
    model = TemporalHeteroGNN(hidden=16)
    embeddings = model(graphs)
    logits = model.edge_logits(embeddings, torch.as_tensor(np.concatenate((positive, negative))))
    loss = model.feature_head(embeddings[masked]).square().mean() + logits.square().mean()
    loss.backward()
    assert embeddings.shape == (len(dataset.symbols), 16)
    assert any(parameter.grad is not None for parameter in model.parameters())

    ablated = to_heterodata(
        current,
        scaler,
        device,
        disabled_relations=frozenset({"mst", "correlated", "industry", "market"}),
    )
    assert all(edge_index.shape[1] == 0 for edge_index in ablated.edge_index_dict.values())
    assert model([ablated] * dataset.config.sequence_length).shape == (
        len(dataset.symbols),
        16,
    )


def test_audit_and_baseline_evaluation(tmp_path) -> None:
    dataset = _dataset()
    research_audit = audit_dataset(dataset)
    assert not research_audit["production_eligible"]
    safe_dataset = replace(dataset, universe_mode="source_time_filtered_historical_industry")
    assert audit_dataset(safe_dataset)["production_eligible"]

    drift_path = tmp_path / "stock_drift.csv"
    with drift_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "symbol", "embedding_drift"])
        writer.writeheader()
        for current, prior in zip(dataset.snapshots[1:], dataset.snapshots, strict=False):
            valid = current.active & prior.active
            for stock in np.flatnonzero(valid):
                writer.writerow(
                    {
                        "date": current.day.isoformat(),
                        "symbol": dataset.symbols[int(stock)],
                        "embedding_drift": float(
                            np.linalg.norm(current.stock_x[stock] - prior.stock_x[stock])
                        ),
                    }
                )
    report = evaluate(dataset, drift_path)
    assert report["status"] == "research_only"
    assert "gnn" in report["methods"]
    assert report["samples"]["test"] > 0
