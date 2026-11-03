import { describe, it, expect } from 'vitest';
import { lineLength, polygonArea, esc, offsetPolyline, closeRing } from './utils.js';

describe('тилиты', () => {
  it('lineLength', () => {
    expect(lineLength([[55,37],[56,37]])).toBeGreaterThan(110000);
  });

  it('polygonArea', () => {
    expect(polygonArea([[55,37],[55,37.01],[55.01,37.01],[55.01,37],[55,37]])).toBeGreaterThan(600000);
  });

  it('esc', () => {
    expect(esc('<')).toBe('&lt;');
  });

    it('offset', () => {
    const s = offsetPolyline([[55,37],[55,37.01]], 0.0001);
    // Функция сдвигает линию перпендикулярно. Для линии вдоль долготы
    // сдвиг происходит по долготе (вторая координата), а не по широте.
    expect(s[0][1]).not.toBe(37);
  });
  it('closeRing', () => {
    const c = closeRing([[55,37],[55,37.01],[55.01,37.01]]);
    expect(c[0]).toEqual(c[c.length - 1]);
  });
});
