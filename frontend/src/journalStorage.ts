/**
 * PRISM Journal & Portfolio Snapshot Storage Service
 *
 * Local-first, anonymous storage for Research Notes, Investment Decisions, and Portfolio Snapshots.
 * Uses native browser IndexedDB ('prism_journal_db', version 2) with automatic in-memory fallback
 * for headless/SSR/test environments where window.indexedDB may not be available.
 *
 * Every record enforces: id, schemaVersion, createdAt (ISO), and updatedAt (ISO).
 */

export interface ResearchNote {
  id: string;
  schemaVersion: number;
  createdAt: string;
  updatedAt: string;
  symbol: string;
  content: string;
  tags: string[];
}

export type DecisionType = "Buy" | "Hold" | "Sell" | "Review";

export interface DecisionContextSnapshot {
  riskScore?: number | null;
  riskLabel?: string | null;
  sectorDivergenceScore?: number | null;
  sectorDivergenceHorizon?: number | null;
  portfolioWeight?: number | null;
  mstCluster?: string | null;
  capturedAt?: string;
}

export interface InvestmentDecision {
  id: string;
  schemaVersion: number;
  createdAt: string;
  updatedAt: string;
  symbol: string;
  decisionType: DecisionType;
  decisionDate: string; // YYYY-MM-DD
  rationale: string;
  tags: string[];
  snapshot: DecisionContextSnapshot;
}

/* ─── Feature C: Portfolio Snapshots & Metrics ─── */

export interface PortfolioSnapshotHolding {
  symbol: string;
  weight: number;
  quantity?: number;
  buyPrice?: number;
  currentPrice?: number | null;
  annualizedVolatility?: number | null;
  marginalRisk?: number | null;
  riskContribution?: number | null;
  divergenceScore?: number | null;
}

export interface PortfolioSnapshotSectorExposure {
  sector: string;
  weight: number;
}

export interface PortfolioSnapshotDiversification {
  holdingHhi?: number | null;
  industryHhi?: number | null;
  effectiveHoldings?: number | null;
  effectiveIndustries?: number | null;
  diversificationScore?: number | null;
}

export interface PortfolioSnapshotRiskMetrics {
  totalReturn?: number | null;
  annualizedReturn?: number | null;
  annualizedVolatility?: number | null;
  downsideVolatility?: number | null;
  maxDrawdown?: number | null;
  portfolioRiskScore?: number | null;
  portfolioClassification?: string | null;
}

export interface PortfolioSnapshotMstContext {
  runId?: string | null;
  edgeCount?: number | null;
  directEdgeCount?: number | null;
  clusterCount?: number | null;
  clusterHhi?: number | null;
  bridgeStocks?: string[];
}

export interface PortfolioSnapshotCalculationMeta {
  horizon: number; // e.g. 250 or 20
  lookbackStart?: string | null;
  asOf?: string | null;
  parameters?: Record<string, unknown>;
  schemaVersion?: number;
}

export interface PortfolioSnapshot {
  id: string;
  schemaVersion: number;
  createdAt: string; // ISO
  updatedAt: string; // ISO
  name: string;
  description?: string;
  calculationMeta: PortfolioSnapshotCalculationMeta;
  holdings: PortfolioSnapshotHolding[];
  sectorExposures: PortfolioSnapshotSectorExposure[];
  riskMetrics: PortfolioSnapshotRiskMetrics;
  diversification: PortfolioSnapshotDiversification;
  mstContext: PortfolioSnapshotMstContext;
}

export interface JournalBackup {
  version: number;
  exportedAt: string;
  notes: ResearchNote[];
  decisions: InvestmentDecision[];
  snapshots?: PortfolioSnapshot[];
}

const DB_NAME = "prism_journal_db";
const DB_VERSION = 2;
const STORE_NOTES = "research_notes";
const STORE_DECISIONS = "investment_decisions";
const STORE_SNAPSHOTS = "portfolio_snapshots";
export const CURRENT_SCHEMA_VERSION = 1;

/* ─── In-Memory Fallback Store (for test/SSR environments) ─── */

