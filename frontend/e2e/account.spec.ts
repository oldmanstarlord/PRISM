import { test, expect } from "@playwright/test";
test("account sign-in stays accessible on desktop and mobile without running a workspace command", async ({
  page,
}) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Test: service unavailable" }),
    }),
  );
  await page.addInitScript(() =>
    sessionStorage.setItem("prism.intro.entered", "true"),
  );
  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign in", exact: true });
  await expect(signIn).toBeEnabled();
  await signIn.click();
  await expect(
    page.getByRole("dialog", { name: "Sign in to PRISM" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(signIn).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(signIn).toBeVisible();
  await signIn.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
