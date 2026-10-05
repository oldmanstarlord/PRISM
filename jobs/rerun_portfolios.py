"""Idempotently rerun every persisted portfolio against its latest holding date."""

from sqlalchemy import select

from backend.app.db.models import Portfolio
from backend.app.db.session import SessionLocal
from backend.app.portfolio.schemas import RiskRunRequest
from backend.app.portfolio.service import run_portfolio_risk


def main() -> None:
    completed = 0
    with SessionLocal() as session:
        portfolio_ids = session.scalars(select(Portfolio.id).order_by(Portfolio.id)).all()
        for portfolio_id in portfolio_ids:
            run_portfolio_risk(session, portfolio_id, RiskRunRequest(force_rerun=False))
            completed += 1
    print(f"Created or reused risk runs for {completed} portfolios.")


if __name__ == "__main__":
    main()
