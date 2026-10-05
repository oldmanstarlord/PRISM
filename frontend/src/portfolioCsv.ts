import type { PortfolioInputRow } from "./types";

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
    const symbol = columns[0].trim().toUpperCase();
    const value = columns[1].trim();
    if (!symbol || !value || !Number.isFinite(Number(value))) {
      throw new Error(`Row ${index + 2}: symbol and numeric value are required`);
    }
    return { symbol, value };
  });
}
