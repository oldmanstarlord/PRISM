import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Preview: data service unavailable"}',
    }),
  );
});

test("native intro finishes within four seconds and the live welcome waits for Explore", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  // Control the intro timeline so slow screenshot capture cannot race its reveal.
  await page.clock.install({ time: "2026-10-29T12:00:00Z" });
  await page.clock.pauseAt("2026-10-29T12:00:01Z");
  const mediaRequests: string[] = [];
  page.on("request", (request) => {
    if (/\.(mp4|webm|mov)(\?|$)/.test(request.url()))
      mediaRequests.push(request.url());
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const intro = page.getByLabel("PRISM startup animation", { exact: true });
  await expect(intro).toHaveAttribute("data-phase", "playing");
  await expect(page.locator(".terminal-frame")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Explore", exact: true }),
  ).toBeHidden();
  await page.clock.runFor(700);
  await page.screenshot({ path: "test-results/prism-signal.png" });
  await page.clock.runFor(650);
  await page.screenshot({ path: "test-results/prism-contact.png" });
  await page.clock.runFor(400);
  await page.screenshot({ path: "test-results/prism-materialize.png" });
  await page.clock.runFor(650);
  await page.screenshot({ path: "test-results/prism-refraction.png" });
  await page.clock.runFor(480);
  await page.screenshot({ path: "test-results/prism-streams.png" });
  await page.clock.runFor(300);
  await expect(intro).toHaveAttribute("data-phase", "playing");
  const brand = page.locator(".intro-brand");
  const before = await brand.evaluate((el) =>
    Number(getComputedStyle(el).opacity),
  );
  await page.clock.runFor(40);
  const after = await brand.evaluate((el) =>
    Number(getComputedStyle(el).opacity),
  );
  // Entering the welcome phase must not restart or jump the visual timeline.
  expect(before).toBeGreaterThan(0.1);
  expect(after - before).toBeGreaterThanOrEqual(0);
  expect(after - before).toBeLessThan(0.18);
  await expect(intro).toHaveAttribute("data-phase", "welcome", {
    timeout: 2500,
  });
  await expect(
    page.getByRole("heading", { name: "PRISM", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".intro-feature")).toHaveCount(3);
  await expect(
    page.getByRole("heading", { name: "Portfolio Analytics", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Sector Divergence", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Market Structure (MST)", exact: true }),
  ).toBeVisible();
  await expect(intro).not.toContainText(/Market Strergence|Market Steregence/);
  await expect(page.locator("video, .intro-still")).toHaveCount(0);
  const canvas = page.locator(".intro-scene");
  const first = await canvas.evaluate((el: HTMLCanvasElement) =>
    el.toDataURL(),
  );
  await page.clock.runFor(900);
  expect(
    await canvas.evaluate((el: HTMLCanvasElement) => el.toDataURL()),
  ).not.toBe(first);
  await expect(intro).toHaveAttribute("data-phase", "welcome");
  await expect(page.locator(".terminal-frame")).toHaveCount(0);
  await page.screenshot({ path: "test-results/prism-welcome-desktop.png" });
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await expect(intro).toHaveCount(0);
  await expect(page.locator(".terminal-frame")).toBeVisible();
  await page.getByRole("link", { name: "Network", exact: true }).click();
  await expect(
    page.getByRole("tabpanel", { name: "Network", exact: true }),
  ).toBeVisible();
  await expect(intro).toHaveCount(0);
  expect(mediaRequests).toEqual([]);
  expect(errors).toEqual([]);
  await page.reload();
  await expect(intro).toHaveCount(0);
  await expect(page).toHaveURL(/\/mst$/);
  await expect(page.getByRole("tabpanel", { name: "Network", exact: true })).toBeVisible();
});

for (const size of [
  { width: 390, height: 844 },
  { width: 375, height: 667 },
  { width: 844, height: 390 },
]) {
  test(`responsive welcome remains readable and Explore opens the deep link at ${size.width}x${size.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await page.goto("/mst");
    await page.keyboard.press("Escape");
    await expect(page.locator(".prism-intro")).toHaveAttribute(
      "data-phase",
      "welcome",
    );
    await page.waitForTimeout(1000);
    const explore = page.getByRole("button", { name: "Explore", exact: true });
    await expect(explore).toBeInViewport();
    const buttonBox = await explore.boundingBox();
    for (const feature of await page.locator(".intro-feature").all()) {
      await expect(feature).toBeInViewport({ ratio: 1 });
      const box = await feature.boundingBox();
      expect(
        box &&
          buttonBox &&
          (box.y + box.height <= buttonBox.y ||
            box.x >= buttonBox.x + buttonBox.width),
      ).toBeTruthy();
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `test-results/prism-welcome-${size.width}.png`,
    });
    await explore.focus();
    await explore.press("Enter");
    await expect(page.locator(".prism-intro")).toHaveCount(0);
    await expect(
      page.getByRole("tabpanel", { name: "Network", exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/mst$/);
  });
}

test("reduced motion draws a sharp static scene and waits for Explore", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const intro = page.locator(".prism-intro");
  await expect(intro).toHaveAttribute("data-phase", "welcome");
  const canvas = page.locator(".intro-scene");
  await page.waitForTimeout(100);
  const initial = await canvas.evaluate((el: HTMLCanvasElement) =>
    el.toDataURL(),
  );
  await page.waitForTimeout(600);
  expect(await canvas.evaluate((el: HTMLCanvasElement) => el.toDataURL())).toBe(
    initial,
  );
  await expect(page.locator(".terminal-frame")).toHaveCount(0);
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await expect(page.locator(".terminal-frame")).toBeVisible();
});

test("motion preference changes stop and resume the native scene", async ({
  page,
}) => {
  await page.goto("/");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".prism-intro")).toHaveAttribute(
    "data-phase",
    "welcome",
  );
  await page.waitForTimeout(100);
  const canvas = page.locator(".intro-scene");
  const initial = await canvas.evaluate((el: HTMLCanvasElement) =>
    el.toDataURL(),
  );
  await page.waitForTimeout(300);
  expect(await canvas.evaluate((el: HTMLCanvasElement) => el.toDataURL())).toBe(
    initial,
  );
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.waitForTimeout(300);
  expect(
    await canvas.evaluate((el: HTMLCanvasElement) => el.toDataURL()),
  ).not.toBe(initial);
  await expect(page.locator(".terminal-frame")).toHaveCount(0);
});

test("the welcome and Explore remain usable without a canvas context", async ({
  page,
}) => {
  await page.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = (() =>
      null) as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Skip startup animation" }).click();
  await expect(
    page.getByRole("heading", { name: "PRISM", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await expect(page.locator(".terminal-frame")).toBeVisible();
});

test("canvas follows resize and renders at retina pixel density", async ({
  browser,
}) => {
  const context = await browser.newContext({
    deviceScaleFactor: 2,
    reducedMotion: "reduce",
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("/");
  const canvas = page.locator(".intro-scene");
  await expect
    .poll(() =>
      canvas.evaluate((el: HTMLCanvasElement) => [el.width, el.height]),
    )
    .toEqual([2880, 1800]);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      canvas.evaluate((el: HTMLCanvasElement) => [el.width, el.height]),
    )
    .toEqual([780, 1688]);
  await expect(
    page.getByRole("button", { name: "Explore", exact: true }),
  ).toBeInViewport();
  await context.close();
});

test("prism turns toward the pointer while the welcome stays usable", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.clock.install({ time: "2026-10-29T12:00:00Z" });
  await page.clock.pauseAt("2026-10-29T12:00:01Z");
  await page.goto("/");
  await page.clock.runFor(4000);
  const pixels = () => page.locator(".intro-scene").evaluate((el: HTMLCanvasElement) => {
    const data = el.getContext("2d")!.getImageData(540, 220, 400, 400).data;
    const sample: number[] = [];
    for (let i = 0; i < data.length; i += 16) sample.push(data[i], data[i + 1], data[i + 2]);
    return sample;
  });
  const difference = (a: number[], b: number[]) => a.reduce((sum, value, i) => sum + Math.abs(value - b[i]), 0) / a.length;
  const start = await pixels();
  await page.clock.runFor(600);
  const idle = await pixels();
  const idleChange = difference(start, idle);
  await page.mouse.move(1320, 80);
  await page.clock.runFor(600);
  const right = await pixels();
  expect(difference(idle, right)).toBeGreaterThan(idleChange * 1.5);
  await page.screenshot({ path: "test-results/prism-pointer-upper-right.png" });
  await page.mouse.move(120, 820);
  await page.clock.runFor(600);
  const left = await pixels();
  expect(difference(right, left)).toBeGreaterThan(idleChange * 1.5);
  await expect(page.getByRole("button", { name: "Explore", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Explore", exact: true }).click();
  await expect(page.locator(".terminal-frame")).toBeVisible();
});
