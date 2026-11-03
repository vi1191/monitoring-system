import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('pinned-test-init')) { localStorage.clear(); sessionStorage.setItem('pinned-test-init', '1'); } localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
});

test('закреплённый маршрут машины сохраняется и показывается при выборе категории', async ({ page }) => {
  const plate = await page.evaluate(async () => {
    const { MACHINES, STREETS } = await import('/src/data.js');
    const state = await import('/src/state.js');
    const m = MACHINES.find(m => m.isODH);
    const street = STREETS[0];
    state.rbRoutesByVehicle[m.plate] = [
      { name: 'Первый', items: [{ name: street.name, type: 'street', coords: street.coords }] },
      { name: 'Закреплённый', items: [{ name: STREETS[1].name, type: 'street', coords: STREETS[1].coords }] }
    ];
    window.setCategory('odh', false);
    return m.plate;
  });
  await page.locator('#search').fill(plate);
  await page.locator('.subtype-header').first().click();
  await page.locator('.card-route-select').selectOption('1');
  await page.evaluate(() => window.saveData(false));
  await page.locator('.cat-tab[data-cat="odh"]').click();
  const selected = await page.evaluate(plate => import('/src/routes.js').then(r => r.getPinnedRouteIndex(plate)), plate);
  expect(selected).toBe(1);
  await page.reload();
  expect(await page.evaluate(plate => import('/src/routes.js').then(r => r.getPinnedRouteIndex(plate)), plate)).toBe(1);
});

test('участок можно назначить машине и снять; переключение вкладки не оставляет пустой список', async ({ page }) => {
  await page.locator('.cat-tab[data-cat="other"]').click();
  await page.locator('.uch-btn[data-u="5"]').click();
  await page.locator('.btn-add').click();
  const plate = await page.locator('#modal-list .copy-item').first().innerText();
  await page.locator('#modal-list .copy-item').first().click();
  await expect(page.locator('#shown-count')).not.toHaveText('0');
  await page.evaluate(() => window.closeModal());
  await page.locator('.uch-btn[data-u="5"]').click();
  await page.locator('.cat-tab[data-cat="odh"]').click();
  await expect(page.locator('#shown-count')).not.toHaveText('0');
  expect(plate).toBeTruthy();
});

test('верхние часы и однофайловая выгрузка содержат исходники и сохранённое состояние', async ({ page }) => {
  await expect(page.locator('#live-clock')).not.toBeEmpty();
  const download = page.waitForEvent('download');
  await page.evaluate(() => window.exportAIContext());
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.md$/);
  const fs = await import('node:fs/promises');
  const text = await fs.readFile(await file.path(), 'utf8');
  expect(text).toContain('## Файл: src/routes.js');
  expect(text).toContain('## Состояние браузера');
});

test('подсказка общего объекта перечисляет обе машины', async ({ page }) => {
  const plates = await page.evaluate(async () => {
    const { MACHINES, STREETS } = await import('/src/data.js');
    const state = await import('/src/state.js');
    const two = MACHINES.filter(m => m.isDvory).slice(0, 2);
    for (const machine of two) {
      state.rbRoutesByVehicle[machine.plate] = [{ name: 'М1', items: [{ name: STREETS[0].name, type: 'street', coords: STREETS[0].coords }] }];
    }
    window.setCategory('dvory');
    return two.map(m => m.plate);
  });
  const tooltips = await page.evaluate(async () => {
    const { routeLayerGroup } = await import('/src/state.js');
    return routeLayerGroup.getLayers().filter(l => l._routeShape).map(l => l.getTooltip()?.getContent());
  });
  expect(tooltips.some(text => plates.every(plate => text.includes(plate)))).toBe(true);
});