"""Chronological self-supervised training; no price-direction target."""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn

from backend.app.gnn.dataset import GraphDataset, split_indices
from backend.app.gnn.learning import Scaler, sample_task, to_heterodata
from backend.app.gnn.model import TemporalHeteroGNN


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 30
    patience: int = 5
    learning_rate: float = 0.001
    hidden: int = 64
    seed: int = 42
    edge_weight: float = 0.5
    disabled_relations: tuple[str, ...] = ()
    disabled_stock_features: tuple[int, ...] = ()


def _loss(
    model: TemporalHeteroGNN,
    dataset: GraphDataset,
    end: int,
    scaler: Scaler,
    device: torch.device,
    rng: np.random.Generator,
    edge_weight: float,
) -> tuple[Tensor, dict[str, float]]:
    current = dataset.snapshots[end]
    masked, positive, negative = sample_task(current, rng)
    start = end - dataset.config.sequence_length + 1
    graphs = [
        to_heterodata(
            dataset.snapshots[index],
            scaler,
            device,
            masked if index == end else None,
            positive if index == end else None,
            frozenset(model.disabled_relations),
            frozenset(model.disabled_stock_features),
        )
        for index in range(start, end + 1)
    ]
    embedding = model(graphs)
    target = torch.as_tensor(
        (current.stock_x[masked] - scaler.stock_mean) / scaler.stock_std,
        dtype=torch.float32,
        device=device,
    )
    feature_loss = nn.functional.smooth_l1_loss(model.feature_head(embedding[masked]), target)
    pairs = torch.as_tensor(np.concatenate((positive, negative)), dtype=torch.long, device=device)
    labels = torch.cat(
        (torch.ones(len(positive), device=device), torch.zeros(len(negative), device=device))
    )
    edge_loss = nn.functional.binary_cross_entropy_with_logits(
        model.edge_logits(embedding, pairs), labels
    )
    total = feature_loss + edge_loss * edge_weight
    return total, {
        "feature_mae": float(
            torch.abs(model.feature_head(embedding[masked]) - target).mean().detach()
        ),
        "edge_accuracy": float(
            ((model.edge_logits(embedding, pairs) > 0) == labels.bool()).float().mean().detach()
        ),
    }


def train(
    dataset: GraphDataset, output: Path, config: TrainConfig, *, device_name: str = "auto"
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    if config.epochs < 1 or config.patience < 1:
        raise ValueError("epochs and patience must be positive")
    splits = split_indices(len(dataset.snapshots), dataset.config)
    if dataset.config.embargo_snapshots < dataset.config.sequence_length - 1:
        raise ValueError("Embargo must be at least sequence_length - 1")
    device = torch.device(
        "cuda"
        if device_name == "auto" and torch.cuda.is_available()
        else "cpu"
        if device_name == "auto"
        else device_name
    )
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(config.seed)
    scaler = Scaler.fit(dataset, int(splits["train"][-1]))
    model = TemporalHeteroGNN(config.hidden).to(device)
    model.disabled_relations = config.disabled_relations
    model.disabled_stock_features = config.disabled_stock_features
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
    output.mkdir(parents=True)
    history: list[dict[str, float | int]] = []
    best = float("inf")
    stale = 0
    for epoch in range(config.epochs):
        model.train()
        train_losses = []
        for index in np.random.default_rng(config.seed + epoch).permutation(splits["train"]):
            optimizer.zero_grad(set_to_none=True)
            loss, _ = _loss(
                model,
                dataset,
                int(index),
                scaler,
                device,
                np.random.default_rng(config.seed * 100000 + epoch * 1000 + int(index)),
                config.edge_weight,
            )
            loss.backward()  # type: ignore[no-untyped-call]
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_losses.append(float(loss.detach()))
        model.eval()
        validation = []
        with torch.no_grad():
            for index in splits["validation"]:
                loss, _ = _loss(
                    model,
                    dataset,
                    int(index),
                    scaler,
                    device,
                    np.random.default_rng(config.seed + int(index)),
                    config.edge_weight,
                )
                validation.append(float(loss))
        row: dict[str, float | int] = {
            "epoch": epoch + 1,
            "train_loss": float(np.mean(train_losses)),
            "validation_loss": float(np.mean(validation)),
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if row["validation_loss"] < best - 1e-5:
            best = float(row["validation_loss"])
            stale = 0
            torch.save(model.state_dict(), output / "best_model.pt")
        else:
            stale += 1
            if stale >= config.patience:
                break
    model.load_state_dict(
        torch.load(output / "best_model.pt", map_location=device, weights_only=True)
    )
    model.disabled_relations = config.disabled_relations
    model.disabled_stock_features = config.disabled_stock_features
    model.eval()
    test_rows = []
    with torch.no_grad():
        for index in splits["test"]:
            loss, metrics = _loss(
                model,
                dataset,
                int(index),
                scaler,
                device,
                np.random.default_rng(config.seed + int(index)),
                config.edge_weight,
            )
            test_rows.append({"loss": float(loss), **metrics})
    report: dict[str, object] = {
        "dataset_fingerprint": dataset.fingerprint,
        "data_cutoff": dataset.data_cutoff.isoformat(),
        "universe_mode": dataset.universe_mode,
        "train_config": asdict(config),
        "graph_config": dataset.config.manifest(),
        "split_dates": {
            name: [
                dataset.snapshots[int(indices[0])].day.isoformat(),
                dataset.snapshots[int(indices[-1])].day.isoformat(),
            ]
            for name, indices in splits.items()
        },
        "split_counts": {name: len(indices) for name, indices in splits.items()},
        "scaler": scaler.save(),
        "history": history,
        "test": {key: float(np.mean([row[key] for row in test_rows])) for key in test_rows[0]},
        "device": str(device),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
