"""Leakage-conscious graph conversion and self-supervised objectives."""

from dataclasses import dataclass

import numpy as np
import torch
from torch import Tensor
from torch_geometric.data import HeteroData  # type: ignore[import-untyped]

from backend.app.gnn.dataset import GraphDataset, Snapshot


@dataclass(frozen=True)
class Scaler:
    stock_mean: np.ndarray
    stock_std: np.ndarray
    industry_mean: np.ndarray
    industry_std: np.ndarray
    market_mean: np.ndarray
    market_std: np.ndarray

    @classmethod
    def fit(cls, dataset: GraphDataset, last_train_index: int) -> "Scaler":
        train = dataset.snapshots[: last_train_index + 1]
        stock = np.concatenate([s.stock_x[s.active] for s in train])
        industry = np.concatenate([s.industry_x for s in train])
        market = np.concatenate([s.market_x for s in train])

        def stats(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            return values.mean(0).astype(np.float32), np.maximum(values.std(0), 1e-6).astype(
                np.float32
            )

        return cls(*stats(stock), *stats(industry), *stats(market))

    def save(self) -> dict[str, list[float]]:
        return {field: getattr(self, field).tolist() for field in self.__dataclass_fields__}

    @classmethod
    def read(cls, data: dict[str, list[float]]) -> "Scaler":
        return cls(
            *(np.asarray(data[field], dtype=np.float32) for field in cls.__dataclass_fields__)
        )


def _bidirectional(pairs: np.ndarray, device: torch.device) -> Tensor:
    if len(pairs) == 0:
        return torch.empty((2, 0), dtype=torch.long, device=device)
    directed = np.concatenate((pairs, pairs[:, ::-1]), axis=0).copy()
    return torch.as_tensor(directed.T, dtype=torch.long, device=device)


def to_heterodata(
    snapshot: Snapshot,
    scaler: Scaler,
    device: torch.device,
    masked_stocks: np.ndarray | None = None,
    withheld_edges: np.ndarray | None = None,
    disabled_relations: frozenset[str] = frozenset(),
    disabled_stock_features: frozenset[int] = frozenset(),
) -> HeteroData:
    """Build six typed relations; held-out edges are removed from all stock channels."""
    graph = HeteroData()
    stock = ((snapshot.stock_x - scaler.stock_mean) / scaler.stock_std).copy()
    if disabled_stock_features:
        stock[:, list(disabled_stock_features)] = 0
    stock[~snapshot.active] = 0
    if masked_stocks is not None:
        stock[masked_stocks] = 0
    graph["stock"].x = torch.as_tensor(
        np.column_stack((stock, snapshot.active.astype(np.float32))),
        dtype=torch.float32,
        device=device,
    )
    industry_x = snapshot.industry_x.copy()
    market_x = snapshot.market_x.copy()
    if masked_stocks is not None:
        visible = snapshot.active.copy()
        visible[masked_stocks] = False
        for industry in range(len(industry_x)):
            members = snapshot.stock_x[visible & (snapshot.stock_industry == industry)]
            industry_x[industry] = (
                (np.median(members[:, 0]), np.median(members[:, 1]), np.std(members[:, 0]))
                if len(members)
                else 0
            )
        members = snapshot.stock_x[visible]
        market_x[0] = (
            (np.median(members[:, 0]), np.median(members[:, 1]), np.std(members[:, 0]))
            if len(members)
            else 0
        )
    graph["industry"].x = torch.as_tensor(
        (industry_x - scaler.industry_mean) / scaler.industry_std,
        dtype=torch.float32,
        device=device,
    )
    graph["market"].x = torch.as_tensor(
        (market_x - scaler.market_mean) / scaler.market_std, dtype=torch.float32, device=device
    )
    withheld = (
        {tuple(sorted(pair)) for pair in withheld_edges.tolist()}
        if withheld_edges is not None
        else set()
    )

    def filter_pairs(pairs: np.ndarray) -> np.ndarray:
        return np.asarray(
            [pair for pair in pairs if tuple(sorted(pair)) not in withheld], dtype=np.int64
        ).reshape(-1, 2)

    graph["stock", "mst", "stock"].edge_index = _bidirectional(
        np.empty((0, 2), dtype=np.int64)
        if "mst" in disabled_relations
        else filter_pairs(snapshot.mst_edges),
        device,
    )
    graph["stock", "correlated", "stock"].edge_index = _bidirectional(
        np.empty((0, 2), dtype=np.int64)
        if "correlated" in disabled_relations
        else filter_pairs(snapshot.correlation_edges),
        device,
    )
    membership = np.column_stack(
        (np.flatnonzero(snapshot.active), snapshot.stock_industry[snapshot.active])
    )
    membership_edges = (
        torch.empty((2, 0), dtype=torch.long, device=device)
        if "industry" in disabled_relations
        else torch.as_tensor(membership.T.copy(), dtype=torch.long, device=device)
    )
    graph["stock", "in_industry", "industry"].edge_index = membership_edges
    graph["industry", "has_stock", "stock"].edge_index = graph[
        "stock", "in_industry", "industry"
    ].edge_index.flip(0)
    industry_ids = np.unique(snapshot.stock_industry[snapshot.active])
    industry_market = np.vstack((industry_ids, np.zeros(len(industry_ids), dtype=np.int64)))
    market_edges = (
        torch.empty((2, 0), dtype=torch.long, device=device)
        if "market" in disabled_relations
        else torch.as_tensor(industry_market, dtype=torch.long, device=device)
    )
    graph["industry", "in_market", "market"].edge_index = market_edges
    graph["market", "has_industry", "industry"].edge_index = graph[
        "industry", "in_market", "market"
    ].edge_index.flip(0)
    return graph


def sample_task(
    snapshot: Snapshot,
    rng: np.random.Generator,
    mask_fraction: float = 0.15,
    edge_fraction: float = 0.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    active = np.flatnonzero(snapshot.active)
    masked = rng.choice(active, max(1, round(len(active) * mask_fraction)), replace=False)
    positives = snapshot.mst_edges[
        rng.choice(
            len(snapshot.mst_edges),
            max(1, round(len(snapshot.mst_edges) * edge_fraction)),
            replace=False,
        )
    ]
    existing = {
        tuple(sorted(pair))
        for pair in np.concatenate((snapshot.mst_edges, snapshot.correlation_edges))
    }
    candidates = [
        (int(a), int(b))
        for i, a in enumerate(active)
        for b in active[i + 1 :]
        if (int(a), int(b)) not in existing
    ]
    if not candidates:
        raise ValueError("No non-edge pairs available for link reconstruction")
    negative_indices = rng.choice(
        len(candidates), len(positives), replace=len(candidates) < len(positives)
    )
    negatives = np.asarray([candidates[int(index)] for index in negative_indices], dtype=np.int64)
    return masked, positives, negatives
