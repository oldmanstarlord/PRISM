import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfidencePanel } from "./ConfidencePanel";
import { MissingDataBanner } from "./MissingDataBanner";

describe("Step 12 confidence components", () => {
  it("renders factor values, meanings, and caps", () => {
    render(
      <ConfidencePanel
        score={50}
        caps={["stale_price_cap_50"]}
        factors={{
          data_freshness: {
            value: 0.42,
            weight: 1,
            description: "Age against the configured maximum.",
          },
        }}
      />
    );
    expect(screen.getByText(/Data freshness: 42%/i)).toBeInTheDocument();
    expect(screen.getByText(/Age against the configured maximum/i)).toBeInTheDocument();
    expect(screen.getByText(/stale_price_cap_50/i)).toBeInTheDocument();
  });

  it("lists unavailable components and the confidence consequence", () => {
    render(
      <MissingDataBanner
        components={[
          {
            component_id: "gov_promoter_pledge",
            name: "Promoter pledge",
            dimension: "governance",
            status: "missing",
            reason: "no published filing",
          },
        ]}
      />
    );
    expect(screen.getByText(/lowered.*coverage and confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Promoter pledge.*no published filing/i)).toBeInTheDocument();
  });
});
