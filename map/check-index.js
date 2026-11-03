// check-index.js — утилита для проверки index.html
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const file = path.join(__dirname, 'index.html');
if (!fs.existsSync(file)) {
  console.error('Файл index.html не найден');
  process.exit(1);
}

const content = fs.readFileSync(file, 'utf8');
const lines = content.split('\n');

console.log('=== ПРОВЕРКА index.html ===\n');

// 1. Ищем все STREETS = ...
console.log('--- 1. Присваивания STREETS ---');
let foundStreets = false;
lines.forEach((line, i) => {
  if (line.includes('STREETS =') && !line.includes('setStreets')) {
    console.log(`  Строка ${i + 1}: ${line.trim()}`);
    foundStreets = true;
  }
});
if (!foundStreets) console.log('  (не найдено — хорошо)');

// 2. Ищем все window.xxx = ...
console.log('\n--- 2. Экспорт в window ---');
lines.forEach((line, i) => {
  if (line.includes('window.') && line.includes('=')) {
    console.log(`  Строка ${i + 1}: ${line.trim().substring(0, 80)}...`);
  }
});

// 3. Ищем все <script> и </script>
console.log('\n--- 3. Теги script ---');
lines.forEach((line, i) => {
  if (line.includes('<script') || line.includes('</script>')) {
    console.log(`  Строка ${i + 1}: ${line.trim().substring(0, 80)}`);
  }
});

// 4. Ищем все import
console.log('\n--- 4. Импорты ---');
lines.forEach((line, i) => {
  if (line.includes('import ')) {
    console.log(`  Строка ${i + 1}: ${line.trim().substring(0, 80)}...`);
  }
});

// 5. Проверка на незакрытые скобки
console.log('\n--- 5. Баланс скобок ---');
let openBraces = 0, closeBraces = 0, openParens = 0, closeParens = 0;
lines.forEach((line) => {
  openBraces += (line.match(/{/g) || []).length;
  closeBraces += (line.match(/}/g) || []).length;
  openParens += (line.match(/\(/g) || []).length;
  closeParens += (line.match(/\)/g) || []).length;
});
console.log(`  { : ${openBraces}, } : ${closeBraces} (${openBraces === closeBraces ? 'OK' : 'РАСХОЖДЕНИЕ!'})`);
console.log(`  ( : ${openParens}, ) : ${closeParens} (${openParens === closeParens ? 'OK' : 'РАСХОЖДЕНИЕ!'})`);

console.log('\n=== ПРОВЕРКА ЗАВЕРШЕНА ===');