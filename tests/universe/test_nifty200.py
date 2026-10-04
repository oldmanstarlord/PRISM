import pytest

from backend.app.universe.nifty200 import parse_constituents

HEADER = "Company Name,Industry,Symbol,Series,ISIN Code\n"
ROW_A = "Alpha Ltd.,Technology,ALPHA,EQ,INE000A01001\n"
ROW_B = "Beta Ltd.,Financial Services,BETA,EQ,INE000B01009\n"


def test_parse_constituents() -> None:
    result = parse_constituents(HEADER + ROW_A + ROW_B, expected_count=2)

    assert [item.symbol for item in result] == ["ALPHA", "BETA"]
    assert result[0].industry == "Technology"


def test_parse_constituents_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="Expected 2 constituents"):
        parse_constituents(HEADER + ROW_A, expected_count=2)


def test_parse_constituents_rejects_duplicate_symbols() -> None:
    duplicate = "Beta Ltd.,Financial Services,ALPHA,EQ,INE000B01009\n"

    with pytest.raises(ValueError, match="duplicate symbols"):
        parse_constituents(HEADER + ROW_A + duplicate, expected_count=2)

