"""Approved correlation-mst-v1 implementation using Kruskal and Union-Find."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import sqrt
from uuid import UUID

import numpy as np

from backend.app.correlation_mst.inputs import FORMULA_VERSION, MstInputExclusion, MstInputs

MINIMUM_PAIRED_OBSERVATIONS = 100
NUMERICAL_ZERO_TOLERANCE = 1e-15


@dataclass(frozen=True, slots=True)
class MstExclusion:
    security_id: UUID
    symbol: str
    reason: str
    details: str


@dataclass(frozen=True, slots=True)
class MstNode:
    security_id: UUID
    symbol: str
    industry: str
    observations_used: int
    membership_source: str


@dataclass(frozen=True, slots=True)
class MstEdgeResult:
    security_a_id: UUID
    security_b_id: UUID
    symbol_a: str
    symbol_b: str
    correlation: float
    distance: float
    paired_observations: int
    edge_rank: int


@dataclass(frozen=True, slots=True)
class MstCalculation:
    window_start: date
    window_end: date
    nodes: tuple[MstNode, ...]
    edges: tuple[MstEdgeResult, ...]
    exclusions: tuple[MstExclusion | MstInputExclusion, ...]
    is_connected: bool
    is_acyclic: bool
    implementation_version: str
    computed_at: datetime


class _UnionFind:
    def __init__(self, symbols: list[str]) -> None:
        self.parent = {symbol: symbol for symbol in symbols}
        self.rank = {symbol: 0 for symbol in symbols}

    def find(self, symbol: str) -> str:
        root = symbol
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[symbol] != symbol:
            next_symbol = self.parent[symbol]
            self.parent[symbol] = root
            symbol = next_symbol
        return root

    def union(self, left: str, right: str) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return False
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1
        return True


def _invalid_pair_reason(left: np.ndarray, right: np.ndarray) -> str | None:
    paired = np.isfinite(left) & np.isfinite(right)
    if int(paired.sum()) < MINIMUM_PAIRED_OBSERVATIONS:
        return "insufficient_pairwise_observations"
    if (
        float(np.var(left[paired], ddof=1)) <= NUMERICAL_ZERO_TOLERANCE
        or float(np.var(right[paired], ddof=1)) <= NUMERICAL_ZERO_TOLERANCE
    ):
        return "degenerate_return_variance"
    return None


def calculate_mst(inputs: MstInputs, *, computed_at: datetime | None = None) -> MstCalculation:
    calculation_time = computed_at or datetime.now(UTC)
    if calculation_time.tzinfo is None or calculation_time.utcoffset() is None:
        raise ValueError("computed_at must be timezone-aware")
    if inputs.formula_version != FORMULA_VERSION:
        raise ValueError(f"Unsupported formula version {inputs.formula_version}")
    if inputs.adjusted_closes.index.has_duplicates:
        raise ValueError("Adjusted-close panel contains duplicate dates")
    if inputs.window_end not in inputs.adjusted_closes.index:
        raise ValueError("The requested window end has no adjusted-price observations")

    prices = inputs.adjusted_closes.sort_index().loc[: inputs.window_end]
    returns = np.log(prices.astype("float64")).diff().tail(120)
    active = sorted(inputs.security_ids)
    exclusions: list[MstExclusion | MstInputExclusion] = list(inputs.exclusions)

    for symbol in list(active):
        count = int(np.isfinite(returns[symbol].to_numpy(dtype=float)).sum())
        if count < MINIMUM_PAIRED_OBSERVATIONS:
            active.remove(symbol)
            exclusions.append(
                MstExclusion(
                    inputs.security_ids[symbol], symbol, "insufficient_return_observations",
                    f"Required {MINIMUM_PAIRED_OBSERVATIONS}; found {count}",
                )
            )

    while True:
        invalid: list[tuple[str, str, str]] = []
        for index, symbol_a in enumerate(active):
            left = returns[symbol_a].to_numpy(dtype=float)
            for symbol_b in active[index + 1:]:
                reason = _invalid_pair_reason(left, returns[symbol_b].to_numpy(dtype=float))
                if reason:
                    invalid.append((symbol_a, symbol_b, reason))
        if not invalid:
            break
        counts = {symbol: 0 for symbol in active}
        reasons: dict[str, set[str]] = {symbol: set() for symbol in active}
        for symbol_a, symbol_b, reason in invalid:
            counts[symbol_a] += 1
            counts[symbol_b] += 1
            reasons[symbol_a].add(reason)
            reasons[symbol_b].add(reason)
        removed = sorted(active, key=lambda symbol: (-counts[symbol], symbol))[0]
        active.remove(removed)
        exclusions.append(
            MstExclusion(
                inputs.security_ids[removed], removed, sorted(reasons[removed])[0],
                f"Excluded deterministically to resolve {counts[removed]} invalid pairs",
            )
        )

    if len(active) < 2:
        raise ValueError("Fewer than two securities have a valid complete correlation graph")

    candidates: list[tuple[float, str, str, float, int]] = []
    for index, symbol_a in enumerate(active):
        left = returns[symbol_a].to_numpy(dtype=float)
        for symbol_b in active[index + 1:]:
            right = returns[symbol_b].to_numpy(dtype=float)
            paired = np.isfinite(left) & np.isfinite(right)
            paired_count = int(paired.sum())
            correlation = float(np.corrcoef(left[paired], right[paired])[0, 1])
            correlation = min(1.0, max(-1.0, correlation))
            distance = sqrt(2.0 * (1.0 - correlation))
            candidates.append((distance, symbol_a, symbol_b, correlation, paired_count))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))

    union_find = _UnionFind(active)
    edges: list[MstEdgeResult] = []
    for distance, symbol_a, symbol_b, correlation, paired_count in candidates:
        if not union_find.union(symbol_a, symbol_b):
            continue
        edges.append(
            MstEdgeResult(
                inputs.security_ids[symbol_a], inputs.security_ids[symbol_b],
                symbol_a, symbol_b, correlation, distance, paired_count, len(edges) + 1,
            )
        )
        if len(edges) == len(active) - 1:
            break

    is_connected = len({union_find.find(symbol) for symbol in active}) == 1
    is_acyclic = len(edges) == len(active) - 1
    if not is_connected or not is_acyclic:
        raise ValueError("MST validation failed: graph is not a connected acyclic N-1 tree")
    nodes = tuple(
        MstNode(
            inputs.security_ids[symbol], symbol, inputs.industries[symbol],
            int(np.isfinite(returns[symbol].to_numpy(dtype=float)).sum()),
            inputs.membership_sources[symbol],
        )
        for symbol in active
    )
    exclusions.sort(key=lambda item: (item.symbol, item.reason))
    return MstCalculation(
        window_start=returns.index[0],
        window_end=inputs.window_end,
        nodes=nodes,
        edges=tuple(edges),
        exclusions=tuple(exclusions),
        is_connected=is_connected,
        is_acyclic=is_acyclic,
        implementation_version=FORMULA_VERSION,
        computed_at=calculation_time,
    )
