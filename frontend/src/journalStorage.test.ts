import { beforeEach, describe, expect, it } from "vitest";
import {
  _resetMemoryStoreForTests,
  exportJournalBackup,
  getDecisionsBySymbol,
  getNotesBySymbol,
  getNotesCountMap,
  importJournalBackup,
  saveDecision,
  saveNote,
  validateDecision,
  validateNote,
} from "./journalStorage";

describe("journalStorage", () => {
  beforeEach(() => {
    _resetMemoryStoreForTests();
  });

  describe("Research Notes", () => {
    it("creates, retrieves, and isolates notes by canonical symbol", async () => {
      await saveNote({
        symbol: "tcs",
        content: "Strong margins expected in Q3 cloud bookings.",
        tags: ["Review", "Tech"],
      });

      await saveNote({
        symbol: "infy",
        content: "Management guidance revised upward.",
        tags: ["Guidance"],
      });

      const tcsNotes = await getNotesBySymbol("TCS");
      expect(tcsNotes).toHaveLength(1);
      expect(tcsNotes[0].symbol).toBe("TCS");
      expect(tcsNotes[0].content).toContain("Strong margins");
      expect(tcsNotes[0].tags).toEqual(["Review", "Tech"]);
      expect(tcsNotes[0].createdAt).toBeDefined();
      expect(tcsNotes[0].updatedAt).toBeDefined();

      const infyNotes = await getNotesBySymbol("INFY");
      expect(infyNotes).toHaveLength(1);
      expect(infyNotes[0].symbol).toBe("INFY");

      const hdfcNotes = await getNotesBySymbol("HDFCBANK");
      expect(hdfcNotes).toHaveLength(0);

      const countMap = await getNotesCountMap();
      expect(countMap["TCS"]).toBe(1);
      expect(countMap["INFY"]).toBe(1);
      expect(countMap["HDFCBANK"]).toBeUndefined();
    });

    it("safely handles and skips corrupt or malformed note records", () => {
      expect(validateNote(null)).toBeNull();
      expect(validateNote({})).toBeNull();
      expect(validateNote({ id: "1" })).toBeNull(); // missing symbol & content
      expect(validateNote({ id: "1", symbol: "TCS" })).toBeNull(); // missing content

      const validRaw = {
        id: "note-123",
        symbol: "  sbin  ",
        content: "NIM expansion thesis intact.",
        tags: ["Banking", "NIM", 123, null], // invalid tag elements cleaned up
      };
      const result = validateNote(validRaw);
      expect(result).not.toBeNull();
      expect(result?.symbol).toBe("SBIN");
      expect(result?.tags).toEqual(["Banking", "NIM"]);
      expect(result?.schemaVersion).toBe(1);
    });
  });

  describe("Investment Decisions", () => {
    it("captures decision snapshots accurately without replacing missing values with 0", async () => {
      const decision = await saveDecision({
        symbol: "HDFCBANK",
        decisionType: "Buy",
        decisionDate: "2024-03-15",
        rationale: "Long-term deposit repricing cycle complete.",
        tags: ["Core Allocation"],
        snapshot: {
          riskScore: 2,
          riskLabel: "Moderate",
          sectorDivergenceScore: 1.45,
          sectorDivergenceHorizon: 20,
          portfolioWeight: null, // unavailable at capture
          mstCluster: "Financial Services",
          capturedAt: "2024-03-15T10:00:00Z",
        },
      });

      expect(decision.id).toBeDefined();
      expect(decision.symbol).toBe("HDFCBANK");
      expect(decision.decisionType).toBe("Buy");
      // Critical check: unavailable portfolioWeight remains null, NOT 0
      expect(decision.snapshot.portfolioWeight).toBeNull();
      expect(decision.snapshot.riskScore).toBe(2);
      expect(decision.snapshot.sectorDivergenceScore).toBe(1.45);

      const retrieved = await getDecisionsBySymbol("HDFCBANK");
      expect(retrieved).toHaveLength(1);
      expect(retrieved[0].snapshot.portfolioWeight).toBeNull();
    });

    it("safely validates and discards corrupted decision records", () => {
      expect(validateDecision(null)).toBeNull();
      expect(validateDecision("not an object")).toBeNull();
      expect(validateDecision({ id: "d1" })).toBeNull(); // missing symbol

      const malformed = {
        id: "d-bad",
        symbol: "TCS",
        decisionType: "INVALID_ACTION", // should fallback to Review
        decisionDate: "invalid-date",
        rationale: "Testing fallback",
        snapshot: {
          riskScore: "NaN", // invalid type, should become null
          portfolioWeight: null,
        },
      };

      const validated = validateDecision(malformed);
      expect(validated).not.toBeNull();
      expect(validated?.decisionType).toBe("Review");
      expect(validated?.snapshot.riskScore).toBeNull();
      expect(validated?.snapshot.portfolioWeight).toBeNull();
    });
  });

  describe("Backup and Restore (Export & Import)", () => {
    it("exports and imports valid records while skipping corrupt items without crashing", async () => {
      await saveNote({
        symbol: "RELIANCE",
        content: "Capex cycle in new energy moving on track.",
        tags: ["Energy", "Capex"],
      });

      await saveDecision({
        symbol: "RELIANCE",
        decisionType: "Hold",
        decisionDate: "2024-04-01",
        rationale: "Maintain position until refining margins stabilize.",
        tags: ["Quarterly"],
        snapshot: {
          riskScore: 3,
          riskLabel: "High",
          sectorDivergenceScore: -0.85,
          sectorDivergenceHorizon: 5,
          portfolioWeight: 10.5,
          mstCluster: "Energy",
          capturedAt: "2024-04-01T09:00:00Z",
        },
      });

      const jsonStr = await exportJournalBackup();
      const parsed = JSON.parse(jsonStr);
      expect(parsed.version).toBe(2);
      expect(parsed.notes).toHaveLength(1);
      expect(parsed.decisions).toHaveLength(1);

      // Inject a corrupt record into the export
      parsed.notes.push({ id: 9999, invalid: true }); // corrupt note
      parsed.decisions.push({ bogus: "record" }); // corrupt decision

      // Reset and import back
      _resetMemoryStoreForTests();
      const result = await importJournalBackup(JSON.stringify(parsed));

      expect(result.importedNotes).toBe(1);
      expect(result.importedDecisions).toBe(1);
      expect(result.skipped).toBe(2);

      const notes = await getNotesBySymbol("RELIANCE");
      expect(notes).toHaveLength(1);
      expect(notes[0].content).toContain("Capex cycle");
    });
  });
});
