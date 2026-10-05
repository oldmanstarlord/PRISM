"""Classification rules, trading calendar rollover, and security linking (D1, D4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import EventRule, Security, SecurityAlias, TradingCalendar

IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE_IST = time(15, 30, 0)


def resolve_effective_trading_date(
    session: Session,
    published_at: datetime,
    market_close_time: time = MARKET_CLOSE_IST,
) -> date:
    """Determine effective trading date: after-close signals affect next trading day (D4)."""
    # Normalize publication time to IST
    if published_at.tzinfo is None:
        published_ist = published_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(IST)
    else:
        published_ist = published_at.astimezone(IST)

    pub_date = published_ist.date()
    is_after_close = published_ist.time() >= market_close_time

    # Query trading calendar
    trading_day_row = session.scalar(
        select(TradingCalendar).where(
            TradingCalendar.trading_date == pub_date,
            TradingCalendar.is_trading_day.is_(True),
        )
    )

    if trading_day_row is not None and not is_after_close:
        return pub_date

    # Find next trading day strictly after pub_date
    next_day_row = session.scalar(
        select(TradingCalendar)
        .where(
            TradingCalendar.trading_date > pub_date,
            TradingCalendar.is_trading_day.is_(True),
        )
        .order_by(TradingCalendar.trading_date.asc())
        .limit(1)
    )

    if next_day_row is not None:
        return next_day_row.trading_date

    # Fallback when trading_calendar table has no rows (e.g. in unit tests or unseeded DB)
    if not is_after_close and pub_date.weekday() < 5:
        return pub_date

    target = pub_date + timedelta(days=1)
    while target.weekday() >= 5:  # Saturday or Sunday
        target += timedelta(days=1)
    return target


def link_security(
    session: Session,
    symbol: str | None,
    isin: str | None,
    company_name: str | None,
) -> tuple[Security | None, str]:
    """Link announcement to security: ISIN first, symbol second, name matching fallback (D4)."""
    # 1. Exact ISIN match (highest authority)
    if isin:
        sec = session.scalar(select(Security).where(Security.isin == isin.strip()))
        if sec:
            return sec, "isin_exact"

    # 2. Exact Symbol match via SecurityAlias
    if symbol:
        clean_sym = symbol.strip().upper()
        alias = session.scalar(select(SecurityAlias).where(SecurityAlias.symbol == clean_sym))
        if alias:
            sec = session.get(Security, alias.security_id)
            if sec:
                return sec, "symbol_exact"

    # 3. Name matching as a flagged fallback
    if company_name:
        clean_name = company_name.strip().lower()
        # Strip common legal entity suffixes for matching
        for suffix in [" limited", " ltd.", " ltd", " inc.", " corp."]:
            clean_name = clean_name.removesuffix(suffix)

        for sec_cand in session.scalars(select(Security)).all():
            cand_name = sec_cand.company_name.lower()
            for suffix in [" limited", " ltd.", " ltd", " inc.", " corp."]:
                cand_name = cand_name.removesuffix(suffix)

            if clean_name and (clean_name == cand_name or clean_name in cand_name):
                return sec_cand, "name_fallback"

    return None, "unmatched"


def classify_announcement(
    session: Session,
    source_category: str,
    headline: str,
    rules: Sequence[EventRule] | None = None,
) -> tuple[str, bool, str, str]:
    """Classify announcement into canonical event_type using dynamic event_rule rows (D1).

    Returns:
        (event_type, risk_relevant, direction, rule_key)
    """
    rule_list: Sequence[EventRule]
    if rules is None:
        rule_list = list(session.scalars(select(EventRule).where(EventRule.active.is_(True))).all())
    else:
        rule_list = rules

    clean_cat = source_category.strip().lower()
    clean_head = headline.strip().lower()

    # 1. Try exact or partial source_category match
    for rule in rule_list:
        rule_cat = rule.source_category.lower()
        if rule_cat in clean_cat or clean_cat in rule_cat:
            return rule.event_type, rule.risk_relevant, rule.direction, rule.rule_key

    # 2. Keyword fallback on headline if source category was ambiguous
    keyword_map: list[tuple[list[str], str, bool, str, str]] = [
        (
            ["penalty", "sebi", "rbi notice", "warning", "show cause", "investigation"],
            "regulatory_action",
            True,
            "negative",
            "headline_regulatory",
        ),
        (
            ["default", "delay in payment", "downgrade", "debt servicing"],
            "debt_rating",
            True,
            "negative",
            "headline_debt_neg",
        ),
        (
            ["reaffirmed", "upgrade", "rating"],
            "debt_rating",
            False,
            "positive",
            "headline_debt_pos",
        ),
        (
            ["resignation", "resigns", "auditor"],
            "management_change",
            True,
            "negative",
            "headline_mgmt_neg",
        ),
        (
            ["appointment", "appointed"],
            "management_change",
            False,
            "positive",
            "headline_mgmt_pos",
        ),
        (
            ["pledge", "invocation of pledge", "promoter stake"],
            "promoter_insider",
            True,
            "negative",
            "headline_promoter",
        ),
        (
            ["order win", "bags contract", "award of contract", "billion usd", "crore order"],
            "ma_order",
            False,
            "positive",
            "headline_order_win",
        ),
        (
            ["demerger", "merger", "acquisition", "restructuring"],
            "ma_order",
            True,
            "negative",
            "headline_ma",
        ),
        (
            ["dividend", "buyback"],
            "dividend",
            False,
            "positive",
            "headline_dividend",
        ),
        (
            ["financial results", "quarterly results", "q1", "q2", "q3", "q4"],
            "results",
            True,
            "negative",
            "headline_results",
        ),
    ]

    for keywords, ev_type, risk_rel, dir_val, r_key in keyword_map:
        if any(kw in clean_head for kw in keywords):
            return ev_type, risk_rel, dir_val, r_key

    return "other", False, "neutral", "rule_general_announcement_v1"
