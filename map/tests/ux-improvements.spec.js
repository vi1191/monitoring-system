import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('ux-started')) { localStorage.clear(); sessionStorage.setItem('ux-started', '1'); } localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
});

test('поиск и счётчик маршрутов используют общую фильтрацию', async ({ page }) => {
  await page.locator('.cat-tab[data-cat="other"]').click();
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.locator('#search').fill(plate);
  await expect(page.locator('#shown-count')).toHaveText('1');
  await page.locator('#on-route-count').click();
  await expect(page.locator('#on-route-count')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#shown-count')).toHaveText('0');
  await expect(page.locator('.list-empty')).toContainText('ничего не найдено');
  await page.locator('.list-empty button').click();
  await expect(page.locator('#search')).toHaveValue('');
  await expect(page.locator('#on-route-count')).toHaveAttribute('aria-pressed', 'false');
});

test('выбор найденных включает свёрнутые группы и не трогает другие категории', async ({ page }) => {
  await page.locator('.cat-tab[data-cat="other"]').click();
  const plates = await page.evaluate(async () => (await import('/src/data.js')).MACHINES.slice(0, 2).map(m => m.plate));
  await page.locator('#search').fill(plates[0]);
  await page.locator('.btn-all').click();
  await expect(page.locator('.btn-all')).toContainText('Снять с найденных');
  await page.locator('#search').fill(plates[1]);
  await page.locator('.btn-all').click();
  await page.locator('#search').fill(plates[0]);
  await expect(page.locator('.btn-all')).toContainText('Снять с найденных');
  await page.locator('.btn-all').click();
  await page.reload();
  const selected = await page.evaluate(() => JSON.parse(localStorage.getItem('zhilischnik_v45')).selectedForShow);
  expect(selected).not.toContain(plates[0]);
  expect(selected).toContain(plates[1]);
});

test('диалог подтверждения закрывается Escape и возвращает фокус', async ({ page }) => {
  await page.locator('#dd-tools > button').click();
  await page.locator('#dd-tools .danger').click();
  await expect(page.locator('#action-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#action-dialog')).toBeHidden();
  await expect(page.locator('#dd-tools .danger')).toBeFocused();
});

test('на узком экране элементы управления доступны без горизонтального переполнения', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await expect(page.locator('#sidebar')).toBeVisible();
  await expect(page.locator('.btn-all')).toBeInViewport();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});