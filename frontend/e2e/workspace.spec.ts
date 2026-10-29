import { test, expect } from '@playwright/test';
test('workspace tabs preserve research and adapt to a narrow screen', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Preview: data service unavailable' }) }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Explore the market', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Network', exact: true }).click();
  await expect(page.getByText('Market network', {exact:true})).toBeVisible();
  await expect(page.getByText('ERR: NETWORK UNAVAILABLE')).toBeVisible();
  await page.getByRole('link', { name: 'News', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'News', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Network', exact: true }).click();
  await page.getByRole('tab', { name: 'Network', exact: true }).press('Alt+ArrowLeft');
  await expect(page.getByRole('tab').first()).toHaveText('Network');
  await page.screenshot({ path: 'test-results/workspace-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'RETRY' })).toBeVisible();
  await page.screenshot({ path: 'test-results/workspace-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
