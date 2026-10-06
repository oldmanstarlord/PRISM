"""Point-in-time, idempotent news impact calculation and query service."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.data_sources.service import list_data_sources
from backend.app.db.models import (
    DataSource,
    ModelConfig,
    MstCluster,
    NewsImpact,
    NewsImpactItem,
    NewsItem,
    NewsSecurityLink,
    PolicyEvent,
    PolicyRule,
    PortfolioHolding,
    PortfolioRiskContribution,
    PortfolioRiskRun,
    SectorMacroSensitivity,
    Security,
    SecurityAlias,
)
from backend.app.news_impact.math import (
    combine_exposures,
    exposure_band,
    path_exposure,
    recency_decay,
    spillover_is_eligible,
)
from backend.app.news_impact.schemas import (
    AffectedStockOut,
    NewsImpactPathOut,
    NewsInsightOut,
    NewsInsightsResponse,
    PortfolioHoldingImpactOut,
    PortfolioNewsOverlayOut,
)
from backend.app.policy.provenance import VERIFIED_NEWS_SOURCE_MAP, base_news_source
from backend.app.portfolio.covariance import get_adjusted_returns_panel
from backend.app.portfolio.shock import calculate_regression_betas


@dataclass(frozen=True)
class ImpactCandidate:
    security_id: UUID | None
    industry: str
    path_type: str
    direction: str
    severity: float
    signal_strength: float
    confidence: float
    transmission: dict[str, object]
    evidence: list[dict[str, object]]


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def load_news_impact_config(session: Session) -> tuple[dict[str, Any], str]:
    row = session.scalar(
        select(ModelConfig).where(
            ModelConfig.config_key == "news_impact",
            ModelConfig.version == "1.0.0",
            ModelConfig.status.in_(["draft", "approved"]),
        )
    )
    if row is None:
        raise LookupError("draft news_impact config 1.0.0 is not installed")
    return dict(row.configuration), row.configuration_hash


def _source_is_live(session: Session, news: NewsItem, config: dict[str, Any]) -> bool:
    mapping = config.get("live_source_map", {})
    source_key = mapping.get(base_news_source(news.source)) if isinstance(mapping, dict) else None
    if not isinstance(source_key, str):
        return False
    source = session.get(DataSource, source_key)
    return bool(source and source.status == "live" and source.last_success_at is not None)


def _rule_candidates(
    session: Session, news: NewsItem, config: dict[str, Any]
) -> list[ImpactCandidate]:
    candidates: list[ImpactCandidate] = []
    rows = session.execute(
        select(PolicyEvent, PolicyRule)
        .join(PolicyRule, PolicyRule.id == PolicyEvent.rule_id)
        .where(PolicyEvent.news_item_id == news.id, PolicyRule.active.is_(True))
        .order_by(PolicyRule.rule_key, PolicyEvent.affected_industry)
    ).all()
    penalty = float(config["unreviewed_rule_confidence_penalty"])
    base = float(config["base_confidence"]["rule"])
    for event, rule in rows:
        unreviewed = not rule.reviewer.strip() or rule.reviewer.strip().upper() == "UNREVIEWED"
        confidence = max(0.0, base - (penalty if unreviewed else 0.0))
        securities = session.scalars(
            select(Security)
            .where(
                Security.is_active.is_(True),
                func.lower(Security.industry) == event.affected_industry.lower(),
            )
            .order_by(Security.company_name)
            .limit(int(config["maximum_stocks_per_item"]))
        ).all()
        targets: list[Security | None] = list(securities) or [None]
        for security in targets:
            candidates.append(
                ImpactCandidate(
                    security_id=security.id if security else None,
                    industry=event.affected_industry,
                    path_type="rule",
                    direction=rule.direction,
                    severity=float(event.severity),
                    signal_strength=1.0,
                    confidence=confidence,
                    transmission={
                        "rule_key": rule.rule_key,
                        "rule_version": rule.version,
                        "rationale": rule.rationale,
                        "reviewer": rule.reviewer,
                        "unreviewed": unreviewed,
                    },
                    evidence=[
                        {"source_table": "policy_event", "source_ref": str(event.id)},
                        {"source_table": "policy_rule", "source_ref": str(rule.id)},
                    ],
                )
            )
        candidates.extend(_macro_candidates(session, news, event, rule, config, confidence))
    return candidates


def _macro_candidates(
    session: Session,
    news: NewsItem,
    event: PolicyEvent,
    rule: PolicyRule,
    config: dict[str, Any],
    rule_confidence: float,
) -> list[ImpactCandidate]:
    links = rule.macro_series_links or []
    output: list[ImpactCandidate] = []
    for raw_link in links:
        if not isinstance(raw_link, dict):
            continue
        series_key = raw_link.get("series_key")
        expected = raw_link.get("expected_direction")
        if not isinstance(series_key, str) or expected not in {"up", "down"}:
            continue
        rows = session.scalars(
            select(SectorMacroSensitivity)
            .where(
                SectorMacroSensitivity.series_key == series_key,
                SectorMacroSensitivity.window_end <= news.published_at.date(),
                SectorMacroSensitivity.is_significant.is_(True),
            )
            .order_by(
                desc(SectorMacroSensitivity.window_end), desc(func.abs(SectorMacroSensitivity.beta))
            )
        ).all()
        latest: dict[str, SectorMacroSensitivity] = {}
        for row in rows:
            latest.setdefault(row.industry, row)
        ordered = sorted(latest.values(), key=lambda value: (-abs(value.beta), value.industry))
        for sensitivity in ordered[: int(config["maximum_stocks_per_item"])]:
            signed = sensitivity.beta * (1.0 if expected == "up" else -1.0)
            direction = "tailwind" if signed > 0 else "headwind" if signed < 0 else "ambiguous"
            securities = session.scalars(
                select(Security)
                .where(
                    Security.is_active.is_(True),
                    func.lower(Security.industry) == sensitivity.industry.lower(),
                )
                .order_by(Security.company_name)
                .limit(int(config["maximum_stocks_per_item"]))
            ).all()
            for security in securities:
                output.append(
                    ImpactCandidate(
                        security_id=security.id,
                        industry=sensitivity.industry,
                        path_type="macro",
                        direction=direction,
                        severity=float(event.severity),
                        signal_strength=min(1.0, abs(float(sensitivity.beta))),
                        confidence=min(rule_confidence, float(config["base_confidence"]["macro"])),
                        transmission={
                            "rule_key": rule.rule_key,
                            "series_key": series_key,
                            "expected_direction": expected,
                            "industry_beta": float(sensitivity.beta),
                            "t_stat": float(sensitivity.t_stat),
                        },
                        evidence=[
                            {"source_table": "policy_rule", "source_ref": str(rule.id)},
                            {
                                "source_table": "sector_macro_sensitivity",
                                "source_ref": str(sensitivity.id),
                            },
                        ],
                    )
                )
    return output


def _direct_candidates(
    session: Session, news: NewsItem, config: dict[str, Any]
) -> list[ImpactCandidate]:
    rows = session.execute(
        select(NewsSecurityLink, Security)
        .join(Security, Security.id == NewsSecurityLink.security_id)
        .where(NewsSecurityLink.news_item_id == news.id)
        .order_by(Security.company_name)
    ).all()
    return [
        ImpactCandidate(
            security_id=security.id,
            industry=security.industry or "Unclassified",
            path_type="direct",
            direction="ambiguous",
            severity=float(config["direct_default_severity"]),
            signal_strength=float(link.confidence),
            confidence=min(float(link.confidence), float(config["base_confidence"]["direct"])),
            transmission={"link_method": link.method, "named_company": security.company_name},
            evidence=[
                {"source_table": "news_item", "source_ref": str(news.id)},
                {"source_table": "news_security_link", "source_ref": str(link.id)},
            ],
        )
        for link, security in rows
    ]


def _spillover_candidates(
    session: Session,
    news: NewsItem,
    direct: list[ImpactCandidate],
    config: dict[str, Any],
) -> list[ImpactCandidate]:
    direct_ids = [item.security_id for item in direct if item.security_id is not None]
    if not direct_ids:
        return []
    securities = session.scalars(select(Security).where(Security.is_active.is_(True))).all()
    all_ids = [security.id for security in securities]
    returns, _ = get_adjusted_returns_panel(
        session, all_ids, news.published_at.date(), int(config["regression_window"])
    )
    if returns.empty:
        return []
    by_id = {security.id: security for security in securities}
    output: list[ImpactCandidate] = []
    floor = float(config["spillover_min_r_squared"])
    for source in direct:
        if source.security_id not in returns.columns:
            continue
        betas = calculate_regression_betas(returns, source.security_id)
        source_values = returns[source.security_id].to_numpy(dtype=float)
        ranked: list[tuple[float, ImpactCandidate]] = []
        for target_id, beta in betas.items():
            if target_id in direct_ids or target_id not in by_id:
                continue
            target_values = returns[target_id].to_numpy(dtype=float)
            rho = float(np.corrcoef(source_values, target_values)[0, 1])
            r_squared = rho * rho if np.isfinite(rho) else 0.0
            if not spillover_is_eligible(r_squared, floor):
                continue
            target = by_id[target_id]
            direction = (
                source.direction
                if beta >= 0
                else (
                    "tailwind"
                    if source.direction == "headwind"
                    else "headwind"
                    if source.direction == "tailwind"
                    else "ambiguous"
                )
            )
            candidate = ImpactCandidate(
                security_id=target.id,
                industry=target.industry or "Unclassified",
                path_type="spillover",
                direction=direction,
                severity=source.severity,
                signal_strength=min(1.0, r_squared),
                confidence=min(float(config["base_confidence"]["spillover"]), r_squared),
                transmission={
                    "direct_security_id": str(source.security_id),
                    "beta": float(beta),
                    "r_squared": r_squared,
                    "observations": len(returns),
                },
                evidence=[
                    {"source_table": "news_security_link", "source_ref": str(source.security_id)},
                    {
                        "source_table": "price_daily_adjusted",
                        "source_ref": f"through:{news.published_at.date()}",
                    },
                ],
            )
            ranked.append((r_squared, candidate))
        output.extend(
            item
            for _, item in sorted(ranked, key=lambda pair: -pair[0])[
                : int(config["maximum_stocks_per_item"])
            ]
        )
    return output


def calculate_news_impact(session: Session, news: NewsItem) -> tuple[NewsImpact | None, bool]:
    config, config_fingerprint = load_news_impact_config(session)
    if not _source_is_live(session, news, config):
        return None, False
    direct = _direct_candidates(session, news, config)
    candidates = [*direct, *_rule_candidates(session, news, config)]
    candidates.extend(_spillover_candidates(session, news, direct, config))
    input_fingerprint = _fingerprint(
        {
            "news": [str(news.id), news.content_hash, news.published_at, news.ingested_at],
            "candidates": [candidate.__dict__ for candidate in candidates],
            "config": config_fingerprint,
        }
    )
    existing = session.scalar(
        select(NewsImpact).where(
            NewsImpact.news_item_id == news.id,
            NewsImpact.config_fingerprint == config_fingerprint,
            NewsImpact.input_fingerprint == input_fingerprint,
        )
    )
    if existing is not None:
        return existing, True
    run = NewsImpact(
        news_item_id=news.id,
        config_fingerprint=config_fingerprint,
        input_fingerprint=input_fingerprint,
        status="completed",
    )
    session.add(run)
    session.flush()
    age_days = max(0.0, (datetime.now(UTC) - news.published_at).total_seconds() / 86400.0)
    decay = recency_decay(age_days, float(config["recency_half_life_days"]))
    bands = config["exposure_bands"]
    for candidate in candidates:
        score = path_exposure(
            candidate.severity,
            float(config["path_weights"][candidate.path_type]),
            decay,
            candidate.signal_strength,
        )
        session.add(
            NewsImpactItem(
                news_impact_id=run.id,
                security_id=candidate.security_id,
                industry=candidate.industry,
                path_type=candidate.path_type,
                transmission=candidate.transmission,
                direction=candidate.direction,
                severity=candidate.severity,
                exposure_score=score,
                exposure_band=exposure_band(
                    score, float(bands["medium_min"]), float(bands["high_min"])
                ),
                confidence=candidate.confidence,
                evidence=candidate.evidence,
            )
        )
    session.commit()
    session.refresh(run)
    return run, False


def run_incremental_news_impact(
    session: Session, news_ids: list[UUID] | None = None
) -> dict[str, int]:
    config, _ = load_news_impact_config(session)
    mapping = config.get("live_source_map", {})
    live_keys = session.scalars(
        select(DataSource.source_key).where(
            DataSource.status == "live", DataSource.last_success_at.is_not(None)
        )
    ).all()
    allowed_sources = sorted(
        VERIFIED_NEWS_SOURCE_MAP.get(source, source)
        for source, key in mapping.items()
        if key in live_keys
    )
    statement = (
        select(NewsItem).where(NewsItem.source.in_(allowed_sources)).order_by(NewsItem.published_at)
    )
    if news_ids:
        statement = statement.where(NewsItem.id.in_(news_ids))
    created = reused = skipped = 0
    for news in session.scalars(statement).all():
        run, was_reused = calculate_news_impact(session, news)
        if run is None:
            skipped += 1
        elif was_reused:
            reused += 1
        else:
            created += 1
    return {"created": created, "reused": reused, "skipped": skipped}


def _symbols(session: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    rows = session.execute(
        select(SecurityAlias.security_id, SecurityAlias.symbol)
        .where(SecurityAlias.security_id.in_(ids), SecurityAlias.valid_to.is_(None))
        .order_by(SecurityAlias.security_id, SecurityAlias.symbol)
    ).all()
    output: dict[UUID, str] = {}
    for security_id, symbol in rows:
        output.setdefault(security_id, symbol)
    return output


def _aggregate_rows(
    session: Session, impact: NewsImpact, minimum_confidence: float
) -> list[AffectedStockOut]:
    rows = session.scalars(
        select(NewsImpactItem).where(
            NewsImpactItem.news_impact_id == impact.id,
            NewsImpactItem.confidence >= minimum_confidence,
        )
    ).all()
    symbols = _symbols(session, {row.security_id for row in rows if row.security_id})
    grouped: dict[tuple[UUID | None, str], list[NewsImpactItem]] = defaultdict(list)
    for row in rows:
        grouped[(row.security_id, row.industry)].append(row)
    output: list[AffectedStockOut] = []
    for (security_id, industry), paths in grouped.items():
        winner = max(paths, key=lambda row: (row.exposure_score, row.path_type))
        output.append(
            AffectedStockOut(
                symbol=symbols.get(security_id) if security_id else None,
                security_id=security_id,
                industry=industry,
                direction=winner.direction,
                exposure_score=combine_exposures(row.exposure_score for row in paths),
                exposure_band=winner.exposure_band,
                confidence=max(row.confidence for row in paths),
                paths=[
                    NewsImpactPathOut(
                        path_type=row.path_type,
                        direction=row.direction,
                        severity=row.severity,
                        exposure_score=row.exposure_score,
                        exposure_band=row.exposure_band,
                        confidence=row.confidence,
                        evidence=list(row.evidence),
                    )
                    for row in sorted(
                        paths, key=lambda item: (-item.exposure_score, item.path_type)
                    )
                ],
            )
        )
    return sorted(output, key=lambda row: (-row.exposure_score, row.symbol or row.industry))


def list_news_insights(
    session: Session,
    industry: str | None = None,
    minimum_severity: float | None = None,
    portfolio_id: UUID | None = None,
) -> NewsInsightsResponse:
    config, config_fingerprint = load_news_impact_config(session)
    impacts = session.scalars(
        select(NewsImpact)
        .where(
            NewsImpact.config_fingerprint == config_fingerprint, NewsImpact.status == "completed"
        )
        .order_by(desc(NewsImpact.created_at))
    ).all()
    latest: dict[UUID, NewsImpact] = {}
    for impact in impacts:
        latest.setdefault(impact.news_item_id, impact)
    portfolio_security_ids: set[UUID] | None = None
    if portfolio_id is not None:
        portfolio_security_ids = {
            security_id
            for security_id in session.scalars(
                select(PortfolioHolding.security_id).where(
                    PortfolioHolding.portfolio_id == portfolio_id,
                    PortfolioHolding.security_id.is_not(None),
                )
            ).all()
            if security_id is not None
        }
    items: list[NewsInsightOut] = []
    for impact in latest.values():
        news = session.get(NewsItem, impact.news_item_id)
        if news is None or not _source_is_live(session, news, config):
            continue
        stocks = _aggregate_rows(session, impact, float(config["minimum_confidence_to_display"]))
        if industry and not any(
            stock.industry.casefold() == industry.casefold() for stock in stocks
        ):
            continue
        if portfolio_security_ids is not None and not any(
            stock.security_id in portfolio_security_ids for stock in stocks
        ):
            continue
        severity = max((path.severity for stock in stocks for path in stock.paths), default=0.0)
        if minimum_severity is not None and severity < minimum_severity:
            continue
        rules = session.scalars(
            select(PolicyRule)
            .join(PolicyEvent, PolicyEvent.rule_id == PolicyRule.id)
            .where(PolicyEvent.news_item_id == news.id)
        ).all()
        items.append(
            NewsInsightOut(
                news_id=news.id,
                headline=news.headline,
                source=news.source,
                published_at=news.published_at,
                url=news.url,
                severity=severity,
                affected_industries=sorted({stock.industry for stock in stocks}),
                matched_rules=sorted({rule.rule_key for rule in rules}),
                unreviewed=any(
                    not rule.reviewer.strip() or rule.reviewer.strip().upper() == "UNREVIEWED"
                    for rule in rules
                ),
                affected_stocks=stocks,
            )
        )
    sources = [source for source in list_data_sources(session) if source.dataset == "news_policy"]
    return NewsInsightsResponse(
        items=sorted(items, key=lambda item: item.published_at, reverse=True),
        source_statuses=sources,
        limitations=list(config["limitations"]),
    )


def get_portfolio_news_overlay(
    session: Session, portfolio_id: UUID, news_id: UUID
) -> PortfolioNewsOverlayOut:
    config, fingerprint = load_news_impact_config(session)
    insight = next(
        (item for item in list_news_insights(session).items if item.news_id == news_id), None
    )
    if insight is None:
        raise LookupError("news impact is unavailable or below its display confidence threshold")
    holdings = session.scalars(
        select(PortfolioHolding)
        .where(PortfolioHolding.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioHolding.as_of), PortfolioHolding.symbol)
    ).all()
    if not holdings:
        raise LookupError("portfolio has no holdings")
    latest_date = max(holding.as_of for holding in holdings)
    holdings = [holding for holding in holdings if holding.as_of == latest_date]
    by_security = {
        stock.security_id: stock for stock in insight.affected_stocks if stock.security_id
    }
    latest_risk = session.scalar(
        select(PortfolioRiskRun)
        .where(PortfolioRiskRun.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioRiskRun.as_of), desc(PortfolioRiskRun.computed_at))
    )
    contribution_rows = (
        session.scalars(
            select(PortfolioRiskContribution).where(
                PortfolioRiskContribution.run_id == latest_risk.id
            )
        ).all()
        if latest_risk
        else []
    )
    contributions = {
        row.security_id: float(row.percent_contribution)
        for row in contribution_rows
        if row.security_id is not None
    }
    latest_cluster_run = session.scalar(
        select(MstCluster.run_id).order_by(desc(MstCluster.created_at))
    )
    clusters = (
        {
            row.security_id: row.cluster_id
            for row in session.scalars(
                select(MstCluster).where(MstCluster.run_id == latest_cluster_run)
            ).all()
        }
        if latest_cluster_run
        else {}
    )
    affected: list[PortfolioHoldingImpactOut] = []
    total_weight = 0.0
    cluster_members: dict[str, list[str]] = defaultdict(list)
    for holding in holdings:
        if holding.security_id is None:
            continue
        stock = by_security.get(holding.security_id)
        if stock is None:
            continue
        weight = float(holding.weight)
        total_weight += weight
        cluster_id = clusters.get(holding.security_id)
        if cluster_id:
            cluster_members[cluster_id].append(holding.symbol)
        affected.append(
            PortfolioHoldingImpactOut(
                symbol=holding.symbol,
                industry=stock.industry,
                weight=weight,
                risk_contribution=contributions.get(holding.security_id),
                exposure_score=stock.exposure_score,
                exposure_band=stock.exposure_band,
                cluster_id=cluster_id,
            )
        )
    confidence = min((stock.confidence for stock in insight.affected_stocks), default=0.0)
    age = max(0, (datetime.now(UTC) - insight.published_at).days)
    return PortfolioNewsOverlayOut(
        portfolio_id=portfolio_id,
        news_id=news_id,
        as_of=datetime.combine(latest_date, datetime.min.time(), tzinfo=UTC),
        affected_industry_weight=total_weight,
        holdings=sorted(affected, key=lambda row: -row.exposure_score),
        cluster_overlap={key: value for key, value in cluster_members.items() if len(value) > 1},
        inputs=[fingerprint, str(news_id), str(portfolio_id), latest_date.isoformat()],
        thresholds={
            "minimum_confidence_to_display": config["minimum_confidence_to_display"],
            "spillover_min_r_squared": config["spillover_min_r_squared"],
        },
        confidence=confidence,
        data_age_days=age,
        limitations=list(config["limitations"]),
        disclaimer=str(config["disclaimer"]),
    )
