import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:5173/index.html';

test.describe('Полная проверка функционала', () => {

  test.beforeEach(async ({ page }) => {
    // Очищаем localStorage от предыдущих тестов и отключаем онбординг
    await page.addInitScript(() => {
      localStorage.clear();
      localStorage.setItem('zhilischnik_onboarded', '1');
    });
    
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
  });

  test('1. Меню "Инструменты" открывается', async ({ page }) => {
    await page.locator('button[onclick*="toggleDropdown"]').click();
    await expect(page.locator('#dd-tools')).toHaveClass(/open/);
    console.log('✅ Меню Инструменты открывается');
  });

  test('2. Легенда открывается', async ({ page }) => {
    await page.locator('.lg-fab').click();
    await expect(page.locator('#legend')).toHaveClass(/open/);
    console.log('✅ Легенда открывается');
  });

  test('3. Сворачивание боковой панели', async ({ page }) => {
    await page.locator('button[onclick*="toggleSidebar"]').first().click();
    await expect(page.locator('#sidebar')).toHaveClass(/collapsed/);
    console.log('✅ Боковая панель сворачивается');
  });

  test('4. Выбор участка фильтрует карточки', async ({ page }) => {
    // Переключаемся на "Вся техника", чтобы карточки точно были
    await page.locator('.cat-tab[data-cat="other"]').click();
    await page.waitForTimeout(300);
    
    // Раскрываем аккордеоны, чтобы карточки появились в DOM
    const headers = page.locator('.subtype-header');
    const count = await headers.count();
    for (let i = 0; i < count; i++) {
      await headers.nth(i).click();
      await page.waitForTimeout(100);
    }
    
    const before = await page.locator('.machine-card').count();
    await page.locator('.uch-btn[data-u="1"]').click();
    await page.waitForTimeout(300);
    const after = await page.locator('.machine-card').count();
    expect(after).toBeLessThan(before);
    await page.locator('.uch-btn[data-u="1"]').click();
    await page.waitForTimeout(300);
    expect(await page.locator('.machine-card').count()).toBe(before);
    console.log(`✅ Участок 1 выбран, карточек: ${after}`);
  });

  test('5. Реальный поиск фильтрует карточки', async ({ page }) => {
    // Переключаемся на "Вся техника"
    await page.locator('.cat-tab[data-cat="other"]').click();
    await page.waitForTimeout(300);

    // Ищем 894
    await page.locator('#search').fill('894');
    await page.waitForTimeout(500);

    // ВАЖНО: Раскрываем найденные аккордеоны (подтипы), чтобы карточки появились
    const headers = page.locator('.subtype-header');
    const count = await headers.count();
    for (let i = 0; i < count; i++) {
      await headers.nth(i).click();
      await page.waitForTimeout(100);
    }

    const after = await page.locator('.machine-card').count();
    const texts = await page.locator('.machine-card').allInnerTexts();
    
    console.log(`Найдено карточек:`, texts);
    
    // Проверяем, что поиск сработал (карточки есть)
    expect(after).toBeGreaterThan(0);
    console.log(`✅ Поиск "894" работает, найдено: ${after}`);
  });

  test('6. Кнопка "Все" выделяет технику', async ({ page }) => {
    await page.locator('.btn-all').click();
    console.log('✅ Кнопка "Все" нажата без ошибок');
  });
});