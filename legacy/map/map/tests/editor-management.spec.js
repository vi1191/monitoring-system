import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('editor-management-started')) {
      localStorage.clear(); sessionStorage.setItem('editor-management-started', '1');
    }
    localStorage.setItem('zhilischnik_onboarded', '1');
  });
  await page.goto('/index.html');
  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
});

test('Добавление, переименование, перемещение и удаление улицы сохраняются', async ({ page }) => {
  await expect(page.locator('#editor-bottom-bar')).toHaveCount(0);
  await page.getByRole('button', { name: '+ Улица' }).click();
  await page.locator('#action-dialog input').fill('Тестовая улица');
  await page.locator('#action-dialog .dialog-ok').click();
  const row = page.locator('.ed-street-item', { hasText: 'Тестовая улица' });
  await expect(row).toHaveCount(1);
  await row.getByRole('button', { name: 'Переименовать Тестовая улица' }).click();
  await page.locator('#action-dialog input').fill('Новая улица');
  await page.locator('#action-dialog .dialog-ok').click();
  const renamed = page.locator('.ed-street-item', { hasText: 'Новая улица' });
  await renamed.getByRole('button', { name: 'Выше Новая улица' }).click();
  await page.reload();
  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
  await expect(page.locator('.ed-street-item', { hasText: 'Новая улица' })).toHaveCount(1);
  await page.locator('.ed-street-item', { hasText: 'Новая улица' }).getByRole('button', { name: 'Удалить объект Новая улица' }).click();
  await page.locator('#action-dialog .dialog-ok').click();
  await expect(page.locator('.ed-street-item', { hasText: 'Новая улица' })).toHaveCount(0);
});

test('Фото машины по ссылке сохраняется после обновления', async ({ page }) => {
  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
  await page.locator('.cat-tab[data-cat="other"]').click();
  const plate = await page.evaluate(async () => (await import('/src/data.js')).MACHINES[0].plate);
  await page.locator('#search').fill(plate);
  const group = page.locator('.subtype-header').first();
  if (await group.count() && !await page.locator(`.machine-card[data-plate="${plate}"]`).count()) await group.click();
  await page.locator(`.machine-card[data-plate="${plate}"] .card-photo-url`).click();
  await page.locator('#action-dialog input').fill('https://example.com/new.jpg');
  await page.locator('#action-dialog .dialog-ok').click();
  await page.reload();
  await page.locator('.cat-tab[data-cat="other"]').click();
  await page.locator('#search').fill(plate);
  if (!await page.locator(`.machine-card[data-plate="${plate}"]`).count()) await page.locator('.subtype-header').first().click();
  await expect(page.locator(`.machine-card[data-plate="${plate}"] .tech-icon`)).toHaveAttribute('src', 'https://example.com/new.jpg');
});

test('Создание участка и подсветка маршрутов при наведении на номер участка', async ({ page }) => {
  await page.getByRole('button', { name: '+ Участок' }).click();
  await page.locator('#action-dialog input').fill('Тестовый участок');
  await page.locator('#action-dialog .dialog-ok').click();
  const polygon = await page.evaluate(async () => (await import('/src/data.js')).STREETS.find(s => s.name === 'Тестовый участок'));
  expect(polygon.polygon).toBe(true);
  await page.reload();
  await expect.poll(() => page.evaluate(async () => !!(await import('/src/data.js')).STREETS.find(s => s.name === 'Тестовый участок'))).toBe(true);
  await page.evaluate(async () => {
    const { MACHINES, STREETS } = await import('/src/data.js');
    const state = await import('/src/state.js');
    const machine = MACHINES.find(m => /^\dуч$/.test(m.area));
    const street = STREETS.find(s => !s.polygon && s.coords?.length >= 2);
    state.rbRoutesByVehicle[machine.plate] = [{ items: [{ name: street.name, type: 'street', coords: street.coords }] }];
    document.querySelector(`.uch-btn[data-u="${machine.area[0]}"]`).dataset.testRoute = 'yes';
  });
  const button = page.locator('.uch-btn[data-test-route="yes"]');
  await button.hover();
  await expect(page.locator('.leaflet-overlay-pane path[stroke]')).not.toHaveCount(0);
});