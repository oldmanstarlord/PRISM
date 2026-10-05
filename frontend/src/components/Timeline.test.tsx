import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Timeline } from "./Timeline";
import type { EventItem } from "../types";

afterEach(() => {
  cleanup();
});

describe("Timeline Component", () => {
  const sampleEvents: EventItem[] = [
    {
      id: "ev-1",
      security_id: "sec-1",
      symbol: "TCS",
      company_name: "Tata Consultancy Services Ltd.",
      event_type: "regulatory_action",
      event_type_method: "rule",
      published_at: "2024-03-20T10:00:00Z",
      effective_trading_date: "2024-03-21",
      importance: 10.0,
      importance_components: { base_weight: 10.0, magnitude_multiplier: 1.0 },
      headline: "SEBI issues warning regarding compliance disclosures",
      source_url: "https://www.nseindia.com/announcements/tcs-1",
      sentiment: "negative",
      p_pos: 0.05,
      p_neg: 0.88,
      p_neu: 0.07,
      evidence_span: "SEBI issues warning regarding compliance disclosures.",
      model_name: "prism_rule_sentiment",
      model_version: "1.0.0",
    },
    {
      id: "ev-2",
      security_id: "sec-1",
      symbol: "TCS",
      company_name: "Tata Consultancy Services Ltd.",
      event_type: "ma_order",
      event_type_method: "rule",
      published_at: "2024-03-15T09:30:00Z",
      effective_trading_date: "2024-03-15",
      importance: 5.0,
      importance_components: { base_weight: 5.0, magnitude_multiplier: 1.0 },
      headline: "TCS wins major cloud transformation deal",
      source_url: "https://www.nseindia.com/announcements/tcs-2",
      sentiment: "positive",
      p_pos: 0.75,
      p_neg: 0.10,
      p_neu: 0.15,
      evidence_span: "TCS wins major cloud transformation deal.",
      model_name: "prism_rule_sentiment",
      model_version: "1.0.0",
    },
  ];

  it("renders market disclaimer and event cards with sentiment and importance", () => {
    render(<Timeline events={sampleEvents} symbol="TCS" />);

    // Markets disclaimer must be visible
    expect(
      screen.getByText(/Markets may have already priced this in/i)
    ).toBeInTheDocument();

    // Headlines
    expect(
      screen.getByText("SEBI issues warning regarding compliance disclosures")
    ).toBeInTheDocument();
    expect(
      screen.getByText("TCS wins major cloud transformation deal")
    ).toBeInTheDocument();

    // Sentiments
    expect(screen.getByText("Negative")).toBeInTheDocument();
    expect(screen.getByText("Positive")).toBeInTheDocument();

    // Importance scores
    expect(screen.getByText("Importance: 10.0/10")).toBeInTheDocument();
    expect(screen.getByText("Importance: 5.0/10")).toBeInTheDocument();

    // Exchange filing link
    expect(screen.getAllByText(/Exchange Filing/i).length).toBe(2);
  });

  it("renders empty state when no events exist", () => {
    render(<Timeline events={[]} symbol="INFY" />);
    expect(
      screen.getByText(/No corporate announcements match the selected criteria/i)
    ).toBeInTheDocument();
  });
});
