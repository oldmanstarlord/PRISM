"""Expand Aarav's saved portfolio to 12 covered stocks; dry-run unless --apply."""

import argparse
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, desc, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.auth import verify_access_token
from backend.app.core.config import settings
from backend.app.db.models import (
    AuditEvent,
    MstNode,
    MstRun,
    Portfolio,
    PortfolioHolding,
    PortfolioSnapshot,
    PortfolioTransaction,
    PriceDailyAdjusted,
    SecurityAlias,
    StockMetricDaily,
)
from backend.app.db.session import SessionLocal
from backend.app.market_data.metrics import METHODOLOGY_VERSION
from backend.app.portfolio.ledger import LedgerTransactionInput, TransactionType, replay_ledger

PREFERRED = [
    "RELIANCE",
    "INFY",
    "ICICIBANK",
    "LT",
    "MARUTI",
    "BHARTIARTL",
    "NTPC",
    "POWERGRID",
    "TITAN",
    "ASIANPAINT",
    "WIPRO",
    "ULTRACEMCO",
    "NESTLEIND",
]


def main(apply: bool, transaction_pooler: bool = False) -> None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise ValueError("Supabase authentication must be configured")
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_publishable_key},
        json={
            "email": "aarav@prism.com",
            "password": os.getenv("PRISM_PRESENTATION_PASSWORD", "Prism@2026"),
        },
        timeout=20,
    )
    if response.status_code != 200:
        raise ValueError("Unable to authenticate Aarav; no data changed")
    user = verify_access_token(response.json()["access_token"])
    if user.email != "aarav@prism.com":
        raise ValueError("Unexpected account identity")
    factory = SessionLocal
    if transaction_pooler:
        url = make_url(settings.database_url)
        if not url.host or not url.host.endswith(".pooler.supabase.com"):
            raise ValueError("Transaction pool option requires a Supabase pooler URL")
        factory = sessionmaker(
            bind=create_engine(
                url.set(port=6543),
                poolclass=NullPool,
                connect_args={"connect_timeout": 10, "prepare_threshold": None},
            ),
            expire_on_commit=False,
        )
    with factory() as session:
        portfolio = session.scalar(
            select(Portfolio)
            .where(
                Portfolio.owner_id == user.id,
                Portfolio.archived_at.is_(None),
            )
            .order_by(desc(Portfolio.updated_at))
            .limit(1)
            .with_for_update()
        )
        if portfolio is None or portfolio.input_mode != "quantities":
            raise ValueError("Expected Aarav's existing quantity portfolio")
        rows = session.scalars(
            select(PortfolioTransaction).where(
                PortfolioTransaction.portfolio_id == portfolio.id,
                PortfolioTransaction.owner_id == user.id,
            )
        ).all()
        ledger = [
            LedgerTransactionInput(
                id=str(tx.id),
                transaction_type=cast(TransactionType, tx.transaction_type),
                trade_date=tx.trade_date,
                symbol=tx.symbol,
                quantity=tx.quantity,
                price=tx.price,
                amount=tx.amount,
                fees=tx.fees,
                notes=tx.notes,
            )
            for tx in rows
        ]
        before = replay_ledger(ledger)
        current = set(before.holdings)
        if len(current) >= 12:
            print(f"Aarav already has {len(current)} stocks; no changes needed")
            return
        metric_date = session.scalar(
            select(func.max(StockMetricDaily.metric_date)).where(
                StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
            )
        )
        metric_symbols = set(
            session.scalars(
                select(StockMetricDaily.symbol).where(
                    StockMetricDaily.metric_date == metric_date,
                    StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
                    StockMetricDaily.quality_status != "fail",
                    StockMetricDaily.score.is_not(None),
                )
            )
        )
        mst = session.scalar(
            select(MstRun)
            .where(MstRun.status == "completed")
            .order_by(
                desc(MstRun.window_end),
                desc(MstRun.computed_at),
            )
            .limit(1)
        )
        if mst is None:
            raise ValueError("No published MST available; no changes made")
        covered = metric_symbols & set(
            session.scalars(
                select(MstNode.symbol).where(
                    MstNode.mst_run_id == mst.id,
                )
            )
        )
        if current - covered:
            raise ValueError(
                f"Existing stocks lack analytics coverage: {sorted(current - covered)}"
            )
        additions = [symbol for symbol in PREFERRED if symbol in covered - current][
            : 12 - len(current)
        ]
        if len(additions) != 12 - len(current):
            raise ValueError("Insufficient covered stocks; no changes made")
        ids: dict[str, UUID] = {}
        for symbol in sorted(current | set(additions)):
            alias = session.scalar(
                select(SecurityAlias)
                .where(
                    SecurityAlias.symbol == symbol,
                    SecurityAlias.exchange == "NSE",
                    SecurityAlias.valid_to.is_(None),
                )
                .order_by(desc(SecurityAlias.valid_from))
                .limit(1)
            )
            if alias is None:
                raise ValueError(f"Missing active security alias: {symbol}")
            ids[symbol] = alias.security_id
        new_rows = []
        for symbol in additions:
            price = session.scalar(
                select(PriceDailyAdjusted)
                .where(
                    PriceDailyAdjusted.security_id == ids[symbol],
                    PriceDailyAdjusted.trade_date <= metric_date,
                    PriceDailyAdjusted.adjusted_close > 0,
                )
                .order_by(desc(PriceDailyAdjusted.trade_date), desc(PriceDailyAdjusted.computed_at))
                .limit(1)
            )
            if price is None:
                raise ValueError(f"No stored price for {symbol}")
            quantity = max(Decimal(1), Decimal(40000) // price.adjusted_close)
            tx_id = uuid4()
            ledger.append(
                LedgerTransactionInput(
                    id=str(tx_id),
                    transaction_type="BUY",
                    symbol=symbol,
                    trade_date=price.trade_date,
                    quantity=quantity,
                    price=price.adjusted_close,
                    amount=quantity * price.adjusted_close,
                )
            )
            new_rows.append(
                PortfolioTransaction(
                    id=tx_id,
                    portfolio_id=portfolio.id,
                    owner_id=user.id,
                    transaction_type="BUY",
                    security_id=ids[symbol],
                    symbol=symbol,
                    trade_date=price.trade_date,
                    quantity=quantity,
                    price=price.adjusted_close,
                    amount=quantity * price.adjusted_close,
                    fees=Decimal(0),
                    notes="Portfolio expansion",
                    idempotency_key=f"aarav-expand-12:{symbol}",
                )
            )
            print(f"Add {symbol}: {quantity} shares; stored price date {price.trade_date}")
        after = replay_ledger(ledger)
        assert len(after.holdings) == 12
        print(
            f"Stocks: {len(current)} -> {len(after.holdings)}; "
            f"metrics: {metric_date}; MST: {mst.window_end}"
        )
        if not apply:
            print("Dry run; no data changed")
            return
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            owner_id=user.id,
            valuation_date=metric_date,
            cash_amount=max(Decimal(0), after.cash),
            cash_weight=Decimal(0),
            input_fingerprint=uuid4().hex,
            source="system",
        )
        session.add(snapshot)
        session.flush()
        for symbol, holding in after.holdings.items():
            session.add(
                PortfolioHolding(
                    snapshot_id=snapshot.id,
                    owner_id=user.id,
                    security_id=ids[symbol],
                    symbol=symbol,
                    quantity=holding.quantity,
                    target_weight=None,
                )
            )
        session.add_all(new_rows)
        portfolio.updated_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                owner_id=user.id,
                event_type="portfolio.expanded",
                entity_type="portfolio",
                entity_id=portfolio.id,
                details={"added_symbols": additions, "holding_count": 12},
            )
        )
        session.commit()
        print("Saved Aarav's 12-stock portfolio")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--transaction-pooler", action="store_true")
    arguments = parser.parse_args()
    main(arguments.apply, arguments.transaction_pooler)
