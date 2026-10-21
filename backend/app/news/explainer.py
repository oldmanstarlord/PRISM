"""Domain-specific, explainable news narrative and investor guidance generator.

Generates a structured, approximately 60-70 word analytical synthesis covering:
1. What the news is (event summary and primary company).
2. How it will affect the market, stocks, and sectors.
3. Actionable investor advice / what you should do.
"""

from __future__ import annotations

import re
from typing import Any

# Security to Sector mapping for standard Indian equities
KNOWN_SECTORS: dict[str, str] = {
    "RELIANCE": "Energy & Diversified",
    "TCS": "Information Technology",
    "HDFCBANK": "Financial Services (Banking)",
    "INFY": "Information Technology",
    "ICICIBANK": "Financial Services (Banking)",
    "BHARTIARTL": "Telecommunications",
    "SBIN": "Financial Services (Banking)",
    "ITC": "Consumer Goods (FMCG)",
    "LT": "Infrastructure & Capital Goods",
    "HINDUNILVR": "Consumer Goods (FMCG)",
    "BAJFINANCE": "Financial Services (NBFC)",
    "KOTAKBANK": "Financial Services (Banking)",
    "MARUTI": "Automobile",
    "TATAMOTORS": "Automobile",
    "TATASTEEL": "Metals & Mining",
    "SUNPHARMA": "Healthcare & Pharma",
    "WIPRO": "Information Technology",
    "AXISBANK": "Financial Services (Banking)",
    "TITAN": "Consumer Discretionary",
    "OIL": "Energy (Oil & Gas)",
    "BEL": "Aerospace & Defense",
    "SAIL": "Metals & Mining",
    "COALINDIA": "Energy & Mining",
    "NTPC": "Power & Utilities",
    "POWERGRID": "Power & Utilities",
    "ONGC": "Energy (Oil & Gas)",
    "JSWSTEEL": "Metals & Mining",
    "ADANIENT": "Diversified Conglomerate",
    "ADANIPORTS": "Infrastructure & Logistics",
}


def _detect_key_topic(headline: str, snippet: str) -> str:
    """Identify key business topic keywords from text."""
    combined = f"{headline} {snippet}".lower()
    if any(k in combined for k in ["profit", "net profit", "revenue", "quarterly", "q1", "q2", "q3", "q4", "results"]):
        return "financial_results"
    if any(k in combined for k in ["order", "contract", "deal", "bagged", "secures", "wins"]):
        return "contract_win"
    if any(k in combined for k in ["expansion", "plant", "invest", "capex", "capacity", "facility"]):
        return "expansion"
    if any(k in combined for k in ["probe", "fine", "penalty", "sebi", "rbi", "notice", "scrutiny", "tax"]):
        return "regulatory"
    if any(k in combined for k in ["acquisition", "merger", "stake", "buyout", "m&a"]):
        return "merger"
    if any(k in combined for k in ["guidance", "outlook", "forecast", "target", "slowdown"]):
        return "guidance"
    if any(k in combined for k in ["dividend", "bonus", "buyback", "payout"]):
        return "capital_return"
    return "general_operations"


