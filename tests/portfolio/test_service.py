from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.portfolio.schemas import PortfolioRowInput
from backend.app.portfolio.service import aggregate_rows


def test_aggregate_rows_combines_duplicates_and_separates_cash() -> None:
    holdings, cash, duplicate_found = aggregate_rows(
        [
            PortfolioRowInput(symbol=" tcs ", value=Decimal("2")),
            PortfolioRowInput(symbol="TCS", value=Decimal("3")),
            PortfolioRowInput(symbol="cash", value=Decimal("1000")),
        ]
    )

    assert holdings == {"TCS": Decimal("5")}
    assert cash == Decimal("1000")
    assert duplicate_found is True


def test_portfolio_row_rejects_non_positive_value() -> None:
    with pytest.raises(ValidationError):
        PortfolioRowInput(symbol="TCS", value=Decimal("0"))
