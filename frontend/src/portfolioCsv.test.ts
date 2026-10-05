import { describe, expect, it } from "vitest";

import { parsePortfolioCsv } from "./portfolioCsv";

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
});
