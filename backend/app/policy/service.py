"""Service layer for policy rules, news items, and stock news dossier (Step 11, D1, D3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    NewsItem,
    NewsSecurityLink,
    PolicyEvent,
    PolicyRule,
    ScoreComponentValue,
    Security,
    SecurityAlias,
)
from backend.app.policy.rules import create_or_version_rule, get_rules
from backend.app.policy.schemas import (
    NewsItemOut,
    PolicyEventOut,
    PolicyRuleOut,
    PolicyRuleUpdate,
    RecentPolicyEventsResponse,
    StockNewsItemOut,
    StockNewsResponse,
)


def get_stock_news(
    session: Session,
    symbol: str,
    limit: int = 20,
) -> StockNewsResponse:
    """Fetch news and policy items relevant to a specific stock symbol and its industry."""
    clean_sym = symbol.strip().upper()

    # 1. Resolve security
    alias = session.scalar(select(SecurityAlias).where(SecurityAlias.symbol == clean_sym))
    if not alias:
        raise HTTPException(status_code=404, detail=f"Stock symbol {clean_sym} not found")

    sec = session.get(Security, alias.security_id)
    if not sec:
        raise HTTPException(status_code=404, detail=f"Security for symbol {clean_sym} not found")

    # 2. Query direct security links
    linked_news_ids = session.scalars(
        select(NewsSecurityLink.news_item_id)
        .where(NewsSecurityLink.security_id == sec.id)
        .limit(limit)
    ).all()

    # 3. Query policy events affecting stock's industry or sector
    stock_industries = []
    if sec.industry:
        stock_industries.append(sec.industry.lower().strip())
    if sec.sector:
        stock_industries.append(sec.sector.lower().strip())

    # Find events where affected_industry matches
    event_query = (
        select(PolicyEvent, NewsItem, PolicyRule)
        .join(NewsItem, NewsItem.id == PolicyEvent.news_item_id)
        .join(PolicyRule, PolicyRule.id == PolicyEvent.rule_id)
    )
    if stock_industries:
        event_query = event_query.where(
            func.lower(PolicyEvent.affected_industry).in_(stock_industries)
        )
    event_query = event_query.order_by(desc(PolicyEvent.matched_at)).limit(limit)

    matched_event_rows = session.execute(event_query).all()

    # Group by news_item_id
    news_items_dict: dict[UUID, tuple[NewsItem, list[PolicyEventOut], str]] = {}

    for evt, item, rule in matched_event_rows:
        if item.id not in news_items_dict:
            news_items_dict[item.id] = (
                item,
                [],
                f"Matched policy rule '{rule.rule_key}' for industry '{evt.affected_industry}'",
            )

        news_items_dict[item.id][1].append(
            PolicyEventOut(
                id=evt.id,
                news_item_id=evt.news_item_id,
                rule_id=evt.rule_id,
                matched_at=evt.matched_at,
                affected_industry=evt.affected_industry,
                severity=float(evt.severity),
                evidence=evt.evidence or {},
                headline=item.headline,
                source=item.source,
                url=item.url,
                published_at=item.published_at,
                rule_key=rule.rule_key,
                rule_description=rule.description,
                direction=rule.direction,
                rationale=rule.rationale,
            )
        )

    # Also include direct links if not already present
    if linked_news_ids:
        direct_items = session.scalars(
            select(NewsItem).where(NewsItem.id.in_(linked_news_ids))
        ).all()
        for d_item in direct_items:
            if d_item.id not in news_items_dict:
                news_items_dict[d_item.id] = (d_item, [], "Direct company announcement / mention")

    # Sort combined items by publication date descending
    sorted_entries = sorted(
        news_items_dict.values(),
        key=lambda x: x[0].published_at,
        reverse=True,
    )[:limit]

    output_items = [
        StockNewsItemOut(
            news_item=NewsItemOut.model_validate(entry[0]),
            matched_events=entry[1],
            relevance_reason=entry[2],
        )
        for entry in sorted_entries
    ]

    # Query latest macro pressure component points if computed
    latest_val = session.scalar(
        select(ScoreComponentValue)
        .where(
            ScoreComponentValue.security_id == sec.id,
            ScoreComponentValue.component_id == "news_policy_pressure",
        )
        .order_by(desc(ScoreComponentValue.data_as_of))
        .limit(1)
    )
    macro_points: float | None = (
        float(latest_val.points) if (latest_val and latest_val.points is not None) else None
    )

    return StockNewsResponse(
        symbol=clean_sym,
        company_name=sec.company_name,
        industry=sec.industry,
        items=output_items,
        macro_pressure_points=macro_points,
    )


def list_policy_rules(
    session: Session,
    active_only: bool = False,
    category: str | None = None,
) -> list[PolicyRuleOut]:
    """Retrieve policy rules matching filter criteria."""
    rules = get_rules(session, active_only=active_only, category=category)
    return [PolicyRuleOut.model_validate(r) for r in rules]


def list_recent_policy_events(
    session: Session,
    limit: int = 50,
    industry: str | None = None,
) -> RecentPolicyEventsResponse:
    """Retrieve latest policy events across all sectors."""
    stmt = (
        select(PolicyEvent, NewsItem, PolicyRule)
        .join(NewsItem, NewsItem.id == PolicyEvent.news_item_id)
        .join(PolicyRule, PolicyRule.id == PolicyEvent.rule_id)
    )
    if industry:
        stmt = stmt.where(PolicyEvent.affected_industry == industry.strip().lower())
    stmt = stmt.order_by(desc(PolicyEvent.matched_at)).limit(limit)

    rows = session.execute(stmt).all()

    events_out: list[PolicyEventOut] = []
    for evt, item, rule in rows:
        events_out.append(
            PolicyEventOut(
                id=evt.id,
                news_item_id=evt.news_item_id,
                rule_id=evt.rule_id,
                matched_at=evt.matched_at,
                affected_industry=evt.affected_industry,
                severity=float(evt.severity),
                evidence=evt.evidence or {},
                headline=item.headline,
                source=item.source,
                url=item.url,
                published_at=item.published_at,
                rule_key=rule.rule_key,
                rule_description=rule.description,
                direction=rule.direction,
                rationale=rule.rationale,
            )
        )

    return RecentPolicyEventsResponse(
        events=events_out,
        total_count=len(events_out),
    )


def update_policy_rule(
    session: Session,
    key: str,
    update: PolicyRuleUpdate,
) -> PolicyRuleOut:
    """Create a new version of an existing policy rule or create a new one (D1)."""
    # 1. Fetch current latest rule for default fallbacks
    latest_rule = session.scalar(
        select(PolicyRule)
        .where(PolicyRule.rule_key == key)
        .order_by(desc(PolicyRule.created_at))
        .limit(1)
    )

    if not latest_rule:
        # If rule doesn't exist, all fields must be provided
        if not update.description or not update.match_keywords or not update.affected_industries:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Rule '{key}' does not exist yet. Please supply description, "
                    "match_keywords, and affected_industries to create it."
                ),
            )
        desc_val = update.description
        kw_val = update.match_keywords
        cat_val = update.match_category or "regulatory"
        ind_val = update.affected_industries
        dir_val = update.direction or "headwind"
        sev_val = update.severity if update.severity is not None else 5.0
    else:
        desc_val = (
            update.description
            if update.description is not None
            else latest_rule.description
        )
        kw_val = (
            update.match_keywords
            if update.match_keywords is not None
            else [str(x) for x in latest_rule.match_keywords]
        )
        cat_val = (
            update.match_category
            if update.match_category is not None
            else latest_rule.match_category
        )
        ind_val = (
            update.affected_industries
            if update.affected_industries is not None
            else [str(x) for x in latest_rule.affected_industries]
        )
        dir_val = update.direction if update.direction is not None else latest_rule.direction
        sev_val = update.severity if update.severity is not None else float(latest_rule.severity)

    active_val = update.active if update.active is not None else True

    try:
        new_rule = create_or_version_rule(
            session=session,
            rule_key=key,
            description=desc_val,
            match_keywords=kw_val,
            match_category=cat_val or "regulatory",
            affected_industries=ind_val,
            direction=dir_val,
            severity=sev_val,
            rationale=update.rationale,
            reviewer=update.reviewer,
            active=active_val,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PolicyRuleOut.model_validate(new_rule)