class MemoryStorage {
  notes = new Map<string, ResearchNote>();
  decisions = new Map<string, InvestmentDecision>();
  snapshots = new Map<string, PortfolioSnapshot>();

  clear() {
    this.notes.clear();
    this.decisions.clear();
    this.snapshots.clear();
  }
}

const memoryStore = new MemoryStorage();

function isIndexedDBSupported(): boolean {
  try {
    return typeof window !== "undefined" && "indexedDB" in window && window.indexedDB !== null;
  } catch {
    return false;
  }
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!isIndexedDBSupported()) {
      return reject(new Error("IndexedDB not supported in current environment"));
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      if (!db.objectStoreNames.contains(STORE_NOTES)) {
        const noteStore = db.createObjectStore(STORE_NOTES, { keyPath: "id" });
        noteStore.createIndex("by_symbol", "symbol", { unique: false });
        noteStore.createIndex("by_updatedAt", "updatedAt", { unique: false });
      }

      if (!db.objectStoreNames.contains(STORE_DECISIONS)) {
        const decisionStore = db.createObjectStore(STORE_DECISIONS, { keyPath: "id" });
        decisionStore.createIndex("by_symbol", "symbol", { unique: false });
        decisionStore.createIndex("by_decisionDate", "decisionDate", { unique: false });
      }

      if (!db.objectStoreNames.contains(STORE_SNAPSHOTS)) {
        const snapshotStore = db.createObjectStore(STORE_SNAPSHOTS, { keyPath: "id" });
        snapshotStore.createIndex("by_createdAt", "createdAt", { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Failed to open IndexedDB"));
  });
}

function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `rec-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/* ─── Validation & Safe Parsing ─── */

export function validateNote(raw: unknown): ResearchNote | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;

  if (typeof obj.id !== "string" || !obj.id.trim()) return null;
  if (typeof obj.symbol !== "string" || !obj.symbol.trim()) return null;
  if (typeof obj.content !== "string") return null;

  const schemaVersion = typeof obj.schemaVersion === "number" ? obj.schemaVersion : CURRENT_SCHEMA_VERSION;
  const createdAt = typeof obj.createdAt === "string" ? obj.createdAt : new Date().toISOString();
  const updatedAt = typeof obj.updatedAt === "string" ? obj.updatedAt : createdAt;

  const rawTags = Array.isArray(obj.tags) ? obj.tags : [];
  const tags: string[] = rawTags
    .filter((t): t is string => typeof t === "string")
    .map((t) => t.trim())
    .filter(Boolean);

  return {
    id: obj.id.trim(),
    schemaVersion,
    createdAt,
    updatedAt,
    symbol: obj.symbol.trim().toUpperCase(),
    content: obj.content,
    tags,
  };
}

export function validateDecision(raw: unknown): InvestmentDecision | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;

  if (typeof obj.id !== "string" || !obj.id.trim()) return null;
  if (typeof obj.symbol !== "string" || !obj.symbol.trim()) return null;

  const validTypes: DecisionType[] = ["Buy", "Hold", "Sell", "Review"];
  const decisionType = validTypes.includes(obj.decisionType as DecisionType)
    ? (obj.decisionType as DecisionType)
    : "Review";

  const decisionDate =
    typeof obj.decisionDate === "string" && /^\d{4}-\d{2}-\d{2}/.test(obj.decisionDate)
      ? obj.decisionDate.substring(0, 10)
      : new Date().toISOString().substring(0, 10);

  const rationale = typeof obj.rationale === "string" ? obj.rationale : "";

  const rawTags = Array.isArray(obj.tags) ? obj.tags : [];
  const tags: string[] = rawTags
    .filter((t): t is string => typeof t === "string")
    .map((t) => t.trim())
    .filter(Boolean);

  const rawSnap = typeof obj.snapshot === "object" && obj.snapshot !== null ? (obj.snapshot as Record<string, unknown>) : {};

  // Crucial: Use null for any unavailable value; never store 0 as substitute for missing data
  const snapshot: DecisionContextSnapshot = {
    riskScore: typeof rawSnap.riskScore === "number" ? rawSnap.riskScore : null,
    riskLabel: typeof rawSnap.riskLabel === "string" ? rawSnap.riskLabel : null,
    sectorDivergenceScore: typeof rawSnap.sectorDivergenceScore === "number" ? rawSnap.sectorDivergenceScore : null,
    sectorDivergenceHorizon: typeof rawSnap.sectorDivergenceHorizon === "number" ? rawSnap.sectorDivergenceHorizon : null,
    portfolioWeight: typeof rawSnap.portfolioWeight === "number" ? rawSnap.portfolioWeight : null,
    mstCluster: typeof rawSnap.mstCluster === "string" ? rawSnap.mstCluster : null,
    capturedAt: typeof rawSnap.capturedAt === "string" ? rawSnap.capturedAt : new Date().toISOString(),
  };

  const schemaVersion = typeof obj.schemaVersion === "number" ? obj.schemaVersion : CURRENT_SCHEMA_VERSION;
  const createdAt = typeof obj.createdAt === "string" ? obj.createdAt : new Date().toISOString();
  const updatedAt = typeof obj.updatedAt === "string" ? obj.updatedAt : createdAt;

  return {
    id: obj.id.trim(),
    schemaVersion,
    createdAt,
    updatedAt,
    symbol: obj.symbol.trim().toUpperCase(),
    decisionType,
    decisionDate,
    rationale,
    tags,
    snapshot,
  };
}

export function validatePortfolioSnapshot(raw: unknown): PortfolioSnapshot | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;

  if (typeof obj.id !== "string" || !obj.id.trim()) return null;
  if (typeof obj.name !== "string" || !obj.name.trim()) return null;

  const schemaVersion = typeof obj.schemaVersion === "number" ? obj.schemaVersion : CURRENT_SCHEMA_VERSION;
  const createdAt = typeof obj.createdAt === "string" ? obj.createdAt : new Date().toISOString();
  const updatedAt = typeof obj.updatedAt === "string" ? obj.updatedAt : createdAt;

  // Calculation Meta
  const rawMeta = typeof obj.calculationMeta === "object" && obj.calculationMeta !== null ? (obj.calculationMeta as Record<string, unknown>) : {};
  const calculationMeta: PortfolioSnapshotCalculationMeta = {
    horizon: typeof rawMeta.horizon === "number" ? rawMeta.horizon : 250,
    lookbackStart: typeof rawMeta.lookbackStart === "string" ? rawMeta.lookbackStart : null,
    asOf: typeof rawMeta.asOf === "string" ? rawMeta.asOf : null,
    parameters: typeof rawMeta.parameters === "object" && rawMeta.parameters !== null ? (rawMeta.parameters as Record<string, unknown>) : {},
    schemaVersion: typeof rawMeta.schemaVersion === "number" ? rawMeta.schemaVersion : CURRENT_SCHEMA_VERSION,
  };

  // Holdings
  const rawHoldings = Array.isArray(obj.holdings) ? obj.holdings : [];
  const holdings: PortfolioSnapshotHolding[] = [];
  for (const h of rawHoldings) {
    if (h && typeof h === "object" && typeof h.symbol === "string" && h.symbol.trim()) {
      holdings.push({
        symbol: h.symbol.trim().toUpperCase(),
        weight: typeof h.weight === "number" ? h.weight : 0,
        quantity: typeof h.quantity === "number" ? h.quantity : undefined,
        buyPrice: typeof h.buyPrice === "number" ? h.buyPrice : undefined,
        currentPrice: typeof h.currentPrice === "number" ? h.currentPrice : null,
        annualizedVolatility: typeof h.annualizedVolatility === "number" ? h.annualizedVolatility : null,
        marginalRisk: typeof h.marginalRisk === "number" ? h.marginalRisk : null,
        riskContribution: typeof h.riskContribution === "number" ? h.riskContribution : null,
        divergenceScore: typeof h.divergenceScore === "number" ? h.divergenceScore : null,
      });
    }
  }

  // Sector exposures
  const rawSectors = Array.isArray(obj.sectorExposures) ? obj.sectorExposures : [];
  const sectorExposures: PortfolioSnapshotSectorExposure[] = [];
  for (const s of rawSectors) {
    if (s && typeof s === "object" && typeof s.sector === "string") {
      sectorExposures.push({
        sector: s.sector,
        weight: typeof s.weight === "number" ? s.weight : 0,
      });
    }
  }

  // Risk metrics - strict null handling
  const rawRisk = typeof obj.riskMetrics === "object" && obj.riskMetrics !== null ? (obj.riskMetrics as Record<string, unknown>) : {};
  const riskMetrics: PortfolioSnapshotRiskMetrics = {
    totalReturn: typeof rawRisk.totalReturn === "number" ? rawRisk.totalReturn : null,
    annualizedReturn: typeof rawRisk.annualizedReturn === "number" ? rawRisk.annualizedReturn : null,
    annualizedVolatility: typeof rawRisk.annualizedVolatility === "number" ? rawRisk.annualizedVolatility : null,
    downsideVolatility: typeof rawRisk.downsideVolatility === "number" ? rawRisk.downsideVolatility : null,
    maxDrawdown: typeof rawRisk.maxDrawdown === "number" ? rawRisk.maxDrawdown : null,
    portfolioRiskScore: typeof rawRisk.portfolioRiskScore === "number" ? rawRisk.portfolioRiskScore : null,
    portfolioClassification: typeof rawRisk.portfolioClassification === "string" ? rawRisk.portfolioClassification : null,
  };

  // Diversification
  const rawDiv = typeof obj.diversification === "object" && obj.diversification !== null ? (obj.diversification as Record<string, unknown>) : {};
  const diversification: PortfolioSnapshotDiversification = {
    holdingHhi: typeof rawDiv.holdingHhi === "number" ? rawDiv.holdingHhi : null,
    industryHhi: typeof rawDiv.industryHhi === "number" ? rawDiv.industryHhi : null,
    effectiveHoldings: typeof rawDiv.effectiveHoldings === "number" ? rawDiv.effectiveHoldings : null,
    effectiveIndustries: typeof rawDiv.effectiveIndustries === "number" ? rawDiv.effectiveIndustries : null,
    diversificationScore: typeof rawDiv.diversificationScore === "number" ? rawDiv.diversificationScore : null,
  };

  // MST Context
  const rawMst = typeof obj.mstContext === "object" && obj.mstContext !== null ? (obj.mstContext as Record<string, unknown>) : {};
  const rawBridges = Array.isArray(rawMst.bridgeStocks) ? rawMst.bridgeStocks : [];
  const bridgeStocks = rawBridges.filter((b): b is string => typeof b === "string");

  const mstContext: PortfolioSnapshotMstContext = {
    runId: typeof rawMst.runId === "string" ? rawMst.runId : null,
    edgeCount: typeof rawMst.edgeCount === "number" ? rawMst.edgeCount : null,
    directEdgeCount: typeof rawMst.directEdgeCount === "number" ? rawMst.directEdgeCount : null,
    clusterCount: typeof rawMst.clusterCount === "number" ? rawMst.clusterCount : null,
    clusterHhi: typeof rawMst.clusterHhi === "number" ? rawMst.clusterHhi : null,
    bridgeStocks,
  };

  return {
    id: obj.id.trim(),
    schemaVersion,
    createdAt,
    updatedAt,
    name: obj.name.trim(),
    description: typeof obj.description === "string" ? obj.description : undefined,
    calculationMeta,
    holdings,
    sectorExposures,
    riskMetrics,
    diversification,
    mstContext,
  };
}

/* ─── Notes Storage Operations ─── */

export async function getNotesBySymbol(symbol: string): Promise<ResearchNote[]> {
  const norm = symbol.trim().toUpperCase();
  if (!isIndexedDBSupported()) {
    const list = Array.from(memoryStore.notes.values()).filter((n) => n.symbol === norm);
    return list.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NOTES, "readonly");
      const store = tx.objectStore(STORE_NOTES);
      const index = store.index("by_symbol");
      const request = index.getAll(norm);

      request.onsuccess = () => {
        const results: ResearchNote[] = [];
        for (const item of request.result || []) {
          const validated = validateNote(item);
          if (validated) results.push(validated);
        }
        results.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  } catch {
    const list = Array.from(memoryStore.notes.values()).filter((n) => n.symbol === norm);
    return list.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }
}

export async function getAllNotes(): Promise<ResearchNote[]> {
  if (!isIndexedDBSupported()) {
    return Array.from(memoryStore.notes.values());
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NOTES, "readonly");
      const store = tx.objectStore(STORE_NOTES);
      const request = store.getAll();

      request.onsuccess = () => {
        const results: ResearchNote[] = [];
        for (const item of request.result || []) {
          const validated = validateNote(item);
          if (validated) results.push(validated);
        }
        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  } catch {
    return Array.from(memoryStore.notes.values());
  }
}

export async function saveNote(
  input: { id?: string; symbol: string; content: string; tags: string[] }
): Promise<ResearchNote> {
  const now = new Date().toISOString();
  const id = input.id && input.id.trim() ? input.id.trim() : generateId();
  const symbol = input.symbol.trim().toUpperCase();

  let createdAt = now;
  if (input.id) {
    const existing = isIndexedDBSupported()
      ? (await getAllNotes()).find((n) => n.id === input.id)
      : memoryStore.notes.get(input.id);
    if (existing) {
      createdAt = existing.createdAt;
    }
  }

  const note: ResearchNote = {
    id,
    schemaVersion: CURRENT_SCHEMA_VERSION,
    createdAt,
    updatedAt: now,
    symbol,
    content: input.content,
    tags: Array.from(new Set(input.tags.map((t) => t.trim()).filter(Boolean))),
  };

  if (!isIndexedDBSupported()) {
    memoryStore.notes.set(note.id, note);
    return note;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NOTES, "readwrite");
      const store = tx.objectStore(STORE_NOTES);
      const req = store.put(note);
      req.onsuccess = () => resolve(note);
      req.onerror = () => reject(req.error);
    });
  } catch {
    memoryStore.notes.set(note.id, note);
    return note;
  }
}

export async function deleteNote(id: string): Promise<void> {
  if (!isIndexedDBSupported()) {
    memoryStore.notes.delete(id);
    return;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NOTES, "readwrite");
      const store = tx.objectStore(STORE_NOTES);
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    memoryStore.notes.delete(id);
  }
}

export async function getNotesCountMap(): Promise<Record<string, number>> {
  const notes = await getAllNotes();
  const map: Record<string, number> = {};
  for (const n of notes) {
    map[n.symbol] = (map[n.symbol] || 0) + 1;
  }
  return map;
}

/* ─── Investment Decisions Storage Operations ─── */

export async function getDecisionsBySymbol(symbol: string): Promise<InvestmentDecision[]> {
  const norm = symbol.trim().toUpperCase();
  if (!isIndexedDBSupported()) {
    const list = Array.from(memoryStore.decisions.values()).filter((d) => d.symbol === norm);
    return list.sort((a, b) => new Date(b.decisionDate).getTime() - new Date(a.decisionDate).getTime());
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_DECISIONS, "readonly");
      const store = tx.objectStore(STORE_DECISIONS);
      const index = store.index("by_symbol");
      const request = index.getAll(norm);

      request.onsuccess = () => {
        const results: InvestmentDecision[] = [];
        for (const item of request.result || []) {
          const validated = validateDecision(item);
          if (validated) results.push(validated);
        }
        results.sort((a, b) => new Date(b.decisionDate).getTime() - new Date(a.decisionDate).getTime());
        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  } catch {
    const list = Array.from(memoryStore.decisions.values()).filter((d) => d.symbol === norm);
    return list.sort((a, b) => new Date(b.decisionDate).getTime() - new Date(a.decisionDate).getTime());
  }
}

export async function getAllDecisions(): Promise<InvestmentDecision[]> {
  if (!isIndexedDBSupported()) {
    return Array.from(memoryStore.decisions.values());
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_DECISIONS, "readonly");
      const store = tx.objectStore(STORE_DECISIONS);
      const request = store.getAll();

      request.onsuccess = () => {
        const results: InvestmentDecision[] = [];
        for (const item of request.result || []) {
          const validated = validateDecision(item);
          if (validated) results.push(validated);
        }
        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  } catch {
    return Array.from(memoryStore.decisions.values());
  }
}

export async function getDecisionsCountMap(): Promise<Record<string, number>> {
  const decisions = await getAllDecisions();
  const map: Record<string, number> = {};
  for (const d of decisions) {
    map[d.symbol] = (map[d.symbol] || 0) + 1;
  }
  return map;
}

export async function saveDecision(
  input: {
    id?: string;
    symbol: string;
    decisionType: DecisionType;
    decisionDate: string;
    rationale: string;
    tags: string[];
    snapshot: DecisionContextSnapshot;
  }
): Promise<InvestmentDecision> {
  const now = new Date().toISOString();
  const id = input.id && input.id.trim() ? input.id.trim() : generateId();
  const symbol = input.symbol.trim().toUpperCase();

  let createdAt = now;
  if (input.id) {
    const existing = isIndexedDBSupported()
      ? (await getAllDecisions()).find((d) => d.id === input.id)
      : memoryStore.decisions.get(input.id);
    if (existing) {
      createdAt = existing.createdAt;
    }
  }

  const decision: InvestmentDecision = {
    id,
    schemaVersion: CURRENT_SCHEMA_VERSION,
    createdAt,
    updatedAt: now,
    symbol,
    decisionType: input.decisionType,
    decisionDate: input.decisionDate,
    rationale: input.rationale,
    tags: Array.from(new Set(input.tags.map((t) => t.trim()).filter(Boolean))),
    snapshot: {
      riskScore: input.snapshot.riskScore,
      riskLabel: input.snapshot.riskLabel,
      sectorDivergenceScore: input.snapshot.sectorDivergenceScore,
      sectorDivergenceHorizon: input.snapshot.sectorDivergenceHorizon,
      portfolioWeight: input.snapshot.portfolioWeight,
      mstCluster: input.snapshot.mstCluster,
      capturedAt: input.snapshot.capturedAt || now,
    },
  };

  if (!isIndexedDBSupported()) {
    memoryStore.decisions.set(decision.id, decision);
    return decision;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_DECISIONS, "readwrite");
      const store = tx.objectStore(STORE_DECISIONS);
      const req = store.put(decision);
      req.onsuccess = () => resolve(decision);
      req.onerror = () => reject(req.error);
    });
  } catch {
    memoryStore.decisions.set(decision.id, decision);
    return decision;
  }
}

export async function deleteDecision(id: string): Promise<void> {
  if (!isIndexedDBSupported()) {
    memoryStore.decisions.delete(id);
    return;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_DECISIONS, "readwrite");
      const store = tx.objectStore(STORE_DECISIONS);
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    memoryStore.decisions.delete(id);
  }
}

/* ─── Feature C: Portfolio Snapshots Storage Operations ─── */

export async function getAllPortfolioSnapshots(): Promise<PortfolioSnapshot[]> {
  if (!isIndexedDBSupported()) {
    const list = Array.from(memoryStore.snapshots.values());
    return list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_SNAPSHOTS, "readonly");
      const store = tx.objectStore(STORE_SNAPSHOTS);
      const request = store.getAll();

      request.onsuccess = () => {
        const results: PortfolioSnapshot[] = [];
        for (const item of request.result || []) {
          const validated = validatePortfolioSnapshot(item);
          if (validated) results.push(validated);
        }
        results.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        resolve(results);
      };
      request.onerror = () => reject(request.error);
    });
  } catch {
    const list = Array.from(memoryStore.snapshots.values());
    return list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }
}

export async function getPortfolioSnapshotById(id: string): Promise<PortfolioSnapshot | null> {
  const snapshots = await getAllPortfolioSnapshots();
  return snapshots.find((s) => s.id === id) || null;
}

export async function savePortfolioSnapshot(
  input: Omit<PortfolioSnapshot, "id" | "schemaVersion" | "createdAt" | "updatedAt"> & { id?: string }
): Promise<PortfolioSnapshot> {
  const now = new Date().toISOString();
  const id = input.id && input.id.trim() ? input.id.trim() : generateId();

  const snapshot: PortfolioSnapshot = {
    id,
    schemaVersion: CURRENT_SCHEMA_VERSION,
    createdAt: now,
    updatedAt: now,
    name: input.name.trim(),
    description: input.description,
    calculationMeta: input.calculationMeta,
    holdings: input.holdings,
    sectorExposures: input.sectorExposures,
    riskMetrics: input.riskMetrics,
    diversification: input.diversification,
    mstContext: input.mstContext,
  };

  if (!isIndexedDBSupported()) {
    memoryStore.snapshots.set(snapshot.id, snapshot);
    return snapshot;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_SNAPSHOTS, "readwrite");
      const store = tx.objectStore(STORE_SNAPSHOTS);
      const req = store.put(snapshot);
      req.onsuccess = () => resolve(snapshot);
      req.onerror = (e) => {
        // Handle storage quota exceeded gracefully
        if (req.error?.name === "QuotaExceededError") {
          reject(new Error("Browser storage is full. Please export a backup and delete older snapshots to free up space."));
        } else {
          reject(req.error || new Error("Failed to save portfolio snapshot"));
        }
      };
    });
  } catch (err) {
    if (err instanceof Error && err.message.includes("full")) {
      throw err;
    }
    memoryStore.snapshots.set(snapshot.id, snapshot);
    return snapshot;
  }
}

export async function deletePortfolioSnapshot(id: string): Promise<void> {
  if (!isIndexedDBSupported()) {
    memoryStore.snapshots.delete(id);
    return;
  }

  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_SNAPSHOTS, "readwrite");
      const store = tx.objectStore(STORE_SNAPSHOTS);
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    memoryStore.snapshots.delete(id);
  }
}

/* ─── Backup & Restore (JSON Export / Import) ─── */

export async function exportJournalBackup(): Promise<string> {
  const [notes, decisions, snapshots] = await Promise.all([
    getAllNotes(),
    getAllDecisions(),
    getAllPortfolioSnapshots(),
  ]);
  const backup: JournalBackup = {
    version: DB_VERSION,
    exportedAt: new Date().toISOString(),
    notes,
    decisions,
    snapshots,
  };
  return JSON.stringify(backup, null, 2);
}

export async function importJournalBackup(
  jsonString: string
): Promise<{ importedNotes: number; importedDecisions: number; importedSnapshots: number; skipped: number }> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonString);
  } catch {
    throw new Error("Invalid JSON format in backup file");
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Backup file must contain a valid JSON object");
  }

  const obj = parsed as Record<string, unknown>;
  const rawNotes = Array.isArray(obj.notes) ? obj.notes : [];
  const rawDecisions = Array.isArray(obj.decisions) ? obj.decisions : [];
  const rawSnapshots = Array.isArray(obj.snapshots) ? obj.snapshots : [];

  let importedNotes = 0;
  let importedDecisions = 0;
  let importedSnapshots = 0;
  let skipped = 0;

  for (const item of rawNotes) {
    const note = validateNote(item);
    if (note) {
      await saveNote(note);
      importedNotes++;
    } else {
      skipped++;
    }
  }

  for (const item of rawDecisions) {
    const decision = validateDecision(item);
    if (decision) {
      await saveDecision(decision);
      importedDecisions++;
    } else {
      skipped++;
    }
  }

  for (const item of rawSnapshots) {
    const snapshot = validatePortfolioSnapshot(item);
    if (snapshot) {
      await savePortfolioSnapshot(snapshot);
      importedSnapshots++;
    } else {
      skipped++;
    }
  }

  return { importedNotes, importedDecisions, importedSnapshots, skipped };
}

/* ─── Test Helpers ─── */

export function _resetMemoryStoreForTests(): void {
  memoryStore.clear();
}
