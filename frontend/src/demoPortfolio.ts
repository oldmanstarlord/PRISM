import type { MstResponse } from "./types";

export interface DemoPortfolioRow {
  symbol: string;
  weightPercent: number;
}

export interface ValidatedDemoHolding {
  symbol: string;
  weight: number;
}

export interface DemoValidation {
  valid: boolean;
  holdings: ValidatedDemoHolding[];
  errors: string[];
  warnings: string[];
}

export function parseDemoPortfolioCsv(content: string): DemoPortfolioRow[] {
  const lines = content.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) throw new Error("The CSV is empty");
  const header = lines[0].split(",").map((value) => value.trim().toLowerCase());
  if (header.length !== 2 || header[0] !== "symbol" || header[1] !== "weight") {
    throw new Error("CSV header must be exactly: symbol,weight");
  }
  return lines.slice(1).map((line, index) => {
    const columns = line.split(",");
    if (columns.length !== 2) throw new Error(`Row ${index + 2}: expected symbol,weight`);
    const symbol = columns[0].trim().toUpperCase();
    const weightPercent = Number(columns[1].trim());
    if (!symbol || !Number.isFinite(weightPercent)) {
      throw new Error(`Row ${index + 2}: symbol and numeric weight are required`);
    }
    return { symbol, weightPercent };
  });
}

export function validateDemoPortfolio(
  rows: DemoPortfolioRow[],
  eligibleSymbols?: Set<string>,
): DemoValidation {
  const errors: string[] = [];
  const warnings: string[] = [];
  const aggregated = new Map<string, number>();
  for (const row of rows) {
    if (row.weightPercent <= 0) {
      errors.push(`${row.symbol || "Blank symbol"}: weight must be greater than zero`);
      continue;
    }
    aggregated.set(row.symbol, (aggregated.get(row.symbol) ?? 0) + row.weightPercent);
  }
  if (aggregated.size < rows.length) warnings.push("Duplicate symbols were combined");
  if (!aggregated.size) errors.push("At least one holding is required");
  const unsupported = eligibleSymbols
    ? [...aggregated.keys()].filter((symbol) => !eligibleSymbols.has(symbol))
    : [];
  if (unsupported.length) errors.push(`Not in the current MST universe: ${unsupported.sort().join(", ")}`);
  const total = [...aggregated.values()].reduce((sum, value) => sum + value, 0);
  if (Math.abs(total - 100) > 0.01) errors.push(`Weights must total 100%; received ${total.toFixed(2)}%`);
  const holdings = [...aggregated.entries()]
    .filter(([symbol]) => !eligibleSymbols || eligibleSymbols.has(symbol))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([symbol, weightPercent]) => ({ symbol, weight: weightPercent / 100 }));
  return { valid: errors.length === 0, holdings, errors, warnings };
}

export function portfolioMstEdges(
  holdings: ValidatedDemoHolding[],
  edges: MstResponse["edges"],
) {
  const symbols = new Set(holdings.map((holding) => holding.symbol));
  return edges
    .filter((edge) => symbols.has(edge.symbol_a) && symbols.has(edge.symbol_b))
    .sort((left, right) => right.correlation - left.correlation);
}
