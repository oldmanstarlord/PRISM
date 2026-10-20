import type { PortfolioInputRow } from "./types";

const FORMULA_INJECTION_PREFIXES = ["=", "+", "-", "@", "\t", "\r"];

export interface CsvTransactionRow {
  id?: string;
  date: string;
  type: "BUY" | "SELL" | "DIVIDEND" | "DEPOSIT" | "WITHDRAWAL" | "FEES";
  symbol?: string;
  quantity?: number;
  price?: number;
  amount?: number;
  fees?: number;
  notes?: string;
}

export function checkFormulaInjection(value: string, rowIdx?: number): void {
  const trimmed = value.trim();
  if (
    FORMULA_INJECTION_PREFIXES.some(
      (p) => value.startsWith(p) || (trimmed.length > 0 && trimmed.startsWith(p))
    )
  ) {
    throw new Error(
      `Row ${rowIdx ?? "?"}: Prohibited formula cell '${value.slice(0, 10)}...' rejected to prevent spreadsheet formula injection.`
    );
  }
}

export function parsePortfolioCsv(content: string): PortfolioInputRow[] {
  const lines = content.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) throw new Error("The CSV is empty");
  const header = lines[0].split(",").map((value) => value.trim().toLowerCase());
  if (header.length !== 2 || header[0] !== "symbol" || header[1] !== "value") {
    throw new Error("CSV header must be exactly: symbol,value");
  }
  return lines.slice(1).map((line, index) => {
    if (line.includes('"')) throw new Error(`Row ${index + 2}: quoted CSV fields are not supported`);
    const columns = line.split(",");
    if (columns.length !== 2) throw new Error(`Row ${index + 2}: expected symbol,value`);
    
    checkFormulaInjection(columns[0], index + 2);
    checkFormulaInjection(columns[1], index + 2);

    const symbol = columns[0].trim().toUpperCase();
    const value = columns[1].trim();
    if (!symbol || !value || !Number.isFinite(Number(value))) {
      throw new Error(`Row ${index + 2}: symbol and numeric value are required`);
    }
    return { symbol, value };
  });
}

export function parseTransactionCsv(content: string): {
  transactions: CsvTransactionRow[];
  errors: string[];
} {
  const lines = content.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return { transactions: [], errors: ["The CSV file is empty."] };

  const rawHeaders = lines[0].split(",").map((h) => h.trim().toLowerCase().replace(" ", "_"));
  const headerMap: Record<string, number> = {};
  rawHeaders.forEach((h, idx) => {
    headerMap[h] = idx;
  });

  const dateIdx = headerMap["date"] ?? headerMap["trade_date"];
  const typeIdx = headerMap["type"] ?? headerMap["transaction_type"];
  if (dateIdx === undefined || typeIdx === undefined) {
    return {
      transactions: [],
      errors: ["CSV missing mandatory headers 'date' and 'type'."],
    };
  }

  const symIdx = headerMap["symbol"];
  const qtyIdx = headerMap["quantity"] ?? headerMap["qty"];
  const pxIdx = headerMap["price"];
  const amtIdx = headerMap["amount"] ?? headerMap["value"];
  const feeIdx = headerMap["fees"] ?? headerMap["fee"];
  const notesIdx = headerMap["notes"] ?? headerMap["description"];

  const transactions: CsvTransactionRow[] = [];
  const errors: string[] = [];

  const validTypes = new Set(["BUY", "SELL", "DIVIDEND", "DEPOSIT", "WITHDRAWAL", "FEES"]);

  lines.slice(1).forEach((line, rowIdx) => {
    const lineNum = rowIdx + 2;
    const parts = line.split(",").map((p) => p.trim());
    try {
      parts.forEach((p) => checkFormulaInjection(p, lineNum));

      const rawDate = parts[dateIdx] || "";
      if (!/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) {
        errors.push(`Row ${lineNum}: Invalid date format '${rawDate}'. Expected YYYY-MM-DD.`);
        return;
      }

      const rawType = (parts[typeIdx] || "").toUpperCase() as CsvTransactionRow["type"];
      if (!validTypes.has(rawType)) {
        errors.push(`Row ${lineNum}: Invalid transaction type '${rawType}'.`);
        return;
      }

      const symbol = symIdx !== undefined && parts[symIdx] ? parts[symIdx].toUpperCase() : undefined;
      const rawQty = qtyIdx !== undefined && parts[qtyIdx] ? parseFloat(parts[qtyIdx]) : undefined;
      const rawPx = pxIdx !== undefined && parts[pxIdx] ? parseFloat(parts[pxIdx]) : undefined;
      const rawAmt = amtIdx !== undefined && parts[amtIdx] ? parseFloat(parts[amtIdx]) : undefined;
      const rawFees = feeIdx !== undefined && parts[feeIdx] ? parseFloat(parts[feeIdx]) : 0;
      const rawNotes = notesIdx !== undefined && parts[notesIdx] ? parts[notesIdx] : undefined;

      if ((rawType === "BUY" || rawType === "SELL") && (!symbol || !rawQty || rawQty <= 0 || !rawPx || rawPx <= 0)) {
        errors.push(`Row ${lineNum}: ${rawType} requires valid symbol, positive quantity, and positive price.`);
        return;
      }

      transactions.push({
        date: rawDate,
        type: rawType,
        symbol,
        quantity: rawQty,
        price: rawPx,
        amount: rawAmt,
        fees: rawFees,
        notes: rawNotes,
      });
    } catch (err) {
      errors.push(err instanceof Error ? err.message : String(err));
    }
  });

  return { transactions: errors.length > 0 ? [] : transactions, errors };
}

export function exportTransactionsToCsv(
  transactions: {
    id: string;
    type: string;
    symbol?: string;
    quantity?: number;
    price?: number;
    amount?: number;
    fees?: number;
    date: string;
    notes?: string;
  }[]
): string {
  const headers = ["id", "trade_date", "transaction_type", "symbol", "quantity", "price", "amount", "fees", "notes"];
  const rows = transactions.map((tx) => {
    let cleanNotes = tx.notes ?? "";
    if (FORMULA_INJECTION_PREFIXES.some((p) => cleanNotes.startsWith(p))) {
      cleanNotes = `'${cleanNotes}`;
    }
    return [
      tx.id,
      tx.date,
      tx.type,
      tx.symbol ?? "",
      tx.quantity ?? "",
      tx.price ?? "",
      tx.amount ?? "",
      tx.fees ?? 0,
      cleanNotes,
    ].join(",");
  });

  return [headers.join(","), ...rows].join("\n");
}
