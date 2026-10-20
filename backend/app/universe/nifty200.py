import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Security, SecurityAlias, Universe, UniverseMembership
from backend.app.market_data.yahoo import YahooFinanceClient

NIFTY_200_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv"
EXPECTED_COLUMNS = ("Company Name", "Industry", "Symbol", "Series", "ISIN Code")
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


@dataclass(frozen=True, slots=True)
class Nifty200Constituent:
    company_name: str
    industry: str
    symbol: str
    series: str
    isin: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    securities_created: int
    securities_updated: int
    aliases_created: int
    memberships_added: int
    memberships_closed: int
    current_members: int


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verified: int
    failed: dict[str, str]


def fetch_constituent_csv(url: str = NIFTY_200_URL) -> str:
    response = httpx.get(
        url,
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": "PRISM/0.1 research project"},
    )
    response.raise_for_status()
    return response.text.lstrip("\ufeff")


def parse_constituents(csv_text: str, expected_count: int = 200) -> list[Nifty200Constituent]:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected constituent columns: {reader.fieldnames}")

    constituents = [
        Nifty200Constituent(
            company_name=row["Company Name"].strip(),
            industry=row["Industry"].strip(),
            symbol=row["Symbol"].strip().upper(),
            series=row["Series"].strip().upper(),
            isin=row["ISIN Code"].strip().upper(),
        )
        for row in reader
    ]
    if len(constituents) != expected_count:
        raise ValueError(f"Expected {expected_count} constituents, received {len(constituents)}")

    symbols = [item.symbol for item in constituents]
    isins = [item.isin for item in constituents]
    if len(set(symbols)) != len(symbols):
        raise ValueError("Constituent file contains duplicate symbols")
    if len(set(isins)) != len(isins):
        raise ValueError("Constituent file contains duplicate ISINs")
    if invalid := [item.isin for item in constituents if not ISIN_PATTERN.fullmatch(item.isin)]:
        raise ValueError(f"Invalid ISIN values: {invalid}")
    if invalid := [item.symbol for item in constituents if not item.symbol]:
        raise ValueError(f"Invalid symbols: {invalid}")
    return constituents


def import_constituents(
    session: Session,
    constituents: list[Nifty200Constituent],
    effective_date: date,
    source: str = NIFTY_200_URL,
) -> ImportResult:
    if len(constituents) != 200:
        raise ValueError("Only a validated 200-member NIFTY 200 snapshot can be imported")

    ingested_at = datetime.now(UTC)
    universe = session.scalar(select(Universe).where(Universe.name == "NIFTY 200"))
    if universe is None:
        universe = Universe(
            name="NIFTY 200",
            description="Versioned NIFTY 200 constituent universe for PRISM",
        )
        session.add(universe)
        session.flush()

    incoming_isins = {item.isin for item in constituents}
    securities = session.scalars(select(Security).where(Security.isin.in_(incoming_isins))).all()
    security_by_isin = {security.isin: security for security in securities}

    securities_created = 0
    securities_updated = 0
    for item in constituents:
        security = security_by_isin.get(item.isin)
        if security is None:
            security = Security(
                isin=item.isin,
                company_name=item.company_name,
                industry=item.industry,
                currency="INR",
                is_active=True,
            )
            session.add(security)
            security_by_isin[item.isin] = security
            securities_created += 1
        elif (
            security.company_name != item.company_name
            or security.industry != item.industry
            or not security.is_active
        ):
            security.company_name = item.company_name
            security.industry = item.industry
            security.is_active = True
            securities_updated += 1
    session.flush()

    security_ids = [security.id for security in security_by_isin.values()]
    active_aliases = session.scalars(
        select(SecurityAlias).where(
            SecurityAlias.security_id.in_(security_ids),
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_to.is_(None),
        )
    ).all()
    alias_by_security = {alias.security_id: alias for alias in active_aliases}

    aliases_created = 0
    for item in constituents:
        security = security_by_isin[item.isin]
        alias = alias_by_security.get(security.id)
        if alias is not None and alias.symbol == item.symbol:
            alias.provider_symbol = f"{item.symbol}.NS"
            continue
        if alias is not None:
            alias.valid_to = effective_date - timedelta(days=1)
        session.add(
            SecurityAlias(
                security_id=security.id,
                symbol=item.symbol,
                exchange="NSE",
                valid_from=effective_date,
                source=source,
                ingested_at=ingested_at,
                provider_symbol=f"{item.symbol}.NS",
            )
        )
        aliases_created += 1

    active_memberships = session.scalars(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe.id,
            UniverseMembership.valid_to.is_(None),
        )
    ).all()
    membership_by_security = {
        membership.security_id: membership for membership in active_memberships
    }
    incoming_security_ids = {security_by_isin[isin].id for isin in incoming_isins}

    memberships_closed = 0
    for security_id, membership in membership_by_security.items():
        if security_id not in incoming_security_ids:
            membership.valid_to = effective_date - timedelta(days=1)
            memberships_closed += 1

    memberships_added = 0
    for security_id in incoming_security_ids:
        if security_id in membership_by_security:
            continue
        session.add(
            UniverseMembership(
                universe_id=universe.id,
                security_id=security_id,
                valid_from=effective_date,
                source=source,
                ingested_at=ingested_at,
            )
        )
        memberships_added += 1

    return ImportResult(
        securities_created=securities_created,
        securities_updated=securities_updated,
        aliases_created=aliases_created,
        memberships_added=memberships_added,
        memberships_closed=memberships_closed,
        current_members=len(incoming_security_ids),
    )


def verify_yfinance_aliases(
    session: Session,
    *,
    as_of: date,
    client: YahooFinanceClient | None = None,
) -> VerificationResult:
    """Test and record every active NIFTY 200 alias without normalizing punctuation."""
    provider = client or YahooFinanceClient()
    aliases = session.scalars(
        select(SecurityAlias)
        .join(UniverseMembership, UniverseMembership.security_id == SecurityAlias.security_id)
        .join(Universe, Universe.id == UniverseMembership.universe_id)
        .where(
            Universe.name == "NIFTY 200",
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_from <= as_of,
            (SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= as_of)),
            UniverseMembership.valid_from <= as_of,
            (UniverseMembership.valid_to.is_(None) | (UniverseMembership.valid_to >= as_of)),
        )
        .order_by(SecurityAlias.symbol)
    ).all()
    if len(aliases) != 200:
        raise ValueError(f"Expected 200 active NIFTY 200 aliases, received {len(aliases)}")

    checked_at = datetime.now(UTC)
    failures: dict[str, str] = {}
    for alias in aliases:
        provider_symbol = f"{alias.symbol}.NS"
        verified, reason = provider.verify(provider_symbol, as_of)
        alias.provider_symbol = provider_symbol
        alias.verification_status = "verified" if verified else "failed"
        alias.verification_reason = reason
        alias.verified_at = checked_at
        if not verified:
            failures[alias.symbol] = reason or "verification_failed_without_provider_reason"
    session.flush()
    return VerificationResult(verified=len(aliases) - len(failures), failed=failures)
