"""Tests for announcement classification, trading calendar rollover, and security linking (D4)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.app.db.models import Security, SecurityAlias
from backend.app.events.rules import (
    classify_announcement,
    link_security,
    resolve_effective_trading_date,
)

IST = ZoneInfo("Asia/Kolkata")


def test_after_close_rollover(session) -> None:
    """Announcements published after 15:30 IST roll over to the next trading day (D4)."""
    # Thursday 14:00 IST (during market hours)
    during_market = datetime(2024, 3, 21, 14, 0, 0, tzinfo=IST)
    eff_date = resolve_effective_trading_date(session, during_market)
    assert eff_date == date(2024, 3, 21)

    # Thursday 16:45 IST (after market close)
    after_market = datetime(2024, 3, 21, 16, 45, 0, tzinfo=IST)
    eff_date_after = resolve_effective_trading_date(session, after_market)
    # Next day Friday
    assert eff_date_after == date(2024, 3, 22)

    # Friday 18:00 IST (after market close on Friday rolls over weekend to Monday)
    friday_evening = datetime(2024, 3, 22, 18, 0, 0, tzinfo=IST)
    eff_date_fri = resolve_effective_trading_date(session, friday_evening)
    # Weekend rollover: Saturday(23), Sunday(24) -> Monday(25)
    assert eff_date_fri == date(2024, 3, 25)


def test_link_security_hierarchy(session) -> None:
    """Security linking hierarchy: ISIN exact > Symbol exact > Name fallback (D4)."""
    # Query an existing security from seed
    sec = session.query(Security).first()
    assert sec is not None

    alias = session.query(SecurityAlias).filter_by(security_id=sec.id).first()
    assert alias is not None

    # 1. Exact ISIN match
    match_sec, method = link_security(session, symbol=None, isin=sec.isin, company_name=None)
    assert match_sec is not None
    assert match_sec.id == sec.id
    assert method == "isin_exact"

    # 2. Exact Symbol match
    match_sym, method_sym = link_security(
        session, symbol=alias.symbol, isin=None, company_name=None
    )
    assert match_sym is not None
    assert match_sym.id == sec.id
    assert method_sym == "symbol_exact"

    # 3. Name matching fallback
    match_name, method_name = link_security(
        session, symbol=None, isin=None, company_name=sec.company_name
    )
    assert match_name is not None
    assert match_name.id == sec.id
    assert method_name == "name_fallback"

    # 4. Unmatched fallback
    no_sec, method_none = link_security(
        session, symbol="NON_EXISTENT_XYZ", isin="IN0000000000", company_name="Fake Corp"
    )
    assert no_sec is None
    assert method_none == "unmatched"


def test_classify_announcement_rules(session) -> None:
    """Dynamic event_rule classification matches source category and headline keywords."""
    # Test regulatory penalty
    ev_type, risk_rel, direction, rule_key = classify_announcement(
        session,
        source_category="SEBI Orders & Warnings",
        headline="Penalty imposed by SEBI",
    )
    assert ev_type == "regulatory_action"
    assert risk_rel is True
    assert direction == "negative"

    # Test order win
    ev_type, risk_rel, direction, rule_key = classify_announcement(
        session,
        source_category="New Order Win",
        headline="Company bags contract valued at 500 crore",
    )
    assert ev_type == "ma_order"
    assert risk_rel is False
    assert direction == "positive"
