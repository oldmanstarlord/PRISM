"""Precompute explanations for top risk stocks, MST edges, sector divergences, and news impacts.

Part of STEP E5:
- Top N stocks by risk: component explanation + score change explanation.
- Every edge of the latest MST run: mst_edge explanation.
- Every divergence flag at or above moderate: divergence explanation.
- Every recent completed news impact: news explanation.
- Reports cache hit rate, counts, and execution timing.
- Idempotent and deterministic.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    MstEdge,
    NewsImpact,
    ScoreComponentValue,
    ScoreRun,
    SectorDivergenceRun,
    SectorDivergenceScore,
    SecurityAlias,
    StockRiskResult,
)
from backend.app.db.session import SessionLocal
from backend.app.explain.service import (
    get_or_create_component_explanation,
    get_or_create_divergence_explanation,
    get_or_create_mst_edge_explanation,
    get_or_create_news_explanation,
    get_or_create_score_change_explanation,
)
from backend.app.mst_diagnostics.service import get_latest_mst_run_for_variant

logger = logging.getLogger(__name__)


def _resolve_symbol(session: Session, security_id: UUID, existing: str | None) -> str:
    if existing:
        return existing
    alias = session.scalars(
        select(SecurityAlias.symbol)
        .where(SecurityAlias.security_id == security_id)
        .order_by(desc(SecurityAlias.valid_from))
    ).first()
    return alias or str(security_id)


def run_precompute(
    session: Session,
    top_n: int = 20,
    max_news: int = 25,
    max_edges: int | None = None,
    max_divergences: int | None = None,
) -> dict[str, Any]:
    """Execute precomputation batch job across key PRISM entities."""
    start_time = time.perf_counter()
    total_items = 0
    cache_hits = 0
    cache_misses = 0

    breakdown = {
        "top_stocks_risk": 0,
        "score_changes": 0,
        "mst_edges": 0,
        "divergences": 0,
        "news_impacts": 0,
    }

    # 1. Top N stocks by risk score
    latest_score_run = session.scalars(
        select(ScoreRun)
        .where(ScoreRun.status == "completed")
        .order_by(desc(ScoreRun.as_of_date), desc(ScoreRun.completed_at))
    ).first()

    if latest_score_run is not None:
        top_stocks = session.scalars(
            select(StockRiskResult)
            .where(StockRiskResult.run_id == latest_score_run.id)
            .order_by(desc(StockRiskResult.total_score))
            .limit(top_n)
        ).all()

        for stock in top_stocks:
            sym = stock.symbol.upper()

            # Precompute score-change explanation
            try:
                _payload, is_cached, _row = get_or_create_score_change_explanation(
                    session, symbol=sym
                )
                total_items += 1
                if is_cached:
                    cache_hits += 1
                else:
                    cache_misses += 1
                breakdown["score_changes"] += 1
            except Exception as exc:
                session.rollback()
                logger.warning("Failed score_change explanation for %s: %s", sym, exc)

            # Precompute top risk component explanations for this stock
            comp_values = session.scalars(
                select(ScoreComponentValue)
                .where(
                    ScoreComponentValue.run_id == latest_score_run.id,
                    ScoreComponentValue.security_id == stock.security_id,
                )
                .order_by(desc(ScoreComponentValue.points))
                .limit(3)
            ).all()

            for comp in comp_values:
                try:
                    _p, is_cached, _r = get_or_create_component_explanation(
                        session,
                        symbol=sym,
                        component_key=comp.component_id,
                        as_of=latest_score_run.as_of_date,
                    )
                    total_items += 1
                    if is_cached:
                        cache_hits += 1
                    else:
                        cache_misses += 1
                    breakdown["top_stocks_risk"] += 1
                except Exception as exc:
                    session.rollback()
                    logger.warning(
                        "Failed risk_component for %s:%s: %s",
                        sym,
                        comp.component_id,
                        exc,
                    )

    # 2. Edges of the latest MST run
    latest_mst = get_latest_mst_run_for_variant(session, variant="raw")
    if latest_mst is not None:
        mst_edges_query = select(MstEdge).where(MstEdge.mst_run_id == latest_mst.id)
        if max_edges is not None:
            mst_edges_query = mst_edges_query.limit(max_edges)
        mst_edges = session.scalars(mst_edges_query).all()

        for idx, edge in enumerate(mst_edges, 1):
            sym_a = _resolve_symbol(session, edge.security_a_id, edge.symbol_a)
            sym_b = _resolve_symbol(session, edge.security_b_id, edge.symbol_b)
            try:
                _p, is_cached, _r = get_or_create_mst_edge_explanation(
                    session,
                    run_id=latest_mst.id,
                    a=sym_a,
                    b=sym_b,
                )
                total_items += 1
                if is_cached:
                    cache_hits += 1
                else:
                    cache_misses += 1
                breakdown["mst_edges"] += 1
            except Exception as exc:
                session.rollback()
                logger.warning(
                    "Failed mst_edge explanation for %s-%s: %s",
                    sym_a,
                    sym_b,
                    exc,
                )
            if idx % 25 == 0 or idx == len(mst_edges):
                print(
                    f"MST Edges: {idx}/{len(mst_edges)} processed "
                    f"(hits={cache_hits}, misses={cache_misses})...",
                    flush=True,
                )

    # 3. Every divergence flag at or above moderate
    latest_div_run = session.scalars(
        select(SectorDivergenceRun)
        .where(SectorDivergenceRun.status == "completed")
        .order_by(
            desc(SectorDivergenceRun.signal_date),
            desc(SectorDivergenceRun.completed_at),
        )
    ).first()

    if latest_div_run is not None:
        divergent_scores = session.scalars(
            select(SectorDivergenceScore)
            .where(
                SectorDivergenceScore.run_id == latest_div_run.id,
                SectorDivergenceScore.interpretation.in_(
                    ["moderate", "strong", "extreme"]
                ),
            )
            .order_by(desc(func.abs(SectorDivergenceScore.divergence_value)))
        ).all()

        seen_div_syms: set[str] = set()
        for dscore in divergent_scores:
            if dscore.symbol in seen_div_syms:
                continue
            if max_divergences is not None and len(seen_div_syms) >= max_divergences:
                break
            seen_div_syms.add(dscore.symbol)

            try:
                _p, is_cached, _r = get_or_create_divergence_explanation(
                    session,
                    symbol=dscore.symbol,
                    as_of=latest_div_run.signal_date,
                )
                total_items += 1
                if is_cached:
                    cache_hits += 1
                else:
                    cache_misses += 1
                breakdown["divergences"] += 1
            except Exception as exc:
                session.rollback()
                logger.warning(
                    "Failed divergence explanation for %s: %s",
                    dscore.symbol,
                    exc,
                )
            if len(seen_div_syms) % 10 == 0:
                print(
                    f"Divergences: {len(seen_div_syms)} processed "
                    f"(hits={cache_hits}, misses={cache_misses})...",
                    flush=True,
                )

    # 4. Every recent completed news impact
    news_impacts = session.scalars(
        select(NewsImpact)
        .where(NewsImpact.status == "completed")
        .order_by(desc(NewsImpact.created_at))
        .limit(max_news)
    ).all()

    for idx, ni in enumerate(news_impacts, 1):
        try:
            _p, is_cached, _r = get_or_create_news_explanation(
                session, news_id=ni.news_item_id
            )
            total_items += 1
            if is_cached:
                cache_hits += 1
            else:
                cache_misses += 1
            breakdown["news_impacts"] += 1
        except Exception as exc:
            session.rollback()
            logger.warning(
                "Failed news explanation for news_id %s: %s",
                ni.news_item_id,
                exc,
            )
        if idx % 10 == 0 or idx == len(news_impacts):
            print(
                f"News impacts: {idx}/{len(news_impacts)} processed "
                f"(hits={cache_hits}, misses={cache_misses})...",
                flush=True,
            )

    elapsed = time.perf_counter() - start_time
    hit_rate = (cache_hits / total_items * 100.0) if total_items > 0 else 100.0

    return {
        "total_items": total_items,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_rate_pct": round(hit_rate, 2),
        "elapsed_seconds": round(elapsed, 4),
        "breakdown": breakdown,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Precompute PRISM explanations for top risk items, graph edges, and flags."
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top risk stocks to precompute",
    )
    parser.add_argument(
        "--max-news",
        type=int,
        default=25,
        help="Maximum recent completed news impacts to precompute",
    )
    parser.add_argument(
        "--max-edges",
        type=int,
        default=None,
        help="Maximum MST edges to precompute (default: all)",
    )
    parser.add_argument(
        "--max-divergences",
        type=int,
        default=None,
        help="Maximum divergence flags to precompute (default: all)",
    )
    args = parser.parse_args()

    print(
        f"Starting explanation precomputation (top_n={args.top_n}, "
        f"max_news={args.max_news}, max_edges={args.max_edges}, "
        f"max_divergences={args.max_divergences})...",
        flush=True,
    )
    with SessionLocal() as session:
        stats = run_precompute(
            session,
            top_n=args.top_n,
            max_news=args.max_news,
            max_edges=args.max_edges,
            max_divergences=args.max_divergences,
        )

    print("\n=== Explanation Precompute Report ===", flush=True)
    print(f"Total processed: {stats['total_items']}", flush=True)
    print(f"Cache hits:      {stats['cache_hits']}", flush=True)
    print(
        f"Cache misses:    {stats['cache_misses']} (newly generated)", flush=True
    )
    print(f"Hit rate:        {stats['hit_rate_pct']:.2f}%", flush=True)
    print(f"Elapsed time:    {stats['elapsed_seconds']:.3f}s", flush=True)
    print(f"Breakdown:       {stats['breakdown']}", flush=True)
    print("=====================================\n", flush=True)


if __name__ == "__main__":
    main()
