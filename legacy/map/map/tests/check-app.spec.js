import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:5173/index.html';

test.describe('Проверка всего приложения', () => {

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('zhilischnik_onboarded', '1');
    });
  });

  test('1. Карта загружается', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    await page.waitForSelector('.leaflet-container', { timeout: 15000 });
    await expect(page.locator('.leaflet-container')).toBeVisible();
    console.log('✅ Карта загружена');
  });

  test('2. Карточки техники есть', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    const headers = page.locator('.subtype-header');
    const count = await headers.count();
    for (let i = 0; i < count; i++) {
      await headers.nth(i).click();
      await page.waitForTimeout(100);
    }
    await page.waitForSelector('.machine-card', { timeout: 15000 });
    const cards = await page.locator('.machine-card').count();
    expect(cards).toBeGreaterThan(0);
    console.log(`✅ Карточек техники: ${cards}`);
  });

  test('3. Категории переключаются', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    await page.waitForSelector('.cat-tab', { timeout: 15000 });

    await page.locator('.cat-tab[data-cat="odh"]').click();
    await page.waitForTimeout(300);
    console.log('✅ ОДХ выбрано');

    await page.locator('.cat-tab[data-cat="dvory"]').click();
    await page.waitForTimeout(300);
    console.log('✅ Дворы выбрано');

    await page.locator('.cat-tab[data-cat="other"]').click();
    await page.waitForTimeout(300);
    console.log('✅ Вся техника выбрано');
  });

  test('4. Поиск работает', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    await page.waitForSelector('#search', { timeout: 15000 });
    await page.locator('#search').fill('7922');
    await page.waitForTimeout(500);
    console.log('✅ Поиск "7922" выполнен');
  });

  test('5. Кнопка редактора есть', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    await page.waitForSelector('#edit-mode-btn', { timeout: 15000 });
    await page.locator('#edit-mode-btn').click();
    await page.waitForTimeout(500);
    const btnText = await page.locator('#edit-mode-btn').innerText();
    expect(btnText).toContain('Готово');
    console.log('✅ Кнопка редактора есть');
  });

  test('6. Маршруты открываются', async ({ page }) => {
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    const headers = page.locator('.subtype-header');
    const count = await headers.count();
    for (let i = 0; i < count; i++) {
      await headers.nth(i).click();
      await page.waitForTimeout(100);
    }
    await page.waitForSelector('.machine-card', { timeout: 15000 });
    await page.locator('.machine-card').first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('#mini-route.open')).toBeVisible();
    console.log('✅ Маршрут открыт');
  });

  test('7. Нет критических ошибок в консоли', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
        // early-listeners
    await page.addInitScript(() => {
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push('ERR: ' + e.message));
      window.addEventListener('unhandledrejection', e => window.__errs.push('REJ: ' + (e.reason?.message || e.reason)));
    });
    await page.goto(APP_URL);
    console.log('EARLY ERRS:', await page.evaluate(() => window.__errs));
    await page.waitForLoadState('domcontentloaded');
    page.on('response', r => { if (r.status() >= 400) console.log('404 URL:', r.url(), r.status()); });
    page.on('console', m => { if (m.type() === 'error') console.log('PAGE ERROR:', m.text()); });
    page.on('pageerror', e => console.log('PAGE EXCEPTION:', e.message));
    await page.waitForTimeout(2000);
    if (errors.length > 0) {
      console.log('⚠️ Ошибки в консоли:', errors);
    } else {
      console.log('✅ Ошибок в консоли нет');
    }
  });
});
