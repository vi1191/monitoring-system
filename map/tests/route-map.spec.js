import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('route-map-started')) { localStorage.clear(); sessionStorage.setItem('route-map-started', '1'); } localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
  await page.locator('.leaflet-container').waitFor();
  await page.evaluate(async () => {
    const { MACHINES, STREETS } = await import('/src/data.js');
    const state = await import('/src/state.js');
    const street = STREETS.find(s => !s.polygon && s.coords.length >= 2);
    for (const m of MACHINES.slice(0, 2)) {
      state.rbRoutesByVehicle[m.plate] = [{ name: 'М1', items: [{ name: street.name, type: 'street', coords: street.coords }] }];
    }
    window.renderList();
  });
});

test('категория фиксирует маршруты, повторный щелчок отключает; карточка подсвечивает', async ({ page }) => {
  const tab = page.locator('.cat-tab[data-cat="other"]');
  await tab.hover();
  await expect(page.locator('.leaflet-overlay-pane path[stroke]')).not.toHaveCount(0);
  await tab.click();
  await expect(tab).toHaveClass(/routes-pinned/);
  await page.locator('#search').hover();
  await expect(tab).toHaveClass(/routes-pinned/);
  await tab.click();
  await expect(tab).not.toHaveClass(/routes-pinned/);
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.locator('#search').fill(plate);
  await page.locator('.subtype-header').first().click();
  await page.locator(`.machine-card[data-plate="${plate}"]`).hover();
  await expect(page.locator('.leaflet-overlay-pane path[stroke]')).not.toHaveCount(0);
});

test('рисование нескольких независимых фигур маршрута сохраняется после перезагрузки', async ({ page }) => {
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.evaluate(async plate => { window.closeMiniRoute(); const s = await import('/src/state.js'); s.rbRoutesByVehicle[plate] = [{ name: 'М1', items: [] }]; window.saveData(false); }, plate);
  await page.evaluate(plate => window.openMiniRoute(plate), plate);
  await page.locator('#route-edit-btn').click();
  await page.evaluate(async () => {
    const { onRouteCreate } = await import('/src/routes.js');
    for (let i = 0; i < 2; i++) {
      const layer = { getLatLngs: () => [{ lat: 55.65 + i * 0.001, lng: 37.48 }, { lat: 55.651 + i * 0.001, lng: 37.481 }] };
      onRouteCreate({ layer });
    }
  });
  await expect(page.locator('#mr-list .mr-item')).toHaveCount(2);
  await page.reload();
  await page.evaluate(plate => window.openMiniRoute(plate), plate);
  await expect(page.locator('#mr-list .mr-item')).toHaveCount(2);
});