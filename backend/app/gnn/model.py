"""Heterogeneous spatial encoder followed by a stock-aligned temporal GRU."""

from collections.abc import Sequence
from typing import cast

import torch
from torch import Tensor, nn
from torch_geometric.data import HeteroData  # type: ignore[import-untyped]
from torch_geometric.nn import HeteroConv, SAGEConv  # type: ignore[import-untyped]

RELATIONS = (
    ("stock", "mst", "stock"),
    ("stock", "correlated", "stock"),
    ("stock", "in_industry", "industry"),
    ("industry", "has_stock", "stock"),
    ("industry", "in_market", "market"),
    ("market", "has_industry", "industry"),
)


class TemporalHeteroGNN(nn.Module):
    def __init__(self, hidden: int = 64, dropout: float = 0.15) -> None:
        super().__init__()
        self.encoders = nn.ModuleDict(
            {
                "stock": nn.Linear(5, hidden),
                "industry": nn.Linear(3, hidden),
                "market": nn.Linear(3, hidden),
            }
        )
        self.layers = nn.ModuleList(
            [
                HeteroConv(
                    {relation: SAGEConv((hidden, hidden), hidden) for relation in RELATIONS},
                    aggr="sum",
                )
                for _ in range(2)
            ]
        )
        self.norms = nn.ModuleList(
            [
                nn.ModuleDict({kind: nn.LayerNorm(hidden) for kind in self.encoders})
                for _ in range(2)
            ]
        )
        self.gru = nn.GRU(hidden, hidden, batch_first=True)
        self.feature_head = nn.Sequential(
            nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 4)
        )
        self.edge_head = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, 1)
        )
        self.dropout = nn.Dropout(dropout)
        # Stored on the model so the common training loss can construct the
        # exact same ablated graph for train, validation and test.
        self.disabled_relations: tuple[str, ...] = ()
        self.disabled_stock_features: tuple[int, ...] = ()

    def encode_graph(self, graph: HeteroData) -> Tensor:
        embeddings = {kind: self.encoders[kind](graph[kind].x) for kind in self.encoders}
        for layer, norms in zip(self.layers, self.norms, strict=True):
            propagated = layer(embeddings, graph.edge_index_dict)
            typed_norms = cast(nn.ModuleDict, norms)
            embeddings = {
                kind: torch.relu(typed_norms[kind](embeddings[kind] + propagated[kind]))
                for kind in embeddings
            }
            embeddings = {kind: self.dropout(value) for kind, value in embeddings.items()}
        return cast(Tensor, embeddings["stock"])

    def forward(self, graphs: Sequence[HeteroData]) -> Tensor:
        if not graphs:
            raise ValueError("At least one graph is required")
        spatial = torch.stack([self.encode_graph(graph) for graph in graphs], dim=1)
        output, _ = self.gru(spatial)
        return cast(Tensor, output[:, -1])

    def edge_logits(self, embeddings: Tensor, pairs: Tensor) -> Tensor:
        a, b = embeddings[pairs[:, 0]], embeddings[pairs[:, 1]]
        # A symmetric edge score prevents arbitrary endpoint ordering effects.
        return cast(
            Tensor, self.edge_head(torch.cat((a + b, torch.abs(a - b)), dim=-1)).squeeze(-1)
        )
