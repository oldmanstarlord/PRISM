import { describe, expect, it } from "vitest";

import {
  exportTransactionsToCsv,
  parsePortfolioCsv,
  parseTransactionCsv,
} from "./portfolioCsv";

describe("parsePortfolioCsv", () => {
  it("normalizes valid symbol,value rows", () => {
    expect(parsePortfolioCsv("symbol,value\n tcs , 2\nCASH,1000\n")).toEqual([
      { symbol: "TCS", value: "2" },
      { symbol: "CASH", value: "1000" },
    ]);
  });

  it("rejects an ambiguous header", () => {
    expect(() => parsePortfolioCsv("ticker,quantity\nTCS,2")).toThrow(
      "CSV header must be exactly: symbol,value",
    );
  });

  it("rejects formula injection cells starting with =", () => {
    expect(() => parsePortfolioCsv("symbol,value\nTCS,=cmd|' /C calc'!A0")).toThrow(
      "Prohibited formula cell",
    );
  });

  it("rejects formula injection cells starting with + or - or @", () => {
    expect(() => parsePortfolioCsv("symbol,value\n@SUM(A1),10")).toThrow(
      "Prohibited formula cell",
    );
  });
});

describe("parseTransactionCsv and exportTransactionsToCsv", () => {
  it("parses valid transaction CSV correctly", () => {
    const csv = `date,type,symbol,quantity,price,amount,fees,notes
2026-01-05,BUY,TCS,10,3200,32000,15,Initial buy
2026-01-10,DEPOSIT,,,,50000,,Funding
`;
    const res = parseTransactionCsv(csv);
    expect(res.errors).toHaveLength(0);
    expect(res.transactions).toHaveLength(2);
    expect(res.transactions[0].symbol).toBe("TCS");
    expect(res.transactions[0].quantity).toBe(10);
    expect(res.transactions[1].type).toBe("DEPOSIT");
  });

  it("atomically rejects entire batch if a formula injection is found", () => {
    const csv = `date,type,symbol,quantity,price,notes
2026-01-05,BUY,TCS,10,3200,Valid note
2026-01-06,BUY,INFY,5,1500,=1+1
`;
    const res = parseTransactionCsv(csv);
    expect(res.transactions).toHaveLength(0); // Atomic rollback: zero partial mutations
    expect(res.errors).toHaveLength(1);
    expect(res.errors[0]).toContain("formula cell");
  });

  it("escapes formula injection characters on CSV export", () => {
    const exported = exportTransactionsToCsv([
      {
        id: "tx-1",
        date: "2026-01-05",
        type: "BUY",
        symbol: "TCS",
        quantity: 10,
        price: 3200,
        notes: "=SUM(A1:B1)",
      },
    ]);
    expect(exported).toContain("'=SUM(A1:B1)");
  });
});
