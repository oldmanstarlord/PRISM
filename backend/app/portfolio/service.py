"""Deterministic portfolio validation and persistence helpers."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    PriceDailyAdjusted,
    Security,
    SecurityAlias,
    Universe,
    UniverseMembership,
)
from backend.app.portfolio.schemas import (
    InputMode,
    PortfolioPreviewRequest,
    PortfolioPreviewResponse,
    PortfolioRowInput,
    PreviewHolding,
)

WEIGHT_TOLERANCE = Decimal("0.0001")
CASH_SYMBOL = "CASH"


@dataclass(frozen=True)
class EligibleSecurity:
    id: UUID
    symbol: str
    company_name: str
    industry: str | None


def aggregate_rows(
    rows: list[PortfolioRowInput],
) -> tuple[dict[str, Decimal], Decimal, bool]:
    aggregated: dict[str, Decimal] = {}
    for row in rows:
        aggregated[row.symbol] = aggregated.get(row.symbol, Decimal(0)) + row.value
    cash_value = aggregated.pop(CASH_SYMBOL, Decimal(0))
    duplicate_found = len(rows) != len(aggregated) + (1 if cash_value else 0)
    return aggregated, cash_value, duplicate_found


def _eligible_securities(session: Session) -> dict[str, EligibleSecurity]:
    rows = session.execute(
        select(Security.id, SecurityAlias.symbol, Security.company_name, Security.industry)
        .join(SecurityAlias, SecurityAlias.security_id == Security.id)
        .join(UniverseMembership, UniverseMembership.security_id == Security.id)
        .join(Universe, Universe.id == UniverseMembership.universe_id)
        .where(
            Universe.name == "NIFTY 200",
            UniverseMembership.valid_to.is_(None),
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_to.is_(None),
            Security.is_active.is_(True),
        )
    ).all()
    return {
        symbol.upper(): EligibleSecurity(
            id=security_id,
            symbol=symbol.upper(),
            company_name=company_name,
            industry=industry,
        )
        for security_id, symbol, company_name, industry in rows
    }


def _latest_common_date(session: Session, security_ids: list[UUID]) -> date | None:
    if not security_ids:
        return None
    return session.scalar(
        select(PriceDailyAdjusted.trade_date)
        .where(PriceDailyAdjusted.security_id.in_(security_ids))
        .group_by(PriceDailyAdjusted.trade_date)
        .having(func.count(distinct(PriceDailyAdjusted.security_id)) == len(security_ids))
        .order_by(PriceDailyAdjusted.trade_date.desc())
        .limit(1)
    )


def _fingerprint(
    input_mode: InputMode,
    valuation_date: date,
    holdings: list[PreviewHolding],
    cash_value: Decimal,
) -> str:
    payload = {
        "input_mode": input_mode,
        "valuation_date": valuation_date.isoformat(),
        "cash_value": str(cash_value.normalize()),
        "holdings": [
            {
                "security_id": str(row.security_id),
                "symbol": row.symbol,
                "value": str(row.value.normalize()),
            }
            for row in holdings
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def preview_portfolio(
    session: Session, request: PortfolioPreviewRequest
) -> PortfolioPreviewResponse:
    aggregated, cash_value, duplicate_found = aggregate_rows(request.rows)
    errors: list[str] = []
    warnings: list[str] = []
    if not aggregated:
        errors.append("At least one NIFTY 200 security is required; cash alone is not a portfolio")
    if len(aggregated) > 200:
        errors.append("A portfolio can contain at most 200 securities")

    eligible = _eligible_securities(session)
    unknown = sorted(set(aggregated) - set(eligible))
    if unknown:
        errors.append("Outside the active NIFTY 200 universe: " + ", ".join(unknown))

    holdings = [
        PreviewHolding(
            security_id=eligible[symbol].id,
            symbol=symbol,
            company_name=eligible[symbol].company_name,
            industry=eligible[symbol].industry,
            value=value,
        )
        for symbol, value in sorted(aggregated.items())
        if symbol in eligible
    ]
    if request.input_mode == "weights":
        total_weight = sum((holding.value for holding in holdings), cash_value)
        if abs(total_weight - Decimal(1)) > WEIGHT_TOLERANCE:
            errors.append(
                f"Weights including cash must total 1.0; received {total_weight.normalize()}"
            )
    valuation_date = _latest_common_date(session, [holding.security_id for holding in holdings])
    if holdings and valuation_date is None:
        errors.append("No common closing-price date exists for all holdings")
    if duplicate_found:
        warnings.append("Duplicate symbols were combined")

    fingerprint = None
    if not errors and valuation_date is not None:
        fingerprint = _fingerprint(request.input_mode, valuation_date, holdings, cash_value)
    return PortfolioPreviewResponse(
        valid=not errors,
        input_mode=request.input_mode,
        valuation_date=valuation_date,
        holdings=holdings,
        cash_value=cash_value,
        errors=errors,
        warnings=warnings,
        preview_fingerprint=fingerprint,
    )
