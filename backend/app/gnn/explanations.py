"""Transparent supporting evidence, separate from learned GNN attribution."""

from itertools import combinations
from statistics import median
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def explain(
    holdings: list[str],
    snapshots: list[dict[str, Any]],
    prices: pd.DataFrame,
) -> dict[str, Any]:
    dates = sorted({row["date"] for row in snapshots})
    if not dates:
        return {"stocks": {}, "diversification": {"status": "unavailable"}}
    latest = {row["symbol"]: row for row in snapshots if row["date"] == dates[-1]}
    lookup = {(row["symbol"], row["date"]): row for row in snapshots}
    prices = prices.sort_index().loc[: dates[-1]]
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    pairs: list[dict[str, Any]] = []
    if len(returns) >= 41:
        prior, current = returns.iloc[-40:-20], returns.iloc[-20:]
        for left, right in combinations(sorted(set(holdings) & set(prices.columns)), 2):
            old, new = prior[[left, right]].dropna(), current[[left, right]].dropna()
            if len(old) < 15 or len(new) < 15:
                continue
            before, after = old[left].corr(old[right]), new[left].corr(new[right])
            if np.isfinite(before) and np.isfinite(after):
                pairs.append(
                    {
                        "symbols": [left, right],
                        "prior": float(before),
                        "current": float(after),
                        "change": float(after - before),
                    }
                )
    diversification: dict[str, Any] = {
        "status": "unavailable",
        "pairs": len(pairs),
        "requested_pairs": len(set(holdings)) * (len(set(holdings)) - 1) // 2,
        "method": (
            "Equal-weight mean pairwise daily-return correlation; two non-overlapping "
            "20-session windows, at least 15 paired returns in each. "
            "No portfolio weights or GNN embeddings are used."
        ),
    }
    if pairs:
        before = float(np.mean([p["prior"] for p in pairs]))
        after = float(np.mean([p["current"] for p in pairs]))
        diversification.update(
            status="available",
            prior=before,
            current=after,
            change=after - before,
            prior_start=str(prior.index[0]),
            prior_end=str(prior.index[-1]),
            current_start=str(current.index[0]),
            current_end=str(current.index[-1]),
            largest_changes=sorted(pairs, key=lambda p: abs(p["change"]), reverse=True)[:3],
        )
    five_day: dict[str, float] = {}
    if len(prices) >= 6:
        for symbol in prices:
            values = prices[symbol].iloc[-6:]
            if values.notna().all() and (values > 0).all():
                five_day[symbol] = float(values.iloc[-1] / values.iloc[0] - 1)
    stocks = {}
    for symbol in holdings:
        if symbol not in latest:
            continue
        row = latest[symbol]
        streak = 0
        for day in reversed(dates):
            observation = lookup.get((symbol, day))
            if observation is None or observation["alert_level"] == "normal":
                break
            streak += 1
        peers = [
            name
            for name, other in latest.items()
            if name != symbol and other["industry"] == row["industry"] and name in five_day
        ]
        peer: dict[str, Any] = {"status": "unavailable", "count": len(peers)}
        if len(peers) >= 3 and symbol in five_day:
            midpoint = median(five_day[name] for name in peers)
            peer.update(
                status="available",
                stock_return=five_day[symbol],
                peer_median_return=midpoint,
                gap=five_day[symbol] - midpoint,
                symbols=sorted(peers),
                start=str(prices.index[-6]),
                end=str(prices.index[-1]),
            )
        stocks[symbol] = {
            "peer_comparison": peer,
            "persistence": {
                "consecutive_elevated": streak,
                "window_snapshots": len(dates),
                "history": [
                    {
                        "date": str(day),
                        "percentile": lookup[(symbol, day)]["drift_percentile"],
                        "alert_level": lookup[(symbol, day)]["alert_level"],
                    }
                    for day in dates
                    if (symbol, day) in lookup
                ],
                "missing_snapshots": sum((symbol, day) not in lookup for day in dates),
            },
        }
    return {
        "as_of": str(dates[-1]),
        "stocks": stocks,
        "diversification": diversification,
        "method": (
            "Price comparisons are transparent context, not explanations of the model's "
            "internal reasoning. Peer groups use the saved analysis industry and exclude "
            "the stock itself; these classifications may be broad. Prices use revisions "
            "available at the model's data cutoff. Persistence counts consecutive saved "
            "snapshots; missing observations break the streak."
        ),
    }
