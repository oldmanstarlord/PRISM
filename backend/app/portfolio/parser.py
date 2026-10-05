"""Input parsing, row validation, symbol resolution, and weight normalization."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import PriceDailyAdjusted, Security, SecurityAlias
from backend.app.portfolio.schemas import HoldingInput, RowValidationError

CASH_SYMBOLS = {"CASH", "INR", "CASH_INR"}


@dataclass
class ResolvedHolding:
    symbol: str
    security_id: UUID | None
    quantity: Decimal | None
    weight: Decimal
    as_of: date
    source: str
    notes: str | None = None


def parse_csv_holdings(csv_content: str) -> tuple[list[HoldingInput], list[RowValidationError]]:
    """Parse CSV text containing symbol, and quantity or weight.

    Row indices are 1-based (row 1 is the header if present, or first data row).
    Errors are captured on a per-row basis.
    """
    lines = csv_content.strip().splitlines()
    if not lines:
        return [], [RowValidationError(row=1, error="CSV content is empty")]

    # Detect delimiter
    sample = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    reader = csv.reader(lines, delimiter=delimiter)
    all_rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not all_rows:
        return [], [RowValidationError(row=1, error="CSV contains no data")]

    first_row = [c.strip().lower() for c in all_rows[0]]

    # Detect header
    symbol_col = -1
    qty_col = -1
    weight_col = -1

    for idx, col in enumerate(first_row):
        col_clean = col.replace(" ", "").replace("_", "")
        if col_clean in {"symbol", "ticker", "isin", "asset", "code", "security"}:
            symbol_col = idx
        elif col_clean in {"quantity", "qty", "shares", "units", "count"}:
            qty_col = idx
        elif col_clean in {"weight", "wt", "weightpct", "allocation", "pct", "percentage"}:
            weight_col = idx

    has_header = symbol_col != -1 or qty_col != -1 or weight_col != -1
    data_rows = all_rows[1:] if has_header else all_rows
    start_row_num = 2 if has_header else 1

    if not has_header:
        # Default assumption: col 0 is symbol, col 1 is qty or weight
        symbol_col = 0
        if len(all_rows[0]) > 1:
            try:
                val = float(all_rows[0][1].strip().replace("%", ""))
                if 0.0 <= val <= 1.0 or "%" in all_rows[0][1]:
                    weight_col = 1
                else:
                    qty_col = 1
            except ValueError:
                qty_col = 1

    holdings: list[HoldingInput] = []
    errors: list[RowValidationError] = []
    seen_symbols: set[str] = set()

    for idx, row in enumerate(data_rows, start=start_row_num):
        if not row or not any(cell.strip() for cell in row):
            continue

        if symbol_col >= len(row) or not row[symbol_col].strip():
            errors.append(
                RowValidationError(
                    row=idx,
                    field="symbol",
                    error="Symbol column is missing or blank",
                )
            )
            continue

        raw_sym = row[symbol_col].strip().upper()

        if raw_sym in seen_symbols:
            errors.append(
                RowValidationError(
                    row=idx,
                    symbol=raw_sym,
                    field="symbol",
                    error=f"Duplicate symbol '{raw_sym}' in input",
                )
            )
            continue
        seen_symbols.add(raw_sym)

        qty_val: float | None = None
        if qty_col != -1 and qty_col < len(row) and row[qty_col].strip():
            raw_qty = row[qty_col].strip().replace(",", "")
            try:
                qty_val = float(raw_qty)
                if qty_val < 0:
                    errors.append(
                        RowValidationError(
                            row=idx,
                            symbol=raw_sym,
                            field="quantity",
                            error=f"Quantity cannot be negative (got {qty_val})",
                        )
                    )
                    continue
            except ValueError:
                errors.append(
                    RowValidationError(
                        row=idx,
                        symbol=raw_sym,
                        field="quantity",
                        error=f"Non-numeric quantity '{raw_qty}'",
                    )
                )
                continue

        weight_val: float | None = None
        if weight_col != -1 and weight_col < len(row) and row[weight_col].strip():
            raw_wt = row[weight_col].strip().replace(",", "")
            is_pct = "%" in raw_wt
            raw_wt = raw_wt.replace("%", "")
            try:
                weight_val = float(raw_wt)
                if is_pct or weight_val > 1.0:
                    weight_val = weight_val / 100.0
                if weight_val < 0:
                    errors.append(
                        RowValidationError(
                            row=idx,
                            symbol=raw_sym,
                            field="weight",
                            error=f"Weight cannot be negative (got {weight_val})",
                        )
                    )
                    continue
            except ValueError:
                errors.append(
                    RowValidationError(
                        row=idx,
                        symbol=raw_sym,
                        field="weight",
                        error=f"Non-numeric weight '{raw_wt}'",
                    )
                )
                continue

        if qty_val is None and weight_val is None:
            errors.append(
                RowValidationError(
                    row=idx,
                    symbol=raw_sym,
                    field="quantity|weight",
                    error="Row must provide either quantity or weight",
                )
            )
            continue

        holdings.append(
            HoldingInput(
                symbol=raw_sym,
                quantity=qty_val,
                weight=weight_val,
            )
        )

    return holdings, errors


def resolve_symbols(
    session: Session, symbols: list[str], as_of: date
) -> tuple[dict[str, UUID | None], list[str]]:
    """Resolve a list of symbols to security IDs.

    Resolves against:
    1. Cash symbols (CASH, INR) -> None
    2. SecurityAlias.symbol (matching valid_from/valid_to for as_of)
    3. Security.isin
    4. Exact match on Security.ticker (if present) or SecurityAlias without date restriction
    """
    resolved: dict[str, UUID | None] = {}
    unresolved: list[str] = []

    clean_symbols = [s.strip().upper() for s in symbols]

    for sym in clean_symbols:
        if sym in CASH_SYMBOLS:
            resolved[sym] = None

    remaining = [s for s in clean_symbols if s not in resolved]
    if not remaining:
        return resolved, []

    # 1. Alias lookup valid at as_of
    alias_stmt = select(SecurityAlias.symbol, SecurityAlias.security_id).where(
        func.upper(SecurityAlias.symbol).in_(remaining),
        SecurityAlias.valid_from <= as_of,
        (SecurityAlias.valid_to.is_(None)) | (SecurityAlias.valid_to >= as_of),
    )
    for alias_sym, sec_id in session.execute(alias_stmt):
        resolved[alias_sym.upper()] = sec_id

    # 2. ISIN lookup
    remaining = [s for s in remaining if s not in resolved]
    if remaining:
        isin_stmt = select(Security.isin, Security.id).where(
            func.upper(Security.isin).in_(remaining)
        )
        for isin, sec_id in session.execute(isin_stmt):
            resolved[isin.upper()] = sec_id

    # 3. Fallback: Any alias match regardless of date (best effort for symbol resolution)
    remaining = [s for s in remaining if s not in resolved]
    if remaining:
        fallback_stmt = select(SecurityAlias.symbol, SecurityAlias.security_id).where(
            func.upper(SecurityAlias.symbol).in_(remaining)
        )
        for alias_sym, sec_id in session.execute(fallback_stmt):
            if alias_sym.upper() not in resolved:
                resolved[alias_sym.upper()] = sec_id

    remaining = [s for s in remaining if s not in resolved]
    unresolved.extend(remaining)

    return resolved, unresolved


def normalize_portfolio_holdings(
    session: Session,
    inputs: list[HoldingInput],
    as_of: date,
    source: str = "manual_entry",
) -> tuple[list[ResolvedHolding], list[RowValidationError], list[str]]:
    """Normalize input holdings, validate symbols, and construct weights summing to 1.0.

    Adheres to PORTFOLIO_MATH_SPEC.md:
    - Normalizes raw weights or derives weights from quantities using latest adjusted close.
    - Explicit CASH line: if weights < 1.0, residual allocated to CASH.
    """
    if not inputs:
        return [], [RowValidationError(row=1, error="No holdings provided")], []

    warnings: list[str] = []
    errors: list[RowValidationError] = []

    # Check duplicate symbols in input list
    seen: dict[str, int] = {}
    for idx, h in enumerate(inputs, start=1):
        sym = h.symbol.strip().upper()
        if sym in seen:
            errors.append(
                RowValidationError(
                    row=idx,
                    symbol=sym,
                    field="symbol",
                    error=f"Duplicate symbol '{sym}' (first seen at row {seen[sym]})",
                )
            )
        else:
            seen[sym] = idx

        if h.quantity is not None and h.quantity < 0:
            errors.append(
                RowValidationError(
                    row=idx,
                    symbol=sym,
                    field="quantity",
                    error=f"Negative quantity {h.quantity}",
                )
            )
        if h.weight is not None and h.weight < 0:
            errors.append(
                RowValidationError(
                    row=idx,
                    symbol=sym,
                    field="weight",
                    error=f"Negative weight {h.weight}",
                )
            )

    if errors:
        return [], errors, []

    # Symbol resolution
    sym_list = list(seen.keys())
    resolved_map, unresolved = resolve_symbols(session, sym_list, as_of)

    if unresolved:
        for sym in unresolved:
            row_idx = seen[sym]
            errors.append(
                RowValidationError(
                    row=row_idx,
                    symbol=sym,
                    field="symbol",
                    error=f"Unknown security symbol or ISIN '{sym}'",
                )
            )
        return [], errors, []

    # Determine input mode: weight-based if any holding has weight, otherwise quantity-based
    has_weights = any(h.weight is not None for h in inputs)

    holdings_out: list[ResolvedHolding] = []

    if has_weights:
        # Weight-based normalization
        total_raw_weight = Decimal("0")
        cash_holding: ResolvedHolding | None = None
        raw_items: list[tuple[HoldingInput, Decimal]] = []

        for h in inputs:
            sym = h.symbol.strip().upper()
            wt = Decimal(str(h.weight)) if h.weight is not None else Decimal("0")
            sec_id = resolved_map[sym]
            if sym in CASH_SYMBOLS:
                cash_holding = ResolvedHolding(
                    symbol="CASH",
                    security_id=None,
                    quantity=None,
                    weight=wt,
                    as_of=as_of,
                    source=source,
                    notes=h.notes,
                )
            else:
                total_raw_weight += wt
                raw_items.append((h, wt))

        if cash_holding is not None:
            total_raw_weight += cash_holding.weight

        if total_raw_weight <= Decimal("0"):
            return (
                [],
                [
                    RowValidationError(
                        row=1, error="Total portfolio weight must be strictly positive"
                    )
                ],
                [],
            )

        if total_raw_weight < Decimal("0.9999"):
            # Residual weight allocated to cash line per PORTFOLIO_MATH_SPEC
            residual = Decimal("1.0") - total_raw_weight
            warnings.append(
                f"Weights summed to {total_raw_weight:.4f}; "
                f"residual {residual:.4f} allocated to CASH"
            )
            if cash_holding is not None:
                cash_holding.weight += residual
            else:
                cash_holding = ResolvedHolding(
                    symbol="CASH",
                    security_id=None,
                    quantity=None,
                    weight=residual,
                    as_of=as_of,
                    source=source,
                    notes="Automatic cash drag allocation",
                )
            for h, wt in raw_items:
                holdings_out.append(
                    ResolvedHolding(
                        symbol=h.symbol.strip().upper(),
                        security_id=resolved_map[h.symbol.strip().upper()],
                        quantity=Decimal(str(h.quantity)) if h.quantity is not None else None,
                        weight=wt,
                        as_of=as_of,
                        source=source,
                        notes=h.notes,
                    )
                )
            holdings_out.append(cash_holding)
        else:
            # Rescale all weights so they sum strictly to 1.0
            scale = Decimal("1.0") / total_raw_weight
            for h, wt in raw_items:
                holdings_out.append(
                    ResolvedHolding(
                        symbol=h.symbol.strip().upper(),
                        security_id=resolved_map[h.symbol.strip().upper()],
                        quantity=Decimal(str(h.quantity)) if h.quantity is not None else None,
                        weight=wt * scale,
                        as_of=as_of,
                        source=source,
                        notes=h.notes,
                    )
                )
            if cash_holding is not None:
                cash_holding.weight *= scale
                holdings_out.append(cash_holding)
            elif abs(total_raw_weight - Decimal("1.0")) > Decimal("0.0001"):
                warnings.append(
                    f"Weights summed to {total_raw_weight:.4f}; rescaled by factor {scale:.6f}"
                )

    else:
        # Quantity-based valuation
        # Fetch latest adjusted price for each security on or before as_of
        market_values: list[tuple[HoldingInput, Decimal, Decimal | None]] = []
        total_val = Decimal("0")

        for h in inputs:
            sym = h.symbol.strip().upper()
            qty = Decimal(str(h.quantity)) if h.quantity is not None else Decimal("0")
            sec_id = resolved_map[sym]

            if sym in CASH_SYMBOLS:
                # Cash price is 1.0 INR
                val = qty
                total_val += val
                market_values.append((h, val, Decimal("1.0")))
            else:
                # Query latest price
                price_stmt = (
                    select(PriceDailyAdjusted.adjusted_close)
                    .where(
                        PriceDailyAdjusted.security_id == sec_id,
                        PriceDailyAdjusted.trade_date <= as_of,
                    )
                    .order_by(PriceDailyAdjusted.trade_date.desc())
                    .limit(1)
                )
                price = session.scalar(price_stmt)
                if price is None:
                    # Missing price warning or assumption: cannot value asset
                    errors.append(
                        RowValidationError(
                            row=seen[sym],
                            symbol=sym,
                            field="price",
                            error=f"No adjusted price available for '{sym}' on or before {as_of}",
                        )
                    )
                    continue

                price_dec = Decimal(str(price))
                val = qty * price_dec
                total_val += val
                market_values.append((h, val, price_dec))

        if errors:
            return [], errors, []

        if total_val <= Decimal("0"):
            return (
                [],
                [
                    RowValidationError(
                        row=1, error="Total portfolio valuation must be strictly positive"
                    )
                ],
                [],
            )

        for h, val, _ in market_values:
            sym = h.symbol.strip().upper()
            sec_id = resolved_map[sym]
            wt = val / total_val
            holdings_out.append(
                ResolvedHolding(
                    symbol="CASH" if sym in CASH_SYMBOLS else sym,
                    security_id=sec_id,
                    quantity=Decimal(str(h.quantity)) if h.quantity is not None else None,
                    weight=wt,
                    as_of=as_of,
                    source=source,
                    notes=h.notes,
                )
            )

    # Final normalization check: ensure sum is exactly 1.0 within numerical rounding
    sum_wt = sum(h.weight for h in holdings_out)
    if abs(sum_wt - Decimal("1.0")) > Decimal("0.00000001"):
        diff = Decimal("1.0") - sum_wt
        holdings_out[0].weight += diff

    return holdings_out, [], warnings
