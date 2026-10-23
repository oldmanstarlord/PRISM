import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NewsIntelligencePanel } from "./NewsIntelligence";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
const sentiment = { label: "neutral", score: 0, confidence: 1, probabilities: { positive: 0, negative: 0, neutral: 1 } };
const status = { configured: true, model_ready: true, warnings: [], sources: [], auto_refresh: true, refresh_minutes: 60 };

it("keeps previous days through midnight and expires publications after seven days", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T18:29:59Z"));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    status,
    articles: [
      ["Today", "2026-10-22T12:00:00Z"], ["Yesterday", "2026-10-21T18:29:59Z"],
      ["Boundary", "2026-10-15T18:30:00Z"], ["Expired", "2026-10-15T18:29:58Z"],
      ["Undated", null], ["Future", "2026-10-23T18:29:59Z"], ["Naive", "2026-10-22T12:00:00"],
    ].map(([title, published_at]) => ({ title, published_at, url: `https://example.com/${title}`, companies: {}, sentiment })),
  }) }));
  await act(async () => { render(<NewsIntelligencePanel />); });
  for (const name of ["Today", "Yesterday", "Boundary"]) expect(screen.getByRole("heading", { name })).toBeInTheDocument();
  for (const name of ["Expired", "Undated", "Future", "Naive"]) expect(screen.queryByRole("heading", { name })).not.toBeInTheDocument();
  expect(screen.getByText("3 articles · last 7 days")).toBeInTheDocument();
  await act(async () => { vi.advanceTimersByTime(2000); });
  expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Yesterday" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Boundary" })).not.toBeInTheDocument();
});

it("labels retained context and removes it when supporting news expires", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T12:00:00Z"));
  const related = "https://example.com/followup";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    status,
    articles: [
      { title: "Followup", published_at: "2026-10-15T12:00:01Z", url: related },
      { title: "Old relevant event", published_at: "2026-10-01T12:00:00Z", url: "https://example.com/old",
        is_retained_context: true, relevance_until: "2026-10-22T12:00:01Z", related_article_url: related, relevance_reason: "Recent company-event followup." },
      { title: "Unsupported old event", published_at: "2026-10-01T12:00:00Z", url: "https://example.com/unsupported",
        is_retained_context: true, relevance_until: "2026-10-30T12:00:00Z", related_article_url: "https://example.com/missing" },
    ].map(article => ({ ...article, companies: {}, sentiment })),
  }) }));
  await act(async () => { render(<NewsIntelligencePanel />); });
  expect(screen.getByRole("heading", { name: "Old relevant event" })).toBeInTheDocument();
  expect(screen.getByText("Older relevant context.")).toBeInTheDocument();
  expect(screen.getByText("1 older relevant story")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Unsupported old event" })).not.toBeInTheDocument();
  await act(async () => { vi.advanceTimersByTime(2000); });
  expect(screen.queryByRole("heading", { name: "Old relevant event" })).not.toBeInTheDocument();
});
