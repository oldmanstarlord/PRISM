import { expect, test } from "@playwright/test";

test("market numeric headers align with values, including after sorting", async ({ page }) => {
  await page.route("**/api/v1/**", route => {
    if (route.request().url().includes("/rankings?")) return route.fulfill({ json: {
      horizon: 20,
      run: { signal_date: "2026-10-29", data_cutoff: "2026-10-29", completed_at: "2026-10-29", implementation_version: "test", score_count: 2, issue_count: 0, exclusion_count: 0 },
      results: [
        { symbol: "ALPHA", industry: "Technology", divergence_value: -2.63, industry_percentile: 2, interpretation: "strong", observations_used: 20 },
        { symbol: "BETA", industry: "Financial Services", divergence_value: 1.82, industry_percentile: 100, interpretation: "moderate", observations_used: 20 },
      ],
    } });
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  const table = page.getByRole("table", { name: "Companies compared with industry peers" });
  await expect(table).toBeVisible();
  for (const title of ["Peer difference", "Industry percentile"]) {
    const heading = table.getByRole("button", { name: title, exact: true });
    await expect(heading.locator("..")).toHaveCSS("text-align", "right");
    const aligned = await heading.evaluate(el => {
      const cell = el.closest("th")!;
      return Math.abs(el.getBoundingClientRect().right - (cell.getBoundingClientRect().right - parseFloat(getComputedStyle(cell).paddingRight))) < 1;
    });
    expect(aligned).toBe(true);
    await heading.click();
  }
  await expect(table.locator("tbody td").first()).toHaveCSS("font-size", "12px");
  await page.screenshot({ path: "test-results/market-readable-columns.png", fullPage: true });
});

test("decision and confidence labels keep readable foregrounds", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => localStorage.setItem("prism_portfolio_holdings", JSON.stringify([
    { id: "readability", symbol: "ALPHA", companyName: "Alpha Ltd", sector: "Technology", quantity: 10, buyPrice: 100, buyDate: "2026-01-01", exchange: "NSE" },
  ])));
  const decisions = ["HOLD", "WAIT & WATCH", "SELL"].map((decision, i) => ({
    symbol: ["ALPHA", "BETA", "GAMMA"][i], company_name: "Sample company", sector: "Technology",
    fundamental: { fundamental_strength_score: 80, availability: "available" },
    sector_strength: { sector_strength_score: 70, availability: "available" },
    news: { news_score: 65, availability: "available", major_events: [], sources: [] },
    applied_weights: { fundamental: .6, sector: .25, news: .15, regime: "normal" },
    final_score: 80 - i * 25, decision, confidence: ["high", "medium", "low"][i], risk_alerts: [], reasons: [], status: "analyzed",
  }));
  await page.route("**/api/v1/**", route => {
    if (route.request().url().endsWith("/portfolio/analyze")) return route.fulfill({ json: {
      summary: { total_stocks: 3, hold_count: 1, wait_and_watch_count: 1, sell_count: 1, unavailable_count: 0, portfolio_weighted_risk_exposure: 30, average_final_score: 55 }, decisions,
    } });
    if (route.request().url().endsWith("/securities")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/portfolio?tab=stock-decisions");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await page.getByRole("button", { name: "3. Research", exact: true }).click();
  await page.getByRole("button", { name: "Decision review", exact: true }).click();
  for (const stock of decisions) {
    const card = page.getByTestId(`stock-card-${stock.symbol}`);
    await expect(card).toBeVisible();
    await expect(card.getByText(stock.decision, { exact: true })).toHaveCSS("color", "rgb(0, 0, 0)");
  }
  const medium = page.getByTestId("stock-card-BETA").getByText("Medium Confidence", { exact: true }).locator("..");
  await expect(medium).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await expect(medium).toHaveCSS("color", "rgb(255, 159, 26)");
  await expect(page.getByTestId("stock-card-GAMMA").getByText("Low Confidence", { exact: true })).toHaveCSS("color", "rgb(230, 230, 230)");
  await page.reload();
  await expect(page.locator(".prism-intro")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Decision review", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByTestId("stock-card-ALPHA")).toBeVisible();
  await page.screenshot({ path: "test-results/decision-readable-badges.png", fullPage: true });
});

test("loading uses an animated signal without rotating text", async ({ page }) => {
  let release: () => void = () => {};
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/**", async route => {
    if (route.request().url().includes("/rankings?")) await pending;
    await route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  const loader = page.getByRole("progressbar", { name: "Loading companies" });
  await expect(loader).toBeVisible();
  await expect(loader).toHaveCSS("animation-name", "none");
  await expect(loader).toHaveCSS("transform", "none");
  expect(await loader.evaluate(el => getComputedStyle(el, "::after").content)).toBe("none");
  expect(await loader.evaluate(el => getComputedStyle(el, "::before").animationName)).toBe("prism-loading-signal");
  await page.screenshot({ path: "test-results/prism-loading-signal.png", fullPage: true });
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await loader.evaluate(el => getComputedStyle(el, "::before").animationName)).toBe("none");
  release();
});

test("holding badges remain readable and a badge destination survives reload", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    localStorage.setItem("prism_portfolio_holdings", JSON.stringify([
      { id: "badge-check", symbol: "ICICIBANK", companyName: "ICICI Bank Ltd.", sector: "Financial Services", quantity: 10, buyPrice: 100, buyDate: "2026-01-01", exchange: "NSE" },
    ]));
  });
  await page.route("**/api/v1/**", route => {
    if (route.request().url().endsWith("/portfolio-analysis/preview")) return route.fulfill({ json: {
      holdings: [{ symbol: "ICICIBANK", industry: "Financial Services", weight: 1, annualized_volatility: .2, risk_contribution: 1, divergence_20d: 2, divergence_band: "strong" }],
      concentration: { effective_holdings: 1, effective_industries: 1 },
    } });
    if (route.request().url().endsWith("/securities")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto("/portfolio");
  // Seed a research note before the portfolio mounts, using its normal storage API.
  await page.evaluate(async () => {
    const modulePath = "/src/journalStorage.ts";
    const journal = await import(modulePath);
    await journal.saveNote({ symbol: "ICICIBANK", content: "Review earnings", tags: [] });
  });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  const notes = page.getByText("Notes: 1", { exact: true }).locator("..");
  const model = page.getByText("Model: Unusual", { exact: true }).locator("..");
  await expect(notes).toBeVisible();
  await expect(notes).toHaveCSS("color", "rgb(0, 0, 0)");
  await expect(notes).toHaveCSS("background-color", "rgb(61, 220, 90)");
  await expect(model).toBeVisible();
  await expect(model).toHaveCSS("color", "rgb(255, 77, 61)");
  await expect(model).toHaveCSS("background-color", "rgb(0, 0, 0)");
  await page.screenshot({ path: "test-results/holdings-readable-badges.png", fullPage: true });
  await model.click();
  await expect(page.getByRole("button", { name: "AI insights", exact: true })).toHaveAttribute("aria-current", "page");
  await page.reload();
  await expect(page.locator(".prism-intro")).toHaveCount(0);
  await expect(page).toHaveURL(/\/portfolio$/);
  await expect(page.getByRole("button", { name: "AI insights", exact: true })).toHaveAttribute("aria-current", "page");
});
