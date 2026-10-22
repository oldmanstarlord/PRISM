import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { NewsIntelligencePanel } from "./NewsIntelligence";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("shows only verified publications today in IST and expires them at midnight", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T18:29:59Z"));
  const sentiment = { label: "neutral", score: 0, confidence: 1, probabilities: { positive: 0, negative: 1, neutral: 0 } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    status: { configured: true, model_ready: true, warnings: [], sources: [], auto_refresh: true, refresh_minutes: 60 },
    articles: [
      ["Today", "2026-10-21T18:30:00Z"],
      ["Yesterday", "2026-10-21T18:29:59Z"],
      ["Undated", null], ["Future", "2026-10-22T18:29:59.500Z"],
    ].map(([title, published_at]) => ({ title, published_at, url: `https://example.com/${title}`, companies: {}, sentiment })),
  }) }));
  await act(async () => { render(<NewsIntelligencePanel />); });
  expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
  for (const name of ["Yesterday", "Undated", "Future"]) {
    expect(screen.queryByRole("heading", { name })).not.toBeInTheDocument();
  }
  expect(screen.getByText("1 article today · IST")).toBeInTheDocument();
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(screen.queryByRole("heading", { name: "Today" })).not.toBeInTheDocument();
  expect(screen.getByText("No news published today yet")).toBeInTheDocument();
});
