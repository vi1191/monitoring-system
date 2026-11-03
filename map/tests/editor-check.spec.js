import { test, expect } from '@playwright/test';

test('E2E: Редактор рисует и сохраняет', async ({ page }) => {
  await page.addInitScript(() => { localStorage.clear(); localStorage.setItem('zhilischnik_onboarded', '1'); });
  await page.goto('http://localhost:5173/index.html');
  await page.waitForLoadState('networkidle');

  await page.locator('#topbar button[onclick="toggleEditor()" ]').click();
  await expect(page.locator('#editor-panel')).toHaveClass(/open/);

  const firstStreet = page.locator('.ed-street-item').first();
  await firstStreet.click();
  await page.evaluate(async () => {
    const { onGeomanCreate } = await import('/src/editor.js');
    onGeomanCreate({ shape: 'Line', layer: {
      getLatLngs: () => [{ lat: 55.65, lng: 37.48 }, { lat: 55.651, lng: 37.481 }]
    } });
  });

  const ptsText = await firstStreet.locator('.pts').innerText();
  console.log('Точки в списке:', ptsText);
  expect(ptsText).not.toBe('0т');

  const hasData = await page.evaluate(() => {
    const data = localStorage.getItem('zhilischnik_v45_streets');
    return data ? data.includes('coords') : false;
  });
  expect(hasData).toBeTruthy();
});
