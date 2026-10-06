"""Reconstruct quarterly fundamental scores without using future financial periods.

Yahoo does not publish original statement vintages/release dates. These are delayed,
restatement-prone historical reconstructions, not certified point-in-time backtests.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from lxml import html

from backend.app.fundamentals.data import BASE_NUMERIC, LIMITED, clean_rows, sha256
from jobs import build_fundamentals as source
from jobs.acquire_fundamental_history import DEFAULT, OLD, load
from jobs.fundamental_context import metrics

DATES = [
    f"{year}-{quarter}"
    for year in range(2023, 2027)
    for quarter in ["03-31", "06-30", "09-30", "12-31"]
    if f"{year}-{quarter}" <= "2026-09-30"
]


def pick(record: dict[str, Any], *keys: str) -> float | None:
    return next((record[k] for k in keys if record.get(k) is not None), None)


def ratio(a: float | None, b: float | None, scale: float = 1) -> float | None:
    return a / b * scale if a is not None and b is not None and b > 0 else None


def income(record: dict[str, Any], months: int) -> dict[str, Any]:
    revenue = pick(record, "TotalRevenue", "OperatingRevenue")
    ebit = pick(record, "OperatingIncome")
    depreciation = pick(
        record,
        "ReconciledDepreciation",
        "DepreciationAndAmortizationInIncomeStatement",
        "DepreciationIncomeStatement",
    )
    operating = ebit + depreciation if ebit is not None and depreciation is not None else None
    net = pick(record, "NetIncomeIncludingNoncontrollingInterests", "NetIncome")
    interest = pick(record, "InterestExpenseNonOperating", "InterestExpense")
    result: dict[str, Any] = {
        "months": months,
        "revenue": revenue,
        "net": net,
        "ebit": ebit,
        "depreciation": depreciation,
        "operating": operating,
        "interest": interest,
    }
    for key in ["revenue", "net", "ebit", "depreciation", "operating", "interest"]:
        value = result[key]
        result[key] = value / 1e7 if value is not None else None
    result.update(margin=ratio(operating, revenue, 100), payout=None, source="Yahoo")
    return result


def available(period: str, as_of: date, delay: int) -> bool:
    return date.fromisoformat(period) + timedelta(days=delay) <= as_of


def usable_statement(table: str, values: dict[str, Any]) -> bool:
    if table.endswith("balance"):
        return (
            pick(values, "TotalDebt") is not None
            and pick(values, "StockholdersEquity", "CommonStockEquity") is not None
        )
    if table.endswith("cash"):
        return pick(values, "OperatingCashFlow") is not None
    return (
        pick(values, "TotalRevenue", "OperatingRevenue") is not None
        and pick(values, "NetIncomeIncludingNoncontrollingInterests", "NetIncome") is not None
    )


def history_at(yahoo: dict[str, Any], original: dict[str, Any], as_of: date) -> dict[str, Any]:
    tables = yahoo["statements"]
    history: dict[str, Any] = {k: {} for k in ["annual", "quarters", "balance", "cash", "returns"]}
    # Yahoo's consolidated statements can only be supplemented on the same basis.
    # Older cached observations precede each Yahoo section's oldest available period.
    if original.get("Financial_Basis") == "Consolidated":
        mapping = {
            "annual": "yearly_income",
            "quarters": "quarterly_income",
            "balance": "yearly_balance",
            "cash": "yearly_cash",
            "returns": "yearly_income",
        }
        for section, table in mapping.items():
            oldest = min(
                (
                    p
                    for p, values in tables.get(table, {}).items()
                    if usable_statement(table, values)
                ),
                default="0001-01-01",
            )
            for period, value in original["_financial_history"].get(section, {}).items():
                delay = 60 if section == "quarters" else 90
                if period < oldest and available(period, as_of, delay):
                    history[section][period] = copy.deepcopy(value)
                    if section in {"annual", "quarters", "balance"}:
                        history[section][period]["source"] = "Cached_Screener_older_period"
    for freq, target, months, delay in [
        ("yearly", "annual", 12, 90),
        ("quarterly", "quarters", 3, 60),
    ]:
        for period, record in tables.get(freq + "_income", {}).items():
            if available(period, as_of, delay):
                # Frequency does not prove duration: new/demerged issuers can have stub years.
                reported_months = (
                    original["_financial_history"]
                    .get(target, {})
                    .get(period, {})
                    .get("months", months)
                )
                converted = income(record, reported_months)
                if converted["net"] is not None and converted["revenue"] is not None:
                    history[target][period] = converted
        for period, record in tables.get(freq + "_balance", {}).items():
            if available(period, as_of, delay):
                debt = pick(record, "TotalDebt")
                equity = pick(record, "StockholdersEquity", "CommonStockEquity")
                if debt is not None and equity is not None:
                    history["balance"][period] = {
                        "debt": debt / 1e7,
                        "equity": equity / 1e7,
                        "de": ratio(debt, equity),
                        "source": "Yahoo",
                    }
        if freq == "yearly":
            for period, record in tables.get("yearly_cash", {}).items():
                if available(period, as_of, 90):
                    cfo = pick(record, "OperatingCashFlow")
                    if cfo is not None:
                        history["cash"][period] = cfo / 1e7
                    dividends = pick(record, "CashDividendsPaid", "CommonStockDividendPaid")
                    annual = history["annual"].get(period)
                    if annual and dividends is not None:
                        annual["payout"] = ratio(abs(dividends) / 1e7, annual["net"], 100)
    for period, annual in history["annual"].items():
        if annual.get("source") == "Yahoo":
            bs = tables.get("yearly_balance", {}).get(period, {})
            assets, current = pick(bs, "TotalAssets"), pick(bs, "CurrentLiabilities")
            employed = (
                (assets - current) / 1e7 if assets is not None and current is not None else None
            )
            history["returns"][period] = ratio(annual["ebit"], employed, 100)
    # TTM requires four consecutive quarters actually admitted by the release delay.
    periods = sorted(history["quarters"])[-4:]
    if len(periods) == 4 and all(
        80 <= (date.fromisoformat(b) - date.fromisoformat(a)).days <= 100
        for a, b in zip(periods, periods[1:], strict=False)
    ):
        records = [history["quarters"][p] for p in periods]
        if any(r.get("months") != 3 for r in records):
            return history
        ttm: dict[str, Any] = {"months": 12}
        for key in ["revenue", "net", "ebit", "interest", "depreciation", "operating"]:
            ttm[key] = (
                sum(r[key] for r in records)
                if all(r.get(key) is not None for r in records)
                else None
            )
        ttm["margin"] = ratio(ttm["operating"], ttm["revenue"], 100)
        history["ttm"] = ttm
    return history


def ownership_at(filings: list[dict[str, Any]], as_of: date) -> dict[str, dict[str, Any]]:
    admitted: dict[str, dict[str, Any]] = {}
    for filing in sorted(filings, key=lambda f: (f["release_date"], f["record_id"])):
        if filing.get("facts") and date.fromisoformat(filing["release_date"]) <= as_of:
            admitted[filing["period"]] = filing
    return admitted


def snapshot_row(
    original: dict[str, Any],
    yahoo: dict[str, Any],
    filings: list[dict[str, Any]],
    as_of: date,
    parent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        k: original.get(k)
        for k in ["Symbol", "Company", "Sector", "Broad_Industry", "Business_Type"]
    }
    row.update({k: None for k in BASE_NUMERIC})
    history = history_at(yahoo, original, as_of)
    row.update(
        Snapshot_Date=as_of.isoformat(),
        _financial_history=history,
        Financial_Basis="Yahoo_Consolidated_with_same_basis_older_period_supplement",
    )
    annual = history["annual"].get(max(history["annual"], default=""), {})
    balance = history["balance"].get(max(history["balance"], default=""), {})
    ttm = history.get("ttm") or annual
    row.update(
        _net_profit=ttm.get("net"),
        _last_annual_profit=annual.get("net"),
        _equity=balance.get("equity"),
        Debt_Equity=balance.get("de"),
        OPM=ttm.get("margin"),
        ROCE=history["returns"].get(max(history["returns"], default="")),
        ROE=ratio(annual.get("net"), balance.get("equity"), 100),
        Balance_Sheet_Period=max(history["balance"], default=""),
        ROCE_Period=max(history["returns"], default=""),
    )
    admitted = ownership_at(filings, as_of)
    period = max(admitted, default="")
    if period:
        filing = admitted[period]
        row.update({k: v for k, v in filing["facts"].items() if not k.endswith("URL")})
        row.update(Shareholding_Period=period, Ownership_Release_Date=filing["release_date"])
        previous = source.prior_quarter(date.fromisoformat(period)).isoformat()
        year = (
            date.fromisoformat(period).replace(year=date.fromisoformat(period).year - 1).isoformat()
        )
        for prefix in ["Promoter", "FII", "DII", "Retail"]:
            field = prefix + "_Holding"
            for suffix, comparison in [("QoQ", previous), ("YoY", year)]:
                older = admitted.get(comparison, {}).get("facts", {}).get(field)
                current = row.get(field)
                row[prefix + "_" + suffix] = (
                    current - older if current is not None and older is not None else None
                )
    prices = {p: v for p, v in yahoo.get("prices", {}).items() if p <= as_of.isoformat()}
    row["Historical_Price_Coverage"] = bool(prices)
    if prices:
        price_day = max(prices)
        close = prices[price_day].get("Close")
        row["Price_Period"] = price_day
        # Yahoo Close/dividends are split adjusted. Reverse future splits for filed share counts.
        factor = 1.0
        for p, observation in yahoo["prices"].items():
            if p > price_day and observation.get("Stock Splits", 0):
                factor *= observation["Stock Splits"]
        shares = row.get("_total_shares")
        if close and shares:
            for p, observation in prices.items():
                if p > period and observation.get("Stock Splits", 0):
                    shares *= observation["Stock Splits"]
            row["Market_Cap"] = close * factor * shares / 1e7
            row["PE"] = ratio(row["Market_Cap"], ttm.get("net"))
        dividends = sum(
            v.get("Dividends") or 0
            for p, v in prices.items()
            if date.fromisoformat(p) > as_of - timedelta(days=365)
        )
        row["Dividend_Yield"] = ratio(dividends, close, 100)
    if parent:
        parent_history = {
            k: {
                p: v
                for p, v in parent.get(k, {}).items()
                if available(p, as_of, 60 if k == "quarters" else 90)
            }
            for k in ["annual", "quarters", "balance", "cash", "returns"]
        }
        row["_core_cash_metrics"] = metrics(parent_history)
    return row


def build(directory: Path, output: Path) -> None:
    original_path = OLD / "parsed_snapshot.json"
    originals = json.loads(original_path.read_text())
    yahoo = {
        r["Symbol"]: load(directory / "yahoo" / f"{source.safe(r['Symbol'])}.json.gz")
        for r in originals
    }
    owners: dict[str, list[dict[str, Any]]] = {r["Symbol"]: [] for r in originals}
    for path in sorted((directory / "ownership").glob("*.json.gz")):
        filing = load(path)
        facts = filing.get("facts", {})
        if facts:
            xml = (
                directory
                / "nse_xbrl"
                / f"{source.safe(filing['symbol'])}_{filing['record_id']}.xml.gz"
            )
            if xml.exists():
                try:
                    parsed = source.xbrl_row(xml)
                    facts.update({k: v for k, v in parsed.items() if v is not None})
                except (ValueError, OSError):
                    pass
        owners[filing["symbol"]].append(filing)
    parents = {}
    for symbol in ["BAJAJ-AUTO", "M&M", "ASHOKLEY"]:
        path = OLD / "context_standalone" / f"{source.safe(symbol)}.html.gz"
        if path.exists():
            import gzip

            parents[symbol] = source.context_history(
                html.fromstring(gzip.decompress(path.read_bytes()))
            )
    panel: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for timestamp in DATES:
        as_of = date.fromisoformat(timestamp)
        rows = [
            snapshot_row(
                r, yahoo[r["Symbol"]], owners[r["Symbol"]], as_of, parents.get(r["Symbol"])
            )
            for r in originals
        ]
        cleaned, audit = clean_rows(rows, as_of)
        for row in cleaned:
            if not row["Historical_Price_Coverage"]:
                row.update(Fundamental=LIMITED, Fundamental_Score=None)
                row["_quality_limits"].append("No observed trading history by this date")
        kept = 0
        for row in cleaned:
            # Price-only repeats do not create additional fundamental training examples.
            state = {
                "history": row["_financial_history"],
                "ownership": {
                    k: row.get(k)
                    for k in BASE_NUMERIC
                    if k.startswith(("Promoter", "FII", "DII", "Retail", "Number"))
                },
                "ownership_period": row.get("Shareholding_Period"),
                "parent_cash": row.get("_core_cash_metrics"),
            }
            fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
            row["Fundamental_State_SHA256"] = fingerprint
            row["Training_State_Changed"] = seen.get(row["Symbol"]) != fingerprint
            if row["Fundamental"] != LIMITED and row["Training_State_Changed"]:
                kept += 1
            seen[row["Symbol"]] = fingerprint
            panel.append(row)
        coverage.append(
            {
                "date": timestamp,
                "labels": dict(Counter(r["Fundamental"] for r in cleaned)),
                "eligible_changed_states": kept,
                "quality": audit,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "historical_panel.json").write_text(json.dumps(panel, allow_nan=False))
    summary = {
        "target": "Fundamental_Score",
        "policy": "3.1-freshness",
        "universe": len(originals),
        "rows": len(panel),
        "coverage": coverage,
        "source_snapshot_sha256": sha256(original_path),
        "assumptions": {
            "annual_release_delay_days": 90,
            "quarterly_release_delay_days": 60,
            "period_durations": "Reported fiscal durations override API frequency defaults",
            "ownership_release": "NSE actual submission/broadcast date, latest available revision",
            "older_financial_supplement": (
                "Cached Screener periods before oldest Yahoo section; consolidated basis only"
            ),
            "roce": "Yahoo operating EBIT / (total assets - current liabilities) * 100",
            "debt_equity": "Yahoo total debt including leases / stockholders equity",
            "opm": "(Yahoo operating income + depreciation) / revenue * 100",
            "prices": ("Historical prices downloaded; future returns and current scores excluded"),
            "limitations": [
                "Current data vintages can contain restatements",
                "Assumed statement release delays",
                "Current Nifty 200 membership introduces survivorship bias",
                "Rule-score imitation, not stock-return forecasting",
                "Market cap uses split-adjusted filed shares; intervening issuance may differ",
            ],
        },
    }
    (output / "data_report.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(
        json.dumps(
            {
                "rows": len(panel),
                "dates": [{k: v for k, v in r.items() if k != "quality"} for r in coverage],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            source.ROOT
            / "data/processed/fundamentals"
            / "history-yahoo-2026-10-06-duration-verified"
        ),
    )
    args = parser.parse_args()
    build(args.input.resolve(), args.output.resolve())
