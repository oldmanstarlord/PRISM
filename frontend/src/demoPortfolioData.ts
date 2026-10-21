import type { PortfolioHolding, TransactionRecord } from "./PortfolioManager";

const rows: Array<[string, string, string, number, number, string]> = [
  ["ICICIBANK", "ICICI Bank Ltd.", "Financial Services", 180, 1150, "2024-03-15"],
  ["HDFCBANK", "HDFC Bank Ltd.", "Financial Services", 250, 790, "2024-01-10"],
  ["SBIN", "State Bank of India", "Financial Services", 180, 780, "2023-11-20"],
  ["AXISBANK", "Axis Bank Ltd.", "Financial Services", 110, 1120, "2024-02-14"],
  ["KOTAKBANK", "Kotak Mahindra Bank Ltd.", "Financial Services", 220, 490, "2024-04-05"],
  ["BAJFINANCE", "Bajaj Finance Ltd.", "Financial Services", 110, 850, "2024-05-12"],
  ["TCS", "Tata Consultancy Services Ltd.", "Information Technology", 90, 2180, "2023-09-08"],
  ["INFY", "Infosys Ltd.", "Information Technology", 190, 995, "2023-12-01"],
  ["HCLTECH", "HCL Technologies Ltd.", "Information Technology", 110, 1260, "2024-01-25"],
  ["TECHM", "Tech Mahindra Ltd.", "Information Technology", 55, 1940, "2024-06-18"],
  ["WIPRO", "Wipro Ltd.", "Information Technology", 400, 215, "2024-02-28"],
  ["LT", "Larsen & Toubro Ltd.", "Construction", 70, 3150, "2023-10-15"],
  ["RELIANCE", "Reliance Industries Ltd.", "Oil Gas & Consumable Fuels", 180, 1290, "2024-07-02"],
  ["MARUTI", "Maruti Suzuki India Ltd.", "Automobile and Auto Components", 18, 9850, "2023-08-22"],
  ["TITAN", "Titan Company Ltd.", "Consumer Durables", 35, 4720, "2024-06-10"],
  ["HINDUNILVR", "Hindustan Unilever Ltd.", "Fast Moving Consumer Goods", 75, 2040, "2024-03-01"],
  ["SUNPHARMA", "Sun Pharmaceutical Industries Ltd.", "Healthcare", 80, 1490, "2023-11-05"],
  ["ITC", "ITC Ltd.", "Fast Moving Consumer Goods", 380, 235, "2024-01-18"],
];

export const DEFAULT_CURATED_HOLDINGS: PortfolioHolding[] = rows.map(
  ([symbol, companyName, sector, quantity, buyPrice, buyDate]) => ({
    id: `demo-${symbol.toLowerCase()}`,
    symbol,
    companyName,
    sector,
    quantity,
    buyPrice,
    buyDate,
    exchange: "NSE",
  }),
);

export const DEFAULT_CURATED_TRANSACTIONS: TransactionRecord[] = DEFAULT_CURATED_HOLDINGS.map(
  (holding, index) => ({
    id: `demo-transaction-${holding.symbol.toLowerCase()}`,
    type: "BUY",
    symbol: holding.symbol,
    quantity: holding.quantity,
    price: holding.buyPrice,
    date: holding.buyDate,
    timestamp: new Date(holding.buyDate).getTime() || Date.now() - (18 - index) * 86_400_000,
  }),
);
