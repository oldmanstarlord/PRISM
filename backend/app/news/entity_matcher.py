"""Entity matching against security master with ambiguity scoring and market-wide detection."""

from __future__ import annotations

import re
from typing import Any

from backend.app.news.schemas import NewsEntityMatchSchema

# Known symbols that collide with common English words or general economic terms
AMBIGUOUS_TICKER_COLLISIONS: dict[str, list[str]] = {
    "OIL": ["oil india", "oil india ltd", "oil india limited"],
    "CAN": ["canara bank"],
    "BEL": ["bharat electronics", "bharat electronics ltd", "bel share"],
    "SAIL": ["steel authority", "steel authority of india"],
    "GAIL": ["gail india", "gail india ltd"],
    "IDEA": ["vodafone idea", "telecom idea"],
    "ACC": ["acc ltd", "acc cement", "acc limited"],
    "UCO": ["uco bank"],
    "IOB": ["indian overseas bank"],
    "MRF": ["mrf tyres", "mrf ltd"],
}

# Standard NIFTY 200 reference data for matching when DB session is not passed
NIFTY_CORE_ENTITIES: list[dict[str, Any]] = [
    {
        "symbol": "RELIANCE",
        "company_name": "Reliance Industries Limited",
        "isin": "INE002A01018",
        "aliases": ["Reliance", "RIL"],
    },
    {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services Limited",
        "isin": "INE467B01029",
        "aliases": ["Tata Consultancy", "TCS"],
    },
    {
        "symbol": "HDFCBANK",
        "company_name": "HDFC Bank Limited",
        "isin": "INE040A01034",
        "aliases": ["HDFC Bank", "HDFC"],
    },
    {
        "symbol": "INFY",
        "company_name": "Infosys Limited",
        "isin": "INE009A01021",
        "aliases": ["Infosys", "Infy"],
    },
    {
        "symbol": "ICICIBANK",
        "company_name": "ICICI Bank Limited",
        "isin": "INE090A01021",
        "aliases": ["ICICI Bank", "ICICI"],
    },
    {
        "symbol": "BHARTIARTL",
        "company_name": "Bharti Airtel Limited",
        "isin": "INE397D01024",
        "aliases": ["Bharti Airtel", "Airtel"],
    },
    {
        "symbol": "SBIN",
        "company_name": "State Bank of India",
        "isin": "INE062A01020",
        "aliases": ["State Bank of India", "SBI"],
    },
    {
        "symbol": "ITC",
        "company_name": "ITC Limited",
        "isin": "INE154A01025",
        "aliases": ["ITC Ltd", "ITC"],
    },
    {
        "symbol": "LT",
        "company_name": "Larsen & Toubro Limited",
        "isin": "INE018A01030",
        "aliases": ["Larsen & Toubro", "L&T"],
    },
    {
        "symbol": "HINDUNILVR",
        "company_name": "Hindustan Unilever Limited",
        "isin": "INE030A01027",
        "aliases": ["Hindustan Unilever", "HUL"],
    },
    {
        "symbol": "BAJFINANCE",
        "company_name": "Bajaj Finance Limited",
        "isin": "INE296A01024",
        "aliases": ["Bajaj Finance"],
    },
    {
        "symbol": "KOTAKBANK",
        "company_name": "Kotak Mahindra Bank Limited",
        "isin": "INE237A01028",
        "aliases": ["Kotak Mahindra", "Kotak Bank"],
    },
    {
        "symbol": "MARUTI",
        "company_name": "Maruti Suzuki India Limited",
        "isin": "INE585B01010",
        "aliases": ["Maruti Suzuki", "Maruti"],
    },
    {
        "symbol": "TATAMOTORS",
        "company_name": "Tata Motors Limited",
        "isin": "INE155A01022",
        "aliases": ["Tata Motors"],
    },
    {
        "symbol": "TATASTEEL",
        "company_name": "Tata Steel Limited",
        "isin": "INE081A01020",
        "aliases": ["Tata Steel"],
    },
    {
        "symbol": "SUNPHARMA",
        "company_name": "Sun Pharmaceutical Industries Limited",
        "isin": "INE044A01036",
        "aliases": ["Sun Pharma"],
    },
    {
        "symbol": "WIPRO",
        "company_name": "Wipro Limited",
        "isin": "INE075A01022",
        "aliases": ["Wipro"],
    },
    {
        "symbol": "AXISBANK",
        "company_name": "Axis Bank Limited",
        "isin": "INE238A01034",
        "aliases": ["Axis Bank"],
    },
    {
        "symbol": "TITAN",
        "company_name": "Titan Company Limited",
        "isin": "INE280A01028",
        "aliases": ["Titan Company", "Titan"],
    },
    {
        "symbol": "OIL",
        "company_name": "Oil India Limited",
        "isin": "INE274J01014",
        "aliases": ["Oil India"],
    },
    {
        "symbol": "BEL",
        "company_name": "Bharat Electronics Limited",
        "isin": "INE263A01024",
        "aliases": ["Bharat Electronics"],
    },
    {
        "symbol": "SAIL",
        "company_name": "Steel Authority of India Limited",
        "isin": "INE114A01011",
        "aliases": ["Steel Authority of India"],
    },
]

