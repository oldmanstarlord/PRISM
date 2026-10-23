import { GuidedSteps, ReviewDetails } from "./GuidedReview";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { NewsIntelligencePanel } from "./NewsIntelligence";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  LinearProgress,
  Link as MuiLink,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { Link } from "react-router-dom";

import AppShell from "./AppShell";
import { fetchJson, fetchPortfolioDecisionAnalysis, postJson } from "./api";
import { useAuth } from "./authState";
import {
  DiversificationSection,
  PortfolioRiskSection,
  SectorExposureSection,
  StockRiskSection,
} from "./Phase2RiskSections";
import {
  HistoricalRiskTrackingSection,
  MstHoldingsInspector,
  StructuralMonitoringDashboard,
} from "./Phase3StructuralSections";
import { loadAlertThresholds } from "./methodologyRegistry";
import { CorrelationMstExplainer } from "./PrismExplainer";
import PortfolioMstGraph from "./PortfolioMstGraph";
import PortfolioSnapshotSection from "./PortfolioSnapshotSection";
import StockResearchNotes from "./StockResearchNotes";
import { AiInsightsTab } from "./AiInsightsTab";
import StockDecisionEngineTab from "./StockDecisionEngineTab";
import {
  exportJournalBackup,
  getNotesCountMap,
  importJournalBackup,
  saveDecision,
  syncLocalJournalToServer,
  type DecisionContextSnapshot,
  type DecisionType,
} from "./journalStorage";
import {
  exportTransactionsToCsv,
  parseTransactionCsv,
  type CsvTransactionRow,
} from "./portfolioCsv";
import type {
  BatchQuotesResponse,
  ComprehensiveRiskResponse,
  LiveQuote,
  PortfolioAnalysisResponse,
  PortfolioDecisionResponse,
  PortfolioHoldingAnalytics,
  PortfolioNewsSummary,
  PortfolioPerformancePoint,
  PortfolioStressInput,
  StockDecision,
  StructuralMonitoringSnapshot,
} from "./types";

/* ─── Security Universe from backend ─── */

interface SecurityInfo {
  id: string;
  isin: string;
  company_name: string;
  industry: string;
  symbol: string;
  latest_price: number | null;
  latest_trade_date: string | null;
}

/* ─── Holding & Transaction models ─── */

export interface PortfolioHolding {
  id: string;
  symbol: string;
  companyName: string;
  sector?: string;
  quantity: number;
  buyPrice: number;
  buyDate: string;
  exchange: string;
}

export interface TransactionRecord {
  id: string;
  type: "BUY" | "SELL";
  symbol: string;
  quantity: number;
  price: number;
  date: string;
  timestamp: number;
  realizedPnl?: number;
}

const LEGACY_DEMO_HOLDINGS: PortfolioHolding[] = [
  // Cluster 1: Financial Services & Banking (6 stocks)
  {
    id: "hold-icicibank",
    symbol: "ICICIBANK",
    companyName: "ICICI Bank Ltd.",
    sector: "Financial Services",
    quantity: 180,
    buyPrice: 1150.0,
    buyDate: "2024-03-15",
    exchange: "NSE",
  },
  {
    id: "hold-hdfcbank",
    symbol: "HDFCBANK",
    companyName: "HDFC Bank Ltd.",
    sector: "Financial Services",
    quantity: 250,
    buyPrice: 790.0,
    buyDate: "2024-01-10",
    exchange: "NSE",
  },
  {
    id: "hold-sbin",
    symbol: "SBIN",
    companyName: "State Bank of India",
    sector: "Financial Services",
    quantity: 180,
    buyPrice: 780.0,
    buyDate: "2023-11-20",
    exchange: "NSE",
  },
  {
    id: "hold-axisbank",
    symbol: "AXISBANK",
    companyName: "Axis Bank Ltd.",
    sector: "Financial Services",
    quantity: 110,
    buyPrice: 1120.0,
    buyDate: "2024-02-14",
    exchange: "NSE",
  },
  {
    id: "hold-kotakbank",
    symbol: "KOTAKBANK",
    companyName: "Kotak Mahindra Bank Ltd.",
    sector: "Financial Services",
    quantity: 220,
    buyPrice: 490.0,
    buyDate: "2024-04-05",
    exchange: "NSE",
  },
  {
    id: "hold-bajfinance",
    symbol: "BAJFINANCE",
    companyName: "Bajaj Finance Ltd.",
    sector: "Financial Services",
    quantity: 110,
    buyPrice: 850.0,
    buyDate: "2024-05-12",
    exchange: "NSE",
  },

  // Cluster 2: Information Technology (5 stocks)
  {
    id: "hold-tcs",
    symbol: "TCS",
    companyName: "Tata Consultancy Services Ltd.",
    sector: "Information Technology",
    quantity: 90,
    buyPrice: 2180.0,
    buyDate: "2023-09-08",
    exchange: "NSE",
  },
  {
    id: "hold-infy",
    symbol: "INFY",
    companyName: "Infosys Ltd.",
    sector: "Information Technology",
    quantity: 190,
    buyPrice: 995.0,
    buyDate: "2023-12-01",
    exchange: "NSE",
  },
  {
    id: "hold-hcltech",
    symbol: "HCLTECH",
    companyName: "HCL Technologies Ltd.",
    sector: "Information Technology",
    quantity: 110,
    buyPrice: 1260.0,
    buyDate: "2024-01-25",
    exchange: "NSE",
  },
  {
    id: "hold-techm",
    symbol: "TECHM",
    companyName: "Tech Mahindra Ltd.",
    sector: "Information Technology",
    quantity: 55,
    buyPrice: 1940.0,
    buyDate: "2024-06-18",
    exchange: "NSE",
  },
  {
    id: "hold-wipro",
    symbol: "WIPRO",
    companyName: "Wipro Ltd.",
    sector: "Information Technology",
    quantity: 400,
    buyPrice: 215.0,
    buyDate: "2024-02-28",
    exchange: "NSE",
  },

  // Cluster 3: Industrials, Auto, Consumer, Energy & Healthcare (7 stocks)
  {
    id: "hold-lt",
    symbol: "LT",
    companyName: "Larsen & Toubro Ltd.",
    sector: "Construction",
    quantity: 70,
    buyPrice: 3150.0,
    buyDate: "2023-10-15",
    exchange: "NSE",
  },
  {
    id: "hold-reliance",
    symbol: "RELIANCE",
    companyName: "Reliance Industries Ltd.",
    sector: "Oil Gas & Consumable Fuels",
    quantity: 180,
    buyPrice: 1290.0,
    buyDate: "2024-07-02",
    exchange: "NSE",
  },
  {
    id: "hold-maruti",
    symbol: "MARUTI",
    companyName: "Maruti Suzuki India Ltd.",
    sector: "Automobile and Auto Components",
    quantity: 18,
    buyPrice: 9850.0,
    buyDate: "2023-08-22",
    exchange: "NSE",
  },
  {
    id: "hold-titan",
    symbol: "TITAN",
    companyName: "Titan Company Ltd.",
    sector: "Consumer Durables",
    quantity: 35,
    buyPrice: 4720.0,
    buyDate: "2024-06-10",
    exchange: "NSE",
  },
  {
    id: "hold-hindunilvr",
    symbol: "HINDUNILVR",
    companyName: "Hindustan Unilever Ltd.",
    sector: "Fast Moving Consumer Goods",
    quantity: 75,
    buyPrice: 2040.0,
    buyDate: "2024-03-01",
    exchange: "NSE",
  },
  {
    id: "hold-sunpharma",
    symbol: "SUNPHARMA",
    companyName: "Sun Pharmaceutical Industries Ltd.",
    sector: "Healthcare",
    quantity: 80,
    buyPrice: 1490.0,
    buyDate: "2023-11-05",
    exchange: "NSE",
  },
  {
    id: "hold-itc",
    symbol: "ITC",
    companyName: "ITC Ltd.",
    sector: "Fast Moving Consumer Goods",
    quantity: 380,
    buyPrice: 235.0,
    buyDate: "2024-01-18",
    exchange: "NSE",
  },
];

// Keep the historical fixture available only to development builds. Rollup
// eliminates both this branch and the fixture from production output.
if (import.meta.env.DEV) void LEGACY_DEMO_HOLDINGS;

const STORAGE_KEY = "prism_portfolio_holdings";
const TX_STORAGE_KEY = "prism_portfolio_transactions";

function loadHoldings(): PortfolioHolding[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as PortfolioHolding[];
      if (Array.isArray(parsed)) return parsed;
    }
    return [];
  } catch {
    return [];
  }
}

function saveHoldings(holdings: PortfolioHolding[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings));
}

function loadTransactions(): TransactionRecord[] {
  try {
    const raw = localStorage.getItem(TX_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as TransactionRecord[];
      if (Array.isArray(parsed)) return parsed;
    }
    return [];
  } catch {
    return [];
  }
}

function saveTransactions(txns: TransactionRecord[]) {
  localStorage.setItem(TX_STORAGE_KEY, JSON.stringify(txns));
}

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function deriveHoldingsFromLedger(
  txns: TransactionRecord[],
  knownSecurities: SecurityInfo[] = []
): {
  holdings: PortfolioHolding[];
  cash: number;
  totalRealizedPnl: number;
  totalInvestedCost: number;
} {
  const sorted = [...txns].sort(
    (a, b) => a.date.localeCompare(b.date) || a.timestamp - b.timestamp
  );

  const posMap = new Map<
    string,
    { quantity: number; investedCost: number; buyDate: string }
  >();
  let cash = 1000000;
  let totalRealized = 0;

  for (const tx of sorted) {
    const sym = tx.symbol.toUpperCase();
    if (tx.type === "BUY") {
      const existing = posMap.get(sym) ?? {
        quantity: 0,
        investedCost: 0,
        buyDate: tx.date,
      };
      const newQty = existing.quantity + tx.quantity;
      const outlay = tx.quantity * tx.price;
      const newCost = existing.investedCost + outlay;
      posMap.set(sym, {
        quantity: newQty,
        investedCost: newCost,
        buyDate: tx.date,
      });
      cash -= outlay;
    } else if (tx.type === "SELL") {
      const existing = posMap.get(sym);
      if (existing && existing.quantity > 0) {
        const avgPx = existing.investedCost / existing.quantity;
        const soldQty = Math.min(tx.quantity, existing.quantity);
        const costBasisSold = soldQty * avgPx;
        const proceeds = soldQty * tx.price;
        const pnl = proceeds - costBasisSold;
        totalRealized += pnl;
        cash += proceeds;
        const remainingQty = existing.quantity - soldQty;
        const remainingCost = existing.investedCost - costBasisSold;
        if (remainingQty > 0) {
          posMap.set(sym, {
            quantity: remainingQty,
            investedCost: remainingCost,
            buyDate: existing.buyDate,
          });
        } else {
          posMap.delete(sym);
        }
      }
    }
  }

  const derivedHoldings: PortfolioHolding[] = [];
  let totalInvestedCost = 0;
  for (const [sym, pos] of posMap.entries()) {
    if (pos.quantity > 0) {
      const sec = knownSecurities.find((s) => s.symbol.toUpperCase() === sym);
      const buyPrice = Math.round((pos.investedCost / pos.quantity) * 100) / 100;
      totalInvestedCost += pos.investedCost;
      derivedHoldings.push({
        id: `derived-${sym}`,
        symbol: sym,
        companyName: sec?.company_name || sym,
        sector: sec?.industry,
        quantity: pos.quantity,
        buyPrice,
        buyDate: pos.buyDate,
        exchange: "NSE",
      });
    }
  }

  return {
    holdings: derivedHoldings,
    cash,
    totalRealizedPnl: Math.round(totalRealized * 100) / 100,
    totalInvestedCost,
  };
}

/* ─── Currency & Percent Formatting Helpers ─── */

function formatCurrency(val: number | null | undefined, maximumFractionDigits = 0): string {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `₹${val.toLocaleString("en-IN", {
    minimumFractionDigits: maximumFractionDigits === 0 ? 0 : 2,
    maximumFractionDigits,
  })}`;
}

function formatPercent(val: number | null | undefined, digits = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `${val >= 0 ? "+" : ""}${val.toFixed(digits)}%`;
}

function formatDecimal(val: number | null | undefined, digits = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return val.toFixed(digits);
}

/* ─── Risk scoring helpers ─── */

function riskScoreFromVolatility(vol: number): { score: number; label: string; color: string } {
  const annualVol = vol * 100;
  if (annualVol < 15) return { score: 1, label: "Low", color: "#046A38" };
  if (annualVol < 25) return { score: 2, label: "Moderate", color: "#8A5A00" };
  if (annualVol < 35) return { score: 3, label: "High", color: "#8A5A00" };
  return { score: 4, label: "Very High", color: "#B8321A" };
}

function portfolioRiskScore(holdings: PortfolioHoldingAnalytics[]): { score: number; label: string; color: string } {
  if (!holdings.length) return { score: 0, label: "N/A", color: "#686B64" };
  const weightedVol = holdings.reduce((sum, h) => sum + h.weight * h.annualized_volatility, 0);
  return riskScoreFromVolatility(weightedVol);
}

function diversityGrade(effectiveHoldings: number, effectiveIndustries: number, totalHoldings: number): { grade: string; label: string; color: string } {
  const holdingRatio = totalHoldings > 0 ? effectiveHoldings / totalHoldings : 0;
  if (holdingRatio > 0.75 && effectiveIndustries >= 3) return { grade: "A", label: "Well diversified", color: "#046A38" };
  if (holdingRatio > 0.5 && effectiveIndustries >= 2) return { grade: "B", label: "Moderately diversified", color: "#8A5A00" };
  if (holdingRatio > 0.3) return { grade: "C", label: "Concentrated", color: "#8A5A00" };
  return { grade: "D", label: "Highly concentrated", color: "#B8321A" };
}

const bandColor = { normal: "default", moderate: "warning", strong: "error", extreme: "error" } as const;

/* ─── Shared Layout ─── */

function Page({ children }: { children: ReactNode }) {
  return (
    <AppShell subtitle="Portfolio Risk & Explainability">
      {children}
    </AppShell>
  );
}

type SortField =
  | "symbol"
  | "sector"
  | "quantity"
  | "buyPrice"
  | "investedValue"
  | "currentPrice"
  | "marketValue"
  | "unrealizedPnl"
  | "unrealizedPnlPercent"
  | "weight"
  | "todayPnl";

type PortfolioTab =
  | "monitoring"
  | "dashboard"
  | "stock-decisions"
  | "stock-risk"
  | "portfolio-risk"
  | "sector-exposure"
  | "diversification"
  | "network"
  | "analysis"
  | "stress"
  | "news-preview"
  | "transactions"
  | "ai-insights";

const portfolioGroups: { label: string; description: string; tabs: { id: PortfolioTab; label: string }[] }[] = [
  { label: "Holdings", description: "Start with your holdings, then review your activity.", tabs: [{ id: "dashboard", label: "Overview" }, { id: "transactions", label: "Activity" }] },
  { label: "Review risk", description: "Review portfolio health and investigate individual risks.", tabs: [{ id: "monitoring", label: "Summary" }, { id: "stock-risk", label: "Company risk" }, { id: "portfolio-risk", label: "Portfolio risk" }, { id: "sector-exposure", label: "Sectors" }, { id: "diversification", label: "Diversification" }] },
  { label: "Research", description: "Explore the evidence behind your portfolio decisions.", tabs: [{ id: "network", label: "Portfolio network" }, { id: "analysis", label: "Performance" }, { id: "stress", label: "Stress testing" }, { id: "stock-decisions", label: "Decision review" }, { id: "ai-insights", label: "AI insights" }, { id: "news-preview", label: "News" }] },
];

/* ─── Main Portfolio Manager Component ─── */

