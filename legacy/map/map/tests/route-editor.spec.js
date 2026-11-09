import { test, expect } from '@playwright/test';

test('добавить объекты, переставить и восстановить маршрут после перезагрузки', async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('route-started')) { localStorage.clear(); sessionStorage.setItem('route-started', '1'); } localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.evaluate(plate => window.openMiniRoute(plate), plate);
  await page.locator('#mini-route button[onclick="openPicker()" ]').click();
  await page.locator('#picker-search').fill('улица');
  await page.locator('#picker-streets input[type="checkbox"]').nth(0).check();
  await page.locator('#picker-streets input[type="checkbox"]').nth(1).check();
  await page.locator('#picker .p-actions button').click();
  const names = await page.locator('#mr-list .name').allTextContents();
  await page.locator('#mr-list .mr-item').nth(1).locator('.mr-up').click();
  await expect(page.locator('#mr-list .name').first()).toHaveText(names[1]);
  await expect(page.locator('.route-order-icon')).toHaveCount(2);
  await page.reload();
  await page.evaluate(plate => window.openMiniRoute(plate), plate);
  await expect(page.locator('#mr-list .name').first()).toHaveText(names[1]);
  await expect(page.locator('#mr-list .name').nth(1)).toHaveText(names[0]);
});

test('из выбора объекта можно открыть его геометрию', async ({ page }) => {
  await page.addInitScript(() => { localStorage.clear(); localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.evaluate(plate => window.openMiniRoute(plate), plate);
  await page.locator('#mini-route button[onclick="openPicker()" ]').click();
  await page.locator('#picker-streets .draw-btn').first().click();
  await expect(page.locator('#editor-panel')).toHaveClass(/open/);
  await expect(page.locator('.ed-street-item.editing')).toHaveCount(1);
});

test('удаление фигуры отменяется и сохраняется при перезагрузке', async ({ page }) => {
  await page.addInitScript(() => { if (!sessionStorage.getItem('geometry-started')) { localStorage.clear(); sessionStorage.setItem('geometry-started', '1'); } localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('/index.html');
  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
  await page.locator('.ed-street-item').first().click();
  const first = page.locator('.ed-street-item').first();
  const original = await first.locator('.pts').innerText();
  await page.evaluate(async () => {
    const { onGeomanRemove } = await import('/src/editor.js');
    const { STREETS } = await import('/src/data.js');
    onGeomanRemove({ layer: STREETS[0]._layer });
  });
  await expect(first.locator('.pts')).toHaveText('0т');
  await page.locator('#undo-btn').click();
  await expect(first.locator('.pts')).toHaveText(original);
  await page.reload();
  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
  await expect(page.locator('.ed-street-item').first().locator('.pts')).toHaveText(original);
});