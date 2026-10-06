"""Pure deterministic calculations used by MST explanations, separate from Layer 2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import median

import numpy as np
import pandas as pd

from backend.app.portfolio.shock import calculate_regression_betas


@dataclass(frozen=True, slots=True)
class PairStatistics:
    correlation: float
    distance: float
    beta_b_on_a: float
    r_squared: float
    observations: int
    returns_a: tuple[float, ...]
    returns_b: tuple[float, ...]
    dates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptedEdgeContext:
    symbol_a: str
    symbol_b: str
    step: int
    left_size: int
    right_size: int
    distance: float


@dataclass(frozen=True, slots=True)
class PersistenceSummary:
    present_windows: int
    total_windows: int
    share: float
    minimum: float | None
    median: float | None
    maximum: float | None


def pair_statistics(
    prices: pd.DataFrame, a: str, b: str, as_of: date | None = None
) -> PairStatistics:
    """Reproduce Layer 2 pair returns without imputation and reuse shock beta."""
    if a not in prices or b not in prices:
        raise ValueError("both price columns are required")
    if as_of is None:
        point_in_time = prices
    else:
        mask = [
            (value.date() if isinstance(value, pd.Timestamp) else value) <= as_of
            for value in prices.index
        ]
        point_in_time = prices.loc[mask]
    returns = np.log(point_in_time[[a, b]].astype("float64")).diff().tail(120)
    paired = returns.dropna()
    if len(paired) < 2:
        raise ValueError("at least two paired finite returns are required")
    rho = float(paired[a].corr(paired[b]))
    rho = min(1.0, max(-1.0, rho))
    distance = sqrt(2.0 * (1.0 - rho))
    beta = calculate_regression_betas(paired, a)[b]
    return PairStatistics(
        correlation=rho,
        distance=distance,
        beta_b_on_a=beta,
        r_squared=rho * rho,
        observations=len(paired),
        returns_a=tuple(float(value) for value in paired[a]),
        returns_b=tuple(float(value) for value in paired[b]),
        dates=tuple(
            str(value.date() if hasattr(value, "date") else value) for value in paired.index
        ),
    )


class _Groups:
    def __init__(self, symbols: list[str]) -> None:
        self.parent = {symbol: symbol for symbol in symbols}
        self.members = {symbol: 1 for symbol in symbols}

    def find(self, symbol: str) -> str:
        while self.parent[symbol] != symbol:
            self.parent[symbol] = self.parent[self.parent[symbol]]
            symbol = self.parent[symbol]
        return symbol

    def sizes_and_union(self, a: str, b: str) -> tuple[int, int]:
        left, right = self.find(a), self.find(b)
        if left == right:
            raise ValueError("persisted accepted edge would create a cycle")
        left_size, right_size = self.members[left], self.members[right]
        self.parent[right] = left
        self.members[left] = left_size + right_size
        return left_size, right_size


def reconstruct_accepted_steps(
    symbols: list[str], edges: list[tuple[str, str, float, int]]
) -> list[AcceptedEdgeContext]:
    """Recover group sizes from the persisted one-based acceptance order."""
    groups = _Groups(sorted(symbols))
    ordered = sorted(edges, key=lambda item: item[3])
    if [edge[3] for edge in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("persisted edge ranks are not consecutive")
    output: list[AcceptedEdgeContext] = []
    for a, b, distance, step in ordered:
        left_size, right_size = groups.sizes_and_union(a, b)
        output.append(AcceptedEdgeContext(a, b, step, left_size, right_size, distance))
    if len(symbols) > 1 and len(output) != len(symbols) - 1:
        raise ValueError("persisted tree does not contain N-1 accepted edges")
    return output


def tree_path(
    edges: list[tuple[str, str, float, float]], start: str, end: str
) -> list[tuple[str, str, float, float]]:
    adjacency: dict[str, list[tuple[str, float, float]]] = {}
    for a, b, rho, distance in edges:
        adjacency.setdefault(a, []).append((b, rho, distance))
        adjacency.setdefault(b, []).append((a, rho, distance))
    queue: deque[tuple[str, list[tuple[str, str, float, float]]]] = deque([(start, [])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        if current == end:
            return path
        for neighbour, rho, distance in sorted(adjacency.get(current, [])):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append((neighbour, [*path, (current, neighbour, rho, distance)]))
    raise LookupError(f"no stored tree path between {start} and {end}")


def persistence_summary(present: list[bool], correlations: list[float]) -> PersistenceSummary:
    if len(present) != len(correlations):
        raise ValueError("presence and correlation windows must align")
    total = len(present)
    return PersistenceSummary(
        present_windows=sum(present),
        total_windows=total,
        share=sum(present) / total if total else 0.0,
        minimum=min(correlations) if correlations else None,
        median=median(correlations) if correlations else None,
        maximum=max(correlations) if correlations else None,
    )


def downsample[T](items: list[T], maximum: int) -> list[T]:
    if maximum < 1:
        raise ValueError("maximum must be positive")
    if len(items) <= maximum:
        return items
    indices = np.linspace(0, len(items) - 1, maximum, dtype=int)
    return [items[int(index)] for index in indices]
