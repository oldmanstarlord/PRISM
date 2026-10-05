"""Fetch a dated Nifty 200 fundamentals snapshot. Run with Python and lxml installed.

Raw public-source responses are cached under data/raw/fundamentals for audit/reuse.
The input universe is never changed. Missing facts are never replaced by zero.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import gzip
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lxml import etree, html

if TYPE_CHECKING or __package__:
    from . import fundamental_context as context_model
else:
    import fundamental_context as context_model

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 5)
CACHE = ROOT / "data/raw/fundamentals/2026-10-05"
OUT = ROOT / "data/processed/fundamentals"
UNIVERSE_PATH = ROOT / "data/raw/nifty200/2026-09-30.csv"
PREFERRED_STANDALONE: set[str] = set()
REQUEST_LOCK = threading.Lock()
LAST_REQUEST = 0.0


def fetch(url: str, path: Path, attempts: int = 3) -> bytes:
    if path.exists():
        return gzip.decompress(path.read_bytes())
    last_error = None
    for attempt in range(attempts):
        try:
            global LAST_REQUEST
            with REQUEST_LOCK:
                delay = 1.6 if "screener.in" in url else 0.25
                time.sleep(max(0, delay - (time.monotonic() - LAST_REQUEST)))
                LAST_REQUEST = time.monotonic()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.nseindia.com/"
                    if "nseindia" in url
                    else "https://www.screener.in/",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                content = bytes(response.read())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(content))
            return content
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(30 if getattr(error, "code", None) == 429 else 1 + attempt * 2)
    raise RuntimeError(f"{url}: {last_error}")


def safe(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", symbol)


def universe() -> list[dict[str, Any]]:
    with UNIVERSE_PATH.open(newline="") as file:
        return list(csv.DictReader(file))


def configure(
    as_of: date,
    cache: Path,
    output: Path,
    universe_path: Path,
    preferred_standalone: set[str] | None = None,
) -> None:
    """Choose explicit dated inputs/outputs; never overwrite the historical snapshot."""
    global AS_OF, CACHE, OUT, UNIVERSE_PATH, PREFERRED_STANDALONE
    AS_OF, CACHE, OUT, UNIVERSE_PATH = as_of, cache, output, universe_path
    PREFERRED_STANDALONE = preferred_standalone or set()


def acquire_company(row: dict[str, Any]) -> dict[str, Any]:
    symbol = row["Symbol"]
    url = f"https://www.screener.in/company/{urllib.parse.quote(symbol)}/consolidated/"
    path = CACHE / "screener" / f"{safe(symbol)}.html.gz"
    try:
        content = fetch(url, path)
        doc = html.fromstring(content)
        if not doc.xpath('//*[@id="top-ratios"]'):
            raise ValueError("Company financial table missing")
        financial_periods = [period_date(p) for p in table(doc, "profit-loss")[0] if p != "TTM"]
        latest = max(financial_periods, default="")
        if (
            symbol in PREFERRED_STANDALONE
            or not latest
            or (AS_OF - date.fromisoformat(latest)).days > 550
        ):
            # Some issuers' consolidated pages contain obsolete statements.
            alternate_url = f"https://www.screener.in/company/{urllib.parse.quote(symbol)}/"
            alternate_path = CACHE / "screener_standalone" / f"{safe(symbol)}.html.gz"
            alternate = html.fromstring(fetch(alternate_url, alternate_path))
            periods = [period_date(p) for p in table(alternate, "profit-loss")[0] if p != "TTM"]
            if symbol not in PREFERRED_STANDALONE and (not periods or max(periods) <= latest):
                alternate_path.unlink(missing_ok=True)
        if symbol in {"BAJAJ-AUTO", "M&M", "ASHOKLEY"}:
            fetch(
                f"https://www.screener.in/company/{urllib.parse.quote(symbol)}/",
                CACHE / "context_standalone" / f"{safe(symbol)}.html.gz",
            )
        return {"symbol": symbol, "url": url, "path": str(path), "status": "ok"}
    except Exception as error:
        return {"symbol": symbol, "url": url, "status": "error", "error": str(error)}


def acquire() -> None:
    rows = universe()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(acquire_company, row) for row in rows]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["status"] != "ok" or len(results) % 20 == 0:
                print(f"Screener {len(results)}/{len(rows)}: {result}", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "screener_manifest.json").write_text(json.dumps(results, indent=2))
    print("Screener acquisition complete", flush=True)
    if any(r["status"] != "ok" for r in results):
        raise RuntimeError("Incomplete company acquisition; previous publication preserved")


def filing_date(value: str) -> date:
    from datetime import datetime

    return datetime.strptime(value, "%d-%b-%Y").date()


def prior_quarter(value: date) -> date:
    from datetime import timedelta

    return value.replace(day=1, month=((value.month - 1) // 3) * 3 + 1) - timedelta(days=1)


def acquire_filings() -> None:
    rows = universe()
    url = (
        "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities"
        f"&from_date={(AS_OF - timedelta(days=550)):%d-%m-%Y}&to_date={AS_OF:%d-%m-%Y}"
    )
    data = json.loads(fetch(url, CACHE / "nse_filings.json.gz"))
    selected = [entry for entry in data if entry.get("symbol") in {row["Symbol"] for row in rows}]
    (CACHE / "nse_selected_filings.json").write_text(json.dumps(selected, indent=2))
    print(f"NSE index: {len(data)} filings, {len(selected)} for universe", flush=True)
    chosen = []
    for row in rows:
        entries = sorted(
            [
                e
                for e in selected
                if e["symbol"] == row["Symbol"]
                and filing_date(e["date"]) <= AS_OF
                and filing_date(e["date"]).month in {3, 6, 9, 12}
                and filing_date(e["date"]).day
                == calendar.monthrange(filing_date(e["date"]).year, filing_date(e["date"]).month)[1]
            ],
            key=lambda e: (filing_date(e["date"]), e.get("systemDate") or ""),
            reverse=True,
        )
        if not entries:
            print(f"NO FILINGS: {row['Symbol']}", flush=True)
            continue
        current = filing_date(entries[0]["date"])
        wanted = {current, prior_quarter(current), current.replace(year=current.year - 1)}
        for period in sorted(wanted, reverse=True):
            matches = [e for e in entries if filing_date(e["date"]) == period]
            if matches:
                chosen.append(matches[0])
    (CACHE / "nse_chosen_filings.json").write_text(json.dumps(chosen, indent=2))

    def one(entry: dict[str, Any]) -> dict[str, Any]:
        path = CACHE / "nse_xbrl" / f"{safe(entry['symbol'])}_{filing_date(entry['date'])}.xml.gz"
        try:
            doc = etree.fromstring(fetch(entry["xbrl"], path))
            if etree.QName(doc).localname != "xbrl":
                raise ValueError("Not XBRL")
            return {"symbol": entry["symbol"], "date": entry["date"], "status": "ok"}
        except Exception as error:
            return {
                "symbol": entry["symbol"],
                "date": entry["date"],
                "status": "error",
                "error": str(error),
            }

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, e) for e in chosen]):
            result = future.result()
            results.append(result)
            if len(results) % 50 == 0 or result["status"] == "error":
                print(f"XBRL {len(results)}/{len(chosen)}: {result}", flush=True)
    (CACHE / "nse_xbrl_manifest.json").write_text(json.dumps(results, indent=2))


def number(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.replace(",", "").replace("%", "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def text_of(element: Any) -> str:
    return " ".join(element.text_content().split()).replace(" +", "")


def table(doc: Any, section: str) -> tuple[list[str], dict[str, list[float | None]]]:
    tables = doc.xpath(f'//*[@id="{section}"]//table')
    if not tables:
        return [], {}
    lines = tables[0].xpath(".//tr")
    headers = [text_of(e) for e in lines[0].xpath("./th|./td")][1:]
    values = {}
    for line in lines[1:]:
        cells = [text_of(e) for e in line.xpath("./th|./td")]
        if cells:
            values[cells[0]] = [number(e) for e in cells[1:]]
    return headers, values


def period_date(value: str) -> str:
    from datetime import datetime

    try:
        dt = datetime.strptime(re.sub(r" \d+m$", "", value), "%b %Y")
        return date(dt.year, dt.month, calendar.monthrange(dt.year, dt.month)[1]).isoformat()
    except ValueError:
        return value


def context_history(doc: Any) -> dict[str, Any]:
    """Keep aligned periods/bases for cross-feature and trend analysis."""
    history: dict[str, Any] = {
        "annual": {},
        "quarters": {},
        "balance": {},
        "cash": {},
        "returns": {},
    }

    def at(values: dict[str, list[float | None]], names: list[str], index: int) -> float | None:
        for name in names:
            if name in values:
                return values[name][index]
        return None

    for section, target in [("profit-loss", "annual"), ("quarters", "quarters")]:
        headers, values = table(doc, section)
        for i, label in enumerate(headers):
            revenue = at(values, ["Sales", "Revenue"], i)
            op = at(values, ["Operating Profit"], i)
            depreciation = at(values, ["Depreciation"], i)
            duration = re.search(r"(\d+)m$", label)
            record = {
                "source_label": label,
                "months": int(duration.group(1)) if duration else 12 if target == "annual" else 3,
                "revenue": revenue,
                "operating": op,
                "net": at(values, ["Net Profit"], i),
                "interest": at(values, ["Interest"], i),
                "depreciation": depreciation,
                "ebit": op - depreciation if op is not None and depreciation is not None else None,
                "margin": op / revenue * 100
                if op is not None and revenue is not None and revenue > 0
                else None,
                "payout": at(values, ["Dividend Payout %"], i),
            }
            if label == "TTM":
                history["ttm"] = record
            else:
                history[target][period_date(label)] = record
    headers, values = table(doc, "balance-sheet")
    for i, label in enumerate(headers):
        debt = at(values, ["Borrowings", "Borrowing"], i)
        eq = at(values, ["Equity Capital"], i)
        reserves = at(values, ["Reserves"], i)
        equity = eq + reserves if eq is not None and reserves is not None else None
        history["balance"][period_date(label)] = {
            "debt": debt,
            "equity": equity,
            "de": debt / equity if debt is not None and equity is not None and equity > 0 else None,
        }
    for section, target, names in [
        ("cash-flow", "cash", ["Cash from Operating Activity"]),
        ("ratios", "returns", ["ROCE %"]),
    ]:
        headers, values = table(doc, section)
        for i, label in enumerate(headers):
            history[target][period_date(label)] = at(values, names, i)
    return history


def screener_row(source: dict[str, Any]) -> dict[str, Any]:
    path = CACHE / "screener" / f"{safe(source['Symbol'])}.html.gz"
    standalone = CACHE / "screener_standalone" / f"{safe(source['Symbol'])}.html.gz"
    if standalone.exists() and source["Symbol"] != "VAML":
        path = standalone
    doc = html.fromstring(gzip.decompress(path.read_bytes()))
    row: dict[str, Any] = {
        "Symbol": source["Symbol"],
        "Company": source["Company Name"],
        "Sector": source["Industry"],
        "ISIN": source["ISIN Code"],
        "Snapshot_Date": AS_OF.isoformat(),
        "Financial_Source_URL": f"https://www.screener.in/company/{urllib.parse.quote(source['Symbol'])}/"
        + ("" if path == standalone else "consolidated/"),
    }
    info = doc.xpath('//*[@id="company-info"]')[0]
    row["Financial_Basis"] = (
        "Consolidated" if info.get("data-consolidated") == "true" else "Standalone"
    )
    for li in doc.xpath('//*[@id="top-ratios"]//li'):
        names = li.xpath('.//*[contains(@class,"name")]')
        nums = li.xpath('.//*[contains(@class,"number")]')
        if names and nums:
            name = text_of(names[0])
            key = {
                "Market Cap": "Market_Cap",
                "Stock P/E": "PE",
                "ROCE": "ROCE",
                "ROE": "ROE",
                "Dividend Yield": "Dividend_Yield",
            }.get(name)
            if key:
                row[key] = number(text_of(nums[0]))
    for name in ["Industry", "Broad Industry"]:
        nodes = doc.xpath(f'//*[@id="peers"]//a[@title="{name}"]')
        row[name.replace(" ", "_")] = text_of(nodes[0]) if nodes else ""
    broad = row["Broad_Industry"]
    row["Business_Type"] = (
        "Regulated_Financial"
        if broad in {"Banks", "Finance", "Insurance"}
        else "Non_Financial_or_Capital_Markets"
    )
    bh, bv = table(doc, "balance-sheet")
    debt = bv.get("Borrowings", bv.get("Borrowing", [None] * len(bh)))[-1] if bh else None
    equity = bv.get("Equity Capital", [None] * len(bh))[-1] if bh else None
    reserves = bv.get("Reserves", [None] * len(bh))[-1] if bh else None
    denominator = equity + reserves if equity is not None and reserves is not None else None
    row["Debt_Equity"] = (
        debt / denominator
        if debt is not None and denominator is not None and denominator > 0
        else None
    )
    row["Debt_Equity_Basis"] = "Screener borrowings / (equity capital + reserves)"
    row["Balance_Sheet_Period"] = period_date(bh[-1]) if bh else ""
    row["_equity"] = denominator
    ph, pv = table(doc, "profit-loss")
    sales = pv.get("Sales", pv.get("Revenue", [None] * len(ph)))
    operating = pv.get("Operating Profit", [None] * len(ph))
    pos = len(ph) - 1
    last_sales = sales[pos] if ph else None
    last_operating = operating[pos] if ph else None
    row["OPM"] = (
        last_operating / last_sales * 100
        if last_sales is not None and last_sales > 0 and last_operating is not None
        else None
    )
    row["OPM_Basis"] = ph[pos] if ph else ""
    financing = pv.get("Financing Profit", [None] * len(ph))
    last_financing = financing[pos] if ph else None
    row["Financing_Margin"] = (
        last_financing / last_sales * 100
        if last_sales is not None and last_sales > 0 and last_financing is not None
        else None
    )
    net = pv.get("Net Profit", [None] * len(ph))
    row["_net_profit"] = net[-1] if net else None
    row["_last_annual_profit"] = (
        net[-2] if ph and ph[-1] == "TTM" and len(net) >= 2 else row["_net_profit"]
    )
    rh, rv = table(doc, "ratios")
    annual_roce = rv.get("ROCE %", [])
    valid_roce = [i for i, v in enumerate(annual_roce) if v is not None]
    row["ROCE_Period"] = period_date(rh[valid_roce[-1]]) if valid_roce else ""
    row["ROCE_Basis"] = (
        "Screener published annual ROCE"
        if valid_roce
        else "Screener published ROCE; period not specified"
    )
    row["Annual_Financial_Period"] = (
        period_date(ph[-2] if ph and ph[-1] == "TTM" else ph[-1]) if ph else ""
    )
    # Preserve broad public ownership separately. It is never substituted for retail.
    sh, sv = table(doc, "quarterly-shp")
    row["_screener_shareholding"] = {
        period_date(p): {k: v[i] for k, v in sv.items()} for i, p in enumerate(sh)
    }
    if source["Symbol"] == "VAML" and AS_OF == date(2026, 10, 5):
        # Post-demerger figures checked against issuer PDFs (results p5;
        # earnings presentation p4). The pre-operation standalone entity
        # is not representative of the now-listed aluminium undertaking.
        row.update(
            {
                "Debt_Equity": 1.17,
                "_equity": 30441,
                "Debt_Equity_Basis": "Issuer published consolidated total debt / total equity",
                "Balance_Sheet_Period": "2026-06-30",
                "ROCE": 42.0,
                "ROCE_Period": "2026-06-30",
                "ROCE_Basis": "Issuer published TTM ROCE",
                "Financial_Auxiliary_Source_URLs": "https://d1rbiogke1jwo5.cloudfront.net/wp-content/uploads/2026/07/Consolidated-Financials.pdf;"
                "https://d1rbiogke1jwo5.cloudfront.net/wp-content/uploads/2026/07/Q1FY27_VAML_Earnings-Presentation-VFF.pdf",
            }
        )
    row["_financial_history"] = context_history(doc)
    row["_context_metrics"] = context_model.metrics(row["_financial_history"])
    # These issuers' financing subsidiaries make consolidated CFO/profit and
    # debt/EBITDA unsuitable as standalone industrial quality measures.
    if source["Symbol"] in {"BAJAJ-AUTO", "M&M", "ASHOKLEY"}:
        core = CACHE / "context_standalone" / f"{safe(source['Symbol'])}.html.gz"
        if core.exists():
            core_doc = html.fromstring(gzip.decompress(core.read_bytes()))
            row["_core_cash_metrics"] = context_model.metrics(context_history(core_doc))
            row["Core_Cash_Supplement_Source_URL"] = (
                f"https://www.screener.in/company/{urllib.parse.quote(source['Symbol'])}/"
            )
    return row


def xbrl_row(path: Path) -> dict[str, Any]:
    doc = etree.fromstring(gzip.decompress(path.read_bytes()))
    contexts: dict[str, str] = {}
    facts: dict[str, dict[str, Any]] = {}
    for node in doc:
        local = etree.QName(node).localname
        if local == "context":
            members = node.xpath('.//*[local-name()="explicitMember"]')
            # Only category summaries, never nested individual-holder disclosures.
            if len(members) == 1 and node.xpath('.//*[local-name()="typedMember"]') == []:
                contexts[members[0].text.split(":")[-1].removesuffix("Member")] = node.get("id")
        elif node.get("contextRef"):
            facts.setdefault(node.get("contextRef"), {})[local] = node.text

    def category(name: str) -> dict[str, Any]:
        context = contexts.get(name)
        return facts.get(context, {}) if context is not None else {}

    total = category("ShareholdingPattern")
    reported_total = number(total.get("ShareholdingAsAPercentageOfTotalNumberOfShares"))
    scale = 100 if reported_total == 1 else 1 if reported_total == 100 else None
    if scale is None:
        raise ValueError(f"Cannot establish percentage scale: {path.name}, total={reported_total}")

    def pct(name: str) -> float | None:
        value = number(category(name).get("ShareholdingAsAPercentageOfTotalNumberOfShares"))
        return value * scale if value is not None else None

    promoter = category("ShareholdingOfPromoterAndPromoterGroup")
    retail_names = [
        k for k in contexts if "ShareholdersHoldingNominalShareCapitalUpToRsTwoLakh" in k
    ]
    retail = pct(retail_names[0]) if len(retail_names) == 1 else None
    fp_names = [
        k
        for k in contexts
        if k.startswith("InstitutionsForeignPortfolioInvestorCategory")
        or k in {"ForeignPortfolioInvestors", "ForeignInstitutionalInvestors"}
    ]
    fp_values = [pct(k) for k in fp_names]
    fii = (
        sum(v for v in fp_values if v is not None)
        if fp_values and all(v is not None for v in fp_values)
        else None
    )
    promoter_shares = number(promoter.get("NumberOfShares"))
    total_shares = number(total.get("NumberOfShares"))
    pledged = number(promoter.get("NumberOfSharesEncumberedUnderPledged"))
    encumbered = number(promoter.get("NumberOfSharesEncumbered"))
    main = facts.get("MainI", {})
    if (
        pledged is None
        and main.get(
            "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup"
        )
        == "false"
    ):
        pledged = 0
    encumbrance_flags = [
        main.get(k)
        for k in [
            "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup",
            "WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup",
            "WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup",
        ]
    ]
    if encumbered is None and all(v == "false" for v in encumbrance_flags):
        encumbered = 0
    result = {
        "Promoter_Holding": pct("ShareholdingOfPromoterAndPromoterGroup"),
        "FII_Holding": fii,
        "DII_Holding": pct("InstitutionsDomestic"),
        "Retail_Holding": retail,
        "Public_Holding": pct("PublicShareholding"),
        "Number_of_Shareholders": number(total.get("NumberOfShareholders")),
    }
    public_shares = number(category("PublicShareholding").get("NumberOfShares"))
    nonpublic_shares = (
        number(category("SharesHeldByNonPromoterNonPublicShareholders").get("NumberOfShares")) or 0
    )
    if (
        not promoter
        and total_shares is not None
        and public_shares is not None
        and total_shares == public_shares + nonpublic_shares
    ):
        result["Promoter_Holding"] = 0
        promoter_shares = 0
    foreign_shares = number(category("InstitutionsForeign").get("NumberOfShares"))
    other_foreign_shares = sum(
        number(category(k).get("NumberOfShares")) or 0
        for k in ["OtherInstitutionsForeign", "ForeignDirectInvestment"]
    )
    if not fp_values and foreign_shares is not None and foreign_shares == other_foreign_shares:
        result["FII_Holding"] = 0
    result["Promoter_Pledge"] = (
        pledged / promoter_shares * 100
        if pledged is not None and promoter_shares is not None and promoter_shares > 0
        else 0
        if pledged == 0 and promoter_shares == 0
        else None
    )
    result["Promoter_Encumbrance"] = (
        encumbered / promoter_shares * 100
        if encumbered is not None and promoter_shares is not None and promoter_shares > 0
        else 0
        if encumbered == 0 and promoter_shares == 0
        else None
    )
    result["Encumbrance_Total_Capital"] = (
        encumbered / total_shares * 100
        if encumbered is not None and total_shares is not None and total_shares > 0
        else None
    )
    result["_scale"] = scale
    return result


MCX_SOURCES = {
    "2026-06-30": "https://www.mcxindia.com/docs/default-source/investor-relations/share-holding-pattern/shp_30_06_2026.pdf?sfvrsn=956d389b_3",
    "2026-03-31": "https://www.mcxindia.com/docs/default-source/investor-relations/share-holding-pattern/shp-report_31-03-2026.pdf",
    "2025-06-30": "https://www.mcxindia.com/docs/default-source/investor-relations/share-holding-pattern/shp_30-06-2025-(1).pdf",
}


def mcx_ownership(row: dict[str, Any]) -> None:
    periods = {}
    for period in MCX_SOURCES:
        markdown = (CACHE / "mcx" / f"{period}.md").read_text()
        lines = [
            [v.strip() for v in line.strip().strip("|").split("|")]
            for line in markdown.splitlines()
            if line.startswith("|")
        ]
        # First table has actual holdings; later tables repeat diluted/encumbrance values.
        total = next(
            v
            for v in lines
            if len(v) >= 8 and v[1] == "Total" and number(v[3]) is not None and number(v[7]) == 100
        )
        domestic = next(
            v
            for v in lines
            if len(v) >= 8 and v[0] == "Sub-Total (B) (1)" and number(v[7]) is not None
        )
        foreign = next(
            v
            for v in lines
            if len(v) >= 8 and v[0] == "Sub-Total (B) (2)" and number(v[7]) is not None
        )
        retail = next(
            v
            for v in lines
            if len(v) >= 8
            and v[1].startswith("Resident Individuals holding nominal share capital up to")
            and number(v[7]) is not None
        )
        periods[period] = {
            "Promoter_Holding": 0,
            "FII_Holding": number(foreign[7]),
            "DII_Holding": number(domestic[7]),
            "Retail_Holding": number(retail[7]),
            "Number_of_Shareholders": int(total[2]),
            "Promoter_Pledge": 0,
            "Promoter_Encumbrance": 0,
            "Encumbrance_Total_Capital": 0,
            "Public_Holding": 99.81,
        }
    row.update(periods["2026-06-30"])
    row.update(
        {
            "Shareholding_Period": "2026-06-30",
            "Shareholding_QoQ_Period": "2026-03-31",
            "Shareholding_YoY_Period": "2025-06-30",
            "Shareholding_Source_URL": MCX_SOURCES["2026-06-30"],
            "Shareholding_QoQ_Source_URL": MCX_SOURCES["2026-03-31"],
            "Shareholding_YoY_Source_URL": MCX_SOURCES["2025-06-30"],
            "Ownership_Source": "Company_BSE_filing_PDF_via_Firecrawl",
            "SEBI_Encumbrance_Disclosure_Review": "Below_threshold",
            "Data_Notes": (
                "MCX has no promoters. Retail uses resident individuals up to Rs 2 lakh "
                "nominal capital. Stock split changes category eligibility."
            ),
        }
    )
    for prefix in ["Promoter", "FII", "DII", "Retail"]:
        for suffix, period in [("QoQ", "2026-03-31"), ("YoY", "2025-06-30")]:
            row[f"{prefix}_{suffix}"] = round(
                row[prefix + "_Holding"] - periods[period][prefix + "_Holding"], 4
            )


def nse_json_row(entry: dict[str, Any]) -> tuple[dict[str, Any], str]:
    symbol, record = entry["symbol"], entry["recordId"]
    bundles = {}
    urls = []
    for index in ["summary", "promoter", "public-shareholder"]:
        url = f"https://www.nseindia.com/api/corporate-share-holdings-equities?ndsId={record}&index={index}"
        path = CACHE / "nse_json" / f"{safe(symbol)}_{record}_{index}.json.gz"
        bundles[index] = json.loads(fetch(url, path))
        urls.append(url)
    summary = bundles["summary"]
    total = next(r for r in summary if (r.get("COL_II") or "").strip() == "Total")
    prom = next(r for r in summary if r.get("COL_I") == "A")
    public = bundles["public-shareholder"]

    def lookup(predicate: Callable[[str], bool]) -> float | None:
        candidates = [r for r in public if predicate((r.get("COL_I") or "").lower())]
        return number(candidates[0].get("COL_VIII")) if len(candidates) == 1 else None

    fpi = [
        number(r.get("COL_VIII"))
        for r in public
        if (r.get("COL_I") or "").lower().startswith("foreign portfolio investors")
    ]
    promoter_total = next(
        r
        for r in bundles["promoter"]
        if (r.get("COL_I") or "").startswith("Total Shareholding of Promoter")
    )
    pledged = number(promoter_total.get("COL_XIX"))
    encumbered = number(promoter_total.get("COL_XIII_A"))
    promoter_shares = number(prom.get("COL_VII"))
    total_shares = number(total.get("COL_VII"))

    def ratio(count: float | None, base: float | None) -> float | None:
        return (
            count / base * 100
            if count is not None and base is not None and base > 0
            else 0
            if count == 0 and base == 0
            else None
        )

    return {
        "Promoter_Holding": number(prom.get("COL_VIII")),
        "FII_Holding": sum(v for v in fpi if v is not None)
        if fpi and all(v is not None for v in fpi)
        else None,
        "DII_Holding": lookup(lambda s: s == "sub-total (b)(1)"),
        "Retail_Holding": lookup(
            lambda s: s.startswith("resident individuals holding nominal share capital up to")
        ),
        "Public_Holding": number(next(r for r in summary if r.get("COL_I") == "B").get("COL_VIII")),
        "Number_of_Shareholders": number(total.get("COL_III")),
        "Promoter_Pledge": ratio(pledged, promoter_shares),
        "Promoter_Encumbrance": ratio(encumbered, promoter_shares),
        "Encumbrance_Total_Capital": ratio(encumbered, total_shares),
    }, ";".join(urls)


REQUESTED_FIELDS = [
    "Symbol",
    "Company",
    "Sector",
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


def attach_ownership(row: dict[str, Any], filings: list[dict[str, Any]]) -> None:
    if row["Symbol"] == "MCX" and (CACHE / "mcx/2026-06-30.md").exists():
        mcx_ownership(row)
        return
    entries = sorted(
        [e for e in filings if e["symbol"] == row["Symbol"]],
        key=lambda e: filing_date(e["date"]),
        reverse=True,
    )
    if not entries:
        row["Data_Notes"] = "NSE filing unavailable"
        return
    current = filing_date(entries[0]["date"])
    periods = {}
    source_urls = {}
    auxiliary = []
    for entry in entries:
        period = filing_date(entry["date"])
        path = CACHE / "nse_xbrl" / f"{safe(row['Symbol'])}_{period}.xml.gz"
        if path.exists():
            periods[period] = xbrl_row(path)
            source_urls[period] = entry["xbrl"]
        else:
            periods[period], source_urls[period] = nse_json_row(entry)
            auxiliary.append(source_urls[period])
        if periods[period].get("Retail_Holding") is None:
            fallback, urls = nse_json_row(entry)
            if fallback.get("Retail_Holding") is not None:
                periods[period]["Retail_Holding"] = fallback["Retail_Holding"]
                auxiliary.append(urls)
    if current not in periods:
        row["Data_Notes"] = "Latest NSE XBRL unavailable"
        return
    row.update({k: v for k, v in periods[current].items() if not k.startswith("_")})
    row["Shareholding_Period"] = current.isoformat()
    row["Shareholding_QoQ_Period"] = prior_quarter(current).isoformat()
    row["Shareholding_YoY_Period"] = current.replace(year=current.year - 1).isoformat()
    row["Shareholding_Source_URL"] = source_urls[current]
    row["Ownership_Source"] = "NSE_XBRL_with_JSON_fallback" if auxiliary else "NSE_XBRL"
    row["Ownership_Auxiliary_Source_URLs"] = ";".join(auxiliary)
    for suffix, period in [
        ("QoQ", prior_quarter(current)),
        ("YoY", current.replace(year=current.year - 1)),
    ]:
        row[f"Shareholding_{suffix}_Source_URL"] = source_urls.get(period, "")
        for prefix in ["Promoter", "FII", "DII", "Retail"]:
            now = row.get(prefix + "_Holding")
            old = periods.get(period, {}).get(prefix + "_Holding")
            row[prefix + "_" + suffix] = (
                round(now - old, 4) if now is not None and old is not None else None
            )
    row["SEBI_Encumbrance_Disclosure_Review"] = (
        "Threshold_reached_review_disclosure"
        if row.get("Promoter_Encumbrance") is not None
        and (row["Promoter_Encumbrance"] >= 50 or (row.get("Encumbrance_Total_Capital") or 0) >= 20)
        else "Below_threshold"
        if row.get("Promoter_Encumbrance") is not None
        else "Unknown"
    )


def grade_high(value: float | None, strong: float, moderate: float) -> str:
    if value is None:
        return "Missing"
    return "Strong" if value >= strong else "Moderate" if value >= moderate else "Weak"


def grade_low(value: float | None, strong: float, moderate: float) -> str:
    if value is None:
        return "Missing"
    return (
        "Strong" if 0 <= value <= strong else "Moderate" if strong < value <= moderate else "Weak"
    )


def fundamental_label(score: float) -> str:
    """Map the final, risk-capped score to non-overlapping published bands."""
    if not 0 <= score <= 100:
        raise ValueError("Fundamental score must be between 0 and 100")
    if score >= 90:
        return "Very Strong"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Weak"
    return "Very Weak"


def classify(row: dict[str, Any], all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    contextual = context_model.assess(row, all_rows)
    dimensions = contextual["dimensions"]
    regulated = row.get("Business_Type") == "Regulated_Financial"
    assessments = {
        key: {"class": "Informational", "weight": 0, "value": row.get(key)}
        for key in REQUESTED_FIELDS
    }
    for key, dimension in {
        "Debt_Equity": "Leverage",
        "OPM": "Operating_Performance",
        "ROCE": "Capital_Efficiency",
        "Promoter_Pledge": "Ownership_Risk",
        "Promoter_YoY": "Ownership_Risk",
    }.items():
        assessments[key]["class"] = (
            "Not_applicable_to_financial_business"
            if regulated and key in {"Debt_Equity", "OPM", "ROCE"}
            else dimensions.get(dimension, "Missing")
        )
    assessments["PE"]["class"] = contextual["valuation"]
    for dimension, grade in dimensions.items():
        assessments["Context_" + dimension] = {
            "class": grade,
            "weight": context_model.DIMENSION_WEIGHTS.get(dimension, 0) if not regulated else 0,
            "value": None,
            "component_score": contextual.get("component_scores", {}).get(dimension),
        }
    for key in REQUESTED_FIELDS:
        if row.get(key) is None:
            assessments[key]["class"] = "Missing_or_not_applicable"
    for prefix in ["Promoter", "FII", "DII", "Retail"]:
        for suffix in ["QoQ", "YoY"]:
            key = prefix + "_" + suffix
            val = row.get(key)
            assessments[key]["class"] = (
                "Missing"
                if val is None
                else "Increased"
                if val > 0
                else "Decreased"
                if val < 0
                else "Unchanged"
            )
    score, raw = contextual["score"], contextual["raw_score"]
    caps = []
    if score is not None and raw is not None and score < raw:
        caps.append({"maximum": score, "reason": contextual["profile"]})
    reasons = contextual["reasons"] + contextual["limits"]
    row.update(
        {
            "Fundamental": contextual["label"],
            "Fundamental_Score": score,
            "Fundamental_Raw_Score": raw,
            "Fundamental_Score_Caps": caps,
            "Classification_Model_Version": "3.0",
            "Eligibility_Profile": contextual["profile"],
            "Context_Assessments": dimensions,
            "Context_Component_Scores": contextual.get("component_scores", {}),
            "Valuation_Assessment": contextual["valuation"],
            "Assessment_Limits": contextual["limits"],
            "Classification_Status": "Limited_financial_sector_assessment"
            if regulated
            else "Contextual_assessment_with_limits"
            if contextual["limits"]
            else "Contextual_assessment",
            "Classification_Reasons": "; ".join(reasons)
            or "Profits, cash generation, growth/stability and leverage assessed together",
            "Peer_Group": "Industry:" + row.get("Industry", ""),
            "Peer_PE_Median": contextual.get("peer_pe"),
            "Peer_OPM_Median": contextual.get("peer_opm"),
            "PE_Assessment": contextual["valuation"],
            "Debt_Equity_Assessment": assessments["Debt_Equity"]["class"],
            "OPM_Assessment": assessments["OPM"]["class"],
            "ROCE_Assessment": assessments["ROCE"]["class"],
            "Promoter_Pledge_Assessment": assessments["Promoter_Pledge"]["class"],
        }
    )
    return assessments


def build() -> None:
    rows = [screener_row(row) for row in universe()]
    filings = json.loads((CACHE / "nse_chosen_filings.json").read_text())
    for row in rows:
        attach_ownership(row, filings)
        missing = [key for key in REQUESTED_FIELDS if row.get(key) is None]
        row["Missing_Fields"] = ";".join(missing)
        notes = [row.get("Data_Notes", "")]
        if row.get("Financing_Margin") is not None and row.get("OPM") is None:
            notes.append(
                "OPM not applicable to financing presentation; Financing_Margin supplied separately"
            )
        if not row.get("ROCE_Period"):
            notes.append("ROCE headline period not specified by source; not scored for lenders")
        if row.get("PE") is None:
            notes.append("Positive P/E unavailable; see profitability screen")
        if row.get("_equity") is not None and row["_equity"] <= 0:
            notes.append("Debt_Equity undefined with nonpositive equity")
        if row.get("Promoter_YoY") is None:
            notes.append("Matching prior-year quarter filing unavailable")
        if row.get("Promoter_QoQ") is None:
            notes.append("Matching previous quarter filing unavailable")
        if row["Symbol"] == "VAML":
            notes.append(
                "Post-demerger debt/equity and TTM ROCE from issuer PDFs; "
                "pre-operation standalone ratios excluded. OPM retains Screener "
                "EBITDA-like convention, not issuer EBIT-margin convention"
            )
        row["Data_Notes"] = "; ".join(n for n in notes if n)
        if row.get("Number_of_Shareholders") is not None:
            row["Number_of_Shareholders"] = int(row["Number_of_Shareholders"])
    assessments = {row["Symbol"]: classify(row, rows) for row in rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"field_assessments_{AS_OF}.json").write_text(json.dumps(assessments, indent=2))
    (OUT / f"contextual_assessments_{AS_OF}.json").write_text(
        json.dumps(
            [
                {
                    "Symbol": row["Symbol"],
                    "Fundamental": row["Fundamental"],
                    "Fundamental_Score": row["Fundamental_Score"],
                    "Eligibility_Profile": row["Eligibility_Profile"],
                    "Context_Assessments": row["Context_Assessments"],
                    "Supporting_Metrics": row["_context_metrics"],
                    "Parent_Cash_Supplement": row.get("_core_cash_metrics"),
                    "Valuation_Assessment": row["Valuation_Assessment"],
                    "Reason": row["Classification_Reasons"],
                    "Assessment_Limits": row["Assessment_Limits"],
                }
                for row in rows
            ],
            indent=2,
        )
    )
    # Keep the deliverable limited to requested data and the actual quality score.
    # Sources, coverage, dates and explanatory metadata stay in parsed_snapshot.json.
    destination = OUT / f"nifty200_fundamentals_{AS_OF}.csv"
    with destination.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=REQUESTED_FIELDS + ["Fundamental", "Fundamental_Score"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()})
    (CACHE / "parsed_snapshot.json").write_text(json.dumps(rows, indent=2))
    from collections import Counter

    print(
        json.dumps(
            {
                "rows": len(rows),
                "ratings": dict(Counter(r["Fundamental"] for r in rows)),
                "missing": {k: sum(r.get(k) is None for r in rows) for k in REQUESTED_FIELDS},
                "output": str(destination),
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["acquire", "filings", "build"])
    parser.add_argument("--as-of", type=date.fromisoformat, default=AS_OF)
    parser.add_argument("--universe", type=Path, default=UNIVERSE_PATH)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    configure(args.as_of, ROOT / f"data/raw/fundamentals/{args.as_of}", args.output, args.universe)
    if args.stage == "acquire":
        acquire()
    elif args.stage == "filings":
        acquire_filings()
    else:
        build()
