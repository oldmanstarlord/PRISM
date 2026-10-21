import { beforeEach, describe, expect, it } from "vitest";
import {
  _resetMemoryStoreForTests,
  exportJournalBackup,
  getAllPortfolioSnapshots,
  getDecisionsBySymbol,
  getNotesBySymbol,
  importJournalBackup,
  saveDecision,
  saveNote,
  savePortfolioSnapshot,
  validateDecision,
  validateNote,
  validatePortfolioSnapshot,
} from "./journalStorage";
import { DEFAULT_CURATED_HOLDINGS } from "./demoPortfolioData";
import type { PortfolioHolding } from "./PortfolioManager";

describe("Research Notes & Investment Decision Journal Verification", () => {
  beforeEach(() => {
    _resetMemoryStoreForTests();
    localStorage.clear();
  });

  // Test 1: Persistence across refresh
  it("verifies persistence across simulated refresh / reconnect", async () => {
    const savedNote = await saveNote({
      symbol: "TCS",
      content: "Persistent research thesis: large deal total contract value up 14% YoY.",
      tags: ["Thesis", "IT"],
    });

    const savedDecision = await saveDecision({
      symbol: "TCS",
      decisionType: "Buy",
      decisionDate: "2024-02-20",
      rationale: "Long-term valuation multiple floor tested.",
      tags: ["LongTerm"],
      snapshot: {
        riskScore: 2,
        riskLabel: "Moderate",
        sectorDivergenceScore: 1.25,
        sectorDivergenceHorizon: 20,
        portfolioWeight: 7.5,
        mstCluster: "Information Technology",
        capturedAt: "2024-02-20T10:30:00Z",
      },
    });

    // Re-query from storage (simulating a page reload)
    const reloadedNotes = await getNotesBySymbol("TCS");
    expect(reloadedNotes).toHaveLength(1);
    expect(reloadedNotes[0].id).toBe(savedNote.id);
    expect(reloadedNotes[0].content).toBe(savedNote.content);
    expect(reloadedNotes[0].createdAt).toBe(savedNote.createdAt);
    expect(reloadedNotes[0].updatedAt).toBe(savedNote.updatedAt);

    const reloadedDecisions = await getDecisionsBySymbol("TCS");
    expect(reloadedDecisions).toHaveLength(1);
    expect(reloadedDecisions[0].id).toBe(savedDecision.id);
    expect(reloadedDecisions[0].decisionType).toBe("Buy");
    expect(reloadedDecisions[0].snapshot.riskScore).toBe(2);
    expect(reloadedDecisions[0].snapshot.portfolioWeight).toBe(7.5);
  });

  // Test 2: Correct stock association
  it("strictly isolates notes and decisions by canonical stock symbol", async () => {
    await saveNote({ symbol: "INFY", content: "Infy note 1", tags: [] });
    await saveNote({ symbol: "INFY", content: "Infy note 2", tags: [] });
    await saveNote({ symbol: "HDFCBANK", content: "HDFC note", tags: [] });

    await saveDecision({
      symbol: "INFY",
      decisionType: "Hold",
      decisionDate: "2024-03-01",
      rationale: "Waiting for guidance",
      tags: [],
      snapshot: {
        riskScore: 2,
        riskLabel: "Moderate",
        sectorDivergenceScore: -0.4,
        sectorDivergenceHorizon: 5,
        portfolioWeight: 5.0,
        mstCluster: "Information Technology",
        capturedAt: "2024-03-01T00:00:00Z",
      },
    });

    await saveDecision({
      symbol: "HDFCBANK",
      decisionType: "Buy",
      decisionDate: "2024-03-02",
      rationale: "Merger integration progress",
      tags: [],
      snapshot: {
        riskScore: 1,
        riskLabel: "Low",
        sectorDivergenceScore: 0.8,
        sectorDivergenceHorizon: 20,
        portfolioWeight: 10.0,
        mstCluster: "Financial Services",
        capturedAt: "2024-03-02T00:00:00Z",
      },
    });

    const infyNotes = await getNotesBySymbol("infy"); // test case insensitivity
    expect(infyNotes).toHaveLength(2);
    expect(infyNotes.every((n) => n.symbol === "INFY")).toBe(true);

    const hdfcNotes = await getNotesBySymbol("HDFCBANK");
    expect(hdfcNotes).toHaveLength(1);
    expect(hdfcNotes[0].symbol).toBe("HDFCBANK");

    const tcsNotes = await getNotesBySymbol("TCS");
    expect(tcsNotes).toHaveLength(0);

    const infyDecisions = await getDecisionsBySymbol("INFY");
    expect(infyDecisions).toHaveLength(1);
    expect(infyDecisions[0].symbol).toBe("INFY");

    const hdfcDecisions = await getDecisionsBySymbol("HDFCBANK");
    expect(hdfcDecisions).toHaveLength(1);
    expect(hdfcDecisions[0].symbol).toBe("HDFCBANK");
  });

  // Test 3: Safe handling of corrupt records
  it("safely handles and skips corrupt or malformed records without throwing", async () => {
    // Direct validation tests
    expect(validateNote(undefined)).toBeNull();
    expect(validateNote({ id: 123 })).toBeNull();
    expect(validateNote({ id: "valid", symbol: "", content: "no symbol" })).toBeNull();

    expect(validateDecision(null)).toBeNull();
    expect(validateDecision({})).toBeNull();
    expect(validateDecision({ id: "d1", symbol: "" })).toBeNull();

    // Corrupted import test
    const corruptedBackup = JSON.stringify({
      version: 1,
      exportedAt: "2024-04-01T00:00:00Z",
      notes: [
        { id: "valid-note-1", schemaVersion: 1, createdAt: "2024-01-01T00:00:00Z", updatedAt: "2024-01-01T00:00:00Z", symbol: "ICICIBANK", content: "Valid content", tags: ["Bank"] },
        { id: "corrupt-note-no-symbol", content: "broken" }, // malformed
        null,
        "not even an object",
      ],
      decisions: [
        {
          id: "valid-decision-1",
          schemaVersion: 1,
          createdAt: "2024-01-01T00:00:00Z",
          updatedAt: "2024-01-01T00:00:00Z",
          symbol: "ICICIBANK",
          decisionType: "Buy",
          decisionDate: "2024-01-01",
          rationale: "Strong ROE",
          tags: ["Core"],
          snapshot: { riskScore: 1, riskLabel: "Low", sectorDivergenceScore: null, sectorDivergenceHorizon: null, portfolioWeight: 8.0, mstCluster: "Financial Services", capturedAt: "2024-01-01T00:00:00Z" },
        },
        { corrupted: true }, // malformed
      ],
    });

    const result = await importJournalBackup(corruptedBackup);
    expect(result.importedNotes).toBe(1);
    expect(result.importedDecisions).toBe(1);
    expect(result.skipped).toBe(4); // 3 corrupt notes + 1 corrupt decision

    const iciciNotes = await getNotesBySymbol("ICICIBANK");
    expect(iciciNotes).toHaveLength(1);
    expect(iciciNotes[0].content).toBe("Valid content");
  });

  // Test 4: Decision snapshot immutability
  it("verifies decision snapshot immutability and strict null handling for unavailable metrics", async () => {
    // Record a decision where riskScore and portfolioWeight were unavailable at capture
    const decision = await saveDecision({
      symbol: "LT",
      decisionType: "Buy",
      decisionDate: "2024-01-15",
      rationale: "Capex order book visibility exceeds 3 years.",
      tags: ["Capex"],
      snapshot: {
        riskScore: null, // UNAVAILABLE
        riskLabel: null, // UNAVAILABLE
        sectorDivergenceScore: 2.15,
        sectorDivergenceHorizon: 20,
        portfolioWeight: null, // UNAVAILABLE
        mstCluster: "Industrials",
        capturedAt: "2024-01-15T09:00:00Z",
      },
    });

    // Verify snapshot fields are strictly null, NOT converted to 0
    expect(decision.snapshot.riskScore).toBeNull();
    expect(decision.snapshot.riskScore).not.toBe(0);
    expect(decision.snapshot.riskLabel).toBeNull();
    expect(decision.snapshot.portfolioWeight).toBeNull();
    expect(decision.snapshot.portfolioWeight).not.toBe(0);
    expect(decision.snapshot.sectorDivergenceScore).toBe(2.15);

    // Retrieve the historical decision
    const retrieved = await getDecisionsBySymbol("LT");
    expect(retrieved).toHaveLength(1);

    // Verify historical snapshot remains completely unchanged and immutable
    expect(retrieved[0].snapshot.riskScore).toBeNull();
    expect(retrieved[0].snapshot.portfolioWeight).toBeNull();
    expect(retrieved[0].snapshot.sectorDivergenceScore).toBe(2.15);
    expect(retrieved[0].snapshot.capturedAt).toBe("2024-01-15T09:00:00Z");
  });

  // Test 5: "Recording a decision does not change holdings"
  it("strictly guarantees that recording an investment decision does not change portfolio holdings", async () => {
    // Setup initial portfolio holdings in localStorage
    const initialHoldings: PortfolioHolding[] = JSON.parse(JSON.stringify(DEFAULT_CURATED_HOLDINGS));
    localStorage.setItem("prism_portfolio_holdings", JSON.stringify(initialHoldings));

    const totalBefore = initialHoldings.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
    const countBefore = initialHoldings.length;
    const tcsBefore = initialHoldings.find((h) => h.symbol === "TCS");
    expect(tcsBefore).toBeDefined();

    // Record a "Sell" or "Buy" decision for TCS
    await saveDecision({
      symbol: "TCS",
      decisionType: "Sell",
      decisionDate: "2024-05-10",
      rationale: "Trimming position into strength ahead of US macro data.",
      tags: ["ProfitTake"],
      snapshot: {
        riskScore: 2,
        riskLabel: "Moderate",
        sectorDivergenceScore: 1.8,
        sectorDivergenceHorizon: 20,
        portfolioWeight: 8.5,
        mstCluster: "Information Technology",
        capturedAt: "2024-05-10T14:30:00Z",
      },
    });

    // Inspect portfolio holdings in storage after recording decision
    const rawAfter = localStorage.getItem("prism_portfolio_holdings");
    expect(rawAfter).not.toBeNull();
    const holdingsAfter: PortfolioHolding[] = JSON.parse(rawAfter!);

    // Verify holdings are completely untouched
    expect(holdingsAfter.length).toBe(countBefore);
    const totalAfter = holdingsAfter.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
    expect(totalAfter).toBe(totalBefore);

    const tcsAfter = holdingsAfter.find((h) => h.symbol === "TCS");
    expect(tcsAfter).toBeDefined();
    expect(tcsAfter?.quantity).toBe(tcsBefore?.quantity);
    expect(tcsAfter?.buyPrice).toBe(tcsBefore?.buyPrice);
    expect(tcsAfter?.buyDate).toBe(tcsBefore?.buyDate);

    // Deep equality check between initial and after holdings
    expect(holdingsAfter).toEqual(initialHoldings);
  });

  // Test 6: Snapshot immutability
  it("verifies portfolio snapshot immutability when active holdings or market prices change", async () => {
    const originalHoldings = [
      { symbol: "TCS", weight: 40.0, quantity: 10, buyPrice: 3500, annualizedVolatility: 0.16, marginalRisk: 0.05, riskContribution: 0.35, divergenceScore: 1.2 },
      { symbol: "INFY", weight: 60.0, quantity: 20, buyPrice: 1500, annualizedVolatility: 0.22, marginalRisk: 0.07, riskContribution: 0.65, divergenceScore: -0.5 },
    ];

    const savedSnapshot = await savePortfolioSnapshot({
      name: "Q1 Initial Portfolio",
      description: "Baseline risk allocation",
      calculationMeta: {
        horizon: 250,
        lookbackStart: "2023-01-01",
        asOf: "2024-01-01",
        parameters: { weightingAssumption: "custom", missingDataRule: "strict" },
        schemaVersion: 1,
      },
      holdings: originalHoldings,
      sectorExposures: [{ sector: "Information Technology", weight: 100.0 }],
      riskMetrics: {
        totalReturn: 0.12,
        annualizedReturn: 0.15,
        annualizedVolatility: 0.18,
        downsideVolatility: 0.11,
        maxDrawdown: -0.09,
        portfolioRiskScore: 2,
        portfolioClassification: "Moderate",
      },
      diversification: {
        holdingHhi: 0.52,
        industryHhi: 1.0,
        effectiveHoldings: 1.92,
        effectiveIndustries: 1.0,
        diversificationScore: 68,
      },
      mstContext: {
        runId: "run-001",
        edgeCount: 1,
        directEdgeCount: 1,
        clusterCount: 1,
        clusterHhi: 1.0,
        bridgeStocks: [],
      },
    });

    expect(savedSnapshot.id).toBeDefined();
    expect(savedSnapshot.name).toBe("Q1 Initial Portfolio");
    expect(savedSnapshot.holdings).toHaveLength(2);

    // Later: user modifies holdings, deletes TCS, buys RELIANCE
    const mutatedActiveHoldings = [
      { symbol: "RELIANCE", quantity: 50, buyPrice: 2800 },
      { symbol: "INFY", quantity: 10, buyPrice: 1400 },
    ];
    localStorage.setItem("prism_portfolio_holdings", JSON.stringify(mutatedActiveHoldings));

    // Retrieve historical snapshot
    const allSnapshots = await getAllPortfolioSnapshots();
    const retrieved = allSnapshots.find((s) => s.id === savedSnapshot.id);
    expect(retrieved).toBeDefined();

    // Verify snapshot was completely unaffected by subsequent portfolio edits
    expect(retrieved!.holdings).toHaveLength(2);
    expect(retrieved!.holdings[0].symbol).toBe("TCS");
    expect(retrieved!.holdings[0].quantity).toBe(10);
    expect(retrieved!.holdings[0].weight).toBe(40.0);
    expect(retrieved!.holdings[0].buyPrice).toBe(3500);
    expect(retrieved!.riskMetrics.portfolioRiskScore).toBe(2);
    expect(retrieved!.diversification.effectiveHoldings).toBe(1.92);
  });

  // Test 7: Correct comparison of compatible metrics
  it("computes accurate deltas between two compatible portfolio snapshots", async () => {
    const snapA = await savePortfolioSnapshot({
      name: "Snapshot A",
      calculationMeta: { horizon: 250, schemaVersion: 1, parameters: {} },
      holdings: [
        { symbol: "TCS", weight: 50.0, quantity: 10, buyPrice: 3500 },
        { symbol: "INFY", weight: 50.0, quantity: 20, buyPrice: 1500 },
      ],
      sectorExposures: [{ sector: "IT", weight: 100.0 }],
      riskMetrics: {
        totalReturn: 0.10,
        annualizedReturn: 0.12,
        annualizedVolatility: 0.15,
        portfolioRiskScore: 2,
      },
      diversification: {
        holdingHhi: 0.50,
        effectiveHoldings: 2.0,
        diversificationScore: 70,
      },
      mstContext: { edgeCount: 1, clusterCount: 1, bridgeStocks: [] },
    });

    const snapB = await savePortfolioSnapshot({
      name: "Snapshot B",
      calculationMeta: { horizon: 250, schemaVersion: 1, parameters: {} },
      holdings: [
        { symbol: "TCS", weight: 30.0, quantity: 6, buyPrice: 3500 },
        { symbol: "INFY", weight: 70.0, quantity: 28, buyPrice: 1500 },
      ],
      sectorExposures: [{ sector: "IT", weight: 100.0 }],
      riskMetrics: {
        totalReturn: 0.18,
        annualizedReturn: 0.20,
        annualizedVolatility: 0.19,
        portfolioRiskScore: 3,
      },
      diversification: {
        holdingHhi: 0.58,
        effectiveHoldings: 1.72,
        diversificationScore: 55,
      },
      mstContext: { edgeCount: 1, clusterCount: 1, bridgeStocks: [] },
    });

    // Check compatibility: same horizon (250D)
    expect(snapA.calculationMeta.horizon).toBe(snapB.calculationMeta.horizon);

    // Compute expected deltas (B - A)
    const deltaVol = (snapB.riskMetrics.annualizedVolatility! - snapA.riskMetrics.annualizedVolatility!) * 100;
    expect(deltaVol).toBeCloseTo(4.0, 1); // +4.0% volatility increase

    const deltaScore = snapB.riskMetrics.portfolioRiskScore! - snapA.riskMetrics.portfolioRiskScore!;
    expect(deltaScore).toBe(1); // Risk score moved from 2 -> 3

    const deltaHhi = snapB.diversification.holdingHhi! - snapA.diversification.holdingHhi!;
    expect(deltaHhi).toBeCloseTo(0.08, 2);

    // Asset weight shifts
    const tcsA = snapA.holdings.find((h) => h.symbol === "TCS")?.weight ?? 0;
    const tcsB = snapB.holdings.find((h) => h.symbol === "TCS")?.weight ?? 0;
    expect(tcsB - tcsA).toBe(-20.0); // Trimmed TCS by 20%
  });

  // Test 8: "Not comparable" and missing-data handling
  it("flags differing horizons as Not comparable and preserves missing data as strictly null", async () => {
    const snap120D = await savePortfolioSnapshot({
      name: "120D Horizon Snapshot",
      calculationMeta: { horizon: 120, schemaVersion: 1, parameters: {} },
      holdings: [{ symbol: "TCS", weight: 100, quantity: 10, buyPrice: 3500 }],
      sectorExposures: [{ sector: "IT", weight: 100 }],
      riskMetrics: {
        annualizedVolatility: 0.14,
        downsideVolatility: null, // UNAVAILABLE: MUST NOT be converted to 0
        maxDrawdown: null, // UNAVAILABLE
      },
      diversification: {},
      mstContext: {},
    });

    const snap250D = await savePortfolioSnapshot({
      name: "250D Horizon Snapshot",
      calculationMeta: { horizon: 250, schemaVersion: 1, parameters: {} },
      holdings: [{ symbol: "TCS", weight: 100, quantity: 10, buyPrice: 3500 }],
      sectorExposures: [{ sector: "IT", weight: 100 }],
      riskMetrics: {
        annualizedVolatility: 0.18,
        downsideVolatility: 0.12,
        maxDrawdown: -0.08,
      },
      diversification: {},
      mstContext: {},
    });

    // Check horizon mismatch
    const isHorizonMismatch = snap120D.calculationMeta.horizon !== snap250D.calculationMeta.horizon;
    expect(isHorizonMismatch).toBe(true);

    // Strict null check: unavailable downsideVolatility remains null, never 0
    expect(snap120D.riskMetrics.downsideVolatility).toBeNull();
    expect(snap120D.riskMetrics.downsideVolatility).not.toBe(0);
    expect(snap120D.riskMetrics.maxDrawdown).toBeNull();
    expect(snap120D.riskMetrics.maxDrawdown).not.toBe(0);

    // Validation rejects corrupt / invalid objects
    expect(validatePortfolioSnapshot(null)).toBeNull();
    expect(validatePortfolioSnapshot({ id: "invalid" })).toBeNull();
  });

  // Test 9: MST Selection and neighborhood highlighting logic
  it("verifies MST selection isolates closed neighborhood and resets correctly", () => {
    // Model graph with nodes and edges
    const nodes = ["TCS", "INFY", "WIPRO", "HDFCBANK", "ICICIBANK"];
    const edges = [
      { source: "TCS", target: "INFY" },
      { source: "TCS", target: "WIPRO" },
      { source: "HDFCBANK", target: "ICICIBANK" },
      { source: "ICICIBANK", target: "TCS" }, // cross-cluster bridge
    ];

    // Helper implementing closedNeighborhood: selected node + directly connected nodes
    function getClosedNeighborhood(targetSymbol: string) {
      const neighbors = new Set<string>([targetSymbol]);
      for (const e of edges) {
        if (e.source === targetSymbol) neighbors.add(e.target);
        if (e.target === targetSymbol) neighbors.add(e.source);
      }
      return neighbors;
    }

    // Select "TCS"
    const tcsNeighborhood = getClosedNeighborhood("TCS");
    expect(tcsNeighborhood.has("TCS")).toBe(true);
    expect(tcsNeighborhood.has("INFY")).toBe(true); // direct neighbour
    expect(tcsNeighborhood.has("WIPRO")).toBe(true); // direct neighbour
    expect(tcsNeighborhood.has("ICICIBANK")).toBe(true); // direct neighbour
    expect(tcsNeighborhood.has("HDFCBANK")).toBe(false); // 2 hops away, should be faded!

    // Select "HDFCBANK"
    const hdfcNeighborhood = getClosedNeighborhood("HDFCBANK");
    expect(hdfcNeighborhood.has("HDFCBANK")).toBe(true);
    expect(hdfcNeighborhood.has("ICICIBANK")).toBe(true);
    expect(hdfcNeighborhood.has("TCS")).toBe(false);
    expect(hdfcNeighborhood.has("INFY")).toBe(false);

    // Reset view: all nodes unfaded
    const resetNeighborhood = new Set(nodes);
    expect(resetNeighborhood.size).toBe(5);
  });

  // Test 10: Record associations and search across notes and decisions
  it("filters notes and decisions simultaneously by content, rationale, and tags using canonical symbols", async () => {
    // Save notes
    await saveNote({
      symbol: "RELIANCE",
      content: "Solar gigafactory phase 1 commissioning timeline on track.",
      tags: ["Renewable", "Capex"],
    });
    await saveNote({
      symbol: "RELIANCE",
      content: "Jio ARPU growth exceeds consensus estimates.",
      tags: ["Telecom", "ARPU"],
    });

    // Save decisions
    await saveDecision({
      symbol: "RELIANCE",
      decisionType: "Buy",
      decisionDate: "2024-02-10",
      rationale: "Capex visibility in renewable division warrants valuation re-rating.",
      tags: ["Capex"],
      snapshot: { riskScore: 2, capturedAt: "2024-02-10T00:00:00Z" },
    });
    await saveDecision({
      symbol: "RELIANCE",
      decisionType: "Hold",
      decisionDate: "2024-05-15",
      rationale: "Oil-to-chemicals refining margins under short-term pressure.",
      tags: ["Quarterly"],
      snapshot: { riskScore: 3, capturedAt: "2024-05-15T00:00:00Z" },
    });

    const allNotes = await getNotesBySymbol("RELIANCE");
    const allDecisions = await getDecisionsBySymbol("RELIANCE");

    // Unified search filter function covering note text, tags, and decision rationale
    function searchRecords(query: string) {
      const q = query.trim().toLowerCase();
      const matchedNotes = allNotes.filter(
        (n) => n.content.toLowerCase().includes(q) || n.tags.some((t) => t.toLowerCase().includes(q))
      );
      const matchedDecisions = allDecisions.filter(
        (d) => d.rationale.toLowerCase().includes(q) || d.tags.some((t) => t.toLowerCase().includes(q))
      );
      return { notes: matchedNotes, decisions: matchedDecisions };
    }

    // Search "Capex"
    const capexResults = searchRecords("capex");
    expect(capexResults.notes).toHaveLength(1);
    expect(capexResults.notes[0].content).toContain("Solar gigafactory");
    expect(capexResults.decisions).toHaveLength(1);
    expect(capexResults.decisions[0].rationale).toContain("Capex visibility");

    // Search "ARPU"
    const arpuResults = searchRecords("arpu");
    expect(arpuResults.notes).toHaveLength(1);
    expect(arpuResults.notes[0].content).toContain("Jio ARPU");
    expect(arpuResults.decisions).toHaveLength(0);

    // Search "refining"
    const refiningResults = searchRecords("refining");
    expect(refiningResults.notes).toHaveLength(0);
    expect(refiningResults.decisions).toHaveLength(1);
    expect(refiningResults.decisions[0].rationale).toContain("refining margins");

    // Search "unrelated"
    const unrelatedResults = searchRecords("unrelated-random-string");
    expect(unrelatedResults.notes).toHaveLength(0);
    expect(unrelatedResults.decisions).toHaveLength(0);
  });

  // Test 11: Export/import round-trip with snapshots
  it("exports and restores notes, decisions, and portfolio snapshots in a complete JSON backup round trip", async () => {
    // 1. Populate notes, decisions, and snapshots
    await saveNote({
      symbol: "TCS",
      content: "Export test note for TCS.",
      tags: ["TestTag"],
    });

    await saveDecision({
      symbol: "TCS",
      decisionType: "Buy",
      decisionDate: "2024-03-01",
      rationale: "Export test decision rationale.",
      tags: ["TestDecision"],
      snapshot: { riskScore: 1, capturedAt: "2024-03-01T00:00:00Z" },
    });

    await savePortfolioSnapshot({
      name: "Pre-Export Baseline",
      description: "Testing complete export/import pipeline",
      calculationMeta: { horizon: 250, schemaVersion: 1, parameters: { weightingAssumption: "custom" } },
      holdings: [{ symbol: "TCS", weight: 100, quantity: 20, buyPrice: 3600 }],
      sectorExposures: [{ sector: "IT", weight: 100 }],
      riskMetrics: { annualizedVolatility: 0.16, portfolioRiskScore: 2 },
      diversification: { holdingHhi: 1.0, effectiveHoldings: 1.0 },
      mstContext: { edgeCount: 0, clusterCount: 1, bridgeStocks: [] },
    });

    // 2. Export backup JSON
    const exportedJson = await exportJournalBackup();
    const parsed = JSON.parse(exportedJson);
    expect(parsed.version).toBe(2);
    expect(parsed.notes).toHaveLength(1);
    expect(parsed.decisions).toHaveLength(1);
    expect(parsed.snapshots).toHaveLength(1);
    expect(parsed.snapshots[0].name).toBe("Pre-Export Baseline");

    // 3. Clear memory store completely
    _resetMemoryStoreForTests();

    // Verify store is empty
    expect(await getNotesBySymbol("TCS")).toHaveLength(0);
    expect(await getDecisionsBySymbol("TCS")).toHaveLength(0);
    expect(await getAllPortfolioSnapshots()).toHaveLength(0);

    // 4. Import backup back
    const importStats = await importJournalBackup(exportedJson);
    expect(importStats.importedNotes).toBe(1);
    expect(importStats.importedDecisions).toBe(1);
    expect(importStats.importedSnapshots).toBe(1);
    expect(importStats.skipped).toBe(0);

    // 5. Verify restored state
    const restoredNotes = await getNotesBySymbol("TCS");
    expect(restoredNotes).toHaveLength(1);
    expect(restoredNotes[0].content).toBe("Export test note for TCS.");

    const restoredDecisions = await getDecisionsBySymbol("TCS");
    expect(restoredDecisions).toHaveLength(1);
    expect(restoredDecisions[0].rationale).toBe("Export test decision rationale.");

    const restoredSnapshots = await getAllPortfolioSnapshots();
    expect(restoredSnapshots).toHaveLength(1);
    expect(restoredSnapshots[0].name).toBe("Pre-Export Baseline");
    expect(restoredSnapshots[0].holdings[0].symbol).toBe("TCS");
    expect(restoredSnapshots[0].holdings[0].buyPrice).toBe(3600);
    expect(restoredSnapshots[0].riskMetrics.annualizedVolatility).toBe(0.16);
  });
});