MARKET_WIDE_INDICATORS = [
    "rbi",
    "repo rate",
    "monetary policy",
    "inflation",
    "cpi",
    "gdp",
    "fiscal deficit",
    "sebi",
    "union budget",
    "nifty 50",
    "sensex",
    "dalal street",
    "fii",
    "dii",
    "crude oil prices",
    "rupee slides",
    "rupee gains",
    "bond yields",
]


class EntityMatcher:
    """Matches text against the PRISM Security Master with collision & ambiguity filters."""

    def __init__(self, entities: list[dict[str, Any]] | None = None) -> None:
        self.entities = entities or NIFTY_CORE_ENTITIES

    def is_market_wide_news(self, text: str) -> bool:
        """Determine whether the article concerns macroeconomic or market-wide dynamics."""
        lower = text.lower()
        matches = [kw for kw in MARKET_WIDE_INDICATORS if kw in lower]
        macro_phrases = ["rbi keeps repo rate", "union budget", "monetary policy committee"]
        return len(matches) >= 2 or any(kw in lower for kw in macro_phrases)

    def match_entities(
        self, headline: str, snippet: str | None = None
    ) -> list[NewsEntityMatchSchema]:
        """Extract matching security entities from headline and snippet."""
        full_text = f"{headline} {snippet or ''}"
        text_lower = full_text.lower()
        # Case-sensitive ticker search in headline
        tokens = set(re.findall(r"\b[A-Z0-9]+\b", headline))

        matches: list[NewsEntityMatchSchema] = []
        matched_symbols: set[str] = set()

        for ent in self.entities:
            symbol = ent["symbol"]
            company_name = ent["company_name"]
            isin = ent.get("isin")
            aliases = ent.get("aliases", [])

            # Check if this ticker is known for collision (e.g. OIL, BEL, CAN)
            collision_aliases = AMBIGUOUS_TICKER_COLLISIONS.get(symbol, [])

            # 1. ISIN match (Highest certainty)
            if isin and isin.lower() in text_lower:
                matches.append(
                    NewsEntityMatchSchema(
                        symbol=symbol,
                        company_name=company_name,
                        isin=isin,
                        match_type="isin",
                        confidence=0.99,
                        is_ambiguous=False,
                        status="auto_matched",
                    )
                )
                matched_symbols.add(symbol)
                continue

            # 2. Collision detection for ambiguous ticker words
            if symbol in collision_aliases or symbol in AMBIGUOUS_TICKER_COLLISIONS:
                # If ticker appears as word, requires corroborating alias or explicit mention
                has_corroboration = any(
                    alias.lower() in text_lower
                    for alias in aliases + [company_name.lower()]
                    if alias.lower() != symbol.lower()
                )
                if has_corroboration:
                    matches.append(
                        NewsEntityMatchSchema(
                            symbol=symbol,
                            company_name=company_name,
                            isin=isin,
                            match_type="company_name",
                            confidence=0.92,
                            is_ambiguous=False,
                            status="auto_matched",
                        )
                    )
                    matched_symbols.add(symbol)
                elif symbol in tokens:
                    # Flag as ambiguous for manual quantitative review
                    reason = (
                        f"Word '{symbol}' collides with general dictionary vocabulary "
                        "without confirmed company context."
                    )
                    matches.append(
                        NewsEntityMatchSchema(
                            symbol=symbol,
                            company_name=company_name,
                            isin=isin,
                            match_type="exact_symbol",
                            confidence=0.40,
                            is_ambiguous=True,
                            status="needs_review",
                            ambiguity_reason=reason,
                        )
                    )
                    matched_symbols.add(symbol)
                continue

            # 3. Exact symbol in headline (case-sensitive)
            if symbol in tokens:
                matches.append(
                    NewsEntityMatchSchema(
                        symbol=symbol,
                        company_name=company_name,
                        isin=isin,
                        match_type="exact_symbol",
                        confidence=0.90,
                        is_ambiguous=False,
                        status="auto_matched",
                    )
                )
                matched_symbols.add(symbol)
                continue

            # 4. Company name match
            clean_company_name = re.sub(
                r"\b(limited|ltd|industries|company)\b", "", company_name.lower()
            ).strip()
            if clean_company_name and clean_company_name in text_lower:
                matches.append(
                    NewsEntityMatchSchema(
                        symbol=symbol,
                        company_name=company_name,
                        isin=isin,
                        match_type="company_name",
                        confidence=0.92,
                        is_ambiguous=False,
                        status="auto_matched",
                    )
                )
                matched_symbols.add(symbol)
                continue

            # 5. Aliases match
            for alias in aliases:
                if len(alias) >= 3 and alias.lower() in text_lower:
                    matches.append(
                        NewsEntityMatchSchema(
                            symbol=symbol,
                            company_name=company_name,
                            isin=isin,
                            match_type="alias",
                            confidence=0.85,
                            is_ambiguous=False,
                            status="auto_matched",
                        )
                    )
                    matched_symbols.add(symbol)
                    break

        return matches