def generate_news_explanation(
    headline: str,
    snippet: str,
    entities: list[Any],
    event_category: str,
    sentiment_label: str,
    sentiment_score: float,
    holdings_by_symbol: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Synthesize a structured ~60-70 word explanation with impact and actionable advice."""
    holdings_by_symbol = holdings_by_symbol or {}

    # Identify primary symbol and company
    primary_sym = entities[0].symbol if entities else "PORTFOLIO"
    company_name = entities[0].company_name if entities else (headline.split(" - ")[-1] if " - " in headline else "the company")

    # Clean company name
    if " Limited" in company_name:
        short_company = company_name.replace(" Limited", "").replace(" Ltd", "")
    else:
        short_company = company_name

    # Determine sector
    sector = KNOWN_SECTORS.get(primary_sym)
    if not sector and entities and getattr(entities[0], "sector", None):
        sector = entities[0].sector
    if not sector and primary_sym in holdings_by_symbol:
        sector = holdings_by_symbol[primary_sym].get("sector")
    if not sector:
        sector = "Equities & Business"

    # Check holding status
    is_owned = primary_sym in holdings_by_symbol
    holding_weight = float(holdings_by_symbol[primary_sym].get("weight", 0.0)) * 100.0 if is_owned else 0.0

    topic = _detect_key_topic(headline, snippet)

    # ─── 1. WHAT THE NEWS IS (15 - 20 words) ───
    if event_category == "macro" or primary_sym == "PORTFOLIO":
        what_is = (
            "Broad macroeconomic signals and monetary policy updates are driving institutional sentiment "
            "across the domestic Indian market."
        )
    elif topic == "financial_results":
        if sentiment_score >= 0.15:
            what_is = (
                f"{short_company} delivered strong quarterly financial performance, demonstrating solid revenue traction "
                f"and healthy operating earnings margins."
            )
        elif sentiment_score <= -0.15:
            what_is = (
                f"{short_company} encountered quarterly earnings margin pressure and unexpected revenue headwinds amid "
                f"elevated operational expenditure."
            )
        else:
            what_is = (
                f"{short_company} announced latest quarterly operating updates, matching market forecasts with steady "
                f"underlying business volumes."
            )
    elif topic == "contract_win":
        what_is = (
            f"{short_company} secured significant strategic commercial contracts, expanding order backlog visibility "
            f"and reinforcing near-term revenue pipelines."
        )
    elif topic == "expansion":
        what_is = (
            f"{short_company} initiated strategic capacity expansion and infrastructure investments to capture growing "
            f"domestic market demand."
        )
    elif topic == "regulatory":
        what_is = (
            f"{short_company} is addressing statutory regulatory inquiries and compliance notices regarding operational "
            f"and governance standards."
        )
    elif topic == "merger":
        what_is = (
            f"{short_company} advanced strategic corporate consolidation and asset realignment to unlock operational synergies "
            f"and balance-sheet efficiencies."
        )
    elif topic == "guidance":
        what_is = (
            f"{short_company} published revised forward management guidance reflecting current demand dynamics and "
            f"capital expenditure priorities."
        )
    else:
        # Generic/routine
        what_is = (
            f"{short_company} reported key operational developments regarding business execution and strategic positioning "
            f"in domestic markets."
        )

    # ─── 2. HOW IT WILL AFFECT MARKET, STOCKS & SECTORS (20 - 25 words) ───
    if sentiment_score >= 0.15:
        impact = (
            f"This positive catalyst provides upward price momentum for {primary_sym}, stimulates valuation multiple expansion "
            f"across {sector} peers, and bolsters broader benchmark NIFTY confidence."
        )
    elif sentiment_score <= -0.15:
        impact = (
            f"This development exerts downward pricing pressure on {primary_sym}, elevates short-term volatility across "
            f"{sector} peer stocks, and induces cautious market sentiment."
        )
    else:
        impact = (
            f"This neutral update keeps {primary_sym} rangebound, prompts a wait-and-see posture across {sector} "
            f"competitors, and has limited systemic market spillover."
        )

    # ─── 3. ACTIONABLE INVESTOR ADVICE (20 - 25 words) ───
    if is_owned:
        if sentiment_score >= 0.15:
            advice = (
                f"Holding {holding_weight:.1f}% capital in {primary_sym}: hold to participate in upside momentum, "
                f"but maintain disciplined trailing stop-losses rather than aggressively chasing extended rallies."
            )
        elif sentiment_score <= -0.15:
            advice = (
                f"Holding {holding_weight:.1f}% capital in {primary_sym}: avoid emotional panic-selling; review downside "
                f"risk parameters and consider rebalancing if sector concentration exceeds your policy ceiling."
            )
        else:
            advice = (
                f"Holding {holding_weight:.1f}% capital in {primary_sym}: maintain current allocation without reactive "
                f"trading; track subsequent operational execution and upcoming corporate disclosures."
            )
    else:
        if sentiment_score >= 0.15:
            advice = (
                f"For prospective exposure to {primary_sym}: await orderly price consolidation or pullbacks toward key "
                f"support levels before initiating fresh capital entry."
            )
        elif sentiment_score <= -0.15:
            advice = (
                f"For non-held assets: refrain from speculative dip-buying in {primary_sym} until market selling exhausts "
                f"and technical stabilization is established."
            )
        else:
            advice = (
                f"Stay diversified across {sector} holdings; focus on fundamental balance-sheet strength rather than "
                f"short-term headline speculation."
            )

    full_explanation = f"{what_is} {impact} {advice}"

    return {
        "what_the_news_is": what_is,
        "market_and_sector_impact": impact,
        "actionable_advice": advice,
        "explanation": full_explanation,
    }
