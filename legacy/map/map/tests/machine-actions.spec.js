import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('test-started')) { localStorage.clear(); sessionStorage.setItem('test-started', '1'); } });
  await page.goto('/index.html');
});

test('помощь открывается и листается', async ({ page }) => {
  await page.locator('#help-btn').click();
  await expect(page.locator('#onboarding-overlay')).toHaveClass(/open/);
  await page.locator('#ob-next').click();
  await expect(page.locator('.ob-step.active')).toHaveAttribute('data-step', '1');
  await page.locator('#ob-prev').click();
  await expect(page.locator('.ob-step.active')).toHaveAttribute('data-step', '0');
  await page.getByText('Пропустить').click();
  await expect(page.locator('#onboarding-overlay')).not.toHaveClass(/open/);
});

test('добавление, удаление, подтип и сохранение после перезагрузки', async ({ page }) => {
  const plate = await page.evaluate(async () => {
    const { MACHINES } = await import('/src/data.js');
    return MACHINES.find(m => !m.isDvory).plate;
  });
  await page.locator('.btn-add').click();
  await page.locator('#modal-search').fill(plate);
  await page.locator('#modal-list .copy-item').click();
  await page.evaluate(() => window.closeModal());
  await page.locator('#search').fill(plate);
  await expect(page.locator('#shown-count')).toHaveText('1');
  await page.locator('.subtype-header').first().click();
  await page.locator('.machine-card').click({ button: 'right' });
  await page.locator('#scm-new-input').fill('Тестовый подтип');
  await page.locator('#subtype-context-menu button').click();
  await expect(page.locator('.st-name')).toContainText('Тестовый подтип');
  await page.reload();
  await page.locator('#search').fill(plate);
  await expect(page.locator('#shown-count')).toHaveText('1');
  await expect(page.locator('.st-name')).toContainText('Тестовый подтип');
  await page.locator('.subtype-header').first().click();
  await page.locator('.machine-card .chk').check();
  await page.locator('.btn-rem').click();
  await expect(page.locator('#action-dialog')).toBeVisible();
  await page.locator('#action-dialog .dialog-ok').click();
  await expect(page.locator('#shown-count')).toHaveText('0');
  await page.reload();
  await page.locator('#search').fill(plate);
  await expect(page.locator('#shown-count')).toHaveText('0');
});