"""Prepare observed features without importing scores or rule assessments into X."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from jobs import fundamental_context

BASE_NUMERIC = [
    "Market_Cap",
    "PE",
    "Debt_Equity",
    "OPM",
    "ROCE",
    "Dividend_Yield",
    "Promoter_Holding",
    "Promoter_QoQ",
    "Promoter_YoY",
    "Promoter_Pledge",
    "FII_Holding",
    "FII_QoQ",
    "FII_YoY",
    "DII_Holding",
    "DII_QoQ",
    "DII_YoY",
    "Retail_Holding",
    "Retail_QoQ",
    "Retail_YoY",
    "Number_of_Shareholders",
]
METRICS = [
    "Revenue_Growth_YoY",
    "Profit_Growth_YoY",
    "Operating_Profit_Growth_YoY",
    "Quarter_Revenue_Growth_YoY",
    "Quarter_Profit_Growth_YoY",
    "Quarter_Operating_Profit_Growth_YoY",
    "Latest_Quarter_Profit",
    "Profit_History_Years",
    "Profitable_Years_3Y",
    "Loss_Years_3Y",
    "Revenue_CAGR_3Y",
    "Profit_CAGR_3Y",
    "Debt_Growth_YoY",
    "Debt_Equity_Change_YoY",
    "Latest_Operating_Cash_Flow",
    "Cash_Conversion",
    "Cash_Conversion_Years",
    "Positive_Cash_Flow_Years",
    "Negative_Cash_Flow_Years",
    "Interest_Coverage",
    "Interest_Expense",
    "Core_EBIT",
    "Core_Profit_Before_Tax",
    "Debt_EBITDA",
    "Margin_Change_YoY_PP",
    "ROCE_Change_YoY_PP",
    "Dividend_Payout",
]
EXTRA_NUMERIC = [
    "ROE",
    "Promoter_Encumbrance",
    "Encumbrance_Total_Capital",
    "Net_Profit",
    "Annual_Net_Profit",
    "Equity",
    "Parent_Cash_Conversion",
    "Parent_Cash_Years",
    "Parent_CFO",
    "Parent_Positive_Cash_Years",
    "Parent_Negative_Cash_Years",
]
CLASSES = ["Very Weak", "Weak", "Moderate", "Strong", "Very Strong"]
LABEL_ENCODING = {label: i for i, label in enumerate(CLASSES)}
LIMITED = "Limited Assessment"
POLICY_VERSION = "3.1-freshness"
SCHEMA_VERSION = "1.0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_period(value: Any, as_of: date, max_age: int) -> bool:
    try:
        age = (as_of - date.fromisoformat(value)).days
        return 0 <= age <= max_age
    except (TypeError, ValueError):
        return False


def clean_rows(
    raw_rows: list[dict[str, Any]], as_of: date
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Preserve missing/zero distinctions; stale values cannot support ratings."""
    rows = copy.deepcopy(raw_rows)
    issues: list[dict[str, Any]] = []
    symbols = [r.get("Symbol") for r in rows]
    if not symbols or any(not s for s in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("Empty universe, missing symbol or duplicate symbol")
    for row in rows:
        if date.fromisoformat(row["Snapshot_Date"]) != as_of:
            raise ValueError(f"Snapshot date mismatch for {row['Symbol']}")
        limits = []
        for field in BASE_NUMERIC + ["ROE", "Promoter_Encumbrance", "Encumbrance_Total_Capital"]:
            value = row.get(field)
            if value in (None, ""):
                row[field] = None
                continue
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid number {row['Symbol']}:{field}") from exc
            invalid = not math.isfinite(value)
            if field.endswith("_Holding") or field in {
                "Promoter_Pledge",
                "Promoter_Encumbrance",
                "Encumbrance_Total_Capital",
            }:
                invalid |= not 0 <= value <= 100
            if field.endswith(("_QoQ", "_YoY")):
                invalid |= not -100 <= value <= 100
            if field in {"Market_Cap", "PE"}:
                invalid |= value <= 0
            if field in {"Debt_Equity", "Dividend_Yield", "Number_of_Shareholders"}:
                invalid |= value < 0
            if field == "Number_of_Shareholders":
                invalid |= not value.is_integer()
            row[field] = None if invalid else value
            if invalid:
                limits.append(f"Invalid {field} removed")
        history = row.get("_financial_history")
        if not isinstance(history, dict):
            raise ValueError(f"Missing financial history for {row['Symbol']}")
        # Remove future periods before trend construction, retaining historical baselines.
        for section in ["annual", "quarters", "balance", "cash", "returns"]:
            history[section] = {
                p: v
                for p, v in history.get(section, {}).items()
                if p != "TTM" and date.fromisoformat(p) <= as_of
            }
        annual_ok = valid_period(max(history["annual"], default=""), as_of, 550)
        balance_ok = valid_period(row.get("Balance_Sheet_Period"), as_of, 400)
        cash_ok = valid_period(max(history["cash"], default=""), as_of, 550)
        if not annual_ok:
            limits.append("Annual statements missing or older than 550 days")
            history["annual"] = {}
            row.update(
                OPM=None, PE=None, ROCE=None, ROE=None, _net_profit=None, _last_annual_profit=None
            )
        if not balance_ok:
            limits.append("Balance sheet missing or older than 400 days")
            history["balance"] = {}
            row.update(Debt_Equity=None, _equity=None)
        if not cash_ok:
            limits.append("Cash statement missing or older than 550 days")
            history["cash"] = {}
        if not valid_period(max(history["quarters"], default=""), as_of, 220):
            history["quarters"] = {}
        if row.get("ROCE_Period") and not valid_period(row["ROCE_Period"], as_of, 550):
            row["ROCE"] = None
        owner_ok = valid_period(row.get("Shareholding_Period"), as_of, 200)
        if not owner_ok:
            limits.append("Shareholding period missing or older than 200 days")
            for field in BASE_NUMERIC:
                if field.startswith(("Promoter_", "FII_", "DII_", "Retail_")):
                    row[field] = None
            row["Number_of_Shareholders"] = None
        row["_context_metrics"] = fundamental_context.metrics(history)
        if row.get("_core_cash_metrics") and not valid_period(
            row["_core_cash_metrics"].get("Cash_Flow_Period"), as_of, 550
        ):
            row.pop("_core_cash_metrics")
            limits.append("Parent cash-flow supplement stale")
        row["_quality_limits"] = limits
        row["_quality_eligible"] = annual_ok and balance_ok and cash_ok and owner_ok
        if limits:
            issues.append({"Symbol": row["Symbol"], "issues": limits})
    # Recompute labels from cleaned evidence; cached labels never become features.
    for row in rows:
        assessment = fundamental_context.assess(row, rows)
        if not row["_quality_eligible"] or row.get("Promoter_Pledge") is None:
            assessment.update(
                label=LIMITED, score=None, profile="Insufficient_fresh_or_ownership_evidence"
            )
        row["Fundamental"] = assessment["label"]
        row["Fundamental_Score"] = assessment["score"]
        row["_assessment"] = assessment
    return rows, {
        "rows": len(rows),
        "issues": issues,
        "policy_version": POLICY_VERSION,
        "source_mutated": False,
        "freshness_days": {
            "annual_cash": 550,
            "balance": 400,
            "quarters": 220,
            "shareholding": 200,
        },
    }


def load_snapshot(csv_path: Path, raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = json.loads(raw_path.read_text())
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        source = list(csv.DictReader(file))
    malformed = [r for r in source if any(v is None for v in r.values())]
    if any(any(v not in (None, "") for k, v in r.items() if k != "Symbol") for r in malformed):
        raise ValueError("Malformed CSV row contains partial observations; repair source first")
    source = [r for r in source if r not in malformed]
    if [r["Symbol"] for r in source] != [r["Symbol"] for r in raw]:
        raise ValueError("CSV and raw snapshot symbol order/content differ")
    for original, observed in zip(raw, source, strict=True):
        for field in BASE_NUMERIC:
            value, text = original.get(field), observed[field]
            if (value is None and text != "") or (
                value is not None and (text == "" or abs(float(text) - value) > 0.000051)
            ):
                raise ValueError(f"CSV/raw mismatch: {original['Symbol']}:{field}")
    dates = {r["Snapshot_Date"] for r in raw}
    if len(dates) != 1:
        raise ValueError("Training expects one dated snapshot")
    rows, audit = clean_rows(raw, date.fromisoformat(dates.pop()))
    audit.update(csv_sha256=sha256(csv_path), raw_sha256=sha256(raw_path))
    audit["quarantined_malformed_csv_rows"] = malformed
    return rows, audit


def feature_frame(
    rows: list[dict[str, Any]], contextual: bool = True, extended: bool = False
) -> pd.DataFrame:
    features = []
    for row in rows:
        item = {k: row.get(k) for k in BASE_NUMERIC}
        item["Sector"] = row.get("Sector") or "Unknown"
        if contextual:
            item.update({k: row["_context_metrics"].get(k) for k in METRICS})
            item.update({k: row.get(k) for k in EXTRA_NUMERIC[:3]})
            item.update(
                Net_Profit=row.get("_net_profit"),
                Annual_Net_Profit=row.get("_last_annual_profit"),
                Equity=row.get("_equity"),
            )
            cm = row.get("_core_cash_metrics", {})
            for dest, src in {
                "Parent_Cash_Conversion": "Cash_Conversion",
                "Parent_Cash_Years": "Cash_Conversion_Years",
                "Parent_CFO": "Latest_Operating_Cash_Flow",
                "Parent_Positive_Cash_Years": "Positive_Cash_Flow_Years",
                "Parent_Negative_Cash_Years": "Negative_Cash_Flow_Years",
            }.items():
                item[dest] = cm.get(src)
            item["Broad_Industry"] = row.get("Broad_Industry") or "Unknown"
        if extended:
            history = row["_financial_history"]
            latest = max(history["annual"], default="")
            annual = history["annual"].get(latest, {})
            balance = history["balance"].get(max(history["balance"], default=""), {})
            item.update(
                Annual_Revenue=annual.get("revenue"),
                Annual_Operating_Profit=annual.get("operating"),
                Annual_Core_EBIT=annual.get("ebit"),
                Annual_Duration_Months=annual.get("months"),
                Annual_Aligned_CFO=history["cash"].get(latest),
                Borrowings=balance.get("debt"),
            )
        features.append(item)
    frame = pd.DataFrame(features, index=[r["Symbol"] for r in rows])
    for col in frame.columns.difference(["Sector", "Broad_Industry"]):
        frame[col] = pd.to_numeric(frame[col], errors="raise").replace([np.inf, -np.inf], np.nan)
    if any(
        "Score" in c or "Assessment" in c or c in {"Symbol", "Company", "Fundamental"}
        for c in frame.columns
    ):
        raise AssertionError("Forbidden identity/target-derived feature")
    return frame


def table_payload(frame: pd.DataFrame) -> dict[str, Any]:
    """JSON intermediate for artifact-tool CSV authoring; never exports NaN tokens."""
    values = frame.astype(object).where(pd.notna(frame), None).values.tolist()
    return {"columns": list(frame.columns), "rows": values}
