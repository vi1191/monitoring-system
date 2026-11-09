import fs from 'fs';
import { execSync } from 'child_process';
import path from 'path';
import os from 'os';

const html = fs.readFileSync('index.html', 'utf8');
const m = html.match(/<script type="module">([\s\S]*?)<\/script>/);
if (!m) { console.error('Не найден <script type="module"> в index.html'); process.exit(1); }

const tmp = path.join(os.tmpdir(), 'index-module-' + Date.now() + '.mjs');
fs.writeFileSync(tmp, m[1], 'utf8');
try {
  execSync(`node --check "${tmp}"`, { stdio: 'inherit' });
  console.log('✅ Синтаксис <script type="module"> корректен');
} catch {
  console.error('❌ Синтаксическая ошибка');
  process.exit(1);
} finally {
  fs.unlinkSync(tmp);
}
