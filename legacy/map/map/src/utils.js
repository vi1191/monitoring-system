// src/utils.js

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

export function escAttr(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;')
    .replace(/=/g, '&#61;');
}

export function safeJsonForScript(obj) {
  return JSON.stringify(obj)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

export function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const toHex = (x) => Math.round(255 * x).toString(16).padStart(2, '0');
  return '#' + toHex(f(0)) + toHex(f(8)) + toHex(f(4));
}

export function lineLength(coords) {
  if (!coords || coords.length < 2) return 0;
  let d = 0;
  const R = 6371000;
  const toRad = (x) => (x * Math.PI) / 180;
  for (let i = 1; i < coords.length; i++) {
    const a = coords[i - 1], b = coords[i];
    const dLat = toRad(b[0] - a[0]), dLon = toRad(b[1] - a[1]);
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2;
    d += 2 * R * Math.asin(Math.sqrt(x));
  }
  return d;
}

export function polygonArea(coords) {
  if (!coords || coords.length < 3) return 0;
  const R = 6371000;
  const toRad = (x) => (x * Math.PI) / 180;
  let area = 0;
  for (let i = 0; i < coords.length; i++) {
    const a = coords[i], b = coords[(i + 1) % coords.length];
    area += toRad(b[1] - a[1]) * (2 + Math.sin(toRad(a[0])) + Math.sin(toRad(b[0])));
  }
  return Math.abs((area * R * R) / 2);
}

export function closeRing(coords) {
  const c = coords.slice();
  if (c.length >= 3) {
    const f = c[0], l = c[c.length - 1];
    if (f[0] !== l[0] || f[1] !== l[1]) c.push([f[0], f[1]]);
  }
  return c;
}

export function lighten(hex, percent) {
  const num = parseInt(hex.replace('#', ''), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.min(255, (num >> 16) + amt);
  const G = Math.min(255, ((num >> 8) & 0x00ff) + amt);
  const B = Math.min(255, (num & 0x0000ff) + amt);
  return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

export function inferAreaFromName(name) {
  if (!name) return null;
  const m = String(name).match(/дворы\s+участок\s*(\d+)/i);
  if (m && m[1]) return m[1] + 'уч';
  const m2 = String(name).match(/участок\s*(\d+)/i);
  if (m2 && m2[1]) return m2[1] + 'уч';
  return null;
}

export function isYardObject(s) {
  return !!(s && (s.isYard || s.polygon));
}

export function offsetPolyline(coords, offset) {
  if (!coords || coords.length < 2 || !offset) return coords ? coords.slice() : [];
  const result = [];
  const n = coords.length;
  const cosLat = Math.cos((coords[0][0] * Math.PI) / 180);

  for (let i = 0; i < n; i++) {
    let dx = 0, dy = 0;

    if (i === 0) {
      dx = coords[1][1] - coords[0][1];
      dy = coords[1][0] - coords[0][0];
    } else if (i === n - 1) {
      dx = coords[n - 1][1] - coords[n - 2][1];
      dy = coords[n - 1][0] - coords[n - 2][0];
    } else {
      const dx1 = coords[i][1] - coords[i - 1][1];
      const dy1 = coords[i][0] - coords[i - 1][0];
      const dx2 = coords[i + 1][1] - coords[i][1];
      const dy2 = coords[i + 1][0] - coords[i][0];
      const len1 = Math.hypot(dx1, dy1) || 1e-9;
      const len2 = Math.hypot(dx2, dy2) || 1e-9;
      dx = dx1 / len1 + dx2 / len2;
      dy = dy1 / len1 + dy2 / len2;
    }

    const len = Math.hypot(dx, dy);
    if (len < 1e-9) {
      result.push([coords[i][0], coords[i][1]]);
      continue;
    }

    const nx = (-dy / len) * offset;
    const ny = (dx / len) * offset;

    result.push([coords[i][0] + nx, coords[i][1] + ny / cosLat]);
  }

  return result;
}