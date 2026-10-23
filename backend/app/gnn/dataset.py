"""Historical graph snapshots and safe numeric artifact format."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    PriceDailyAdjusted,
    PriceDailyRaw,
    SecurityAlias,
    SecurityIndustryHistory,
    Universe,
    UniverseMembership,
)
from backend.app.gnn.config import (
    INDUSTRY_FEATURES,
    MARKET_FEATURES,
    SCHEMA_VERSION,
    STOCK_FEATURES,
    GraphConfig,
)
from backend.app.sector_divergence.inputs import (
    load_latest_adjusted_closes,
    load_universe_members,
)


@dataclass(frozen=True)
class Snapshot:
    day: date
    stock_x: np.ndarray
    industry_x: np.ndarray
    market_x: np.ndarray
    active: np.ndarray
    mst_edges: np.ndarray
    correlation_edges: np.ndarray
    stock_industry: np.ndarray


@dataclass(frozen=True)
class GraphDataset:
    symbols: tuple[str, ...]
    industries: tuple[str, ...]
    snapshots: tuple[Snapshot, ...]
    config: GraphConfig
    universe_mode: str
    data_cutoff: datetime
    fingerprint: str


def dataset_fingerprint(dataset: GraphDataset) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "symbols": dataset.symbols,
                "industries": dataset.industries,
                "dates": [snapshot.day.isoformat() for snapshot in dataset.snapshots],
                "config": dataset.config.manifest(),
                "mode": dataset.universe_mode,
            },
            sort_keys=True,
        ).encode()
    )
    for snapshot in dataset.snapshots:
        for value in (
            snapshot.stock_x,
            snapshot.industry_x,
            snapshot.market_x,
            snapshot.active,
            snapshot.mst_edges,
            snapshot.correlation_edges,
            snapshot.stock_industry,
        ):
            digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def split_indices(count: int, config: GraphConfig) -> dict[str, np.ndarray]:
    """Chronological windows with an embargo around both boundaries."""
    config.validate()
    start = config.sequence_length - 1
    first = max(start + 1, int(count * config.train_fraction))
    second = max(
        first + config.embargo_snapshots + 1,
        int(count * (config.train_fraction + config.validation_fraction)),
    )
    gap = config.embargo_snapshots
    splits = {
        "train": np.arange(start, first, dtype=np.int64),
        "validation": np.arange(first + gap, second, dtype=np.int64),
        "test": np.arange(second + gap, count, dtype=np.int64),
    }
    if any(len(index) == 0 for index in splits.values()):
        raise ValueError(
            "Too few snapshots for train, validation and test with the chosen sequence and embargo"
        )
    return splits


def _edges(
    returns: np.ndarray, active: np.ndarray, config: GraphConfig
) -> tuple[np.ndarray, np.ndarray]:
    indices = np.flatnonzero(active)
    pairs: list[tuple[float, int, int]] = []
    for offset, left_index in enumerate(indices):
        for right_index in indices[offset + 1 :]:
            a, b = returns[:, left_index], returns[:, right_index]
            paired = np.isfinite(a) & np.isfinite(b)
            if int(paired.sum()) < config.min_return_observations:
                continue
            corr = float(np.corrcoef(a[paired], b[paired])[0, 1])
            if np.isfinite(corr):
                pairs.append((corr, int(left_index), int(right_index)))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    parent = {int(index): int(index) for index in indices}

    def root(index: int) -> int:
        while parent[index] != index:
            index = parent[index]
        return index

    tree: list[tuple[int, int]] = []
    for _, left, right in pairs:
        root_left, root_right = root(left), root(right)
        if root_left != root_right:
            parent[root_right] = root_left
            tree.append((left, right))
    if len(tree) != len(indices) - 1:
        raise ValueError("Valid stock correlations do not form a connected tree")
    tree_set = set(tree)
    neighbors: dict[int, int] = {int(index): 0 for index in indices}
    correlated: list[tuple[int, int]] = []
    for corr, left, right in pairs:
        if corr < config.correlation_floor or (left, right) in tree_set:
            continue
        if (
            neighbors[left] >= config.max_correlation_neighbors
            or neighbors[right] >= config.max_correlation_neighbors
        ):
            continue
        correlated.append((left, right))
        neighbors[left] += 1
        neighbors[right] += 1

    def array(values: list[tuple[int, int]]) -> np.ndarray:
        return np.asarray(values, dtype=np.int64).reshape(-1, 2)

    return array(tree), array(correlated)


def build_snapshots(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    industries_by_symbol: dict[str, str],
    membership_by_day: dict[date, set[str]],
    config: GraphConfig,
    industries_by_day: dict[date, dict[str, str]] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[Snapshot, ...]]:
    """Build weekly graphs without filling missing market observations."""
    config.validate()
    symbols = tuple(sorted(industries_by_symbol))
    all_industries = set(industries_by_symbol.values())
    if industries_by_day is not None:
        all_industries.update(
            industry for mapping in industries_by_day.values() for industry in mapping.values()
        )
    industries = tuple(sorted(all_industries))
    if not symbols or prices.index.has_duplicates:
        raise ValueError("Empty universe or duplicate price dates")
    prices = prices.reindex(columns=list(symbols)).sort_index()
    volumes = volumes.reindex(index=prices.index, columns=list(symbols))
    log_prices = np.log(prices.where(prices > 0).to_numpy(dtype=np.float64))
    returns = np.diff(log_prices, axis=0, prepend=np.full((1, len(symbols)), np.nan))
    vol = volumes.to_numpy(dtype=np.float64)
    snapshots: list[Snapshot] = []
    for end in range(config.lookback_days, len(prices), config.snapshot_step):
        day = prices.index[end]
        if not isinstance(day, date) or day not in membership_by_day:
            continue
        day_industries = (
            industries_by_day.get(day, {})
            if industries_by_day is not None
            else industries_by_symbol
        )
        stock_industry = np.asarray(
            [
                industries.index(
                    day_industries.get(symbol, industries_by_symbol.get(symbol, industries[0]))
                )
                for symbol in symbols
            ],
            dtype=np.int64,
        )
        window = returns[end - config.lookback_days + 1 : end + 1]
        active = np.asarray([symbol in membership_by_day[day] for symbol in symbols], dtype=bool)
        if industries_by_day is not None:
            active &= np.asarray([symbol in day_industries for symbol in symbols], dtype=bool)
        active &= np.isfinite(log_prices[end])
        active &= np.sum(np.isfinite(window), axis=0) >= config.min_return_observations
        if int(active.sum()) < config.min_stocks:
            continue
        features = np.zeros((len(symbols), len(STOCK_FEATURES)), dtype=np.float32)
        for index in np.flatnonzero(active):
            recent = window[:, index]
            last5 = recent[-5:]
            v20 = vol[end - 19 : end + 1, index]
            previous = vol[end - 39 : end - 19, index]
            valid_recent = np.isfinite(v20) & (v20 >= 0)
            valid_previous = np.isfinite(previous) & (previous >= 0)
            if not np.isfinite(last5).all() or not valid_recent.all() or not valid_previous.all():
                active[index] = False
                continue
            close60 = log_prices[end - 59 : end + 1, index]
            if not np.isfinite(close60).all():
                active[index] = False
                continue
            features[index] = (
                float(last5.sum()),
                float(np.nanstd(recent[-20:], ddof=1) * np.sqrt(252)),
                float(np.log1p(v20.mean()) - np.log1p(previous.mean())),
                float(np.exp(close60[-1] - np.max(close60)) - 1),
            )
            if not np.isfinite(features[index]).all():
                active[index] = False
                features[index] = 0
        if int(active.sum()) < config.min_stocks:
            continue
        industry_x = np.zeros((len(industries), len(INDUSTRY_FEATURES)), dtype=np.float32)
        for industry_index in range(len(industries)):
            members = features[active & (stock_industry == industry_index)]
            if len(members):
                industry_x[industry_index] = (
                    np.median(members[:, 0]),
                    np.median(members[:, 1]),
                    np.std(members[:, 0]),
                )
        members = features[active]
        market_x = np.asarray(
            [[np.median(members[:, 0]), np.median(members[:, 1]), np.std(members[:, 0])]],
            dtype=np.float32,
        )
        try:
            mst, correlation = _edges(window, active, config)
        except ValueError:
            continue
        snapshots.append(
            Snapshot(
                day, features, industry_x, market_x, active, mst, correlation, stock_industry.copy()
            )
        )
    return symbols, industries, tuple(snapshots)


def load_from_database(
    session: Session,
    start: date,
    end: date,
    config: GraphConfig,
    *,
    research_fixed_universe: bool = False,
) -> GraphDataset:
    """Read stored revisions; research mode uses later-known membership and prices."""
    if start >= end:
        raise ValueError("start must precede end")
    all_dates = (
        session.execute(
            select(PriceDailyAdjusted.trade_date)
            .where(PriceDailyAdjusted.trade_date.between(start, end))
            .distinct()
            .order_by(PriceDailyAdjusted.trade_date)
        )
        .scalars()
        .all()
    )
    if len(all_dates) < config.lookback_days + config.snapshot_step:
        raise ValueError("Insufficient stored adjusted-price dates")
    candidate_days = all_dates[config.lookback_days :: config.snapshot_step]
    fixed_members = load_universe_members(session, end) if research_fixed_universe else []
    membership_by_day: dict[date, set[str]] = {}
    membership_ids_by_day: dict[date, set[UUID]] = {}
    members_by_id: dict[UUID, str] = {}
    industries: dict[str, str] = {}
    industries_by_day: dict[date, dict[str, str]] = {}
    for day in candidate_days:
        members = fixed_members if research_fixed_universe else load_universe_members(session, day)
        if not research_fixed_universe:
            known_rows = session.execute(
                select(UniverseMembership.security_id, SecurityAlias.symbol)
                .join(Universe, Universe.id == UniverseMembership.universe_id)
                .join(SecurityAlias, SecurityAlias.security_id == UniverseMembership.security_id)
                .where(
                    Universe.name == "NIFTY 200",
                    UniverseMembership.valid_from <= day,
                    (UniverseMembership.valid_to.is_(None) | (UniverseMembership.valid_to >= day)),
                    UniverseMembership.ingested_at <= datetime.combine(day, time.max, tzinfo=UTC),
                    SecurityAlias.valid_from <= day,
                    (SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= day)),
                    SecurityAlias.ingested_at <= datetime.combine(day, time.max, tzinfo=UTC),
                    SecurityAlias.exchange == "NSE",
                )
            ).all()
            known = {(row.security_id, row.symbol) for row in known_rows}
            members = [member for member in members if (member.security_id, member.symbol) in known]
        membership_ids_by_day[day] = {member.security_id for member in members if member.industry}
        for member in members:
            if member.industry:
                members_by_id[member.security_id] = member.symbol
                if research_fixed_universe:
                    industries[member.symbol] = member.industry.strip()
        if not research_fixed_universe and members:
            member_ids = [member.security_id for member in members]
            history_rows = session.execute(
                select(SecurityIndustryHistory.security_id, SecurityIndustryHistory.industry)
                .where(
                    SecurityIndustryHistory.security_id.in_(member_ids),
                    SecurityIndustryHistory.valid_from <= day,
                    (
                        SecurityIndustryHistory.valid_to.is_(None)
                        | (SecurityIndustryHistory.valid_to >= day)
                    ),
                    SecurityIndustryHistory.ingested_at
                    <= datetime.combine(day, time.max, tzinfo=UTC),
                )
                .order_by(SecurityIndustryHistory.valid_from.desc())
            ).all()
            history_by_id: dict[UUID, str] = {}
            for history_row in history_rows:
                history_by_id.setdefault(
                    history_row.security_id, history_row.industry.strip()
                )
            industries_by_day[day] = {
                member.symbol: history_by_id[member.security_id]
                for member in members
                if member.security_id in history_by_id
            }
            for symbol, industry in industries_by_day[day].items():
                industries.setdefault(symbol, industry)
    if not members_by_id:
        raise ValueError("No observed membership and industry data for the requested period")
    if not industries:
        raise ValueError(
            "No source-time industry history is available; import security_industry_history "
            "before building a point-in-time GNN dataset"
        )
    membership_by_day = {
        day: {
            members_by_id[security_id] for security_id in member_ids if security_id in members_by_id
        }
        for day, member_ids in membership_ids_by_day.items()
    }
    cutoff = (
        datetime.now(UTC)
        if research_fixed_universe
        else datetime.combine(end, time.max, tzinfo=UTC)
    )
    observations = (
        load_latest_adjusted_closes(session, list(members_by_id), start, end, cutoff)
        if research_fixed_universe
        else []
    )
    dates = pd.Index(all_dates, name="trade_date")
    prices = pd.DataFrame(index=dates, columns=sorted(industries), dtype=float)
    for row in observations:
        prices.at[row.trade_date, members_by_id[row.security_id]] = float(row.adjusted_close)
    if not research_fixed_universe:
        revisions = session.execute(
            select(
                PriceDailyAdjusted.security_id,
                PriceDailyAdjusted.trade_date,
                PriceDailyAdjusted.adjusted_close,
                PriceDailyAdjusted.computed_at,
            )
            .where(
                PriceDailyAdjusted.security_id.in_(list(members_by_id)),
                PriceDailyAdjusted.trade_date.between(start, end),
                PriceDailyAdjusted.method_version.like("yfinance-adjclose-v1-r%"),
            )
            .order_by(PriceDailyAdjusted.computed_at.desc())
        ).all()
        seen_prices: set[tuple[UUID, date]] = set()
        for revision_row in revisions:
            key = (revision_row.security_id, revision_row.trade_date)
            if key in seen_prices or revision_row.computed_at > datetime.combine(
                revision_row.trade_date, time.max, tzinfo=UTC
            ):
                continue
            seen_prices.add(key)
            prices.at[revision_row.trade_date, members_by_id[revision_row.security_id]] = float(
                revision_row.adjusted_close
            )
    raw_rows = session.execute(
        select(
            PriceDailyRaw.security_id,
            PriceDailyRaw.trade_date,
            PriceDailyRaw.volume,
            PriceDailyRaw.ingested_at,
            PriceDailyRaw.source_revision,
        )
        .where(
            PriceDailyRaw.security_id.in_(list(members_by_id)),
            PriceDailyRaw.trade_date.between(start, end),
        )
        .order_by(PriceDailyRaw.ingested_at.desc(), PriceDailyRaw.source_revision.desc())
    ).all()
    volumes = pd.DataFrame(index=dates, columns=sorted(industries), dtype=float)
    seen: set[tuple[UUID, date]] = set()
    for raw_row in raw_rows:
        key = (raw_row.security_id, raw_row.trade_date)
        if key in seen or (
            not research_fixed_universe
            and raw_row.ingested_at > datetime.combine(raw_row.trade_date, time.max, tzinfo=UTC)
        ):
            continue
        seen.add(key)
        volumes.at[raw_row.trade_date, members_by_id[raw_row.security_id]] = float(raw_row.volume)
    symbols, industry_names, snapshots = build_snapshots(
        prices,
        volumes,
        industries,
        membership_by_day,
        config,
        None if research_fixed_universe else industries_by_day,
    )
    if not snapshots:
        raise ValueError(
            "No valid weekly graphs; inspect membership coverage and source availability"
        )
    mode = (
        "fixed_current_universe_retrospective_research"
        if research_fixed_universe
        else "source_time_filtered_historical_industry"
    )
    dataset = GraphDataset(symbols, industry_names, snapshots, config, mode, cutoff, "")
    return GraphDataset(
        symbols, industry_names, snapshots, config, mode, cutoff, dataset_fingerprint(dataset)
    )


def save_dataset(dataset: GraphDataset, path: Path) -> None:
    if dataset_fingerprint(dataset) != dataset.fingerprint:
        raise ValueError("Graph dataset fingerprint does not match its content")
    path.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "symbols": dataset.symbols,
        "industries": dataset.industries,
        "dates": [s.day.isoformat() for s in dataset.snapshots],
        "config": dataset.config.manifest(),
        "universe_mode": dataset.universe_mode,
        "data_cutoff": dataset.data_cutoff.isoformat(),
        "fingerprint": dataset.fingerprint,
        "features": {
            "stock": STOCK_FEATURES,
            "industry": INDUSTRY_FEATURES,
            "market": MARKET_FEATURES,
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for index, snapshot in enumerate(dataset.snapshots):
        np.savez_compressed(
            path / f"snapshot_{index:05d}.npz",
            stock_x=snapshot.stock_x,
            industry_x=snapshot.industry_x,
            market_x=snapshot.market_x,
            active=snapshot.active,
            mst_edges=snapshot.mst_edges,
            correlation_edges=snapshot.correlation_edges,
            stock_industry=snapshot.stock_industry,
        )


def read_dataset(path: Path) -> GraphDataset:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported graph dataset schema")
    config = GraphConfig(**manifest["config"])
    snapshots = []
    for index, value in enumerate(manifest["dates"]):
        with np.load(path / f"snapshot_{index:05d}.npz", allow_pickle=False) as data:
            snapshots.append(
                Snapshot(
                    date.fromisoformat(value),
                    *(
                        data[name].copy()
                        for name in (
                            "stock_x",
                            "industry_x",
                            "market_x",
                            "active",
                            "mst_edges",
                            "correlation_edges",
                            "stock_industry",
                        )
                    ),
                )
            )
    dataset = GraphDataset(
        tuple(manifest["symbols"]),
        tuple(manifest["industries"]),
        tuple(snapshots),
        config,
        manifest["universe_mode"],
        datetime.fromisoformat(manifest["data_cutoff"]),
        manifest["fingerprint"],
    )
    if dataset_fingerprint(dataset) != dataset.fingerprint:
        raise ValueError("Graph dataset artifact is corrupt or has been modified")
    return dataset
