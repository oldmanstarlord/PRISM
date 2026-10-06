"""Contextual financial-statement screens; no universal/SEBI rating thresholds.

Assess interacting evidence first. Weights summarize those assessments only;
profile eligibility and known risks determine which rating bands are available.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any

CAPITAL_INTENSIVE = {
    "Power",
    "Telecommunication",
    "Oil Gas & Consumable Fuels",
    "Metals & Mining",
    "Construction",
    "Construction Materials",
    "Realty",
}
DIMENSION_WEIGHTS = {
    "Leverage": 20,
    "Profitability": 20,
    "Growth": 15,
    "Cash_Flow": 20,
    "Capital_Efficiency": 10,
    "Operating_Performance": 10,
    "Ownership_Risk": 5,
}


def change(current: float | None, previous: float | None) -> float | None:
    # Loss-to-profit and negative-base changes are states, not ordinary growth %.
    return (
        (current / previous - 1) * 100
        if (current is not None and previous is not None and previous > 0)
        else None
    )


def earlier(period: str, years: int = 1) -> str:
    d = date.fromisoformat(period)
    return d.replace(year=d.year - years).isoformat()


def metrics(history: dict[str, Any]) -> dict[str, Any]:
    annual = history["annual"]
    quarters = history["quarters"]
    balance = history["balance"]
    cash = history["cash"]
    returns = history["returns"]
    latest = max(annual) if annual else None
    a = annual.get(latest, {})
    old = annual.get(earlier(latest), {}) if latest else {}
    comparable = a.get("months") == old.get("months") == 12
    recent = [annual.get(earlier(latest, y), {}) for y in range(3)] if latest else []
    recent = [x for x in recent if x.get("months") == 12 and x.get("net") is not None]
    qlatest = max(quarters) if quarters else None
    q = quarters.get(qlatest, {})
    qold = quarters.get(earlier(qlatest), {}) if qlatest else {}
    latest_balance = max(balance) if balance else None
    b = balance.get(latest_balance, {})
    bold = balance.get(earlier(latest_balance), {}) if latest_balance else {}
    result = {
        "Annual_Context_Period": latest,
        "Quarter_Context_Period": qlatest,
        "Revenue_Growth_YoY": change(a.get("revenue"), old.get("revenue")) if comparable else None,
        "Profit_Growth_YoY": change(a.get("net"), old.get("net")) if comparable else None,
        "Operating_Profit_Growth_YoY": change(a.get("ebit"), old.get("ebit"))
        if comparable
        else None,
        "Quarter_Revenue_Growth_YoY": change(q.get("revenue"), qold.get("revenue")),
        "Quarter_Profit_Growth_YoY": change(q.get("net"), qold.get("net")),
        "Quarter_Operating_Profit_Growth_YoY": change(q.get("ebit"), qold.get("ebit")),
        "Latest_Quarter_Profit": q.get("net"),
        "Profit_History_Years": len(recent),
        "Profitable_Years_3Y": sum(x["net"] > 0 for x in recent),
        "Loss_Years_3Y": sum(x["net"] <= 0 for x in recent),
        "Revenue_CAGR_3Y": None,
        "Profit_CAGR_3Y": None,
        "Debt_Growth_YoY": change(b.get("debt"), bold.get("debt")),
        "Debt_Equity_Change_YoY": None,
        "Cash_Flow_Period": max(cash) if cash else None,
        "Latest_Operating_Cash_Flow": cash[max(cash)] if cash else None,
        "Cash_Conversion": None,
        "Cash_Conversion_Years": 0,
        "Positive_Cash_Flow_Years": 0,
        "Negative_Cash_Flow_Years": 0,
        "Interest_Coverage": None,
        "Interest_Expense": None,
        "Core_EBIT": None,
        "Core_Profit_Before_Tax": None,
        "Debt_EBITDA": None,
        "Indicative_Debt_Cost": None,
        "Margin_Change_YoY_PP": None,
        "ROCE_Change_YoY_PP": None,
        "Dividend_Payout": a.get("payout"),
        "Growth_Comparability": "Comparable_12_month_periods"
        if comparable
        else "Missing_or_noncomparable_annual_periods",
    }
    if latest:
        three = annual.get(earlier(latest, 3), {})
        for key, target in [("revenue", "Revenue_CAGR_3Y"), ("net", "Profit_CAGR_3Y")]:
            if a.get("months") == three.get("months") == 12 and (
                a.get(key) is not None
                and three.get(key) is not None
                and a[key] > 0
                and three[key] > 0
            ):
                result[target] = ((a[key] / three[key]) ** (1 / 3) - 1) * 100
    ttm = history.get("ttm") or a
    ebit, interest = ttm.get("ebit"), ttm.get("interest")
    result.update(Core_EBIT=ebit, Interest_Expense=interest)
    if ebit is not None and interest is not None:
        result["Core_Profit_Before_Tax"] = ebit - interest
        result["Interest_Coverage"] = ebit / interest if interest > 0 else None
    if b.get("debt") is not None and ttm.get("operating") is not None and ttm["operating"] > 0:
        result["Debt_EBITDA"] = b["debt"] / ttm["operating"]
    if b.get("de") is not None and bold.get("de") is not None:
        result["Debt_Equity_Change_YoY"] = b["de"] - bold["de"]
    if comparable and a.get("margin") is not None and old.get("margin") is not None:
        result["Margin_Change_YoY_PP"] = a["margin"] - old["margin"]
    if latest and a.get("interest") is not None:
        ab, ob = balance.get(latest, {}), balance.get(earlier(latest), {})
        if ab.get("debt") is not None and ob.get("debt") is not None:
            avg = (ab["debt"] + ob["debt"]) / 2
            if avg > 0:
                result["Indicative_Debt_Cost"] = a["interest"] / avg * 100
    if latest and returns.get(latest) is not None and returns.get(earlier(latest)) is not None:
        result["ROCE_Change_YoY_PP"] = returns[latest] - returns[earlier(latest)]
    # Align cash and profit to the same consecutive annual periods and basis.
    cf_latest = result["Cash_Flow_Period"]
    pairs = []
    if cf_latest:
        for y in range(3):
            period = earlier(cf_latest, y)
            profit = annual.get(period, {})
            cf = cash.get(period)
            if cf is None or profit.get("months") != 12 or profit.get("net") is None:
                break
            pairs.append((cf, profit["net"]))
    result["Cash_Conversion_Years"] = len(pairs)
    result["Positive_Cash_Flow_Years"] = sum(cf > 0 for cf, _ in pairs)
    result["Negative_Cash_Flow_Years"] = sum(cf <= 0 for cf, _ in pairs)
    if len(pairs) >= 2 and all(profit > 0 for _, profit in pairs):
        result["Cash_Conversion"] = sum(cf for cf, _ in pairs) / sum(p for _, p in pairs)
    return result


def assess(row: dict[str, Any], all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    m = row["_context_metrics"]
    reasons, limits = [], []
    capital = row["Sector"] in CAPITAL_INTENSIVE
    regulated = row.get("Business_Type") == "Regulated_Financial"
    capital_markets = row.get("Broad_Industry") == "Capital Markets"
    mixed = row.get("_core_cash_metrics") is not None
    cm = row.get("_core_cash_metrics") or m
    if mixed:
        limits.append(
            "Finance subsidiary affects consolidated cash/debt; "
            "parent standalone cash checked separately"
        )
    if m["Growth_Comparability"] != "Comparable_12_month_periods":
        limits.append("Annual growth lacks comparable 12-month baseline; quarterly evidence used")
    debt = row.get("Debt_Equity")
    roce = row.get("ROCE")
    profit = row.get("_net_profit")
    annual_profit = row.get("_last_annual_profit")
    profitable = (
        profit is not None and profit > 0 and annual_profit is not None and annual_profit > 0
    )
    persistent_loss = m["Loss_Years_3Y"] >= 2 or (
        profit is not None
        and profit <= 0
        and annual_profit is not None
        and annual_profit <= 0
        and m["Latest_Quarter_Profit"] is not None
        and m["Latest_Quarter_Profit"] <= 0
    )
    core_positive = m["Core_Profit_Before_Tax"] is not None and m["Core_Profit_Before_Tax"] > 0
    ry, py = m["Revenue_Growth_YoY"], m["Profit_Growth_YoY"]
    qr, qp = m["Quarter_Revenue_Growth_YoY"], m["Quarter_Operating_Profit_Growth_YoY"]
    expanding = (
        ((ry is not None and ry > 0) or (ry is None and qr is not None and qr > 0))
        and ((py is not None and py > 0) or (py is None and qp is not None and qp > 0))
        and (qr is None or qr >= -5)
        and (qp is None or qp >= -10)
    )
    contracting = (
        ry is not None
        and ry < -10
        and py is not None
        and py < -20
        and (qr is not None and qr < 0 or qp is not None and qp < 0)
    )
    stable = ry is not None and ry >= -5 and py is not None and py >= -10
    cash_positive = (
        cm["Latest_Operating_Cash_Flow"] is not None and cm["Latest_Operating_Cash_Flow"] > 0
    )
    conversion = cm["Cash_Conversion"]
    if capital_markets:
        cash_grade = "Moderate"
        limits.append("Capital-market client/settlement cash flows need business-specific review")
    elif (
        cm["Cash_Conversion_Years"] >= 2
        and cash_positive
        and conversion is not None
        and (conversion >= 0.7 and cm["Positive_Cash_Flow_Years"] >= 2)
    ):
        cash_grade = "Strong"
    elif cm["Negative_Cash_Flow_Years"] >= 2 or (conversion is not None and conversion < 0.3):
        cash_grade = "Weak"
    elif cm["Latest_Operating_Cash_Flow"] is None:
        cash_grade = "Missing"
    else:
        cash_grade = "Moderate"
    if cash_grade == "Weak":
        reasons.append("Accounting profits are not converting adequately to operating cash")
    if not profitable:
        profit_grade = (
            "Weak" if persistent_loss else "Moderate" if profit is not None else "Missing"
        )
    elif (
        core_positive
        and m["Profitable_Years_3Y"] >= min(2, m["Profit_History_Years"])
        and (m["Profit_History_Years"] >= 2 and (m["Latest_Quarter_Profit"] or 0) > 0)
    ):
        profit_grade = "Strong"
    else:
        profit_grade = "Moderate"
    if profitable and not core_positive and not regulated:
        reasons.append("Positive net profit is not supported by positive core profit before tax")
    growth_grade = "Strong" if profitable and expanding else "Weak" if contracting else "Moderate"
    mature = profitable and stable and cash_grade == "Strong" and roce is not None and roce >= 15
    if mature:
        growth_grade = "Strong"
        reasons.append("Stable mature business supported by cash generation and capital returns")
    icr = m["Interest_Coverage"]
    no_interest = m["Interest_Expense"] == 0 and m["Core_EBIT"] is not None and m["Core_EBIT"] > 0
    coverage_ok = no_interest or icr is not None and icr >= 3
    de_change = m["Debt_Equity_Change_YoY"]
    debt_rising = de_change is not None and de_change > 0.2
    support = (
        profitable
        and core_positive
        and coverage_ok
        and cash_grade == "Strong"
        and (expanding or mature)
    )
    safe_limit = 2.5 if capital else 1.5
    if debt is None:
        leverage_grade = "Missing"
    elif debt <= 0.1:
        leverage_grade = "Strong" if profitable and core_positive else "Moderate"
        reasons.append(
            "Near-zero leverage reduces funding risk; it does not establish operating strength"
        )
    elif (
        support
        and debt <= safe_limit
        and (m["Debt_EBITDA"] is None or m["Debt_EBITDA"] <= (5 if capital else 3) or mixed)
    ):
        leverage_grade = "Strong"
        reasons.append(
            "Borrowing supported by profits, growth/stability, cash flow and interest coverage"
        )
    elif (
        icr is not None
        and icr < 1.5
        or (debt > safe_limit and cash_grade == "Weak" or debt_rising and cash_grade == "Weak")
    ):
        leverage_grade = "Weak"
        reasons.append("Debt burden is not supported adequately by debt service/cash generation")
    else:
        leverage_grade = "Moderate"
        reasons.append(
            "Leverage requires monitoring alongside cash generation and interest coverage"
        )
    return_floor = 12 if capital else 15
    improving_return = (
        roce is not None
        and roce >= (8 if capital else 12)
        and expanding
        and support
        and m["ROCE_Change_YoY_PP"] is not None
        and m["ROCE_Change_YoY_PP"] >= 0
    )
    if roce is None:
        return_grade = "Missing"
    elif profitable and core_positive and (roce >= return_floor or improving_return):
        return_grade = "Strong"
        if improving_return and roce < return_floor:
            reasons.append(
                "Below headline ROCE threshold, but stable/improving returns "
                "and cash-supported growth"
            )
    elif roce < 8 and not expanding or roce <= 0:
        return_grade = "Weak"
    else:
        return_grade = "Moderate"
    # Margin levels vary by business. Own trend and returns can validate low margins.
    peers = [
        r
        for r in all_rows
        if r.get("Industry") == row.get("Industry")
        and not regulated
        and r.get("OPM") is not None
        and r["OPM"] > 0
    ]
    median = statistics.median(r["OPM"] for r in peers) if len(peers) >= 5 else None
    opm, margin_change = row.get("OPM"), m["Margin_Change_YoY_PP"]
    op_growth = m["Operating_Profit_Growth_YoY"]
    if opm is None:
        margin_grade = "Missing"
    elif (
        opm <= 0
        or margin_change is not None
        and margin_change < -3
        and (op_growth is not None and op_growth < 0 and not core_positive)
    ):
        margin_grade = "Weak"
    elif (
        core_positive
        and (margin_change is None or margin_change >= -2)
        and (op_growth is None or op_growth >= -5)
        and (
            median is None
            or opm >= median * 0.5
            or return_grade == "Strong"
            and cash_grade == "Strong"
        )
    ):
        margin_grade = "Strong"
    else:
        margin_grade = "Moderate"
    pledge = row.get("Promoter_Pledge")
    encumbered = row.get("Promoter_Encumbrance")
    encumbrance_risk = encumbered is not None and (
        encumbered >= 50 or (row.get("Encumbrance_Total_Capital") or 0) >= 20
    )
    owner_fall = row.get("Promoter_YoY") is not None and row["Promoter_YoY"] < -2
    owner_grade = (
        "Missing"
        if pledge is None
        else "Weak"
        if pledge > 10 or encumbrance_risk
        else ("Moderate" if pledge > 0 or owner_fall else "Strong")
    )
    dimensions = dict(
        Leverage=leverage_grade,
        Profitability=profit_grade,
        Growth=growth_grade,
        Cash_Flow=cash_grade,
        Capital_Efficiency=return_grade,
        Operating_Performance=margin_grade,
        Ownership_Risk=owner_grade,
    )
    severe = (
        row.get("_equity") is not None
        and row["_equity"] <= 0
        or (pledge is not None and pledge >= 50)
    )
    distressed = (
        persistent_loss
        and (m["Core_EBIT"] is None or m["Core_EBIT"] <= 0)
        or (icr is not None and icr < 1 and leverage_grade == "Weak" and cash_grade == "Weak")
    )
    if regulated and not severe and not distressed:
        return {
            "dimensions": {
                "Profitability": "Strong"
                if profitable and m["Profitable_Years_3Y"] >= 2
                else "Moderate"
                if profitable
                else "Weak",
                "Growth": growth_grade,
                "Asset_Quality": "Missing",
                "Regulatory_Capital_or_Solvency": "Missing",
                "Liquidity": "Missing",
                "Ownership_Risk": owner_grade,
            },
            "profile": "Financial_sector_requires_specialist_data",
            "score": None,
            "label": "Limited Assessment",
            "raw_score": None,
            "reasons": [
                "Industrial debt/margin/cash-flow rules not applied to banks, lenders or insurers",
                "Need asset quality, regulatory capital/liquidity or insurer solvency data",
            ],
            "limits": limits,
            "valuation": "Separate valuation assessment required",
        }
    if not severe and not distressed and (m["Profit_History_Years"] < 2 or cash_grade == "Missing"):
        return {
            "dimensions": dimensions,
            "profile": "Insufficient_comparable_operating_history",
            "score": None,
            "label": "Limited Assessment",
            "raw_score": None,
            "reasons": reasons
            + ["Need at least two comparable profit years and operating cash evidence"],
            "limits": limits,
            "valuation": "History insufficient for growth-adjusted valuation",
        }

    def progress(value: float | None, target: float) -> float:
        return max(0, min(1, value / target)) if value is not None else 0

    # Rank evidence within an eligible profile. Strong assessments score 80–100
    # according to supporting strength; merely crossing a threshold is not 100.
    strength = {
        "Leverage": (
            (1 if no_interest else progress(icr, 10))
            + progress(safe_limit - (debt or 0), safe_limit)
        )
        / 2,
        "Profitability": (progress(m["Profitable_Years_3Y"], 3) + progress(py, 25)) / 2,
        "Growth": (
            progress(ry if ry is not None else qr, 20) + progress(py if py is not None else qp, 25)
        )
        / 2,
        "Cash_Flow": progress(conversion - 0.7 if conversion is not None else None, 0.6),
        "Capital_Efficiency": progress(
            roce - return_floor if roce is not None else None, return_floor
        ),
        "Operating_Performance": (progress(margin_change, 3) + progress(op_growth, 20)) / 2,
        "Ownership_Risk": 1,
    }
    component_scores = {
        k: 80 + 20 * strength[k] if v == "Strong" else 60 if v == "Moderate" else 0
        for k, v in dimensions.items()
    }
    raw = sum(DIMENSION_WEIGHTS[k] * v / 100 for k, v in component_scores.items())
    score = raw
    profile = "Mixed_evidence"
    if severe:
        score = min(score, 29)
        profile = "Severe_balance_sheet_or_pledge_risk"
    elif distressed:
        score = min(score, 39)
        profile = "Persistent_operating_or_debt_service_distress"
    elif (
        profit_grade == "Weak"
        or leverage_grade == "Weak"
        and cash_grade == "Weak"
        or (cash_grade == "Weak" and growth_grade == "Weak")
    ):
        score = min(score, 59)
        profile = "Weak_joint_operating_evidence"
    elif (
        all(
            dimensions[k] == "Strong"
            for k in ["Leverage", "Profitability", "Growth", "Capital_Efficiency"]
        )
        and (cash_grade == "Strong" or capital_markets)
        and margin_grade != "Weak"
        and owner_grade != "Weak"
    ):
        if all(v == "Strong" for v in dimensions.values()) and (
            m["Profit_History_Years"] >= 3
            and cm["Cash_Conversion_Years"] >= 3
            and m["Revenue_CAGR_3Y"] is not None
            and m["Revenue_CAGR_3Y"] >= 0
            and m["Profit_CAGR_3Y"] is not None
            and m["Profit_CAGR_3Y"] >= 0
            and not mixed
            and roce is not None
            and roce >= return_floor
        ):
            profile = "Consistent_cash_backed_quality"
        else:
            score = min(score, 89)
            profile = "Supported_growth_or_mature_cash_generator"
    else:
        score = min(score, 74)
    if encumbrance_risk:
        score = min(score, 74)
        reasons.append(
            "High aggregate promoter encumbrance; review disclosure, not a finding of breach"
        )
    if m["Profit_History_Years"] < 2 or cash_grade == "Missing":
        score = min(score, 74)
        limits.append(
            "Short or missing comparable profit/cash history prevents a Strong assessment"
        )
    if m["Latest_Quarter_Profit"] is not None and m["Latest_Quarter_Profit"] <= 0:
        score = min(score, 74)
        reasons.append("Latest quarter loss tempers annual/TTM evidence")
    # High P/E is interpreted with growth/returns; it does not establish business health.
    pe_values = [r["PE"] for r in peers if r.get("PE") is not None and r["PE"] > 0]
    pe_median = statistics.median(pe_values) if len(pe_values) >= 5 else None
    premium = row.get("PE") is not None and pe_median is not None and row["PE"] > 1.5 * pe_median
    valuation = (
        "No reliable same-industry valuation benchmark"
        if pe_median is None
        else (
            "Premium multiple with profitable growth support"
            if premium and expanding and return_grade == "Strong"
            else "Premium multiple without established profitable growth support"
            if premium
            else "Within 1.5 times same-industry positive P/E median"
        )
    )
    if row.get("PE") is None:
        valuation = "Positive P/E unavailable; profitability assessed directly"
    if (row.get("Dividend_Yield") or 0) > 0 and (not profitable or cash_grade == "Weak"):
        reasons.append(
            "Dividend yield does not establish sustainable payouts when profits/cash are weak"
        )
    for k, v in dimensions.items():
        if v in {"Weak", "Missing"}:
            reasons.append(f"{k}: {v}")
    label = (
        "Very Strong"
        if score >= 90
        else "Strong"
        if score >= 75
        else ("Moderate" if score >= 60 else "Weak" if score >= 40 else "Very Weak")
    )
    return {
        "dimensions": dimensions,
        "component_scores": component_scores,
        "profile": profile,
        "score": round(score, 2),
        "label": label,
        "raw_score": round(raw, 2),
        "reasons": reasons,
        "limits": limits,
        "valuation": valuation,
        "peer_opm": median,
        "peer_pe": pe_median,
    }
