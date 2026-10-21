import { expect, test } from "@playwright/test";

const holding = {
  id: "e2e-tcs",
  symbol: "TCS",
  companyName: "Tata Consultancy Services Ltd.",
  sector: "Information Technology",
  quantity: 10,
  buyPrice: 3500,
  buyDate: "2026-01-05",
  exchange: "NSE",
};

const transaction = {
  id: "e2e-buy-tcs",
  type: "BUY",
  symbol: "TCS",
  quantity: 10,
  price: 3500,
  date: "2026-01-05",
  timestamp: 1767571200000,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ({ seededHolding, seededTransaction }) => {
      localStorage.setItem("prism_portfolio_holdings", JSON.stringify([seededHolding]));
      localStorage.setItem("prism_portfolio_transactions", JSON.stringify([seededTransaction]));
    },
    { seededHolding: holding, seededTransaction: transaction },
  );

  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/securities")) {
      await route.fulfill({
        json: [
          {
            id: "tcs",
            isin: "INE467B01029",
            company_name: holding.companyName,
            industry: holding.sector,
            symbol: "TCS",
            latest_price: 3600,
            latest_trade_date: "2026-10-19",
          },
        ],
      });
      return;
    }
    if (url.includes("/market-data/quotes")) {
      await route.fulfill({ json: { quotes: {}, benchmark: null, fetched_at: null } });
      return;
    }
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "E2E provider intentionally unavailable" }),
    });
  });
});

test("ten-tab shell, ledger reconciliation, and browser persistence survive reload", async ({
  page,
}) => {
  await page.goto("/portfolio");

  const tabNames = [
    "Structural Overview",
    "Holdings Dashboard",
    "Stock Risk Analysis",
    "Portfolio Risk & History",
    "Sector Exposure",
    "Diversification",
    "Network & Stress (MST)",
    "News Intelligence",
    "Transaction Ledger",
    "AI Insights",
  ];
  for (const tabName of tabNames) {
    await expect(page.getByRole("button", { name: tabName })).toBeVisible();
  }

  await page.getByRole("button", { name: "Transaction Ledger" }).click();
  await expect(page.getByText(/1 Ledger Events/)).toBeVisible();
  await expect(page.getByText(/Ledger Reconciled/)).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Transaction Ledger" }).click();
  await expect(page.getByText(/1 Ledger Events/)).toBeVisible();
});

test("snapshot capture persists in IndexedDB and comparison becomes available", async ({ page }) => {
  await page.goto("/portfolio");
  await page.getByRole("button", { name: "Portfolio Risk & History" }).click();

  await page.getByRole("button", { name: /Save Snapshot Now/ }).click();
  await page.getByLabel("Snapshot Name").fill("E2E baseline");
  await page.getByRole("button", { name: "Save Snapshot", exact: true }).click();
  await expect(page.getByText("E2E baseline")).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Portfolio Risk & History" }).click();
  await expect(page.getByText("E2E baseline")).toBeVisible();
});

test("provider outages show explicit news and AI availability states", async ({ page }) => {
  await page.goto("/portfolio");
  await page.getByRole("button", { name: "News Intelligence" }).click();
  await expect(
    page.getByText(/not configured|not loaded|no verified news|unavailable/i).first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "AI Insights" }).click();
  await expect(page.getByText(/Inference Notice|unavailable|authentication/i).first()).toBeVisible();
});

test.skip("live authenticated creation and re-login isolation", async () => {
  // This gate is intentionally reserved for the deployed test environment. The local mocked
  // suite above never claims to verify Supabase authentication or PostgreSQL persistence.
});