export default function PortfolioManager() {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>(loadHoldings);
  const [transactions, setTransactions] = useState<TransactionRecord[]>(loadTransactions);
  const [securities, setSecurities] = useState<SecurityInfo[]>([]);
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({});
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [lastQuotesUpdated, setLastQuotesUpdated] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<PortfolioAnalysisResponse | null>(null);
  const [comprehensiveRisk, setComprehensiveRisk] = useState<ComprehensiveRiskResponse | null>(null);
  const [structuralMonitoring, setStructuralMonitoring] = useState<StructuralMonitoringSnapshot | null>(null);
  const [newsSummary, setNewsSummary] = useState<PortfolioNewsSummary | null>(null);
  const [decisionResponse, setDecisionResponse] = useState<PortfolioDecisionResponse | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [sellDialogOpen, setSellDialogOpen] = useState(false);
  const [editHolding, setEditHolding] = useState<PortfolioHolding | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const { session } = useAuth();
  const [serverPortfolioId, setServerPortfolioId] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<"idle" | "loading" | "saved" | "error">("idle");
  const [isPersistingTx, setIsPersistingTx] = useState(false);
  const [activeTab, setActiveTab] = useState<PortfolioTab>(() => {
    try {
      const saved = localStorage.getItem("prism_portfolio_active_tab");
      if (
        saved &&
        [
          "monitoring",
          "dashboard",
          "stock-decisions",
          "stock-risk",
          "portfolio-risk",
          "sector-exposure",
          "diversification",
          "network",
          "analysis",
          "stress",
          "news-preview",
          "transactions",
          "ai-insights",
        ].includes(saved)
      ) {
        return saved as PortfolioTab;
      }
    } catch {
      // fallback
    }
    return "dashboard";
  });

  const handleSelectTab = (tabId: typeof activeTab) => {
    setActiveTab(tabId);
    try {
      localStorage.setItem("prism_portfolio_active_tab", tabId);
    } catch {
      // ignore
    }
  };

  const [searchQuery, setSearchQuery] = useState("");
  const [sectorFilter, setSectorFilter] = useState("ALL");
  const [sortField, setSortField] = useState<SortField>("marketValue");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Research Notes & Decision Journal states
  const [notesCountMap, setNotesCountMap] = useState<Record<string, number>>({});
  const [selectedNotesStock, setSelectedNotesStock] = useState<{ symbol: string; companyName?: string } | null>(null);
  const [decisionTxRecord, setDecisionTxRecord] = useState<TransactionRecord | null>(null);
  const [txDecisionType, setTxDecisionType] = useState<DecisionType>("Buy");
  const [txDecisionDate, setTxDecisionDate] = useState(() => new Date().toISOString().substring(0, 10));
  const [txRationale, setTxRationale] = useState("");
  const [txTags, setTxTags] = useState<string[]>([]);
  const [txTagInput, setTxTagInput] = useState("");
  const [backupDialogOpen, setBackupDialogOpen] = useState(false);
  const [backupStatus, setBackupStatus] = useState<string | null>(null);

  // Phase 2: Transaction CSV import & ledger reconciliation states
  const [csvImportDialogOpen, setCsvImportDialogOpen] = useState(false);
  const [csvInputText, setCsvInputText] = useState("");
  const [csvPreview, setCsvPreview] = useState<CsvTransactionRow[]>([]);
  const [csvErrors, setCsvErrors] = useState<string[]>([]);

  const derivedLedger = useMemo(() => {
    return deriveHoldingsFromLedger(transactions, securities);
  }, [transactions, securities]);

  const reconciliation = useMemo(() => {
    const discrepancies: string[] = [];
    const displayedSyms = new Set(holdings.map((h) => h.symbol.toUpperCase()));
    const derivedSyms = new Set(derivedLedger.holdings.map((h) => h.symbol.toUpperCase()));

    for (const sym of derivedSyms) {
      if (!displayedSyms.has(sym)) {
        discrepancies.push(`Position in ledger but missing from display: ${sym}`);
      }
    }
    for (const sym of displayedSyms) {
      if (!derivedSyms.has(sym)) {
        discrepancies.push(`Position in display but missing from ledger: ${sym}`);
      }
    }

    for (const h of holdings) {
      const der = derivedLedger.holdings.find(
        (d) => d.symbol.toUpperCase() === h.symbol.toUpperCase()
      );
      if (der && Math.abs(der.quantity - h.quantity) > 0.001) {
        discrepancies.push(
          `Quantity mismatch for ${h.symbol}: Display (${h.quantity}) vs Ledger (${der.quantity})`
        );
      }
    }

    return {
      isReconciled: discrepancies.length === 0,
      discrepancies,
    };
  }, [holdings, derivedLedger]);

  function handlePreviewCsv(text: string) {
    if (!text.trim()) {
      setCsvPreview([]);
      setCsvErrors([]);
      return;
    }
    const res = parseTransactionCsv(text);
    setCsvPreview(res.transactions);
    setCsvErrors(res.errors);
  }

  async function commitCsvImport() {
    if (csvErrors.length > 0 || csvPreview.length === 0) return;
    const newTxns: TransactionRecord[] = csvPreview.map((c, i) => ({
      id: generateId(),
      type: c.type === "SELL" ? "SELL" : "BUY",
      symbol: (c.symbol || "UNKNOWN").toUpperCase(),
      quantity: c.quantity || 1,
      price: c.price || 0,
      date: c.date,
      timestamp: Date.now() + i,
    }));

    if (serverPortfolioId) {
      setIsPersistingTx(true);
      try {
        await postJson(`/portfolios/${serverPortfolioId}/transactions`, {
          transactions: newTxns.map((tx) => ({
            transaction_type: tx.type,
            symbol: tx.symbol,
            trade_date: tx.date,
            quantity: tx.quantity,
            price: tx.price,
            amount: tx.quantity * tx.price,
            fees: 0,
            notes: `CSV Import ${tx.type} ${tx.symbol}`,
            idempotency_key: tx.id,
          })),
        });
        setSyncStatus("saved");
      } catch {
        setIsPersistingTx(false);
        setSnackbar("Failed to persist CSV transactions to server. Import aborted.");
        return;
      }
      setIsPersistingTx(false);
    }

    const updatedTxns = [...newTxns, ...transactions];
    setTransactions(updatedTxns);
    saveTransactions(updatedTxns);

    // Derive holdings from new ledger
    const derived = deriveHoldingsFromLedger(updatedTxns, securities);
    setHoldings(derived.holdings);
    saveHoldings(derived.holdings);

    setSnackbar(
      `Imported ${newTxns.length} transactions into ledger; derived ${derived.holdings.length} active positions.`
    );
    setCsvInputText("");
    setCsvPreview([]);
    setCsvErrors([]);
    setAnalysis(null);
    void refreshQuotes(
      derived.holdings.map((h) => h.symbol),
      true
    );
  }

  function handleExportCsv() {
    const csvStr = exportTransactionsToCsv(
      transactions.map((tx) => ({
        id: tx.id,
        date: tx.date,
        type: tx.type,
        symbol: tx.symbol,
        quantity: tx.quantity,
        price: tx.price,
        amount: tx.quantity * tx.price,
        fees: 0,
      }))
    );
    const blob = new Blob([csvStr], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prism-portfolio-transactions-${new Date().toISOString().substring(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setSnackbar("Transactions exported to CSV with formula-injection escaping.");
  }

  const refreshNotesCountMap = useCallback(async () => {
    try {
      const counts = await getNotesCountMap();
      setNotesCountMap(counts);
    } catch {
      // Graceful fallback
    }
  }, []);

  useEffect(() => {
    void refreshNotesCountMap();
  }, [refreshNotesCountMap]);

  useEffect(() => { saveHoldings(holdings); }, [holdings]);
  useEffect(() => { saveTransactions(transactions); }, [transactions]);

  /* ─── Server-Side Persistence & Multi-User Isolation ─── */
  useEffect(() => {
    if (!session?.access_token) {
      setServerPortfolioId(null);
      setSyncStatus("idle");
      return;
    }

    let isMounted = true;
    setSyncStatus("loading");

    async function initializeUserPortfolio() {
      try {
        const controller = new AbortController();
        const ensurePayload = {
          name: "Primary Portfolio",
          input_mode: "quantities",
          initial_holdings: holdings.map((h) => ({
            symbol: h.symbol,
            quantity: h.quantity,
            buy_price: h.buyPrice,
            buy_date: h.buyDate,
          })),
        };

        const portfolioDetail = await postJson<{
          id: string;
          name: string;
          holdings: Array<{
            symbol: string;
            company_name: string;
            value: number;
          }>;
        }>("/portfolios/ensure-active", ensurePayload, controller.signal);

        if (!isMounted) return;
        setServerPortfolioId(portfolioDetail.id);

        // Fetch server-persisted transactions
        const serverTxs = await fetchJson<
          Array<{
            id: string;
            transaction_type: "BUY" | "SELL" | string;
            symbol: string | null;
            trade_date: string;
            quantity: number | null;
            price: number | null;
            amount: number;
            fees: number;
            realized_pnl: number | null;
            notes: string | null;
            idempotency_key: string | null;
            created_at: string;
          }>
        >(`/portfolios/${portfolioDetail.id}/transactions`, controller.signal);

        if (!isMounted) return;

        if (serverTxs && serverTxs.length > 0) {
          const mappedTxs: TransactionRecord[] = serverTxs.map((t) => ({
            id: t.id,
            type: t.transaction_type === "SELL" ? "SELL" : "BUY",
            symbol: t.symbol || "UNKNOWN",
            quantity: Number(t.quantity ?? 1),
            price: Number(t.price ?? 0),
            date: t.trade_date,
            timestamp: new Date(t.created_at).getTime(),
            realizedPnl: t.realized_pnl !== null ? Number(t.realized_pnl) : undefined,
          }));
          setTransactions(mappedTxs);
          const derived = deriveHoldingsFromLedger(mappedTxs, securities);
          if (derived.holdings.length > 0) {
            setHoldings(derived.holdings);
          }
        }

        void syncLocalJournalToServer().then(() => {
          if (isMounted) void refreshNotesCountMap();
        });

        setSyncStatus("saved");
      } catch (err) {
        if (!isMounted) return;
        console.warn("Portfolio server synchronization error:", err);
        setSyncStatus("error");
      }
    }

    void initializeUserPortfolio();
    return () => {
      isMounted = false;
    };
  }, [session?.access_token]);

  /* Fetch NIFTY 200 universe for autocomplete */
  useEffect(() => {
    const controller = new AbortController();
    fetchJson<SecurityInfo[]>("/securities", controller.signal)
      .then(setSecurities)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  /* Fetch batch quotes from backend yfinance service */
  const refreshQuotes = useCallback(async (symbolsList?: string[], forceRefresh = false) => {
    const symbols = symbolsList ?? holdings.map((h) => h.symbol);
    if (!symbols.length) return;
    setQuotesLoading(true);
    const controller = new AbortController();
    try {
      const res = await postJson<BatchQuotesResponse>(
        "/market-data/quotes",
        { symbols, force_refresh: forceRefresh },
        controller.signal,
      );
      setQuotes((prev) => ({ ...prev, ...res.quotes }));
      setLastQuotesUpdated(new Date().toLocaleTimeString("en-IN"));
    } catch {
      // Graceful fallback: UI displays available prices or fallback markers
    } finally {
      setQuotesLoading(false);
    }
  }, [holdings]);

  // Initial and holdings change quote fetching
  useEffect(() => {
    if (holdings.length > 0) {
      void refreshQuotes(holdings.map((h) => h.symbol));
    }
  }, [holdings.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const [autoRefreshQuotes, setAutoRefreshQuotes] = useState(true);
  const [refreshCountdown, setRefreshCountdown] = useState(20);

  // Dynamic live quote polling loop every 20 seconds
  useEffect(() => {
    if (!autoRefreshQuotes || holdings.length === 0) return;
    const interval = setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          void refreshQuotes(undefined, true);
          return 20;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [autoRefreshQuotes, holdings.length, refreshQuotes]);

  /* ─── Financial Calculations ─── */

  // 1. Total Invested Value: sum of (quantity * average buy price)
  const totalInvestedValue = useMemo(
    () => holdings.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0),
    [holdings],
  );

  // Computed holding data with live quote integration
  const enrichedHoldings = useMemo(() => {
    return holdings.map((h) => {
      const quote = quotes[h.symbol.toUpperCase()];
      const secInfo = securities.find((s) => s.symbol === h.symbol);
      const currentPrice = quote?.latest_price ?? secInfo?.latest_price ?? null;
      const prevClose = quote?.previous_close ?? null;
      const investedValue = h.quantity * h.buyPrice;

      // Current market value: quantity * latest available price
      const marketValue = currentPrice !== null ? h.quantity * currentPrice : null;

      // Unrealized P&L = Market Value - Cost Basis
      const unrealizedPnl = marketValue !== null ? marketValue - investedValue : null;

      // Unrealized Return % = (Unrealized P&L / Cost Basis) * 100
      const unrealizedPnlPercent =
        unrealizedPnl !== null && investedValue > 0 ? (unrealizedPnl / investedValue) * 100 : null;

      // Today's P&L = quantity * (currentPrice - prevClose)
      const todayPnl =
        currentPrice !== null && prevClose !== null ? h.quantity * (currentPrice - prevClose) : null;
      const todayChangePercent =
        currentPrice !== null && prevClose !== null && prevClose > 0
          ? ((currentPrice - prevClose) / prevClose) * 100
          : null;

      // Sector from quote, holding, or securities universe
      const sector = quote?.sector || secInfo?.industry || h.sector || "General";

      return {
        ...h,
        sector,
        currentPrice,
        prevClose,
        investedValue,
        marketValue,
        unrealizedPnl,
        unrealizedPnlPercent,
        todayPnl,
        todayChangePercent,
        quote,
      };
    });
  }, [holdings, quotes, securities]);

  // 2. Total Current Market Value
  const totalMarketValue = useMemo(() => {
    const hasAnyMarketValue = enrichedHoldings.some((h) => h.marketValue !== null);
    if (!hasAnyMarketValue) return null;
    return enrichedHoldings.reduce((sum, h) => sum + (h.marketValue ?? h.investedValue), 0);
  }, [enrichedHoldings]);

  // 3. Total Unrealized Profit/Loss
  const totalUnrealizedPnl = useMemo(() => {
    if (totalMarketValue === null) return null;
    return totalMarketValue - totalInvestedValue;
  }, [totalMarketValue, totalInvestedValue]);

  // 4. Total Return Percentage
  const totalReturnPercent = useMemo(() => {
    if (totalUnrealizedPnl === null || totalInvestedValue === 0) return null;
    return (totalUnrealizedPnl / totalInvestedValue) * 100;
  }, [totalUnrealizedPnl, totalInvestedValue]);

  // 5. Total Today's Profit/Loss
  const totalTodayPnl = useMemo(() => {
    const validHoldings = enrichedHoldings.filter((h) => h.todayPnl !== null);
    if (!validHoldings.length) return null;
    return validHoldings.reduce((sum, h) => sum + (h.todayPnl ?? 0), 0);
  }, [enrichedHoldings]);

  const totalTodayPercent = useMemo(() => {
    if (totalTodayPnl === null || totalMarketValue === null || totalMarketValue === 0) return null;
    const prevMarketValue = totalMarketValue - totalTodayPnl;
    if (prevMarketValue <= 0) return null;
    return (totalTodayPnl / prevMarketValue) * 100;
  }, [totalTodayPnl, totalMarketValue]);

  // 6. Portfolio Weights (as % of total portfolio market value)
  const holdingsWithWeights = useMemo(() => {
    const basisTotal = totalMarketValue && totalMarketValue > 0 ? totalMarketValue : totalInvestedValue;
    return enrichedHoldings.map((h) => {
      const val = h.marketValue !== null ? h.marketValue : h.investedValue;
      const weight = basisTotal > 0 ? (val / basisTotal) * 100 : 0;
      return { ...h, weight };
    });
  }, [enrichedHoldings, totalMarketValue, totalInvestedValue]);

  // Unique sectors for filter dropdown
  const uniqueSectors = useMemo(() => {
    const set = new Set<string>();
    enrichedHoldings.forEach((h) => set.add(h.sector));
    return Array.from(set).sort();
  }, [enrichedHoldings]);

  // Filtered and Sorted Holdings
  const displayedHoldings = useMemo(() => {
    return holdingsWithWeights
      .filter((h) => {
        if (sectorFilter !== "ALL" && h.sector !== sectorFilter) return false;
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return (
          h.symbol.toLowerCase().includes(q) ||
          h.companyName.toLowerCase().includes(q) ||
          h.sector.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        let diff = 0;
        switch (sortField) {
          case "symbol":
            diff = a.symbol.localeCompare(b.symbol);
            break;
          case "sector":
            diff = a.sector.localeCompare(b.sector);
            break;
          case "quantity":
            diff = a.quantity - b.quantity;
            break;
          case "buyPrice":
            diff = a.buyPrice - b.buyPrice;
            break;
          case "investedValue":
            diff = a.investedValue - b.investedValue;
            break;
          case "currentPrice":
            diff = (a.currentPrice ?? 0) - (b.currentPrice ?? 0);
            break;
          case "marketValue":
            diff = (a.marketValue ?? 0) - (b.marketValue ?? 0);
            break;
          case "unrealizedPnl":
            diff = (a.unrealizedPnl ?? 0) - (b.unrealizedPnl ?? 0);
            break;
          case "unrealizedPnlPercent":
            diff = (a.unrealizedPnlPercent ?? 0) - (b.unrealizedPnlPercent ?? 0);
            break;
          case "weight":
            diff = a.weight - b.weight;
            break;
          case "todayPnl":
            diff = (a.todayPnl ?? 0) - (b.todayPnl ?? 0);
            break;
        }
        return sortOrder === "asc" ? diff : -diff;
      });
  }, [holdingsWithWeights, sectorFilter, searchQuery, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  /* ─── Analyze Portfolio (MST, Diversification, Risk Factors) ─── */
  const holdingWeightsForAnalytics = useMemo(() => {
    const total = holdings.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
    if (total === 0) return [];
    return holdings.map((h) => ({
      symbol: h.symbol,
      weight: (h.quantity * h.buyPrice) / total,
    }));
  }, [holdings]);

  const runAnalysis = useCallback(async (stress?: PortfolioStressInput) => {
    if (!holdings.length) return;
    setAnalysisLoading(true);
    setError(null);
    const controller = new AbortController();
    try {
      const compPayload = {
        holdings: holdings.map((h) => ({
          symbol: h.symbol,
          companyName: h.companyName,
          sector: h.sector || "General",
          quantity: h.quantity,
          buyPrice: h.buyPrice,
          buyDate: h.buyDate,
          exchange: h.exchange || "NSE",
        })),
        thresholds: loadAlertThresholds(),
      };

      const [resPreview, resComp, resMonitoring, resNews] = await Promise.all([
        holdingWeightsForAnalytics.length > 0
          ? postJson<PortfolioAnalysisResponse>(
              "/portfolio-analysis/preview",
              { holdings: holdingWeightsForAnalytics, window: 250, stress: stress ?? null },
              controller.signal,
            ).catch(() => null)
          : Promise.resolve(null),
        postJson<ComprehensiveRiskResponse>(
          "/portfolio-analysis/comprehensive-risk",
          compPayload,
          controller.signal,
        ).catch(() => null),
        postJson<StructuralMonitoringSnapshot>(
          "/portfolio-analysis/structural-monitoring",
          compPayload,
          controller.signal,
        ).catch(() => null),
        postJson<PortfolioNewsSummary>(
          "/portfolio-analysis/news-signals",
          compPayload,
          controller.signal,
        ).catch(() => null),
      ]);

      if (resPreview) setAnalysis(resPreview);
      if (resComp) {
        setComprehensiveRisk(resComp);
        if (serverPortfolioId && resComp.portfolio_profile) {
          const profile = resComp.portfolio_profile;
          const topSec = profile.sector_exposure?.[0];
          const sortedHoldings = [...holdings].sort(
            (a, b) => b.quantity * b.buyPrice - a.quantity * a.buyPrice
          );
          const totalVal = holdings.reduce(
            (sum, h) => sum + h.quantity * h.buyPrice,
            0
          );
          const largestHolding = sortedHoldings[0];
          const largestWeight =
            totalVal > 0 && largestHolding
              ? (largestHolding.quantity * largestHolding.buyPrice) / totalVal
              : 0;

          void postJson(`/portfolios/${serverPortfolioId}/risk-history`, {
            valuation_date: new Date().toISOString().slice(0, 10),
            portfolio_risk_score: profile.portfolio_risk_score,
            portfolio_classification:
              profile.portfolio_classification || "Moderate",
            annualized_volatility: profile.annualized_volatility,
            downside_volatility: profile.downside_volatility,
            max_drawdown: profile.max_drawdown,
            diversification_score: profile.diversification_score,
            effective_holdings: profile.effective_holdings,
            top_sector: topSec?.sector || "Diversified",
            top_sector_weight: topSec?.weight ?? 0,
            largest_holding: largestHolding?.symbol || "N/A",
            largest_holding_weight: largestWeight,
            indicators_summary: {
              var_95: profile.var_historical_95,
              var_99: profile.var_historical_99,
              effective_sectors: profile.effective_sectors,
            },
            methodology_version: "1.0.0",
            data_cutoff: new Date().toISOString().slice(0, 10),
          }).catch((err) => {
            console.warn("Failed to persist risk history snapshot:", err);
          });
        }
      }
      if (resMonitoring) setStructuralMonitoring(resMonitoring);
      if (resNews) setNewsSummary(resNews);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to analyze portfolio");
    } finally {
      setAnalysisLoading(false);
    }
  }, [holdings, holdingWeightsForAnalytics]);

  // Automatically compute structural monitoring and risk metrics if holdings exist
  useEffect(() => {
    if (holdings.length > 0 && !structuralMonitoring) {
      void runAnalysis();
    }
  }, [holdings.length, structuralMonitoring, runAnalysis]);

  /* ─── Decision Engine analysis ─── */
  const runDecisionAnalysis = useCallback(async () => {
    if (!holdings.length) return;
    setDecisionLoading(true);
    setDecisionError(null);
    try {
      const totalVal = holdings.reduce(
        (sum, h) => sum + h.quantity * h.buyPrice,
        0
      );
      const reqHoldings = holdings.map((h) => ({
        symbol: h.symbol,
        company_name: h.companyName,
        sector: h.sector || "General",
        quantity: h.quantity,
        buy_price: h.buyPrice,
        weight: totalVal > 0 ? (h.quantity * h.buyPrice) / totalVal : 0,
      }));
      const res = await fetchPortfolioDecisionAnalysis(reqHoldings);
      setDecisionResponse(res);
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "Failed to analyze stock decisions");
    } finally {
      setDecisionLoading(false);
    }
  }, [holdings]);

  // Auto-fetch decisions whenever holdings exist (runs in background for all tabs)
  useEffect(() => {
    if (holdings.length > 0 && !decisionResponse && !decisionLoading) {
      void runDecisionAnalysis();
    }
  }, [holdings.length, decisionResponse, decisionLoading, runDecisionAnalysis]);

  const decisionMap = useMemo(() => {
    const map = new Map<string, StockDecision>();
    for (const d of decisionResponse?.decisions || []) {
      map.set(d.symbol.toUpperCase(), d);
    }
    return map;
  }, [decisionResponse]);

  /* ─── Add Holding (Multiple purchases weighted-average cost basis) ─── */
  async function addHolding(holding: Omit<PortfolioHolding, "id">) {
    const symbolNorm = holding.symbol.toUpperCase();
    const tradeDate = holding.buyDate || new Date().toISOString().slice(0, 10);
    const clientTxId = generateId();

    if (serverPortfolioId) {
      setIsPersistingTx(true);
      try {
        await postJson(`/portfolios/${serverPortfolioId}/transactions`, {
          transactions: [
            {
              transaction_type: "BUY",
              symbol: symbolNorm,
              trade_date: tradeDate,
              quantity: holding.quantity,
              price: holding.buyPrice,
              amount: holding.quantity * holding.buyPrice,
              fees: 0,
              notes: `Buy ${holding.quantity} @ ₹${holding.buyPrice}`,
              idempotency_key: clientTxId,
            },
          ],
        });
        setSyncStatus("saved");
      } catch {
        setIsPersistingTx(false);
        setSnackbar("Failed to record transaction on server. Action cancelled.");
        return;
      }
      setIsPersistingTx(false);
    }

    const existing = holdings.find((h) => h.symbol.toUpperCase() === symbolNorm);
    if (existing) {
      // Weighted average buy price calculation
      const totalQty = existing.quantity + holding.quantity;
      const totalCost = existing.quantity * existing.buyPrice + holding.quantity * holding.buyPrice;
      const avgPrice = totalCost / totalQty;
      setHoldings((prev) =>
        prev.map((h) =>
          h.id === existing.id
            ? { ...h, quantity: totalQty, buyPrice: Math.round(avgPrice * 100) / 100 }
            : h,
        ),
      );
    } else {
      setHoldings((prev) => [...prev, { ...holding, id: generateId() }]);
    }
    setTransactions((prev) => [
      {
        id: clientTxId,
        type: "BUY",
        symbol: symbolNorm,
        quantity: holding.quantity,
        price: holding.buyPrice,
        date: tradeDate,
        timestamp: Date.now(),
      },
      ...prev,
    ]);
    setSnackbar(`Bought ${holding.quantity} shares of ${symbolNorm} @ ₹${holding.buyPrice}`);
    setAnalysis(null);
    void refreshQuotes([symbolNorm]);
  }

  /* ─── Sell Holding (Partial or full sales with realized P&L) ─── */
  async function sellHolding(symbol: string, quantity: number, sellPrice: number) {
    const symbolNorm = symbol.toUpperCase();
    const existing = holdings.find((h) => h.symbol.toUpperCase() === symbolNorm);
    if (!existing) return;

    const realizedPnl = (sellPrice - existing.buyPrice) * quantity;
    const tradeDate = new Date().toISOString().slice(0, 10);
    const clientTxId = generateId();

    if (serverPortfolioId) {
      setIsPersistingTx(true);
      try {
        await postJson(`/portfolios/${serverPortfolioId}/transactions`, {
          transactions: [
            {
              transaction_type: "SELL",
              symbol: symbolNorm,
              trade_date: tradeDate,
              quantity,
              price: sellPrice,
              amount: quantity * sellPrice,
              fees: 0,
              notes: `Sell ${quantity} @ ₹${sellPrice}`,
              idempotency_key: clientTxId,
            },
          ],
        });
        setSyncStatus("saved");
      } catch {
        setIsPersistingTx(false);
        setSnackbar("Failed to record sell transaction on server. Action cancelled.");
        return;
      }
      setIsPersistingTx(false);
    }

    if (quantity >= existing.quantity) {
      setHoldings((prev) => prev.filter((h) => h.id !== existing.id));
    } else {
      setHoldings((prev) =>
        prev.map((h) =>
          h.id === existing.id ? { ...h, quantity: h.quantity - quantity } : h,
        ),
      );
    }

    setTransactions((prev) => [
      {
        id: clientTxId,
        type: "SELL",
        symbol: symbolNorm,
        quantity,
        price: sellPrice,
        date: tradeDate,
        timestamp: Date.now(),
        realizedPnl: Math.round(realizedPnl * 100) / 100,
      },
      ...prev,
    ]);
    setSnackbar(`Sold ${quantity} shares of ${symbolNorm} @ ₹${sellPrice}`);
    setAnalysis(null);
  }

  function removeHolding(id: string) {
    const h = holdings.find((item) => item.id === id);
    if (h && serverPortfolioId) {
      void postJson(`/portfolios/${serverPortfolioId}/transactions`, {
        transactions: [
          {
            transaction_type: "SELL",
            symbol: h.symbol.toUpperCase(),
            trade_date: new Date().toISOString().slice(0, 10),
            quantity: h.quantity,
            price: h.buyPrice,
            amount: h.quantity * h.buyPrice,
            fees: 0,
            notes: `Liquidate position ${h.symbol}`,
            idempotency_key: generateId(),
          },
        ],
      }).catch((err) => console.warn("Failed to record removal transaction on server:", err));
    }
    setHoldings((prev) => prev.filter((h) => h.id !== id));
    setAnalysis(null);
    setSnackbar("Holding removed");
  }

  function updateHolding(updated: PortfolioHolding) {
    setHoldings((prev) => prev.map((h) => (h.id === updated.id ? updated : h)));
    setAnalysis(null);
    setSnackbar("Holding updated");
    void refreshQuotes([updated.symbol.toUpperCase()]);
  }

  const pRisk = analysis ? portfolioRiskScore(analysis.holdings) : null;
  const dGrade = analysis
    ? diversityGrade(
        analysis.concentration.effective_holdings,
        analysis.concentration.effective_industries,
        analysis.holdings.length,
      )
    : null;

  const activeGroup = Math.max(0, portfolioGroups.findIndex(group => group.tabs.some(tab => tab.id === activeTab)));
  const selectView = (id: PortfolioTab) => {
    handleSelectTab(id);
    if (!["dashboard", "transactions", "ai-insights", "news-preview"].includes(id) && !structuralMonitoring && holdings.length > 0) void runAnalysis();
  };

  return (
    <Page>
      <Stack spacing={3}>
        {/* ─── Header Banner with NIFTY 50 Benchmark ─── */}
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{ justifyContent: "space-between", gap: 2, alignItems: { sm: "center" } }}
          className="no-print"
        >
          <Box>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
              <Typography variant="h1">
                My portfolio
              </Typography>
              {session?.user ? (
                <Chip
                  size="small"
                  label={
                    syncStatus === "loading" || isPersistingTx
                      ? "Saving..."
                      : syncStatus === "error"
                      ? "Could not save"
                      : "Saved to account"
                  }
                  color={syncStatus === "error" ? "error" : "success"}
                  variant="outlined"
                  sx={{ height: 20, fontSize: "0.875rem", borderRadius: 0, fontWeight: 600 }}
                />
              ) : (
                <Chip
                  size="small"
                  label="Saved on this device"
                  variant="outlined"
                  sx={{ height: 20, fontSize: "0.875rem", borderRadius: 0, fontWeight: 600 }}
                />
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.875rem" }}>
              {holdings.length} stock{holdings.length !== 1 ? "s" : ""} · Currency: <strong>INR (₹)</strong>
              {lastQuotesUpdated && ` · Market quotes updated at ${lastQuotesUpdated}`}
            </Typography>
          </Box>

          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
            <Button
              variant="contained"
              onClick={() => setAddDialogOpen(true)}
              sx={{
                borderRadius: 0,
                bgcolor: "#046A38",
                color: "#F9EBD7",
                fontWeight: 700,
                boxShadow: "0 3px 8px rgba(4,106,56,0.20)",
                "&:hover": { bgcolor: "#03532c" },
              }}
            >
              Add holding
            </Button>
            <Button
              onClick={() => setSellDialogOpen(true)}
              disabled={!holdings.length}
              sx={{
                borderRadius: 0,
                border: "none",
                bgcolor: "#E3D7C4",
                color: "#292D2A",
                fontWeight: 700,
                boxShadow: "0 3px 8px rgba(227,66,34,0.20)",
                "&:hover": { bgcolor: "#d8cabc" },
              }}
            >
              Record sale
            </Button>

          </Stack>
        </Stack>

        <ReviewDetails title="More portfolio actions"><Stack direction="row" sx={{ gap: 2, flexWrap: "wrap", alignItems: "center" }}>
            {import.meta.env.DEV && <ReviewDetails title="Demo data">
            <Tooltip title="DEMO fixture: load a synthetic 18-stock portfolio for local interface testing only">
              <Button
                size="small"
                onClick={() => {
                  void import("./demoPortfolioData").then(
                    ({ DEFAULT_CURATED_HOLDINGS, DEFAULT_CURATED_TRANSACTIONS }) => {
                      setHoldings(DEFAULT_CURATED_HOLDINGS);
                      setTransactions(DEFAULT_CURATED_TRANSACTIONS);
                      saveHoldings(DEFAULT_CURATED_HOLDINGS);
                      saveTransactions(DEFAULT_CURATED_TRANSACTIONS);
                      setAnalysis(null);
                      setStructuralMonitoring(null);
                      setComprehensiveRisk(null);
                      setSnackbar("Loaded DEMO fixture portfolio; not production data");
                      void refreshQuotes(DEFAULT_CURATED_HOLDINGS.map((h) => h.symbol), true);
                    },
                  );
                }}
                sx={{
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#E3D7C4",
                  color: "#292D2A",
                  fontWeight: 600,
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                  "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                }}
              >
                DEMO Portfolio
              </Button>
            </Tooltip>
            </ReviewDetails>}
            <Tooltip title="Refresh market prices">
              <span>
                <Button
                  size="small"
                  onClick={() => void refreshQuotes(undefined, true)}
                  disabled={quotesLoading || !holdings.length}
                  sx={{
                    borderRadius: 0,
                    border: "none",
                    bgcolor: "#E3D7C4",
                    color: "#292D2A",
                    fontWeight: 600,
                    boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                    "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                  }}
                >
                  {quotesLoading ? <CircularProgress size={16} sx={{ color: "#046A38" }} /> : "Refresh prices"}
                </Button>
              </span>
            </Tooltip>
            <Button
              variant="contained"
              onClick={() => void runAnalysis()}
              disabled={analysisLoading || !holdings.length}
              sx={{
                borderRadius: 0,
                bgcolor: "#046A38",
                color: "#F9EBD7",
                fontWeight: 700,
                boxShadow: "0 3px 8px rgba(4,106,56,0.20)",
                "&:hover": { bgcolor: "#03532c" },
              }}
            >
              {analysisLoading ? <CircularProgress size={20} sx={{ color: "#F9EBD7" }} /> : "Refresh analysis"}
            </Button>        </Stack></ReviewDetails>

        {error && <Alert severity="error">{error}</Alert>}

        <Box className="no-print">
          <GuidedSteps label="Portfolio review" steps={portfolioGroups.map(group => ({ label: group.label }))} activeStep={activeGroup} onChange={index => selectView(portfolioGroups[index].tabs[0].id)} />
          <Typography variant="body2" sx={{ mt: 2, mb: 1 }}>{portfolioGroups[activeGroup].description}</Typography>
          <Stack component="nav" aria-label={`${portfolioGroups[activeGroup].label} views`} direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
            {portfolioGroups[activeGroup].tabs.map(tab => <Button key={tab.id} onClick={() => selectView(tab.id)} aria-current={activeTab === tab.id ? "page" : undefined} sx={{ px: 2, color: activeTab === tab.id ? "#F9EBD7" : "text.primary", bgcolor: activeTab === tab.id ? "primary.main" : "transparent", "&:hover": { bgcolor: activeTab === tab.id ? "primary.dark" : "#E3D7C4" } }}>{tab.label}</Button>)}
          </Stack>
        </Box>

        {/* ═══════════════════════════════════════════════
            TAB 0: STRUCTURAL OVERVIEW & MONITORING
           ═══════════════════════════════════════════════ */}
        {activeTab === "monitoring" && (
          <StructuralMonitoringDashboard
            monitoring={structuralMonitoring}
            analysis={analysis}
            onRefresh={() => void runAnalysis()}
            portfolioId="default"
            financials={{
              marketValue: totalMarketValue && totalMarketValue > 0 ? totalMarketValue : null,
              investedCost: totalInvestedValue,
              cash: derivedLedger.cash,
              realizedPnl: derivedLedger.totalRealizedPnl,
              unrealizedPnl: totalUnrealizedPnl,
              returnPct: totalReturnPercent,
              volatility: analysis?.performance?.annualized_volatility,
              maxDrawdown: analysis?.performance?.max_drawdown,
              concentrationHhi: analysis?.concentration?.holding_hhi,
              dataFreshness: structuralMonitoring?.data_freshness,
              asOfDate: analysis?.envelope.data_cutoff,
              period: analysis
                ? `${analysis.envelope.lookback_start} to ${analysis.envelope.data_cutoff}`
                : undefined,
            }}
            newsSummary={newsSummary}
            onNavigateTab={(tab) => setActiveTab(tab as typeof activeTab)}
          />
        )}

        {/* ═══════════════════════════════════════════════
            TAB 1: HOLDINGS DASHBOARD
           ═══════════════════════════════════════════════ */}
        {activeTab === "dashboard" && !holdings.length && <Paper sx={{ p: { xs: 3, sm: 5 }, bgcolor: "#E3D7C4", boxShadow: "none" }}>
          <Typography variant="h2">Start with your first holding</Typography>
          <Typography sx={{ mt: 1, mb: 3, maxWidth: "55ch" }}>Record a company you own to see its value, track activity, and review portfolio risk.</Typography>
          <Button variant="contained" onClick={() => setAddDialogOpen(true)}>Add your first holding</Button>
        </Paper>}
        {activeTab === "dashboard" && holdings.length > 0 && (
          <>
            <ReviewDetails title="Price update settings">
              <Stack direction={{ xs: "column", sm: "row" }} sx={{ gap: 2, alignItems: { sm: "center" } }}>
                <Typography variant="body2">{autoRefreshQuotes ? `Prices refresh in ${refreshCountdown}s.` : "Automatic price updates are paused."} {lastQuotesUpdated && `Last update: ${lastQuotesUpdated}.`}</Typography>
                <Button onClick={() => setAutoRefreshQuotes(!autoRefreshQuotes)}>{autoRefreshQuotes ? "Pause updates" : "Resume updates"}</Button>
              </Stack>
            </ReviewDetails>

            {/* ─── 6 SUMMARY CARDS ─── */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
              {/* Card 1: Total Invested Value */}
              <Paper sx={{ p: 2.5, flex: "1 1 180px", minWidth: 160 }}>
                <Typography variant="overline" color="text.secondary">
                  Total Invested Value
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {formatCurrency(totalInvestedValue)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Weighted average cost basis
                </Typography>
              </Paper>

              {/* Card 2: Current Portfolio Market Value */}
              <Paper sx={{ p: 2.5, flex: "1 1 180px", minWidth: 160 }}>
                <Typography variant="overline" color="text.secondary">
                  Current Market Value
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {formatCurrency(totalMarketValue)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Live / latest closing valuation
                </Typography>
              </Paper>

              {/* Card 3: Total Unrealized Profit/Loss */}
              <Paper sx={{ p: 2.5, flex: "1 1 180px", minWidth: 160 }}>
                <Typography variant="overline" color="text.secondary">
                  Total Unrealized P&L
                </Typography>
                <Typography
                  variant="h5"
                  sx={{
                    fontWeight: 700,
                    color:
                      totalUnrealizedPnl === null
                        ? "inherit"
                        : totalUnrealizedPnl >= 0
                        ? "success.main"
                        : "error.main",
                  }}
                >
                  {totalUnrealizedPnl !== null
                    ? `${totalUnrealizedPnl >= 0 ? "+" : ""}${formatCurrency(totalUnrealizedPnl)}`
                    : "—"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Market value minus cost
                </Typography>
              </Paper>

              {/* Card 4: Total Return Percentage */}
              <Paper sx={{ p: 2.5, flex: "1 1 180px", minWidth: 160 }}>
                <Typography variant="overline" color="text.secondary">
                  Total Return
                </Typography>
                <Typography
                  variant="h5"
                  sx={{
                    fontWeight: 700,
                    color:
                      totalReturnPercent === null
                        ? "inherit"
                        : totalReturnPercent >= 0
                        ? "success.main"
                        : "error.main",
                  }}
                >
                  {formatPercent(totalReturnPercent)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Return relative to invested cost
                </Typography>
              </Paper>

              {/* Card 5: Today's Profit/Loss */}
              <Paper sx={{ p: 2.5, flex: "1 1 180px", minWidth: 160 }}>
                <Typography variant="overline" color="text.secondary">
                  Today's P&L
                </Typography>
                <Typography
                  variant="h5"
                  sx={{
                    fontWeight: 700,
                    color:
                      totalTodayPnl === null
                        ? "inherit"
                        : totalTodayPnl >= 0
                        ? "success.main"
                        : "error.main",
                  }}
                >
                  {totalTodayPnl !== null
                    ? `${totalTodayPnl >= 0 ? "+" : ""}${formatCurrency(totalTodayPnl)}`
                    : "—"}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color:
                      totalTodayPercent === null
                        ? "text.secondary"
                        : totalTodayPercent >= 0
                        ? "success.main"
                        : "error.main",
                    fontWeight: 600,
                  }}
                >
                  {totalTodayPercent !== null ? formatPercent(totalTodayPercent) : "—"} vs prev close
                </Typography>
              </Paper>

              {/* Card 6: Number of Holdings */}
              <Paper sx={{ p: 2.5, flex: "1 1 140px", minWidth: 140 }}>
                <Typography variant="overline" color="text.secondary">
                  Holdings
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {holdings.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {uniqueSectors.length} active sector{uniqueSectors.length !== 1 ? "s" : ""}
                </Typography>
              </Paper>

              {/* Card 7: PRISM Risk & Diversification Summary */}
              {comprehensiveRisk?.portfolio_profile && (
                <Paper
                  sx={{
                    p: 2.5,
                    flex: "1 1 180px",
                    minWidth: 180,
                    cursor: "pointer",
                    "&:hover": { bgcolor: "#E3D7C4" },
                  }}
                  onClick={() => setActiveTab("portfolio-risk")}
                >
                  <Typography variant="overline" color="text.secondary">
                    PRISM Risk Score
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <Typography variant="h5" sx={{ fontWeight: 700 }}>
                      {comprehensiveRisk.portfolio_profile.portfolio_risk_score.toFixed(0)}/100
                    </Typography>
                    <Chip
                      size="small"
                      label={comprehensiveRisk.portfolio_profile.portfolio_classification}
                      sx={{
                        bgcolor: `${comprehensiveRisk.portfolio_profile.portfolio_color}18`,
                        color: comprehensiveRisk.portfolio_profile.portfolio_color,
                        fontWeight: 700,
                        height: 22,
                      }}
                    />
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    Div Grade: {comprehensiveRisk.portfolio_profile.diversification_grade} · Click for Risk Tab
                  </Typography>
                </Paper>
              )}
            </Stack>



            {/* ─── Search & Filter Controls ─── */}
            <Paper sx={{ p: 2 }}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={2}
                sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}
              >
                <TextField
                  size="small"
                  placeholder="Search stock ticker, name, or sector..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  sx={{ minWidth: 280, flex: 1 }}
                />
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <FormControl size="small" sx={{ minWidth: 180 }}>
                    <InputLabel id="sector-filter-label">Sector Filter</InputLabel>
                    <Select
                      labelId="sector-filter-label"
                      label="Sector Filter"
                      value={sectorFilter}
                      onChange={(e) => setSectorFilter(e.target.value)}
                    >
                      <MenuItem value="ALL">All Sectors ({holdings.length})</MenuItem>
                      {uniqueSectors.map((s) => (
                        <MenuItem key={s} value={s}>
                          {s}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {searchQuery || sectorFilter !== "ALL" ? (
                    <Button
                      size="small"
                      onClick={() => {
                        setSearchQuery("");
                        setSectorFilter("ALL");
                      }}
                    >
                      Reset
                    </Button>
                  ) : null}
                </Stack>
              </Stack>
            </Paper>

            {/* ─── HOLDINGS TABLE ─── */}
            <Paper sx={{ p: 3 }}>
              <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                <Typography variant="h5">Your holdings</Typography>
                <Typography variant="body2" color="text.secondary">
                  Showing {displayedHoldings.length} of {holdings.length} position{holdings.length !== 1 ? "s" : ""}
                </Typography>
              </Stack>

              {!holdings.length ? (
                <Box sx={{ py: 6, textAlign: "center" }}>
                  <Typography color="text.secondary" gutterBottom>
                    No holdings in your portfolio yet. Add your first stock to get started.
                  </Typography>
                  <Button variant="contained" color="success" onClick={() => setAddDialogOpen(true)} sx={{ mt: 1 }}>
                    + Add Your First Stock
                  </Button>
                </Box>
              ) : (
                <Box sx={{ overflowX: "auto" }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        {/* Stock Symbol & Company */}
                        <TableCell>
                          <TableSortLabel
                            active={sortField === "symbol"}
                            direction={sortField === "symbol" ? sortOrder : "asc"}
                            onClick={() => handleSort("symbol")}
                          >
                            Stock & Ticker
                          </TableSortLabel>
                        </TableCell>

                        {/* Sector */}
                        <TableCell>
                          <TableSortLabel
                            active={sortField === "sector"}
                            direction={sortField === "sector" ? sortOrder : "asc"}
                            onClick={() => handleSort("sector")}
                          >
                            Sector
                          </TableSortLabel>
                        </TableCell>

                        {/* Decision Signal (HOLD / WAIT / SELL) */}
                        <TableCell align="center">
                          <TableSortLabel
                            active={false}
                            direction="asc"
                            onClick={() => handleSelectTab("stock-decisions")}
                          >
                            Decision Signal
                          </TableSortLabel>
                        </TableCell>

                        {/* Quantity */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "quantity"}
                            direction={sortField === "quantity" ? sortOrder : "desc"}
                            onClick={() => handleSort("quantity")}
                          >
                            Qty
                          </TableSortLabel>
                        </TableCell>

                        {/* Avg Purchase Price */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "buyPrice"}
                            direction={sortField === "buyPrice" ? sortOrder : "desc"}
                            onClick={() => handleSort("buyPrice")}
                          >
                            Avg Buy Price
                          </TableSortLabel>
                        </TableCell>

                        {/* Total Invested */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "investedValue"}
                            direction={sortField === "investedValue" ? sortOrder : "desc"}
                            onClick={() => handleSort("investedValue")}
                          >
                            Invested Value
                          </TableSortLabel>
                        </TableCell>

                        {/* Latest Available Price */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "currentPrice"}
                            direction={sortField === "currentPrice" ? sortOrder : "desc"}
                            onClick={() => handleSort("currentPrice")}
                          >
                            Latest Price
                          </TableSortLabel>
                        </TableCell>

                        {/* Current Market Value */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "marketValue"}
                            direction={sortField === "marketValue" ? sortOrder : "desc"}
                            onClick={() => handleSort("marketValue")}
                          >
                            Market Value
                          </TableSortLabel>
                        </TableCell>

                        {/* Unrealized P&L */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "unrealizedPnl"}
                            direction={sortField === "unrealizedPnl" ? sortOrder : "desc"}
                            onClick={() => handleSort("unrealizedPnl")}
                          >
                            Unrealized P&L
                          </TableSortLabel>
                        </TableCell>

                        {/* Return % */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "unrealizedPnlPercent"}
                            direction={sortField === "unrealizedPnlPercent" ? sortOrder : "desc"}
                            onClick={() => handleSort("unrealizedPnlPercent")}
                          >
                            Return %
                          </TableSortLabel>
                        </TableCell>

                        {/* Portfolio Weight */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "weight"}
                            direction={sortField === "weight" ? sortOrder : "desc"}
                            onClick={() => handleSort("weight")}
                          >
                            Weight
                          </TableSortLabel>
                        </TableCell>

                        {/* Today's P&L */}
                        <TableCell align="right">
                          <TableSortLabel
                            active={sortField === "todayPnl"}
                            direction={sortField === "todayPnl" ? sortOrder : "desc"}
                            onClick={() => handleSort("todayPnl")}
                          >
                            Today's P&L
                          </TableSortLabel>
                        </TableCell>

                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {displayedHoldings.map((h) => {
                        const isGain = h.unrealizedPnl !== null && h.unrealizedPnl >= 0;
                        const isTodayGain = h.todayPnl !== null && h.todayPnl >= 0;

                        return (
                          <TableRow key={h.id} hover>
                            {/* Stock & Navigation to Details */}
                            <TableCell>
                              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                                <MuiLink
                                  component={Link}
                                  to={`/companies/${h.symbol}`}
                                  sx={{ fontWeight: 700, color: "#046A38", textDecoration: "none" }}
                                >
                                  {h.symbol}
                                </MuiLink>
                                {notesCountMap[h.symbol.toUpperCase()] ? (
                                  <Tooltip title={`${notesCountMap[h.symbol.toUpperCase()]} research notes`}>
                                    <Chip
                                      size="small"
                                      label={`Notes: ${notesCountMap[h.symbol.toUpperCase()]}`}
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setSelectedNotesStock({ symbol: h.symbol, companyName: h.companyName });
                                      }}
                                      sx={{
                                        cursor: "pointer",
                                        height: 20,
                                        fontSize: "0.875rem",
                                        fontWeight: 700,
                                        bgcolor: "rgba(4, 106, 56, 0.12)",
                                        color: "#046A38",
                                        "&:hover": { bgcolor: "rgba(4, 106, 56, 0.2)" },
                                      }}
                                    />
                                  </Tooltip>
                                ) : null}
                                {newsSummary?.stock_signals?.find((s) => s.symbol.toUpperCase() === h.symbol.toUpperCase()) ? (
                                  (() => {
                                    const s = newsSummary.stock_signals.find((ns) => ns.symbol.toUpperCase() === h.symbol.toUpperCase())!;
                                    const isPos = s.sentiment_label === "positive";
                                    const isNeg = s.sentiment_label === "negative";
                                    return (
                                      <Tooltip title={`${s.news_volume_7d || s.news_volume_24h} news articles · Sentiment: ${s.sentiment_label.toUpperCase()} · Click to open News Intelligence`}>
                                        <Chip
                                          size="small"
                                          label={`News: ${s.news_volume_7d || s.news_volume_24h || 1} ${isPos ? "▲" : isNeg ? "▼" : "■"}`}
                                          onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setActiveTab("news-preview");
                                          }}
                                          sx={{
                                            cursor: "pointer",
                                            height: 20,
                                            borderRadius: 0,
                                            fontSize: "0.875rem",
                                            fontWeight: 700,
                                            bgcolor: isPos ? "#DCE9DE" : isNeg ? "#F6D9CC" : "#E3D7C4",
                                            color: isPos ? "#046A38" : isNeg ? "#B8321A" : "#292D2A",
                                            border: "none",
                                            "&:hover": { bgcolor: "#E3D7C4" },
                                          }}
                                        />
                                      </Tooltip>
                                    );
                                  })()
                                ) : null}
                                {(() => {
                                  const analyticsHolding = analysis?.holdings?.find(
                                    (ah) => ah.symbol.toUpperCase() === h.symbol.toUpperCase()
                                  );
                                  const isUnusual =
                                    analyticsHolding?.divergence_20d !== undefined &&
                                    analyticsHolding.divergence_20d !== null &&
                                    Math.abs(analyticsHolding.divergence_20d) >= 1.5;
                                  if (!isUnusual) return null;
                                  return (
                                    <Tooltip
                                      title={`Model estimate: Unusual sector divergence (${analyticsHolding.divergence_20d?.toFixed(1)}σ) detected. Click to inspect in AI Insights.`}
                                    >
                                      <Chip
                                        size="small"
                                        label="Model: Unusual"
                                        onClick={(e) => {
                                          e.preventDefault();
                                          e.stopPropagation();
                                          setActiveTab("ai-insights");
                                        }}
                                        sx={{
                                          cursor: "pointer",
                                          height: 20,
                                          borderRadius: 0,
                                          fontSize: "0.875rem",
                                          fontWeight: 700,
                                          bgcolor: "#F6D9CC",
                                          color: "#B8321A",
                                          border: "none",
                                          "&:hover": { bgcolor: "#ebc6b5" },
                                        }}
                                      />
                                    </Tooltip>
                                  );
                                })()}
                              </Stack>
                              <Typography variant="caption" sx={{ display: "block" }} color="text.secondary">
                                {h.companyName}
                              </Typography>
                            </TableCell>

                            {/* Sector */}
                            <TableCell>
                              <Chip size="small" label={h.sector} sx={{ fontSize: "0.875rem", borderRadius: 0, bgcolor: "#F9EBD7", color: "#292D2A", border: "none" }} />
                            </TableCell>

                            {/* Decision Flag (HOLD / WAIT & WATCH / SELL) */}
                            <TableCell align="center">
                              {decisionMap.get(h.symbol.toUpperCase()) ? (
                                (() => {
                                  const dec = decisionMap.get(h.symbol.toUpperCase())!;
                                  const isHold = dec.decision === "HOLD";
                                  const isSell = dec.decision === "SELL";
                                  const bg = isHold ? "#046A38" : isSell ? "#E34222" : "#8A5A00";

                                  return (
                                    <Tooltip
                                      title={
                                        <Box sx={{ p: 0.5 }}>
                                          <Typography variant="caption" sx={{ fontWeight: 800, display: "block" }}>
                                            {dec.decision} — Health: {dec.final_score.toFixed(1)}/100
                                          </Typography>
                                          <Typography variant="caption" sx={{ display: "block" }}>
                                            Fundamental: {dec.fundamental.fundamental_strength_score.toFixed(0)} | Sector: {dec.sector_strength.sector_strength_score.toFixed(0)} | News: {dec.news.news_score.toFixed(0)}
                                          </Typography>
                                          <Typography variant="caption" sx={{ color: "#E3D7C4", display: "block", mt: 0.5 }}>
                                            Click to view full 3-factor breakdown & analysis
                                          </Typography>
                                        </Box>
                                      }
                                      arrow
                                    >
                                      <Chip
                                        size="small"
                                        label={dec.decision}
                                        onClick={(e) => {
                                          e.preventDefault();
                                          e.stopPropagation();
                                          handleSelectTab("stock-decisions");
                                        }}
                                        sx={{
                                          cursor: "pointer",
                                          height: 24,
                                          borderRadius: 0,
                                          fontWeight: 800,
                                          fontSize: "0.875rem",
                                          bgcolor: bg,
                                          color: "#F9EBD7",
                                          boxShadow: "0 2px 6px rgba(0,0,0,0.18)",
                                          "&:hover": { opacity: 0.85 },
                                        }}
                                      />
                                    </Tooltip>
                                  );
                                })()
                              ) : decisionLoading ? (
                                <CircularProgress size={16} sx={{ color: "#046A38" }} />
                              ) : (
                                <Chip
                                  size="small"
                                  label="Analyze"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    handleSelectTab("stock-decisions");
                                  }}
                                  sx={{
                                    cursor: "pointer",
                                    height: 20,
                                    borderRadius: 0,
                                    fontSize: "0.875rem",
                                    bgcolor: "#E3D7C4",
                                  }}
                                />
                              )}
                            </TableCell>

                            {/* Qty */}
                            <TableCell align="right" sx={{ fontWeight: 600 }}>
                              {h.quantity}
                            </TableCell>

                            {/* Avg Buy Price */}
                            <TableCell align="right">
                              {formatCurrency(h.buyPrice, 2)}
                            </TableCell>

                            {/* Invested Value */}
                            <TableCell align="right" sx={{ fontWeight: 600 }}>
                              {formatCurrency(h.investedValue)}
                            </TableCell>

                            {/* Latest Price & Quote Quality Badge */}
                            <TableCell align="right">
                              {h.currentPrice !== null ? (
                                <Box>
                                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                    {formatCurrency(h.currentPrice, 2)}
                                  </Typography>
                                  <Tooltip
                                    title={
                                      h.quote?.data_quality === "fallback"
                                        ? `Database closing price (${h.quote.as_of})`
                                        : `Live quote via yfinance (${h.quote?.as_of?.slice(0, 19)})`
                                    }
                                  >
                                    <Chip
                                      size="small"
                                      label={h.quote?.data_quality === "fallback" ? "Close" : "Live"}
                                      color={h.quote?.data_quality === "fallback" ? "default" : "success"}
                                      sx={{ height: 16, fontSize: "0.875rem" }}
                                    />
                                  </Tooltip>
                                </Box>
                              ) : (
                                <Tooltip title={h.quote?.error || "Price currently unavailable"}>
                                  <Chip size="small" label="Unavailable" color="warning" sx={{ height: 18 }} />
                                </Tooltip>
                              )}
                            </TableCell>

                            {/* Current Market Value */}
                            <TableCell align="right" sx={{ fontWeight: 700 }}>
                              {h.marketValue !== null ? formatCurrency(h.marketValue) : "—"}
                            </TableCell>

                            {/* Unrealized P&L */}
                            <TableCell
                              align="right"
                              sx={{
                                fontWeight: 700,
                                color:
                                  h.unrealizedPnl === null
                                    ? "inherit"
                                    : isGain
                                    ? "success.main"
                                    : "error.main",
                              }}
                            >
                              {h.unrealizedPnl !== null
                                ? `${isGain ? "+" : ""}${formatCurrency(h.unrealizedPnl)}`
                                : "—"}
                            </TableCell>

                            {/* Return % */}
                            <TableCell
                              align="right"
                              sx={{
                                fontWeight: 700,
                                color:
                                  h.unrealizedPnlPercent === null
                                    ? "inherit"
                                    : isGain
                                    ? "success.main"
                                    : "error.main",
                              }}
                            >
                              {formatPercent(h.unrealizedPnlPercent)}
                            </TableCell>

                            {/* Portfolio Weight */}
                            <TableCell align="right">
                              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 1 }}>
                                <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: "JetBrains Mono, monospace" }}>
                                  {h.weight.toFixed(1)}%
                                </Typography>
                                <LinearProgress
                                  variant="determinate"
                                  value={Math.min(h.weight, 100)}
                                  sx={{ width: 40, height: 6, borderRadius: 0 }}
                                  color={h.weight > 30 ? "warning" : "primary"}
                                />
                              </Box>
                            </TableCell>

                            {/* Today's P&L */}
                            <TableCell
                              align="right"
                              sx={{
                                fontWeight: 600,
                                color:
                                  h.todayPnl === null
                                    ? "inherit"
                                    : isTodayGain
                                    ? "#046A38"
                                    : "#B8321A",
                              }}
                            >
                              {h.todayPnl !== null ? (
                                <Box>
                                  <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: "JetBrains Mono, monospace" }}>
                                    {isTodayGain ? "+" : ""}
                                    {formatCurrency(h.todayPnl)}
                                  </Typography>
                                  <Typography variant="caption" sx={{ fontSize: "0.875rem", fontFamily: "JetBrains Mono, monospace" }}>
                                    {formatPercent(h.todayChangePercent)}
                                  </Typography>
                                </Box>
                              ) : (
                                "—"
                              )}
                            </TableCell>

                            {/* Actions */}
                            <TableCell align="center">
                              <Stack direction="row" spacing={0.5} sx={{ justifyContent: "center" }}>
                                <Tooltip title="Research notes & thesis">
                                  <IconButton
                                    size="small"
                                    onClick={() => setSelectedNotesStock({ symbol: h.symbol, companyName: h.companyName })}
                                    sx={{ color: notesCountMap[h.symbol.toUpperCase()] ? "#046A38" : "#686B64", borderRadius: 0, fontSize: "0.875rem", fontWeight: 600 }}
                                  >
                                    Notes
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Edit holding">
                                  <IconButton size="small" onClick={() => setEditHolding(h)} sx={{ borderRadius: 0, fontSize: "0.875rem", fontWeight: 600 }}>
                                    Edit
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Remove holding">
                                  <IconButton size="small" onClick={() => removeHolding(h.id)} sx={{ borderRadius: 0, fontSize: "0.875rem", fontWeight: 600, color: "#B8321A" }}>
                                    Delete
                                  </IconButton>
                                </Tooltip>
                              </Stack>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </Paper>

            {/* ─── Sector Exposure Allocation Breakdown ─── */}
            {holdings.length > 1 && (
              <Paper sx={{ p: 3, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
                <Typography variant="h5" gutterBottom sx={{ fontWeight: 700, color: "#292D2A" }}>
                  Sector Allocation & Weight Distribution
                </Typography>
                <Stack spacing={2} sx={{ mt: 1 }}>
                  {uniqueSectors.map((sec) => {
                    const sectorHoldings = holdingsWithWeights.filter((h) => h.sector === sec);
                    const sectorWeight = sectorHoldings.reduce((sum, h) => sum + h.weight, 0);
                    const sectorValue = sectorHoldings.reduce(
                      (sum, h) => sum + (h.marketValue ?? h.investedValue),
                      0,
                    );
                    return (
                      <Box key={sec}>
                        <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600, color: "#292D2A" }}>
                            {sec} ({sectorHoldings.map((h) => h.symbol).join(", ")})
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: "#046A38", fontFamily: "JetBrains Mono, monospace" }}>
                            {formatCurrency(sectorValue)} · {sectorWeight.toFixed(1)}%
                          </Typography>
                        </Stack>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(sectorWeight, 100)}
                          sx={{ height: 8, borderRadius: 0 }}
                          color={sectorWeight > 40 ? "warning" : "primary"}
                        />
                      </Box>
                    );
                  })}
                </Stack>
              </Paper>
            )}
          </>
        )}

        {/* ═══════════════════════════════════════════════
            TAB: STOCK RISK ANALYSIS
           ═══════════════════════════════════════════════ */}
        {activeTab === "stock-risk" && (
          <StockRiskSection
            comprehensiveRisk={comprehensiveRisk}
            loading={analysisLoading}
            onRefresh={() => void runAnalysis()}
            decisionMap={decisionMap}
            onSelectTab={handleSelectTab}
          />
        )}

        {/* ═══════════════════════════════════════════════
            TAB: PORTFOLIO RISK & HISTORY
           ═══════════════════════════════════════════════ */}
        {activeTab === "portfolio-risk" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <PortfolioRiskSection
              comprehensiveRisk={comprehensiveRisk}
              analysis={analysis}
              loading={analysisLoading}
              onRefresh={() => void runAnalysis()}
            />
            <HistoricalRiskTrackingSection monitoring={structuralMonitoring} />
            <PortfolioSnapshotSection
              analysis={analysis}
              comprehensiveRisk={comprehensiveRisk}
              monitoring={structuralMonitoring}
              holdings={holdings}
              totalInvested={totalInvestedValue}
            />
          </Box>
        )}

        {/* ═══════════════════════════════════════════════
            TAB: SECTOR EXPOSURE
           ═══════════════════════════════════════════════ */}
        {activeTab === "sector-exposure" && (
          <SectorExposureSection
            comprehensiveRisk={comprehensiveRisk}
            loading={analysisLoading}
            onRefresh={() => void runAnalysis()}
          />
        )}

        {/* ═══════════════════════════════════════════════
            TAB: DIVERSIFICATION
           ═══════════════════════════════════════════════ */}
        {activeTab === "diversification" && (
          <DiversificationSection
            comprehensiveRisk={comprehensiveRisk}
            loading={analysisLoading}
            onRefresh={() => void runAnalysis()}
          />
        )}

        {activeTab === "network" && (
          <>
            {analysis ? (
              <>
                <PortfolioMstGraph mst={analysis.mst} holdings={analysis.holdings} />
                <ReviewDetails title="Network details and methodology">
                  <Stack spacing={3}>
                    <MstDiagnostics analysis={analysis} />
                    <CorrelationMstExplainer />
                    <MstHoldingsInspector analysis={analysis} />
                  </Stack>
                </ReviewDetails>
              </>
            ) : analysisLoading ? (
              <Paper sx={{ p: 3 }}>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <CircularProgress size={24} />
                  <Typography>Loading your portfolio network…</Typography>
                </Stack>
              </Paper>
            ) : (
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>Portfolio network</Typography>
                <Typography sx={{ mb: 2 }}>
                  {holdings.length ? "Run your portfolio analysis to see the connections between your holdings." : "Add holdings to see how the companies in your portfolio connect."}
                </Typography>
                <Button variant="contained" onClick={() => holdings.length ? void runAnalysis() : setAddDialogOpen(true)}>
                  {holdings.length ? "Load portfolio network" : "Add holding"}
                </Button>
              </Paper>
            )}
          </>
        )}

        {activeTab === "stress" && (
          <>
            {analysis ? (
              <StressPanel analysis={analysis} loading={analysisLoading} onRun={(stress) => void runAnalysis(stress)} />
            ) : analysisLoading ? (
              <Paper sx={{ p: 3 }}>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <CircularProgress size={24} />
                  <Typography>Loading stress testing…</Typography>
                </Stack>
              </Paper>
            ) : (
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>Stress testing</Typography>
                <Typography sx={{ mb: 2 }}>
                  {holdings.length ? "Run your portfolio analysis to test how a hypothetical shock could affect your holdings." : "Add holdings to test how a hypothetical shock could affect your portfolio."}
                </Typography>
                <Button variant="contained" onClick={() => holdings.length ? void runAnalysis() : setAddDialogOpen(true)}>
                  {holdings.length ? "Load stress testing" : "Add holding"}
                </Button>
              </Paper>
            )}
          </>
        )}

        {/* Performance and risk analysis */}
        {activeTab === "analysis" && (
          <>
            {!analysis && !analysisLoading && (
              <Paper sx={{ p: 6, textAlign: "center" }}>
                <Typography variant="h5" color="text.secondary" gutterBottom>
                  No Risk Analysis Calculated Yet
                </Typography>
                <Typography color="text.secondary" gutterBottom>
                  Click "Refresh analysis" to calculate portfolio performance and covariance risk.
                </Typography>
                <Button variant="contained" onClick={() => void runAnalysis()} disabled={!holdings.length} sx={{ mt: 1 }}>
                  Run Risk Analysis
                </Button>
              </Paper>
            )}

            {analysisLoading && (
              <Paper sx={{ p: 3 }}>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <CircularProgress size={24} />
                  <Typography>Calculating performance, covariance risk and MST paths…</Typography>
                </Stack>
              </Paper>
            )}

            {analysis && (
              <>
                {/* Report Header */}
                <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
                  <Box>
                    <Typography variant="h4">Portfolio Quantitative Analysis</Typography>
                    <Typography color="text.secondary">
                      Data through {analysis.envelope.as_of} · {analysis.envelope.observations_used} daily returns
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} className="no-print">
                    <Button
                      onClick={() => {
                        const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: "application/json" });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `prism-report-${analysis.envelope.as_of}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        bgcolor: "#E3D7C4",
                        color: "#292D2A",
                        fontWeight: 600,
                        boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                        "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                      }}
                    >
                      Download report
                    </Button>
                    <Button
                      variant="contained"
                      onClick={() => window.print()}
                      sx={{
                        borderRadius: 0,
                        bgcolor: "#046A38",
                        color: "#F9EBD7",
                        fontWeight: 700,
                        boxShadow: "0 3px 8px rgba(4,106,56,0.20)",
                        "&:hover": { bgcolor: "#03532c" },
                      }}
                    >
                      Print / save PDF
                    </Button>
                  </Stack>
                </Stack>

                {/* Risk + Diversity badges */}
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                  {pRisk && (
                    <Paper sx={{ p: 2.5, flex: 1 }}>
                      <Typography variant="overline" color="text.secondary">
                        Portfolio Risk Score
                      </Typography>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mt: 0.5 }}>
                        <Box
                          sx={{
                            width: 48,
                            height: 48,
                            borderRadius: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            bgcolor: `${pRisk.color}22`,
                            boxShadow: "0 2px 6px rgba(41,45,42,0.10)",
                          }}
                        >
                          <Typography sx={{ fontWeight: 800, color: pRisk.color, fontSize: "1.1rem" }}>
                            {pRisk.score}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="h6" sx={{ fontWeight: 700, color: pRisk.color }}>
                            {pRisk.label} Risk
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Weighted annual volatility risk rating
                          </Typography>
                        </Box>
                      </Stack>
                    </Paper>
                  )}
                  {dGrade && (
                    <Paper sx={{ p: 2.5, flex: 1 }}>
                      <Typography variant="overline" color="text.secondary">
                        Diversity Index
                      </Typography>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mt: 0.5 }}>
                        <Box
                          sx={{
                            width: 48,
                            height: 48,
                            borderRadius: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            bgcolor: `${dGrade.color}22`,
                            boxShadow: "0 2px 6px rgba(41,45,42,0.10)",
                          }}
                        >
                          <Typography sx={{ fontWeight: 800, color: dGrade.color, fontSize: "1.3rem" }}>
                            {dGrade.grade}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="h6" sx={{ fontWeight: 700, color: dGrade.color }}>
                            {dGrade.label}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {analysis.concentration.effective_holdings.toFixed(1)} effective holdings ·{" "}
                            {analysis.concentration.effective_industries.toFixed(1)} effective industries
                          </Typography>
                        </Box>
                      </Stack>
                    </Paper>
                  )}
                </Stack>

                {/* Analytical Metric summary cards */}
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ flexWrap: "wrap" }}>
                  <Metric label="Trailing return" value={formatPercent(analysis.performance.total_return * 100)} />
                  <Metric label="Annual volatility" value={formatDecimal(analysis.performance.annualized_volatility * 100, 1) + "%"} />
                  <Metric label="Maximum drawdown" value={formatPercent(analysis.performance.max_drawdown * 100)} />
                  <Metric label="Effective holdings" value={analysis.concentration.effective_holdings.toFixed(1)} />
                  <Metric label="Effective risk bets" value={analysis.diversification.effective_bets_risk.toFixed(1)} />
                </Stack>



                {/* Performance Chart */}
                <PerformanceChart points={analysis.performance.points} />

                {/* Exposure + Diversification */}
                <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
                  <ExposurePanel analysis={analysis} />
                  <DiversificationPanel analysis={analysis} />
                </Stack>

                {/* Risk Contribution Table (Euler Decomposition) */}
                <RiskContributionTable holdings={analysis.holdings} />

                {/* Divergence Table */}
                <HoldingTable holdings={analysis.holdings} />

                {/* Method & Limitations */}
                <MethodAndLimitations analysis={analysis} />
              </>
            )}
          </>
        )}

        {/* ═══════════════════════════════════════════════
            TAB: NEWS SIGNALS (PREVIEW)
           ═══════════════════════════════════════════════ */}
        {activeTab === "news-preview" && (
          <NewsIntelligencePanel embedded />
        )}

        {/* ═══════════════════════════════════════════════
            TAB 3: TRANSACTION LEDGER
           ═══════════════════════════════════════════════ */}
        {activeTab === "transactions" && (
          <Paper sx={{ p: 3 }}>
            <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 2, flexWrap: "wrap", gap: 1.5 }}>
              <Box>
                <Typography variant="h5" gutterBottom>
                  Activity
                </Typography>
                <Typography color="text.secondary">
                  Recorded purchases and sales, in date order.
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
                <Button
                  size="small"
                  onClick={() => {
                    setCsvInputText("");
                    setCsvPreview([]);
                    setCsvErrors([]);
                    setCsvImportDialogOpen(true);
                  }}
                  sx={{
                    borderRadius: 0,
                    border: "none",
                    bgcolor: "#E3D7C4",
                    color: "#292D2A",
                    boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                    textTransform: "none",
                    fontSize: "0.875rem",
                    py: 0.6,
                    px: 1.5,
                    fontWeight: 600,
                    "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                  }}
                >
                  Import CSV
                </Button>
                <Button
                  size="small"
                  onClick={handleExportCsv}
                  disabled={!transactions.length}
                  sx={{
                    borderRadius: 0,
                    border: "none",
                    bgcolor: "#E3D7C4",
                    color: "#292D2A",
                    boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                    textTransform: "none",
                    fontSize: "0.875rem",
                    py: 0.6,
                    px: 1.5,
                    fontWeight: 600,
                    "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                  }}
                >
                  Export CSV
                </Button>
                <Button
                  size="small"
                  onClick={() => {
                    setBackupStatus(null);
                    setBackupDialogOpen(true);
                  }}
                  sx={{
                    borderRadius: 0,
                    border: "none",
                    bgcolor: "#E3D7C4",
                    color: "#292D2A",
                    boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                    textTransform: "none",
                    fontSize: "0.875rem",
                    py: 0.6,
                    px: 1.5,
                    fontWeight: 600,
                    "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                  }}
                >
                  Journal Backup / Restore
                </Button>
              </Stack>
            </Stack>

            {/* ─── Compact Reconciliation Status Card ─── */}
            <Paper
              sx={{
                p: 2,
                mb: 3,
                bgcolor: reconciliation.isReconciled ? "#DCE9DE" : "#F6D9CC",
                border: "none",
                borderRadius: 0,
                boxShadow: "0 3px 8px rgba(41,45,42,0.08)",
              }}
            >
              <Stack
                direction={{ xs: "column", md: "row" }}
                sx={{
                  justifyContent: "space-between",
                  alignItems: { md: "center" },
                  gap: 1.5,
                }}
              >
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                  <Chip
                    label={reconciliation.isReconciled ? "Ledger Reconciled" : "Discrepancy Detected"}
                    size="small"
                    sx={{
                      bgcolor: reconciliation.isReconciled ? "#046A38" : "#8A5A00",
                      color: "#F9EBD7",
                      fontWeight: 700,
                      borderRadius: 0,
                    }}
                  />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: "#292D2A" }}>
                    {transactions.length} transactions · {derivedLedger.holdings.length} holdings
                  </Typography>
                </Stack>
                <Stack direction="row" spacing={2.5} sx={{ fontSize: "0.875rem", color: "#292D2A", flexWrap: "wrap", alignItems: "center" }}>
                  <Box><strong>Cash:</strong> {formatCurrency(derivedLedger.cash)}</Box>
                  <Box><strong>Realized P&L:</strong> {formatCurrency(derivedLedger.totalRealizedPnl)}</Box>
                  <Box><strong>Invested Cost:</strong> {formatCurrency(derivedLedger.totalInvestedCost)}</Box>
                  {!reconciliation.isReconciled && (
                    <Button
                      size="small"
                      onClick={() => {
                        setHoldings(derivedLedger.holdings);
                        saveHoldings(derivedLedger.holdings);
                        setSnackbar("Holdings re-synchronized to ledger truth.");
                      }}
                      sx={{
                        py: 0.2,
                        px: 1,
                        fontSize: "0.875rem",
                        bgcolor: "#8A5A00",
                        color: "#F9EBD7",
                        borderRadius: 0,
                        fontWeight: 700,
                        textTransform: "none",
                        "&:hover": { bgcolor: "#6f4800" },
                      }}
                    >
                      Sync to Ledger
                    </Button>
                  )}
                </Stack>
              </Stack>
              {!reconciliation.isReconciled && (
                <Box sx={{ mt: 1.5, pt: 1, borderTop: "1px dashed rgba(41,45,42,0.2)" }}>
                  {reconciliation.discrepancies.map((d, i) => (
                    <Typography key={i} variant="caption" sx={{ display: "block", color: "#B8321A", fontWeight: 600 }}>
                      • {d}
                    </Typography>
                  ))}
                </Box>
              )}
            </Paper>
            {!transactions.length ? (
              <Box sx={{ py: 4, textAlign: "center" }}>
                <Typography color="text.secondary">No transactions recorded yet.</Typography>
              </Box>
            ) : (
              <Table size="small">
                <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Symbol</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Quantity</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Execution Price</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Total Value</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Realized P&L</TableCell>
                    <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Date</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Journal Decision</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {transactions.slice(0, 100).map((tx) => (
                    <TableRow key={tx.id} hover sx={{ "&:hover": { bgcolor: "#E3D7C4 !important" } }}>
                      <TableCell sx={{ borderBottom: "none" }}>
                        <Chip
                          size="small"
                          label={tx.type}
                          sx={{
                            borderRadius: 0,
                            fontWeight: 700,
                            bgcolor: tx.type === "BUY" ? "#DCE9DE" : "#F6D9CC",
                            color: tx.type === "BUY" ? "#046A38" : "#B8321A",
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700, borderBottom: "none" }}>
                        <MuiLink component={Link} to={`/companies/${tx.symbol}`} sx={{ color: "#292D2A", textDecoration: "none" }}>
                          {tx.symbol}
                        </MuiLink>
                      </TableCell>
                      <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>{tx.quantity}</TableCell>
                      <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>{formatCurrency(tx.price, 2)}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>
                        {formatCurrency(tx.quantity * tx.price)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontWeight: 700,
                          fontFamily: "JetBrains Mono, monospace",
                          borderBottom: "none",
                          color:
                            tx.realizedPnl === undefined
                              ? "#292D2A"
                              : tx.realizedPnl >= 0
                              ? "#046A38"
                              : "#B8321A",
                        }}
                      >
                        {tx.realizedPnl !== undefined
                          ? `${tx.realizedPnl >= 0 ? "+" : ""}${formatCurrency(tx.realizedPnl)}`
                          : "—"}
                      </TableCell>
                      <TableCell sx={{ color: "#292D2A", borderBottom: "none" }}>{tx.date}</TableCell>
                      <TableCell align="center" sx={{ borderBottom: "none" }}>
                        <Tooltip title={`Record investment decision for ${tx.symbol} on ${tx.date}`}>
                          <Button
                            size="small"
                            onClick={() => {
                              setDecisionTxRecord(tx);
                              setTxDecisionType(tx.type === "BUY" ? "Buy" : "Sell");
                              setTxDecisionDate(tx.date);
                              setTxRationale("");
                              setTxTags(["Ledger Entry"]);
                              setTxTagInput("");
                            }}
                            sx={{
                              py: 0.3,
                              px: 1,
                              fontSize: "0.875rem",
                              borderRadius: 0,
                              border: "none",
                              bgcolor: "#E3D7C4",
                              color: "#292D2A",
                              boxShadow: "0 2px 5px rgba(41,45,42,0.08)",
                              textTransform: "none",
                              fontWeight: 600,
                              "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                            }}
                          >
                            Record Decision
                          </Button>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Paper>
        )}

        {/* ═══════════════════════════════════════════════
            TAB 9: AI INSIGHTS (Phase 4 ML Risk Models)
           ═══════════════════════════════════════════════ */}
        {activeTab === "ai-insights" && (
          <AiInsightsTab
            holdings={holdings}
            totalInvestedValue={totalInvestedValue}
          />
        )}

        {/* ═══════════════════════════════════════════════
            TAB: STOCK DECISION ENGINE (SELL / HOLD / WAIT & WATCH)
           ═══════════════════════════════════════════════ */}
        {activeTab === "stock-decisions" && (
          <StockDecisionEngineTab
            response={decisionResponse}
            loading={decisionLoading}
            error={decisionError}
            holdings={holdings}
            onRefresh={() => void runDecisionAnalysis()}
          />
        )}
      </Stack>

      {/* ─── Modals: Buy, Sell, and Edit ─── */}
      <AddStockDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onAdd={addHolding}
        securities={securities}
      />
      <SellStockDialog
        open={sellDialogOpen}
        onClose={() => setSellDialogOpen(false)}
        holdings={holdings}
        quotes={quotes}
        onSell={sellHolding}
      />
      <EditHoldingDialog
        holding={editHolding}
        onClose={() => setEditHolding(null)}
        onSave={updateHolding}
        securities={securities}
      />

      {/* ─── Modal: Stock Research Notes ─── */}
      <Dialog
        open={Boolean(selectedNotesStock)}
        onClose={() => {
          setSelectedNotesStock(null);
          void refreshNotesCountMap();
        }}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
           Research Notes: {selectedNotesStock?.symbol}
          {selectedNotesStock?.companyName && (
            <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
              {selectedNotesStock.companyName}
            </Typography>
          )}
        </DialogTitle>
        <DialogContent sx={{ p: 2 }}>
          {selectedNotesStock && (
            <StockResearchNotes
              symbol={selectedNotesStock.symbol}
              companyName={selectedNotesStock.companyName}
              defaultExpanded={true}
              onNotesCountChange={() => void refreshNotesCountMap()}
            />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5 }}>
          <Button
            onClick={() => {
              setSelectedNotesStock(null);
              void refreshNotesCountMap();
            }}
            sx={{ color: "#686B64", borderRadius: 0 }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Modal: Record Decision for Transaction ─── */}
      <Dialog
        open={Boolean(decisionTxRecord)}
        onClose={() => setDecisionTxRecord(null)}
        maxWidth="sm"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
          Record Decision: {decisionTxRecord?.symbol} ({decisionTxRecord?.type})
          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
            Ledger Date: {decisionTxRecord?.date} · Execution Price: {decisionTxRecord ? formatCurrency(decisionTxRecord.price, 2) : "—"}
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          {decisionTxRecord && (() => {
            const holdingMatch = holdings.find((h) => h.symbol === decisionTxRecord.symbol);
            const totalInv = totalInvestedValue;
            const weight = holdingMatch && totalInv > 0
              ? (holdingMatch.quantity * holdingMatch.buyPrice / totalInv) * 100
              : null;
            const pRiskScore = comprehensiveRisk?.portfolio_profile?.portfolio_risk_score ?? null;
            const pRiskLabel = comprehensiveRisk?.portfolio_profile?.portfolio_classification ?? null;
            const divScore = analysis?.holdings.find((h) => h.symbol === decisionTxRecord.symbol)?.divergence_20d ?? null;
            const cluster = holdingMatch?.sector ?? null;

            return (
              <Stack spacing={2.5}>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel id="tx-decision-type-label">Decision Type</InputLabel>
                    <Select
                      labelId="tx-decision-type-label"
                      label="Decision Type"
                      value={txDecisionType}
                      onChange={(e) => setTxDecisionType(e.target.value as DecisionType)}
                      sx={{ bgcolor: "#F9EBD7", borderRadius: 0 }}
                    >
                      <MenuItem value="Buy">Buy</MenuItem>
                      <MenuItem value="Hold">Hold</MenuItem>
                      <MenuItem value="Sell">Sell</MenuItem>
                      <MenuItem value="Review">Review</MenuItem>
                    </Select>
                  </FormControl>

                  <TextField
                    size="small"
                    label="Decision Date"
                    type="date"
                    value={txDecisionDate}
                    onChange={(e) => setTxDecisionDate(e.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ flex: 1, bgcolor: "#F9EBD7", borderRadius: 0 }}
                  />
                </Stack>

                <TextField
                  multiline
                  rows={4}
                  label="Investment Rationale & Thesis"
                  placeholder="Why did you execute this trade? What is your forward thesis or risk factor..."
                  value={txRationale}
                  onChange={(e) => setTxRationale(e.target.value)}
                  sx={{
                    bgcolor: "#F9EBD7",
                    borderRadius: 0,
                    "& .MuiInputBase-input": { fontSize: "0.9rem", lineHeight: 1.6, color: "#292D2A" },
                  }}
                />

                <Box>
                  <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700, display: "block", mb: 0.5 }}>
                    Decision Tags
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <TextField
                      size="small"
                      placeholder="Add tag..."
                      value={txTagInput}
                      onChange={(e) => setTxTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          const val = txTagInput.trim();
                          if (val && !txTags.includes(val)) {
                            setTxTags((prev) => [...prev, val]);
                            setTxTagInput("");
                          }
                        }
                      }}
                      sx={{ flex: 1, bgcolor: "#F9EBD7", borderRadius: 0 }}
                    />
                    <Button
                      size="small"
                      onClick={() => {
                        const val = txTagInput.trim();
                        if (val && !txTags.includes(val)) {
                          setTxTags((prev) => [...prev, val]);
                          setTxTagInput("");
                        }
                      }}
                      disabled={!txTagInput.trim()}
                      sx={{
                        borderRadius: 0,
                        border: "none",
                        bgcolor: "#E3D7C4",
                        color: "#292D2A",
                        fontWeight: 600,
                        boxShadow: "0 2px 4px rgba(41,45,42,0.08)",
                        "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                      }}
                    >
                      Add
                    </Button>
                  </Stack>
                  {txTags.length > 0 && (
                    <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mt: 1 }}>
                      {txTags.map((t) => (
                        <Chip
                          key={t}
                          label={t}
                          size="small"
                          onDelete={() => setTxTags((prev) => prev.filter((i) => i !== t))}
                          sx={{
                            height: 24,
                            borderRadius: 0,
                            bgcolor: "#DCE9DE",
                            color: "#046A38",
                            fontWeight: 600,
                          }}
                        />
                      ))}
                    </Stack>
                  )}
                </Box>

                {/* Captured Snapshot Preview */}
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    bgcolor: "#F9EBD7",
                    border: "none",
                    borderRadius: 0,
                    boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "#292D2A", display: "block", mb: 1 }}>
                    Captured Context Snapshot (At Decision Time):
                  </Typography>
                  <Stack spacing={0.5} sx={{ fontSize: "0.875rem", color: "#686B64" }}>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <span>Portfolio Risk Score:</span>
                      <span style={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                        {pRiskScore !== null ? `${pRiskScore} (${pRiskLabel || "Active"})` : "Unavailable"}
                      </span>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <span>20D Sector Divergence:</span>
                      <span style={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                        {divScore !== null ? `${divScore > 0 ? "+" : ""}${divScore.toFixed(2)}σ` : "Unavailable"}
                      </span>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <span>Portfolio Weight:</span>
                      <span style={{ fontWeight: 600, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                        {weight !== null ? `${weight.toFixed(2)}%` : "Unavailable"}
                      </span>
                    </Stack>
                    <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                      <span>MST Cluster:</span>
                      <span style={{ fontWeight: 600, color: "#292D2A" }}>{cluster || "Unavailable"}</span>
                    </Stack>
                  </Stack>
                </Paper>
              </Stack>
            );
          })()}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDecisionTxRecord(null)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={async () => {
              if (!decisionTxRecord) return;
              if (!txRationale.trim()) {
                setSnackbar("Please enter an investment rationale.");
                return;
              }
              const holdingMatch = holdings.find((h) => h.symbol === decisionTxRecord.symbol);
              const totalInv = totalInvestedValue;
              const weight = holdingMatch && totalInv > 0
                ? (holdingMatch.quantity * holdingMatch.buyPrice / totalInv) * 100
                : null;
              const pRiskScore = comprehensiveRisk?.portfolio_profile?.portfolio_risk_score ?? null;
              const pRiskLabel = comprehensiveRisk?.portfolio_profile?.portfolio_classification ?? null;
              const divScore = analysis?.holdings.find((h) => h.symbol === decisionTxRecord.symbol)?.divergence_20d ?? null;
              const cluster = holdingMatch?.sector ?? null;

              const snapshot: DecisionContextSnapshot = {
                riskScore: pRiskScore,
                riskLabel: pRiskLabel,
                sectorDivergenceScore: divScore,
                sectorDivergenceHorizon: 20,
                portfolioWeight: weight,
                mstCluster: cluster,
                capturedAt: new Date().toISOString(),
              };

              await saveDecision({
                symbol: decisionTxRecord.symbol,
                decisionType: txDecisionType,
                decisionDate: txDecisionDate,
                rationale: txRationale.trim(),
                tags: txTags,
                snapshot,
              });

              setSnackbar(`Investment decision recorded for ${decisionTxRecord.symbol}!`);
              setDecisionTxRecord(null);
            }}
            sx={{
              borderRadius: 0,
              bgcolor: "#046A38",
              color: "#F9EBD7",
              fontWeight: 700,
              boxShadow: "0 3px 8px rgba(4,106,56,0.20)",
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            Record Decision
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Modal: Journal Backup & Restore (Export / Import JSON) ─── */}
      <Dialog
        open={backupDialogOpen}
        onClose={() => setBackupDialogOpen(false)}
        maxWidth="xs"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
          Journal Backup & Restore
          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
            Export or restore your research notes, investment decisions, and portfolio snapshots locally in JSON format.
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2.5}>
            {backupStatus && (
              <Alert severity="info" sx={{ fontSize: "0.875rem", borderRadius: 0 }}>
                {backupStatus}
              </Alert>
            )}

            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 0.5 }}>
                1. Export Backup
              </Typography>
              <Typography variant="body2" sx={{ fontSize: "0.875rem", mb: 1.5, color: "#686B64" }}>
                Download a JSON backup of all research notes, investment decisions, and portfolio snapshots to your device.
              </Typography>
              <Button
                variant="contained"
                fullWidth
                onClick={async () => {
                  try {
                    const json = await exportJournalBackup();
                    const blob = new Blob([json], { type: "application/json" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `prism-journal-backup-${new Date().toISOString().substring(0, 10)}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    setBackupStatus("Journal backup downloaded successfully!");
                  } catch {
                    setBackupStatus("Failed to export backup.");
                  }
                }}
                sx={{
                  borderRadius: 0,
                  bgcolor: "#046A38",
                  color: "#F9EBD7",
                  fontWeight: 700,
                  boxShadow: "0 3px 8px rgba(4,106,56,0.20)",
                  "&:hover": { bgcolor: "#03532c" },
                }}
              >
                Download JSON Backup
              </Button>
            </Box>

            <Box sx={{ pt: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#292D2A", mb: 0.5 }}>
                2. Restore from Backup
              </Typography>
              <Typography variant="body2" sx={{ fontSize: "0.875rem", mb: 1.5, color: "#686B64" }}>
                Select a previously exported JSON backup file to import notes and decisions.
              </Typography>
              <Button
                component="label"
                fullWidth
                sx={{
                  borderRadius: 0,
                  border: "none",
                  bgcolor: "#E3D7C4",
                  color: "#292D2A",
                  fontWeight: 600,
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                  "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
                }}
              >
                Upload & Restore Backup
                <input
                  type="file"
                  hidden
                  accept=".json,application/json"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = async (evt) => {
                      const text = evt.target?.result;
                      if (typeof text !== "string") return;
                      try {
                        const res = await importJournalBackup(text);
                        setBackupStatus(
                          `Imported ${res.importedNotes} notes and ${res.importedDecisions} decisions (${res.skipped} invalid records skipped).`
                        );
                        void refreshNotesCountMap();
                        setSnackbar("Journal backup restored successfully!");
                      } catch (err) {
                        setBackupStatus(err instanceof Error ? err.message : "Failed to import backup");
                      }
                    };
                    reader.readAsText(file);
                    e.target.value = "";
                  }}
                />
              </Button>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5 }}>
          <Button onClick={() => setBackupDialogOpen(false)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Done
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Modal: Transaction CSV Import ─── */}
      <Dialog
        open={csvImportDialogOpen}
        onClose={() => setCsvImportDialogOpen(false)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: "#292D2A", pb: 1 }}>
          Import Transactions from CSV
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography variant="body2" sx={{ color: "#686B64" }}>
              Upload or paste CSV transactions (supported headers: <code>date,type,symbol,quantity,price,amount,fees,notes</code>). Spreadsheet formula cells starting with <code>=, +, -, @</code> are strictly rejected to prevent formula injection.
            </Typography>

            <Button
              component="label"
              size="small"
              sx={{
                bgcolor: "#E3D7C4",
                color: "#292D2A",
                fontWeight: 600,
                borderRadius: 0,
                alignSelf: "flex-start",
                boxShadow: "0 2px 6px rgba(41,45,42,0.10)",
                "&:hover": { bgcolor: "#046A38", color: "#F9EBD7" },
              }}
            >
              Choose CSV File
              <input
                type="file"
                hidden
                accept=".csv,text/csv"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const reader = new FileReader();
                    reader.onload = (evt) => {
                      const text = String(evt.target?.result || "");
                      setCsvInputText(text);
                      handlePreviewCsv(text);
                    };
                    reader.readAsText(file);
                    e.target.value = "";
                  }
                }}
              />
            </Button>

            <TextField
              multiline
              rows={4}
              fullWidth
              placeholder="date,type,symbol,quantity,price,amount,fees,notes&#10;2026-01-05,BUY,TCS,10,3200,,15,Initial buy"
              value={csvInputText}
              onChange={(e) => {
                setCsvInputText(e.target.value);
                handlePreviewCsv(e.target.value);
              }}
              sx={{
                "& .MuiInputBase-root": {
                  borderRadius: 0,
                  bgcolor: "#F9EBD7",
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: "0.875rem",
                },
              }}
            />

            {csvErrors.length > 0 && (
              <Alert severity="error" sx={{ borderRadius: 0 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  Validation Errors (Atomic Rollback Active):
                </Typography>
                {csvErrors.map((err, i) => (
                  <Typography key={i} variant="caption" sx={{ display: "block" }}>
                    • {err}
                  </Typography>
                ))}
              </Alert>
            )}

            {csvPreview.length > 0 && (
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1, color: "#046A38" }}>
                  Preview ({csvPreview.length} Valid Transactions):
                </Typography>
                <Table size="small" sx={{ bgcolor: "#F9EBD7" }}>
                  <TableHead sx={{ bgcolor: "#E3D7C4" }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Quantity</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Price</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {csvPreview.slice(0, 5).map((row, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{row.date}</TableCell>
                        <TableCell>{row.type}</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>{row.symbol || "—"}</TableCell>
                        <TableCell align="right">{row.quantity ?? "—"}</TableCell>
                        <TableCell align="right">{row.price ? formatCurrency(row.price) : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2, bgcolor: "#E3D7C4" }}>
          <Button onClick={() => setCsvImportDialogOpen(false)} sx={{ color: "#686B64", borderRadius: 0 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={csvPreview.length === 0 || csvErrors.length > 0}
            onClick={() => {
              commitCsvImport();
              setCsvImportDialogOpen(false);
            }}
            sx={{
              borderRadius: 0,
              bgcolor: "#046A38",
              color: "#F9EBD7",
              fontWeight: 700,
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            Commit {csvPreview.length} Transactions
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={3000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        message={snackbar}
      />
    </Page>
  );
}

/* ─── Metric Card Helper ─── */

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Paper sx={{ p: 2.5, flex: "1 1 180px" }}>
      <Typography variant="overline" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
    </Paper>
  );
}

/* ─── Buy Stock Dialog with Stock Name Autocomplete ─── */

function AddStockDialog({
  open,
  onClose,
  onAdd,
  securities,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (h: Omit<PortfolioHolding, "id">) => void;
  securities: SecurityInfo[];
}) {
  const [selected, setSelected] = useState<SecurityInfo | null>(null);
  const [symbolInput, setSymbolInput] = useState("");
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [buyDate, setBuyDate] = useState(new Date().toISOString().slice(0, 10));
  const [exchange, setExchange] = useState("NSE");
  const [liveQuoteFetching, setLiveQuoteFetching] = useState(false);

  // When stock is selected, fetch quote or auto-populate price
  const handleStockSelect = async (sec: SecurityInfo | null) => {
    setSelected(sec);
    if (!sec) return;
    setSymbolInput(sec.symbol);
    if (sec.latest_price) {
      setBuyPrice(String(sec.latest_price));
    }
    // Attempt fetching live quote via backend
    setLiveQuoteFetching(true);
    try {
      const q = await fetchJson<LiveQuote>(`/market-data/quote/${sec.symbol}`, new AbortController().signal);
      if (q && q.latest_price) {
        setBuyPrice(String(q.latest_price));
      }
    } catch {
      // Keep static price if available
    } finally {
      setLiveQuoteFetching(false);
    }
  };

  function handleSubmit() {
    const sym = selected?.symbol ?? symbolInput.trim().toUpperCase();
    const qty = Number(quantity);
    const price = Number(buyPrice);
    if (!sym || qty <= 0 || price <= 0) return;
    onAdd({
      symbol: sym,
      companyName: selected?.company_name ?? sym,
      sector: selected?.industry,
      quantity: qty,
      buyPrice: price,
      buyDate,
      exchange,
    });
    setSelected(null);
    setSymbolInput("");
    setQuantity("");
    setBuyPrice("");
    setBuyDate(new Date().toISOString().slice(0, 10));
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Buy Stock</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ mt: 1 }}>
          <Autocomplete
            options={securities}
            getOptionLabel={(opt) => (typeof opt === "string" ? opt : `${opt.symbol} — ${opt.company_name}`)}
            filterOptions={(options, { inputValue }) => {
              const q = inputValue.toUpperCase();
              return options
                .filter((o) => o.symbol.includes(q) || o.company_name.toUpperCase().includes(q))
                .slice(0, 15);
            }}
            value={selected}
            onChange={(_, val) => void handleStockSelect(typeof val === "string" ? null : val)}
            inputValue={symbolInput}
            onInputChange={(_, val) => setSymbolInput(val)}
            renderOption={(props, opt) => (
              <Box component="li" {...props} key={opt.id}>
                <Box>
                  <Typography sx={{ fontWeight: 700 }}>{opt.symbol}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {opt.company_name} · {opt.industry}
                  </Typography>
                </Box>
                {opt.latest_price && (
                  <Typography variant="body2" sx={{ ml: "auto", fontWeight: 600 }}>
                    ₹{opt.latest_price.toFixed(2)}
                  </Typography>
                )}
              </Box>
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Stock Symbol or Name (Autocomplete)"
                placeholder="Type TCS, INFY, Reliance, etc."
                required
              />
            )}
            noOptionsText="Type to search NIFTY 200 stocks"
            freeSolo
          />

          {selected && (
            <Alert severity="info" icon={false}>
              <strong>{selected.company_name}</strong> · Sector: {selected.industry}
              {buyPrice && (
                <>
                  {" "}
                  · Live/Close Price: <strong>₹{Number(buyPrice).toFixed(2)}</strong>
                </>
              )}
              {liveQuoteFetching && <CircularProgress size={12} sx={{ ml: 1 }} />}
            </Alert>
          )}

          <Stack direction="row" spacing={2}>
            <TextField
              label="Quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
              slotProps={{ htmlInput: { min: 1 } }}
              sx={{ flex: 1 }}
            />
            <TextField
              label="Purchase Price (₹)"
              type="number"
              value={buyPrice}
              onChange={(e) => setBuyPrice(e.target.value)}
              required
              slotProps={{ htmlInput: { min: 0.01, step: 0.01 } }}
              sx={{ flex: 1 }}
            />
          </Stack>

          <Stack direction="row" spacing={2}>
            <TextField
              label="Buy Date"
              type="date"
              value={buyDate}
              onChange={(e) => setBuyDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ flex: 1 }}
            />
            <FormControl sx={{ flex: 1 }}>
              <InputLabel>Exchange</InputLabel>
              <Select label="Exchange" value={exchange} onChange={(e) => setExchange(e.target.value)}>
                <MenuItem value="NSE">NSE</MenuItem>
                <MenuItem value="BSE">BSE</MenuItem>
              </Select>
            </FormControl>
          </Stack>

          {quantity && buyPrice && Number(quantity) > 0 && Number(buyPrice) > 0 && (
            <Alert severity="success" icon={false}>
              Total Investment: <strong>{formatCurrency(Number(quantity) * Number(buyPrice))}</strong>
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="success"
          disabled={
            !(selected?.symbol || symbolInput.trim()) ||
            Number(quantity) <= 0 ||
            Number(buyPrice) <= 0
          }
        >
          Confirm Purchase
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ─── Sell Stock Dialog ─── */

function SellStockDialog({
  open,
  onClose,
  holdings,
  quotes,
  onSell,
}: {
  open: boolean;
  onClose: () => void;
  holdings: PortfolioHolding[];
  quotes: Record<string, LiveQuote>;
  onSell: (symbol: string, qty: number, price: number) => void;
}) {
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [sellPrice, setSellPrice] = useState("");

  const selectedHolding = holdings.find((h) => h.symbol === selectedSymbol);

  useEffect(() => {
    if (open && holdings.length > 0 && !selectedSymbol) {
      setSelectedSymbol(holdings[0].symbol);
    }
  }, [open, holdings, selectedSymbol]);

  useEffect(() => {
    if (selectedSymbol) {
      const q = quotes[selectedSymbol.toUpperCase()];
      if (q && q.latest_price) {
        setSellPrice(String(q.latest_price));
      } else if (selectedHolding) {
        setSellPrice(String(selectedHolding.buyPrice));
      }
    }
  }, [selectedSymbol, quotes, selectedHolding]);

  function handleSubmit() {
    const qty = Number(quantity);
    const price = Number(sellPrice);
    if (!selectedSymbol || qty <= 0 || price <= 0) return;
    onSell(selectedSymbol, qty, price);
    setSelectedSymbol("");
    setQuantity("");
    setSellPrice("");
    onClose();
  }

  const numQty = Number(quantity);
  const numPrice = Number(sellPrice);
  const proceeds = numQty > 0 && numPrice > 0 ? numQty * numPrice : 0;
  const pnlPerShare = selectedHolding && numPrice > 0 ? numPrice - selectedHolding.buyPrice : 0;
  const totalRealizedPnl = numQty > 0 ? pnlPerShare * numQty : 0;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Sell Stock</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ mt: 1 }}>
          <FormControl fullWidth>
            <InputLabel>Select Holding</InputLabel>
            <Select
              label="Select Holding"
              value={selectedSymbol}
              onChange={(e) => {
                setSelectedSymbol(e.target.value);
                setQuantity("");
              }}
            >
              {holdings.map((h) => (
                <MenuItem key={h.id} value={h.symbol}>
                  {h.symbol} — {h.quantity} shares @ {formatCurrency(h.buyPrice, 2)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {selectedHolding && (
            <Alert severity="info" icon={false}>
              Available to sell: <strong>{selectedHolding.quantity}</strong> shares · Cost basis:{" "}
              <strong>{formatCurrency(selectedHolding.buyPrice, 2)}</strong>
            </Alert>
          )}

          <Stack direction="row" spacing={2}>
            <TextField
              label="Quantity to Sell"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
              slotProps={{
                htmlInput: { min: 1, max: selectedHolding?.quantity ?? 1 },
              }}
              sx={{ flex: 1 }}
            />
            <TextField
              label="Execution Sell Price (₹)"
              type="number"
              value={sellPrice}
              onChange={(e) => setSellPrice(e.target.value)}
              required
              slotProps={{ htmlInput: { min: 0.01, step: 0.01 } }}
              sx={{ flex: 1 }}
            />
          </Stack>

          {selectedHolding && numQty > 0 && numPrice > 0 && (
            <Paper
              elevation={0}
              sx={{
                p: 2,
                borderRadius: 0,
                border: "none",
                bgcolor: "#F9EBD7",
                boxShadow: "0 2px 6px rgba(41,45,42,0.08)",
              }}
            >
              <Stack spacing={0.75}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <Typography variant="body2" sx={{ color: "#686B64" }}>
                    Total Estimated Proceeds
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                    {formatCurrency(proceeds)}
                  </Typography>
                </Stack>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <Typography variant="body2" sx={{ color: "#686B64" }}>
                    Realized P&L
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 700,
                      fontFamily: "JetBrains Mono, monospace",
                      color: totalRealizedPnl >= 0 ? "#046A38" : "#B8321A",
                    }}
                  >
                    {totalRealizedPnl >= 0 ? "+" : ""}
                    {formatCurrency(totalRealizedPnl)} ({formatPercent((pnlPerShare / selectedHolding.buyPrice) * 100)})
                  </Typography>
                </Stack>
              </Stack>
            </Paper>
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="error"
          disabled={
            !selectedSymbol ||
            numQty <= 0 ||
            numPrice <= 0 ||
            (selectedHolding != null && numQty > selectedHolding.quantity)
          }
        >
          Confirm Sale
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ─── Edit Holding Dialog ─── */

function EditHoldingDialog({
  holding,
  onClose,
  onSave,
  securities,
}: {
  holding: PortfolioHolding | null;
  onClose: () => void;
  onSave: (updated: PortfolioHolding) => void;
  securities: SecurityInfo[];
}) {
  const [selected, setSelected] = useState<SecurityInfo | null>(null);
  const [symbolInput, setSymbolInput] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [exchange, setExchange] = useState("NSE");

  useEffect(() => {
    if (holding) {
      setSymbolInput(holding.symbol);
      setCompanyName(holding.companyName);
      setQuantity(String(holding.quantity));
      setBuyPrice(String(holding.buyPrice));
      setBuyDate(holding.buyDate);
      setExchange(holding.exchange || "NSE");
      const match = securities.find((s) => s.symbol === holding.symbol);
      setSelected(match ?? null);
    }
  }, [holding, securities]);

  function handleSave() {
    if (!holding) return;
    onSave({
      ...holding,
      symbol: (selected?.symbol ?? symbolInput).trim().toUpperCase(),
      companyName: selected?.company_name ?? companyName.trim(),
      quantity: Number(quantity),
      buyPrice: Number(buyPrice),
      buyDate,
      exchange,
    });
    onClose();
  }

  return (
    <Dialog open={Boolean(holding)} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Edit Holding</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ mt: 1 }}>
          <TextField
            label="Stock Symbol"
            value={symbolInput}
            disabled
            fullWidth
          />
          <TextField
            label="Company Name"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            fullWidth
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              slotProps={{ htmlInput: { min: 1 } }}
              sx={{ flex: 1 }}
            />
            <TextField
              label="Avg Buy Price (₹)"
              type="number"
              value={buyPrice}
              onChange={(e) => setBuyPrice(e.target.value)}
              slotProps={{ htmlInput: { min: 0.01, step: 0.01 } }}
              sx={{ flex: 1 }}
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Buy Date"
              type="date"
              value={buyDate}
              onChange={(e) => setBuyDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ flex: 1 }}
            />
            <FormControl sx={{ flex: 1 }}>
              <InputLabel>Exchange</InputLabel>
              <Select label="Exchange" value={exchange} onChange={(e) => setExchange(e.target.value)}>
                <MenuItem value="NSE">NSE</MenuItem>
                <MenuItem value="BSE">BSE</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained">
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════════
   PRESERVED ANALYTICAL SUB-COMPONENTS
   ═══════════════════════════════════════════════ */

function PerformanceChart({ points }: { points: PortfolioPerformancePoint[] }) {
  const width = 960;
  const height = 430;
  const left = 62;
  const right = 22;
  const top = 28;
  const firstBottom = 255;
  const secondTop = 300;
  const bottom = 392;

  const indexValues = points.map((p) => p.portfolio_index);
  const indexMin = Math.min(...indexValues);
  const indexMax = Math.max(...indexValues);
  const padding = Math.max((indexMax - indexMin) * 0.1, 1);
  const min = indexMin - padding;
  const max = indexMax + padding;
  const minDrawdown = Math.min(...points.map((p) => p.drawdown), -0.001);

  const x = (i: number) => left + (i / Math.max(points.length - 1, 1)) * (width - left - right);
  const indexY = (v: number) => top + ((max - v) / (max - min)) * (firstBottom - top);
  const drawdownY = (v: number) => secondTop + (v / minDrawdown) * (bottom - secondTop);

  const indexLine = points.map((p, i) => `${x(i)},${indexY(p.portfolio_index)}`).join(" ");
  const drawdownLine = points.map((p, i) => `${x(i)},${drawdownY(p.drawdown)}`).join(" ");

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Historical portfolio performance</Typography>
      <Typography color="text.secondary" gutterBottom>
        Constant-weight daily-rebalanced index; starting value 100. Drawdown is measured from the running peak.
      </Typography>
      <Box
        component="svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Portfolio index and drawdown history"
        sx={{ width: "100%", height: "auto", display: "block" }}
      >
        {[0, 0.5, 1].map((ratio) => {
          const v = max - ratio * (max - min);
          const y = top + ratio * (firstBottom - top);
          return (
            <g key={ratio}>
              <line x1={left} x2={width - right} y1={y} y2={y} stroke="rgba(41,45,42,0.12)" />
              <text x={left - 8} y={y + 4} textAnchor="end" fontSize="12" fill="#686B64" fontFamily="JetBrains Mono, monospace">
                {v.toFixed(0)}
              </text>
            </g>
          );
        })}
        <polyline points={indexLine} fill="none" stroke="#046A38" strokeWidth="3" />
        <line x1={left} x2={width - right} y1={secondTop} y2={secondTop} stroke="rgba(41,45,42,0.12)" />
        <line x1={left} x2={width - right} y1={bottom} y2={bottom} stroke="rgba(41,45,42,0.12)" />
        <text x={left - 8} y={secondTop + 4} textAnchor="end" fontSize="12" fill="#686B64" fontFamily="JetBrains Mono, monospace">
          0%
        </text>
        <text x={left - 8} y={bottom + 4} textAnchor="end" fontSize="12" fill="#686B64" fontFamily="JetBrains Mono, monospace">
          {formatPercent(minDrawdown * 100, 0)}
        </text>
        <polyline points={drawdownLine} fill="none" stroke="#E34222" strokeWidth="2.5" />
        <text x={left} y={height - 10} fontSize="12" fill="#686B64">
          {points[0]?.trade_date}
        </text>
        <text x={width - right} y={height - 10} textAnchor="end" fontSize="12" fill="#686B64">
          {points.at(-1)?.trade_date}
        </text>
        <text x={left} y={top - 9} fontSize="12" fill="#046A38" fontWeight="bold">
          Portfolio index
        </text>
        <text x={left} y={secondTop - 9} fontSize="12" fill="#E34222" fontWeight="bold">
          Drawdown
        </text>
      </Box>
    </Paper>
  );
}

function ExposurePanel({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3, flex: 1, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 700, color: "#292D2A" }}>
        Industry exposure
      </Typography>
      <Stack spacing={2}>
        {analysis.concentration.industry_weights.map((item) => (
          <Box key={item.industry}>
            <Stack direction="row" sx={{ justifyContent: "space-between" }}>
              <Typography variant="body2" sx={{ color: "#292D2A" }}>{item.industry}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>
                {formatPercent(item.weight * 100, 1)}
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={item.weight * 100}
              sx={{ height: 8, borderRadius: 0, mt: 0.5 }}
            />
          </Box>
        ))}
      </Stack>
      <Typography variant="body2" sx={{ mt: 2, color: "#686B64" }}>
        Industry HHI {analysis.concentration.industry_hhi.toFixed(3)} · effective industries{" "}
        {analysis.concentration.effective_industries.toFixed(1)}
      </Typography>
    </Paper>
  );
}

function DiversificationPanel({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3, flex: 1, borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
      <Typography variant="h5" gutterBottom sx={{ fontWeight: 700, color: "#292D2A" }}>
        Diversification
      </Typography>
      <Stack spacing={2}>
        <Box><Typography variant="overline" sx={{ color: "#686B64" }}>Holdings</Typography><Typography variant="h4" sx={{ fontWeight: 700, color: "#292D2A" }}>{analysis.holdings.length}</Typography></Box>
        <Box><Typography variant="overline" sx={{ color: "#686B64" }}>Effective holdings by weight</Typography><Typography variant="h4" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>{analysis.concentration.effective_holdings.toFixed(2)}</Typography></Box>
        <Box><Typography variant="overline" sx={{ color: "#686B64" }}>Effective bets by risk contribution</Typography><Typography variant="h4" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>{analysis.diversification.effective_bets_risk.toFixed(2)}</Typography></Box>
        <Box><Typography variant="overline" sx={{ color: "#686B64" }}>Effective bets by correlation eigenvalues</Typography><Typography variant="h4" sx={{ fontWeight: 700, color: "#292D2A", fontFamily: "JetBrains Mono, monospace" }}>{analysis.diversification.effective_bets_correlation.toFixed(2)}</Typography></Box>
        <Alert severity="info" icon={false} sx={{ borderRadius: 0, bgcolor: "#F9EBD7", color: "#292D2A" }}>
          {analysis.diversification.interpretation}
        </Alert>
      </Stack>
    </Paper>
  );
}

function RiskContributionTable({ holdings }: { holdings: PortfolioHoldingAnalytics[] }) {
  const ordered = [...holdings].sort((a, b) => b.risk_contribution - a.risk_contribution);
  return (
    <Paper sx={{ p: 3, overflowX: "auto", borderRadius: 0, border: "none", bgcolor: "#F9EBD7", boxShadow: "0 6px 16px rgba(41,45,42,0.14)" }}>
      <Typography variant="h5" sx={{ fontWeight: 700, color: "#292D2A" }}>Risk contribution by holding</Typography>
      <Typography sx={{ color: "#686B64", mb: 2 }}>
        Euler decomposition of annualized sample covariance; contributions sum to approximately 100%.
      </Typography>
      <Table size="small">
        <TableHead sx={{ bgcolor: "#E3D7C4" }}>
          <TableRow>
            <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Holding</TableCell>
            <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Weight</TableCell>
            <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Asset volatility</TableCell>
            <TableCell align="right" sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Risk contribution</TableCell>
            <TableCell sx={{ fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Risk score</TableCell>
            <TableCell sx={{ minWidth: 180, fontWeight: 700, color: "#292D2A", borderBottom: "none" }}>Share</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {ordered.map((h) => {
            const risk = riskScoreFromVolatility(h.annualized_volatility);
            return (
              <TableRow key={h.symbol} hover sx={{ "&:hover": { bgcolor: "#E3D7C4 !important" } }}>
                <TableCell sx={{ borderBottom: "none" }}>
                  <MuiLink component={Link} to={`/companies/${h.symbol}`} sx={{ fontWeight: 700, color: "#292D2A" }}>
                    {h.symbol}
                  </MuiLink>
                </TableCell>
                <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>{formatPercent(h.weight * 100, 1)}</TableCell>
                <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>{formatPercent(h.annualized_volatility * 100, 1)}</TableCell>
                <TableCell align="right" sx={{ color: "#292D2A", fontFamily: "JetBrains Mono, monospace", borderBottom: "none" }}>{formatPercent(h.risk_contribution * 100, 1)}</TableCell>
                <TableCell sx={{ borderBottom: "none" }}>
                  <Chip
                    size="small"
                    label={risk.label}
                    sx={{
                      borderRadius: 0,
                      fontWeight: 700,
                      bgcolor: risk.label === "Low" ? "#DCE9DE" : risk.label === "Moderate" ? "#E3D7C4" : "#F6D9CC",
                      color: risk.label === "Low" ? "#046A38" : risk.label === "Moderate" ? "#8A5A00" : "#B8321A",
                    }}
                  />
                </TableCell>
                <TableCell sx={{ borderBottom: "none" }}>
                  <LinearProgress
                    color={h.risk_contribution > 0.35 ? "warning" : "primary"}
                    variant="determinate"
                    value={Math.min(Math.max(h.risk_contribution * 100, 0), 100)}
                    sx={{ height: 8, borderRadius: 0 }}
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Paper>
  );
}

function MstDiagnostics({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">MST concentration and indirect connections</Typography>
      <Typography color="text.secondary" gutterBottom>
        Clusters retain MST edges with correlation ≥ {analysis.mst.cluster_correlation_floor.toFixed(2)}. Paths use the
        unique route through the complete NIFTY 200 MST.
      </Typography>
      <Alert
        severity={
          analysis.mst.stability.confidence === "high"
            ? "success"
            : analysis.mst.stability.confidence === "moderate"
            ? "info"
            : "warning"
        }
        sx={{ mt: 2 }}
      >
        MST stability: {analysis.mst.stability.confidence}. {analysis.mst.stability.reason}
      </Alert>
      <Stack direction={{ xs: "column", md: "row" }} spacing={3} sx={{ mt: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">Portfolio clusters</Typography>
          <Stack spacing={1}>
            {analysis.mst.clusters.map((c) => (
              <Box key={c.cluster_id} sx={{ py: 1.25, px: 1.5, bgcolor: "#E3D7C4", mb: 1, boxShadow: "0 2px 4px rgba(41,45,42,0.06)" }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <Typography sx={{ fontWeight: 700 }}>{c.cluster_id}</Typography>
                  <Chip size="small" label={formatPercent(c.weight * 100, 1)} />
                </Stack>
                <Typography variant="body2">{c.holding_symbols.join(", ")}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {c.full_node_count} full-MST nodes in component
                </Typography>
              </Box>
            ))}
          </Stack>
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">Direct holding links</Typography>
          {!analysis.mst.direct_edges.length && (
            <Typography color="text.secondary">No holdings are directly adjacent.</Typography>
          )}
          {analysis.mst.direct_edges.map((e) => (
            <Stack
              direction="row"
              key={`${e.symbol_a}-${e.symbol_b}`}
              sx={{ justifyContent: "space-between", py: 1, px: 1.5, bgcolor: "#E3D7C4", mb: 0.75, boxShadow: "0 2px 4px rgba(41,45,42,0.06)" }}
            >
              <Typography>
                {e.symbol_a} ↔ {e.symbol_b}
              </Typography>
              <Chip
                size="small"
                label={`ρ ${e.correlation.toFixed(2)}`}
                color={e.correlation >= 0.7 ? "warning" : "default"}
              />
            </Stack>
          ))}
          <Typography variant="h6" sx={{ mt: 2 }}>
            Bridge stocks
          </Typography>
          {analysis.mst.bridge_stocks.slice(0, 6).map((b) => (
            <Stack direction="row" key={b.symbol} sx={{ justifyContent: "space-between", py: 0.75 }}>
              <Typography>
                {b.symbol}
                {b.is_holding ? " (held)" : ""}
              </Typography>
              <Typography variant="body2">{b.path_pair_count} paths</Typography>
            </Stack>
          ))}
        </Box>
      </Stack>
    </Paper>
  );
}

function StressPanel({
  analysis,
  loading,
  onRun,
}: {
  analysis: PortfolioAnalysisResponse;
  loading: boolean;
  onRun: (s: PortfolioStressInput) => void;
}) {
  const [kind, setKind] = useState<"stock" | "industry">("stock");
  const stockTargets = analysis.holdings.map((h) => h.symbol);
  const industryTargets = analysis.concentration.industry_weights.map((i) => i.industry);
  const targets = kind === "stock" ? stockTargets : industryTargets;
  const [target, setTarget] = useState(stockTargets[0] ?? "");
  const [shock, setShock] = useState(-10);
  const selectedTarget = targets.includes(target) ? target : targets[0] ?? "";

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Hypothetical stress test</Typography>
      <Typography color="text.secondary" gutterBottom>
        Apply a holding shock with historical beta propagation, or a parallel shock to one represented industry.
      </Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} className="no-print" sx={{ mt: 2 }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="stress-kind">Shock type</InputLabel>
          <Select
            labelId="stress-kind"
            label="Shock type"
            value={kind}
            onChange={(e) => {
              const k = e.target.value as "stock" | "industry";
              setKind(k);
              setTarget(k === "stock" ? stockTargets[0] ?? "" : industryTargets[0] ?? "");
            }}
          >
            <MenuItem value="stock">Selected holding</MenuItem>
            <MenuItem value="industry">Selected industry</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel id="stress-target">Target</InputLabel>
          <Select
            labelId="stress-target"
            label="Target"
            value={selectedTarget}
            onChange={(e) => setTarget(e.target.value)}
          >
            {targets.map((t) => (
              <MenuItem value={t} key={t}>
                {t}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="Shock (%)"
          type="number"
          value={shock}
          onChange={(e) => setShock(Number(e.target.value))}
          slotProps={{ htmlInput: { min: -30, max: 30, step: 1 } }}
        />
        <Button
          variant="contained"
          disabled={loading || !selectedTarget || shock === 0 || shock < -30 || shock > 30}
          onClick={() => onRun({ kind, target: selectedTarget, shock_percent: shock })}
        >
          Run stress
        </Button>
      </Stack>
      {analysis.stress && (
        <Stack spacing={2} sx={{ mt: 3 }}>
          <Alert severity="warning">
            Estimated portfolio impact: <strong>{analysis.stress.portfolio_impact_percent.toFixed(2)}%</strong> from a{" "}
            {analysis.stress.shock_percent.toFixed(1)}% shock to {analysis.stress.target}. {analysis.stress.disclaimer}
          </Alert>
          <Typography variant="body2">
            <strong>Method:</strong> {analysis.stress.method}
          </Typography>
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Holding</TableCell>
                  <TableCell align="right">Sensitivity</TableCell>
                  <TableCell align="right">Estimated return</TableCell>
                  <TableCell align="right">Portfolio impact</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {analysis.stress.results.map((r) => (
                  <TableRow key={r.symbol}>
                    <TableCell>{r.symbol}</TableCell>
                    <TableCell align="right">{r.sensitivity.toFixed(2)}</TableCell>
                    <TableCell align="right">{r.estimated_return_percent.toFixed(2)}%</TableCell>
                    <TableCell align="right">{r.portfolio_contribution_percent.toFixed(2)}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
          <Box component="ul" sx={{ m: 0 }}>
            {analysis.stress.assumptions.map((a) => (
              <li key={a}>
                <Typography variant="body2">{a}</Typography>
              </li>
            ))}
          </Box>
        </Stack>
      )}
    </Paper>
  );
}

function HoldingTable({ holdings }: { holdings: PortfolioHoldingAnalytics[] }) {
  return (
    <Paper sx={{ p: 3, overflowX: "auto" }}>
      <Typography variant="h5" gutterBottom>
        Holdings and current divergence
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Holding</TableCell>
            <TableCell>Industry</TableCell>
            <TableCell align="right">Weight</TableCell>
            <TableCell align="right">20-day divergence</TableCell>
            <TableCell>Band</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {holdings.map((h) => (
            <TableRow key={h.symbol}>
              <TableCell>
                <MuiLink component={Link} to={`/companies/${h.symbol}`} sx={{ fontWeight: 700 }}>
                  {h.symbol}
                </MuiLink>
              </TableCell>
              <TableCell>{h.industry}</TableCell>
              <TableCell align="right">{formatPercent(h.weight * 100, 1)}</TableCell>
              <TableCell
                align="right"
                sx={{
                  color: h.divergence_20d !== null && h.divergence_20d >= 0 ? "success.main" : "error.main",
                  fontWeight: 700,
                }}
              >
                {h.divergence_20d === null ? "—" : `${h.divergence_20d > 0 ? "+" : ""}${h.divergence_20d.toFixed(2)}σ`}
              </TableCell>
              <TableCell>
                {h.divergence_band ? (
                  <Chip
                    size="small"
                    label={h.divergence_band}
                    color={bandColor[h.divergence_band as keyof typeof bandColor] ?? "default"}
                  />
                ) : (
                  "Unavailable"
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}

function MethodAndLimitations({ analysis }: { analysis: PortfolioAnalysisResponse }) {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Method and limitations</Typography>
      <Typography variant="body2" sx={{ mt: 1 }}>
        {analysis.envelope.return_frequency}; {analysis.envelope.annualisation_factor}-day annualisation;{" "}
        {analysis.envelope.weighting_assumption}; {analysis.envelope.missing_data_rule}.
      </Typography>
      <Box component="ul" sx={{ mb: 0 }}>
        {analysis.limitations.map((l) => (
          <li key={l}>
            <Typography variant="body2">{l}</Typography>
          </li>
        ))}
      </Box>
    </Paper>
  );
}
