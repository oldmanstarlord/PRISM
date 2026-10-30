"""Link administrator-provisioned Supabase identities to presentation portfolios.

Receives only email/UUID pairs on stdin from provision_supabase_accounts.mjs.
Never accepts passwords or administrative API keys.
"""

import json
import sys
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update

from backend.app.core.auth import AuthenticatedUser
from backend.app.core.local_accounts import ACCOUNTS
from backend.app.db.base import Base
from backend.app.db.models import Portfolio
from backend.app.db.session import SessionLocal
from backend.app.portfolio.router import ensure_active_portfolio
from backend.app.portfolio.schemas import EnsurePortfolioRequest, InitialHoldingInput


def link_account(email: str, user_id: UUID) -> None:
    legacy_id, name, holdings = ACCOUNTS[email]
    with SessionLocal() as session:
        old_id = UUID(legacy_id)
        if old_id != user_id:
            old_count = session.scalar(
                select(func.count()).select_from(Portfolio).where(Portfolio.owner_id == old_id)
            )
            new_count = session.scalar(
                select(func.count()).select_from(Portfolio).where(Portfolio.owner_id == user_id)
            )
            if old_count and new_count:
                raise ValueError(
                    f"{email} already has both local and Supabase portfolios; review before merging"
                )
            # The identity map comes from the Supabase administrator, never a browser request.
            for table in Base.metadata.sorted_tables:
                if "owner_id" in table.c:
                    session.execute(
                        update(table).where(table.c.owner_id == old_id).values(owner_id=user_id)
                    )
            session.execute(
                update(Portfolio)
                .where(Portfolio.owner_id == user_id)
                .values(owner_ref=str(user_id))
            )
            session.commit()
        ensure_active_portfolio(
            EnsurePortfolioRequest(
                name=f"{name}'s Portfolio",
                initial_holdings=[
                    InitialHoldingInput(
                        symbol=symbol,
                        quantity=Decimal(quantity),
                        buy_price=Decimal(price),
                        buy_date=date(2026, 1, 5),
                    )
                    for symbol, quantity, price in holdings
                ],
            ),
            session,
            AuthenticatedUser(id=user_id, email=email),
        )
    print(f"Portfolio linked: {email}")


def main() -> None:
    accounts = json.load(sys.stdin)
    if not isinstance(accounts, list) or len(accounts) != len(ACCOUNTS):
        raise ValueError("Expected exactly the three presentation account identities")
    identities = {entry["email"]: UUID(entry["id"]) for entry in accounts}
    if set(identities) != set(ACCOUNTS) or len(set(identities.values())) != len(ACCOUNTS):
        raise ValueError("Account identities must be distinct and match the configured emails")
    for email, user_id in identities.items():
        link_account(email, user_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Keep database URLs, query parameters and credentials out of terminal output.
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        original = getattr(exc, "orig", None)
        if original is not None:
            reason += f" ({type(original).__name__})"
        print(f"Account linking error: {reason}", file=sys.stderr)
        sys.exit(1)
