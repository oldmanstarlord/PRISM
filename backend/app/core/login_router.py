"""Email/password login and first-login portfolio initialization."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.auth import AuthenticatedUser, CurrentUser
from backend.app.core.local_accounts import ACCOUNTS, authenticate
from backend.app.db.session import SessionLocal
from backend.app.portfolio.router import ensure_active_portfolio
from backend.app.portfolio.schemas import EnsurePortfolioRequest, InitialHoldingInput

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.get("/me")
def current_account(user: CurrentUser) -> dict[str, str | None]:
    return {"id": str(user.id), "email": user.email}


@router.post("/login")
def login(request: LoginRequest) -> dict[str, object]:
    email = request.email.strip().lower()
    token, expires = authenticate(email, request.password)
    user_id, name, holdings = ACCOUNTS[email]
    with SessionLocal() as session:
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
            AuthenticatedUser(id=UUID(user_id), email=email),
        )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires,
        "expires_in": 8 * 60 * 60,
        "refresh_token": "",
        "user": {
            "id": user_id,
            "email": email,
            "user_metadata": {"name": name},
            "app_metadata": {},
            "aud": "authenticated",
            "created_at": "2026-01-05T00:00:00Z",
        },
    }
