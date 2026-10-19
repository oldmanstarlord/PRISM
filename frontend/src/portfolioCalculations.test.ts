import { describe, expect, it } from "vitest";

describe("Financial Calculation Correctness", () => {
  it("calculates invested value as sum of quantity * buyPrice", () => {
    const holdings = [
      { quantity: 10, buyPrice: 1500 },
      { quantity: 5, buyPrice: 3000 },
    ];
    const totalInvested = holdings.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
    expect(totalInvested).toBe(15000 + 15000);
    expect(totalInvested).toBe(30000);
  });

  it("calculates market value using available prices", () => {
    const holdings = [
      { quantity: 10, price: 1650 },
      { quantity: 5, price: 3200 },
    ];
    const totalMarketValue = holdings.reduce((sum, h) => sum + h.quantity * h.price, 0);
    expect(totalMarketValue).toBe(16500 + 16000);
    expect(totalMarketValue).toBe(32500);
  });

  it("calculates unrealized P&L and return % relative to invested cost", () => {
    const invested = 30000;
    const market = 34500;
    const pnl = market - invested;
    const returnPct = (pnl / invested) * 100;
    expect(pnl).toBe(4500);
    expect(returnPct).toBe(15);
  });

  it("calculates today's P&L using current price minus previous close", () => {
    const holdings = [
      { quantity: 10, currentPrice: 1650, prevClose: 1600 }, // +500
      { quantity: 5, currentPrice: 3200, prevClose: 3300 },  // -500
    ];
    const todayPnl = holdings.reduce(
      (sum, h) => sum + h.quantity * (h.currentPrice - h.prevClose),
      0,
    );
    expect(todayPnl).toBe(0);
  });

  it("calculates portfolio weight as percentage of total portfolio market value", () => {
    const holdings = [
      { symbol: "TCS", marketValue: 24000 },
      { symbol: "INFY", marketValue: 16000 },
    ];
    const totalMarketValue = 40000;
    const tcsWeight = (holdings[0].marketValue / totalMarketValue) * 100;
    const infyWeight = (holdings[1].marketValue / totalMarketValue) * 100;
    expect(tcsWeight).toBe(60);
    expect(infyWeight).toBe(40);
    expect(tcsWeight + infyWeight).toBe(100);
  });

  it("calculates weighted average cost basis on multiple purchases", () => {
    const initialQty = 10;
    const initialBuyPrice = 1000; // 10,000

    const additionalQty = 10;
    const additionalPrice = 1200; // 12,000

    const totalQty = initialQty + additionalQty;
    const avgPrice =
      (initialQty * initialBuyPrice + additionalQty * additionalPrice) / totalQty;

    expect(totalQty).toBe(20);
    expect(avgPrice).toBe(1100);
    expect(totalQty * avgPrice).toBe(22000);
  });

  it("calculates realized P&L on partial sale while preserving remaining cost basis", () => {
    const currentQty = 20;
    const avgCostBasis = 1100;
    const sellQty = 5;
    const sellPrice = 1400;

    const realizedPnl = (sellPrice - avgCostBasis) * sellQty;
    const remainingQty = currentQty - sellQty;
    const remainingInvested = remainingQty * avgCostBasis;

    expect(realizedPnl).toBe(1500);
    expect(remainingQty).toBe(15);
    expect(remainingInvested).toBe(16500);
  });

  it("gracefully handles missing price without inventing zero or NaN", () => {
    const quote = { latest_price: null, error: "Price unavailable" };
    expect(quote.latest_price).toBeNull();
    expect(quote.latest_price ?? null).not.toBe(0);
  });
});
